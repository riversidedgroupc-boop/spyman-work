# C++ Runtime Phase 5 — 真实平台集成设计

**日期**: 2026-06-05
**状态**: 计划阶段，不实现代码
**前序**: Phase 1-4 已完成（Python 协议层、CLI stub、外部模式隔离）

---

## 1. 背景与目标

Phase 1-4 完成了 C++ runtime 的基础架构：
- **Python 侧**: Pydantic v2 协议模型、`RuntimeBackend` 传输抽象、`create_backend()` 工厂、外部 mode 早期返回
- **C++ 侧**: C++20 递归下降 JSON 解析器、`cx_vision_runtime.exe` one-shot CLI（start/stop/status 命令）
- **当前状态**: C++ exe 是一个 **stub** — `start` 立即返回 `{"state":"running"}`，不做任何实际采集或推理

Phase 5 的目标是将 C++ runtime 从 CLI stub 升级为 **能做实际工作的进程**，同时保持 Python UI 定位为 **operator tooling**（不接管外部 runtime 资源）。

---

## 2. 核心架构决策

### 2.1 进程模型：one-shot CLI 还是长驻进程？

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A: 保持 one-shot CLI | 每次 `start` 启动一个采集周期，完成后退出 | 简单、无状态管理负担 | 启动开销大、相机热插拔困难、无法实时通信 |
| B: 长驻守护进程 | `start` 启动后台进程，持续采集/推理，通过 IPC 通信 | 低延迟、相机持久连接、可实时状态推送 | 进程管理复杂、崩溃恢复、Windows Service 注册 |
| **C: 推荐 — 长驻进程 + named pipe** | 一个长驻进程，Python UI 通过 Windows named pipe 连接 | 低延迟 + 双向通信 + 平台原生 | 需要 pipe 协议设计 |

**建议**: 采用方案 C。Phase 3/4 的 `RuntimeBackend` 协议已经抽象了传输层，只需新增 `CppRuntimePipeBackend` 替换当前的 `CppRuntimeProcessBackend`。

### 2.2 进程生命周期

```
[Python UI 启动]
  → CppRuntimePipeBackend.start()
    → CreateProcess("cx_vision_runtime.exe serve --pipe-name=...")
    → 等待 pipe 连接就绪
  → CppRuntimePipeBackend.status()  // 通过 pipe 轮询
  → CppRuntimePipeBackend.stop()
    → 通过 pipe 发送 shutdown 命令
    → 等待进程退出（超时则 TerminateProcess）

[crash recovery]
  → Python 检测 pipe 断开
  → 自动 restart（最多 N 次）
  → 通知 UI 显示错误
```

---

## 3. 功能边界与职责划分

### 3.1 C++ Runtime 负责（真正的实时部分）

| 功能 | 说明 |
|------|------|
| **相机采集** | 通过海康 MVS SDK 连接相机，管理采集线程 |
| **YOLO 推理** | TensorRT engine 加载与推理 |
| **异常检测** | PatchCore/EfficientAD ONNX Runtime 推理 |
| **编码器读取** | 硬件编码器位置信号读取 |
| **PLC 通信** | 触发信号、NG 分拣信号 |
| **缺陷判定** | 融合逻辑、阈值判断（confidence/IoU） |
| **图像保存** | NG 图像写入磁盘（`save_policy` 控制） |
| **状态上报** | 通过 named pipe 向 Python UI 推送 |

### 3.2 Python UI 保持（operator tooling）

| 功能 | 说明 |
|------|------|
| **生产监控** | 显示 FPS、NG 计数、相机状态（从 pipe 读取） |
| **缺陷追溯** | 查询历史 NG 事件、图像回放 |
| **项目管理** | 客户/项目/规格 CRUD（已有） |
| **模型管理** | 模型版本、训练作业（已有） |
| **配置管理** | 生成 `runtime_config.json` 供 C++ 加载 |
| **启动/停止** | 通过 `RuntimeBackend` 协议控制 C++ 进程 |
| **备份/恢复** | 数据库和配置导出（已有） |

### 3.3 明确不放入 C++ 的功能

- 项目管理 UI（Python 专属）
- 模型训练（Python 专属）
- 数据标注（Python 专属）
- 评估指标计算（Python 专属）
- 历史数据查询（Python 专属）

---

## 4. RuntimeStatus 扩展

当前 `RuntimeStatus` 设计：

```python
class RuntimeStatus(BaseModel):
    state: Literal["idle", "running", "error"]
    uptime_seconds: float
    fps_by_camera: dict[str, float]
    total_frames: int
    ng_count: int
    queue_size: int
    dropped_frames: int
    error_code: str
    error_message: str
```

Phase 5 需扩展：

```python
class CameraRuntimeStatus(BaseModel):
    """单个相机的运行时状态"""
    camera_id: str
    connected: bool
    fps: float
    frames_acquired: int
    frames_dropped: int
    last_error: str = ""
    exposure_time_us: float = 0.0
    gain_db: float = 0.0

class ModelRuntimeStatus(BaseModel):
    """模型加载状态"""
    model_type: Literal["yolo", "anomaly"]
    model_path: str
    loaded: bool
    engine_type: Literal["tensorrt", "onnx"]
    warmup_frames: int = 0
    avg_inference_ms: float = 0.0
    load_error: str = ""

class RuntimeStatus(BaseModel):
    state: Literal["idle", "starting", "running", "stopping", "error"]
    uptime_seconds: float
    cameras: dict[str, CameraRuntimeStatus]  # key = camera_id
    models: dict[str, ModelRuntimeStatus]    # key = "yolo" | "anomaly"
    ng_count: int
    encoder_position_m: float | None
    plc_connected: bool
    plc_state: Literal["unknown", "ready", "running", "fault"]
    error_code: str
    error_message: str
```

### C++ 侧对应结构（JSON 输出）

```json
{
  "state": "running",
  "uptime_seconds": 123.4,
  "cameras": {
    "CAM_01": {
      "camera_id": "CAM_01",
      "connected": true,
      "fps": 30.0,
      "frames_acquired": 3702,
      "frames_dropped": 0,
      "last_error": "",
      "exposure_time_us": 15000.0,
      "gain_db": 0.0
    }
  },
  "models": {
    "yolo": {
      "model_type": "yolo",
      "model_path": "C:\\models\\yolo_v8.engine",
      "loaded": true,
      "engine_type": "tensorrt",
      "avg_inference_ms": 12.5
    }
  },
  "ng_count": 3,
  "encoder_position_m": 45.678,
  "plc_connected": true,
  "plc_state": "running",
  "error_code": "",
  "error_message": ""
}
```

---

## 5. DefectEvent 回传机制

### 5.1 数据流

```
[C++ Runtime]                          [Python UI]
     |                                      |
     |-- NG detected → 保存图像 → ----------|
     |                                      |
     |-- "defect_event" pipe message → -----|
     |   {                                   |
     |     "type": "defect_event",           |
     |     "event_id": "EVT_...",           |
     |     "camera_id": "CAM_01",           |
     |     "timestamp": "2026-06-05T...",   |
     |     "defect_type": "scratch",        |
     |     "confidence": 0.92,              |
     |     "position_meter": 12.34,         |
     |     "image_path": "outputs\\...",    |
     |     "crop_bbox": [x,y,w,h]           |
     |   }                                   |
     |                                      |
     |                                      |-- 写入 SQLite
     |                                      |-- 更新 UI NG 计数
     |                                      |-- 可选：弹窗告警
```

### 5.2 Named Pipe 协议设计

使用 JSONL（每行一个 JSON 对象）over named pipe：

**Python → C++ (commands)**:
```jsonl
{"command": "start", "config_path": "C:\\..."}
{"command": "status"}
{"command": "stop"}
```

**C++ → Python (events)**:
```jsonl
{"type": "status", "payload": {...}}
{"type": "defect_event", "payload": {...}}
{"type": "error", "payload": {"code": "...", "message": "..."}}
{"type": "log", "payload": {"level": "warning", "message": "..."}}
```

### 5.3 Pipe 连接管理

```python
class CppRuntimePipeBackend(RuntimeBackend):
    def __init__(self, pipe_name: str = "cx_vision_runtime"):
        self._pipe_name = pipe_name
        self._process: subprocess.Popen | None = None
        self._pipe: win32file handle | None = None
        self._reader_thread: threading.Thread | None = None
        self._pending_events: queue.Queue = queue.Queue()

    def start(self, config: RuntimeConfig) -> None:
        # 1. 写 runtime_config.json
        # 2. CreateProcess("cx_vision_runtime.exe serve ...")
        # 3. ConnectNamedPipe 等待 C++ 连接
        # 4. 发送 {"command":"start","config_path":"..."}
        # 5. 等待 {"type":"status","payload":{"state":"running"}}
        ...

    def _read_loop(self):
        """后台线程持续从 pipe 读取 JSONL 消息"""
        while self._running:
            line = read_line_from_pipe(self._pipe)
            msg = json.loads(line)
            if msg["type"] == "defect_event":
                self._pending_events.put(msg["payload"])
            elif msg["type"] == "status":
                self._last_status = RuntimeStatus(**msg["payload"])
```

---

## 6. Windows 应用控制策略下的部署方案

### 6.1 问题

当前机器 `cx_vision_runtime.exe` 被 Windows Application Control Policy (Device Guard) 阻止（OSError 4551）。

### 6.2 方案

| 方案 | 可行性 | 适用场景 |
|------|--------|----------|
| A: 代码签名证书 | ✅ 推荐 | 正式部署环境 |
| B: 策略白名单 | ✅ | 工厂产线（IT 部门配置 AppLocker 允许路径/哈希） |
| C: Windows Defender 排除 | ⚠️ 有限 | 开发机（不解决 Device Guard 问题） |
| D: 部署到未锁定机器 | ✅ | 产线工控机通常不启用 Device Guard |

### 6.3 建议

- **开发阶段**: 在关闭了 Device Guard 的开发机或 CI runner 上执行 C++ smoke 测试
- **产线部署**: 使用 EV 代码签名证书签名 + 工控机 AppLocker 白名单
- **CI/CD**: GitHub Actions Windows runner（无 Device Guard）运行 C++ CLI 测试

---

## 7. 相机 SDK 集成边界

### 7.1 海康 MVS SDK

```
C++ 侧：
- 通过 MVS SDK C API 连接相机
- 管理采集线程（回调模式）
- 图像格式转换（Bayer → RGB）

接口边界：
- 相机 IP 列表从 runtime_config.json 读取
- 采集参数（曝光、增益）从 camera 配置段读取
- 图像回调中直接送入推理队列（跳过 Python GIL）
```

### 7.2 TensorRT 推理

```
C++ 侧：
- 加载 .engine 文件（TensorRT 序列化模型）
- 管理 CUDA context、stream
- 预处理（resize, normalize）在 GPU 上
- 后处理（NMS, decode）在 GPU 上

边界：
- 模型路径从 runtime_config.json → model_artifacts 读取
- confidence/IoU 阈值从 config 读取
```

### 7.3 编码器 / PLC

```
编码器：
- 通过串口/以太网读取位置脉冲 → 转换为米
- 编码器参数（mm_per_pulse）从相机配置读取

PLC：
- Modbus TCP / EtherNet/IP
- 信号：start/stop trigger, NG sort signal, heartbeat
```

---

## 8. 实施阶段建议

### Phase 5a: Named Pipe 通信（1-2 天）

- 设计 JSONL pipe 协议
- C++ 侧: `serve` 命令、CreateNamedPipe、读写线程
- Python 侧: `CppRuntimePipeBackend`
- 测试: pipe 连接/断开/重连、status 轮询

### Phase 5b: 相机采集（2-3 天）

- C++ 侧: MVS SDK 集成、采集线程、格式转换
- 配置: 从 `runtime_config.json` cameras 段读取
- 测试: 模拟相机（图像文件回放）→ 验证帧率/丢帧

### Phase 5c: TensorRT 推理（2-3 天）

- C++ 侧: TensorRT engine 加载、预处理/推理/后处理 pipeline
- 模型管理: engine 文件路径从 config 读取
- 测试: 已知图像 → 验证检测结果与 Python ONNX 推理一致

### Phase 5d: 编码器 + PLC（1-2 天）

- C++ 侧: 串口/Modbus 集成
- 位置同步: 编码器位置与采集帧的时间对齐
- 测试: 模拟信号发生器

### Phase 5e: DefectEvent 回传 + UI 集成（1 天）

- 实现 pipe 消息中的 `defect_event` 类型
- Python 侧: 后台线程写入 SQLite、更新 UI
- 测试: 模拟 NG 事件 → 验证 UI 计数和列表更新

### Phase 5f: 部署与签名（1 天）

- EV 代码签名证书申请流程
- CI/CD pipeline 自动签名
- 真实工控机部署验证

---

## 9. 测试策略

| 层级 | 内容 | 环境要求 |
|------|------|----------|
| Python 单元测试 | pipe 协议解析、RuntimeStatus 反序列化、backend 工厂 | 无（纯 Python） |
| C++ 单元测试 | JSON 解析器、config 验证、pipe 消息序列化 | 无（C++ catch2/gtest，无 GPU） |
| Python-C++ 集成测试 | pipe 连接、start/stop/status 往返 | 需要可执行 exe（无 Device Guard） |
| 硬件测试 | 真实相机 + TensorRT + 编码器 | 工控机 + 相机 + GPU |

---

## 10. 风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| MVS SDK C API 兼容性 | 中 | 已有 Python 适配器经验，C API 文档齐全 |
| TensorRT 版本与 GPU 驱动不匹配 | 中 | 锁定 CUDA/TensorRT 版本，CI 中多版本矩阵测试 |
| Named pipe 在 Windows 上的可靠性 | 低 | 成熟技术，多年验证 |
| 实时性能不达标（<30fps 多相机） | 中 | C++ 无 GIL + GPU 预处理 → 预期性能提升 |
| PLC 协议兼容性 | 高 | 不同产线 PLC 型号不同 → 抽象 PLC 适配器接口 |
