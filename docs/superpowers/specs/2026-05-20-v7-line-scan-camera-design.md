# V7 海康线扫相机接入 — 架构设计

> 项目: copper-defect-eval-tool (v0.6.0 → v0.7.0)
> 目标: 将 V6 升级为支持 1-6 台海康 GigE 线扫相机的现场联调版

## 1. 核心决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 设备抽象层 | 新建 `src/device/camera/`，定义 `LineScanDevice` 接口，与 `camera_adapters/` 平行保留 | 线扫相机概念模型与面阵完全不同（行数据流 vs 帧），混在一起维护困难 |
| UI 布局 | 自适应网格，按 `camera_count` 动态分配列数，不显示未启用占位 | 1台→1列，2台→2列，3台→3列，4台→2x2，5-6台→3x2 |
| 线程模型 | 每相机独立采集线程 + SDK handle + 行缓存 + 拼图状态，各自推 ImageBlock 到共享推理队列 | 符合任务书 9.1 节；单路异常隔离，不阻塞其他路 |
| MVS SDK | 复制官方 Python 绑定到项目 `src/device/camera/hikrobot/MvImport/` | 已确认 SDK 安装可用，bolt 项目已验证过 |

## 2. 新增/变更文件

### 2.1 新增 — src/device/camera/ (设备层)

```
src/device/camera/
├── __init__.py
├── line_scan/
│   ├── __init__.py
│   ├── interface.py            # LineScanDevice ABC
│   ├── types.py                # DeviceInfo, FramePacket, CameraStatus
│   ├── block_builder.py        # 线数据缓存 → 固定高度 ImageBlock
│   ├── tile_generator.py       # ImageBlock → 320x320 Tile 切片 + 坐标反算
│   └── encoder_mapper.py       # 编码器脉冲 → 米数位置
├── hikrobot/
│   ├── __init__.py
│   ├── MvImport/               # 从 MVS SDK 复制 Python 绑定
│   ├── sdk_loader.py           # SDK/DLL 加载 + 初始化/反初始化
│   ├── hikrobot_camera.py      # HikrobotLineScanCamera (实现 LineScanDevice)
│   └── error_code.py           # 错误码 → 中文消息映射
├── manager/
│   ├── __init__.py
│   ├── camera_manager.py       # 1-6 相机生命周期管理
│   └── health_monitor.py       # 断线检测 + 自动重连
└── simulator/
    ├── __init__.py
    └── virtual_line_scan.py    # 虚拟线扫相机 (开发/测试用)
```

### 2.2 新增 — UI

```
desktop_app/pages/
└── device/
    ├── __init__.py
    └── commissioning_panel.py  # 联调面板: 相机诊断/调参/编码器校准/图像检查
```

### 2.3 修改 — 现有文件

| 文件 | 变更 |
|------|------|
| `runtime/acquisition_pipeline.py` | 重构为支持每相机独立线程 + 线扫采集 |
| `runtime/inference_pipeline.py` | 适配 Tile 输入，支持每相机推理队列 |
| `runtime/encoder_reader.py` | 扩展 RS422EncoderReader，对接真实编码器 |
| `desktop_app/pages/production_run_page.py` | 改为自适应网格布局 |
| `desktop_app/pages/camera_config_page.py` | 增加 Recipe 编辑（线扫参数 + 编码器参数） |
| `desktop_app/pages/encoder_config_page.py` | 增加编码器标定向导 |
| `core/camera_config.py` | 扩展 CameraConfig 字段 (line_rate, image_block_height, pixel_format) |
| `core/storage.py` | 新增 `camera_recipes` 表 |
| `pyproject.toml` | 版本号 0.6.0 → 0.7.0 |

## 3. 接口定义

### 3.1 LineScanDevice (ABC)

```python
class LineScanDevice(ABC):
    """线扫相机统一接口"""

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]: ...
    def open(self, serial: str) -> bool: ...
    def close(self) -> None: ...
    def start_grabbing(self) -> bool: ...
    def stop_grabbing(self) -> None: ...
    def get_status(self) -> CameraStatus: ...
    def set_param(self, name: str, value) -> None: ...
    def get_param(self, name: str): ...
    def register_line_callback(self, cb: Callable[[FramePacket], None]) -> None: ...
```

### 3.2 核心数据结构

```python
@dataclass
class DeviceInfo:
    vendor: str
    model: str
    serial_number: str
    ip_address: str
    mac_address: str
    transport_layer: str  # "GigE"

@dataclass
class FramePacket:
    camera_id: str
    frame_id: int
    timestamp_ns: int
    encoder_count: int
    width: int
    height: int  # 行高，线扫通常为1
    pixel_format: str
    line_data: np.ndarray  # shape: (height, width) or (1, width)
    metadata: dict

@dataclass
class LineScanImageBlock:
    block_id: str
    camera_id: str
    start_frame_id: int
    end_frame_id: int
    start_encoder_count: int
    end_encoder_count: int
    start_meter: float
    end_meter: float
    width: int
    height: int
    image: np.ndarray
    timestamp_start: float
    timestamp_end: float

@dataclass
class ImageTile:
    tile_id: str
    block_id: str
    camera_id: str
    x0: int; y0: int
    width: int; height: int
    image: np.ndarray
    meter_start: float
    meter_end: float
```

## 4. 数据流

```
MVS SDK 行回调
  → HikrobotLineScanCamera._on_line(frame_packet)
    → BlockBuilder.push_line(line_data, encoder_count)
      → 达到配置高度 (如1024行) → 生成 LineScanImageBlock
        → TileGenerator.slice(block, tile_size=320) → ImageTile[]
          → InferenceScheduler.push(tile)
            → ModelRunner.predict(tile.image) → DetectionBox[]
              → 坐标反算: tile坐标 → block坐标 → 米数位置
                → record_ng_event(camera_id, block_id, meter_position)
```

## 5. 实施阶段

### 阶段 1: 海康单相机 MVP (1-2周)

1. 复制 MvImport 到项目，实现 sdk_loader.py
2. 实现 HikrobotLineScanCamera (枚举、连接、取流、参数读写)
3. 实现虚拟线扫相机 (开发测试用)
4. 单相机简单图像显示

### 阶段 2: 线扫图像块生成 (1-2周)

1. BlockBuilder: 行缓存 + 固定高度拼图
2. TileGenerator: 320×320 切片 + 坐标反算
3. 接入模型推理流程

### 阶段 3: 编码器/触发/米数定位 (1-2周)

1. RS422 编码器对接
2. 编码器标定向导
3. 缺陷米数计算

### 阶段 4: 多相机并发 (2周)

1. CameraManager: 1-6 相机生命周期
2. AcquisitionPipeline 重构
3. 推理调度器 (多队列)
4. 压力测试

### 阶段 5: 联调工具 + 稳定性 (1-2周)

1. CommissioningPanel (相机诊断/调参)
2. HealthMonitor (断线重连)
3. 日志完善 + 异常恢复
4. NG 保存规范实施

## 6. 设计与现有代码的关系

- **复用 `camera_adapters/`**: 保留 folder_watcher 用于开发测试
- **复用 `core/`**: CameraConfig, ProductionEvent, SamplingController 等
- **复用 `model_runners/`**: YOLO/ONNX 运行器无需改动
- **复用 `runtime/`**: FrameBuffer 可继续使用；AcquisitionPipeline/InferencePipeline 需适配线扫模式
- **UI 遵循现有模式**: PySide6 Qt pages，AppContext 单例，ProjectSelector 联动
