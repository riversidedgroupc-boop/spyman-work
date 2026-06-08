# C++ Runtime 迁移实施计划（中文版）

> 给 Claude Code 执行时建议使用：`superpowers:executing-plans` 或 `superpowers:subagent-driven-development`。  
> 本计划不是“把整个 Python 项目翻译成 C++”，而是先把现场生产运行链路拆成可被 C++ 平台承载的 runtime。

## 目标

把 CX-vision 的**现场实时生产能力**逐步迁移到 C++ runtime，让你们现有 C++ 平台可以统一承载：

- 相机采集
- 线扫拼图
- 图像切片
- TensorRT / ONNX Runtime 推理
- 后处理 / NMS / 坐标换算
- NG 缺陷事件输出
- 运行状态 / 健康状态 / 错误码

Python 继续保留为：

- 数据集构建
- 标注 / 复核
- YOLO / PatchCore 训练
- 模型评估
- 报告生成
- 参数调试
- 迁移阶段的工程 UI

## 核心判断

**可行，但不能一上来全量 C++ 重写。**

正确路线是：

1. 先定义 C++ runtime 和 Python / 平台之间的接口。
2. 用 Python fake runtime 做对拍测试。
3. 做 C++ runtime 骨架。
4. 再逐步把实时热路径迁进去。
5. 最后让你们现有 C++ 平台接管 UI 和运行入口。

这样可以避免两个风险：

- Python 项目一次性重写导致功能断层。
- C++ 平台还没接口时，先写了一堆无法集成的 C++ 代码。

---

## 不做什么

第一阶段明确不做：

- 不重写 `desktop_app/`。
- 不重写 `core/` 的 CRUD、SQLite、模型版本、数据集版本管理。
- 不重写 `trainers/`。
- 不重写报告、Excel、PDF、HTML 导出。
- 不删除现有 Python runtime。
- 不要求本地测试必须安装 TensorRT / CUDA。
- 不要求单元测试连接真实相机。
- 不修改 `.env`、密钥、CI/CD、部署发布配置。

---

## 目标架构

### 迁移后分层

```text
C++ Platform
  |
  | start / stop / status / config
  v
cx_vision_runtime     <- C++ production runtime
  |
  | defect events / health / preview
  v
C++ Platform UI / logs / alarm system


Python Toolchain
  |
  | training / evaluation / model package / config package
  v
deployment package
  |
  v
cx_vision_runtime
```

### C++ runtime 负责

```text
cx_vision_runtime
  camera capture
  line scan block builder
  tile generator
  TensorRT / ONNX inference
  postprocess
  defect event publisher
  health monitor
```

### Python 负责

```text
Python app
  dataset
  training
  evaluation
  review workflow
  deployment package
  temporary debug UI
```

---

## Runtime 接口边界

第一个 C++ runtime 命名建议：

```text
cx_vision_runtime
```

它可以先作为独立进程，后续再改成你们 C++ 平台的插件 / DLL。

### 输入

- `RuntimeConfig`
- 相机配置
- 模型 artifact 配置
- 产品 / 规格 metadata
- start / stop / status 命令

### 输出

- `RuntimeStatus`
- 每路相机状态
- `DefectEvent`
- 预览图路径或低频预览 payload
- 稳定错误码

### 初期通信方式

第一阶段建议先用 JSON Lines / 本地进程协议，原因是：

- 简单
- 好测
- Claude Code 容易实现
- C++ 平台也容易临时接入

长期可以升级为：

- Protobuf + gRPC
- ZeroMQ
- 平台已有插件 ABI
- DLL C API

---

## 文件规划

### Python 侧新增

```text
core/runtime_contracts.py
tests/test_runtime_contracts.py

runtime/fake_cpp_runtime.py
tests/test_fake_cpp_runtime.py

runtime/cpp_runtime_client.py
tests/test_cpp_runtime_client.py
```

用途：

- `core/runtime_contracts.py`：定义 runtime 配置、命令、状态、缺陷事件。
- `fake_cpp_runtime.py`：不依赖 C++，用于测试和 UI 对接演练。
- `cpp_runtime_client.py`：Python 调 C++ runtime 的适配器。

### C++ 侧新增

```text
cpp_runtime/CMakeLists.txt
cpp_runtime/include/cx_vision/runtime_contracts.hpp
cpp_runtime/src/runtime_contracts.cpp
cpp_runtime/src/main.cpp
```

用途：

- 先搭 C++ runtime 骨架。
- 支持 `start` / `stop` / `status`。
- 输出 JSON 状态。
- 不接真实相机，不接 TensorRT。

### 文档新增

```text
docs/cpp_runtime_contract.md
docs/cpp_platform_integration.md
```

用途：

- 给 C++ 平台团队看接口。
- 明确字段、错误码、版本兼容策略。

---

## 阶段 1：定义 Python Runtime Contract

### 目标

先把 Python 和 C++ 之间的数据结构定下来。

### 交付物

```text
core/runtime_contracts.py
tests/test_runtime_contracts.py
docs/cpp_runtime_contract.md
```

### 主要模型

```text
CameraRuntimeConfig
RuntimeConfig
RuntimeCommand
RuntimeStatus
DefectEvent
```

### 验收标准

- `RuntimeConfig` 可以 JSON 序列化和反序列化。
- `RuntimeCommand` 只能接受 `start` / `stop` / `status`。
- `RuntimeStatus` 默认值安全。
- `DefectEvent` 字段能被 C++ 平台稳定消费。

### Claude Code 第一轮只做这个

给 Claude Code 的第一条指令建议：

```text
Read docs/superpowers/plans/2026-06-03-cpp-runtime-migration.md.
Use superpowers:executing-plans.
Implement Phase 1 only: Python Runtime Contract.
Do not modify camera_adapters, model_runners, desktop_app, or core/storage.py.
Run the focused tests listed in the plan and report results.
Do not commit.
```

---

## 阶段 2：Fake C++ Runtime + Python Client

### 目标

在真正写 C++ runtime 前，先让 Python UI / 测试能“假装接入 C++ runtime”。

这一步很关键。它能先验证接口是否合理。

### 交付物

```text
runtime/fake_cpp_runtime.py
tests/test_fake_cpp_runtime.py

runtime/cpp_runtime_client.py
tests/test_cpp_runtime_client.py
```

### Fake runtime 行为

- `start(config)` 返回 `running`
- `stop()` 返回 `stopped`
- `status()` 返回当前状态
- `emit_test_defect(camera_id)` 输出一个稳定的测试缺陷事件

### Python client 行为

- `client.start(config)`
- `client.stop()`
- `client.status()`

### 验收标准

- 不需要 C++ 编译器也能测试通过。
- 不需要相机。
- 不需要 TensorRT。
- 后续 UI 可以先接 fake runtime 做联调。

---

## 阶段 3：C++ Runtime 骨架

### 目标

创建最小 C++ runtime 工程。

这一步只证明：

- C++ 项目能构建。
- 能输出和 Python contract 对应的 status JSON。
- C++ 平台未来有明确接入对象。

### 交付物

```text
cpp_runtime/CMakeLists.txt
cpp_runtime/include/cx_vision/runtime_contracts.hpp
cpp_runtime/src/runtime_contracts.cpp
cpp_runtime/src/main.cpp
```

### CLI 行为

```powershell
cx_vision_runtime.exe status
cx_vision_runtime.exe start
cx_vision_runtime.exe stop
```

输出示例：

```json
{"state":"stopped","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}
```

### 验收标准

- CMake 能生成工程。
- 可编译出 `cx_vision_runtime.exe`。
- `status` 命令输出 JSON。
- 未知命令返回稳定错误码 `UNKNOWN_COMMAND`。

---

## 阶段 4：迁移实时热路径

这一阶段才开始动真正性能相关代码。

### 4.1 去掉 Python 推理临时文件

当前 Python 推理链路里有把 numpy 图像写成临时 jpg/png 再推理的路径，这对实时检测不合适。

先做：

```text
predict_array(image: np.ndarray)
```

保留旧的：

```text
predict_image(path)
```

验收标准：

- 支持 numpy 图像直接推理。
- 老 runner 仍能 fallback 到 path 推理。
- 测试证明支持 `predict_array` 时不会写临时文件。

### 4.2 抽象 RuntimeBackend

新增：

```text
PythonRuntimeBackend
CppRuntimeBackend
FakeCppRuntimeBackend
```

目标：

- UI 或运行页面可以按配置选择 backend。
- 现有 Python pipeline 还能跑。
- fake C++ runtime 可以跑。
- 真 C++ runtime 后续接入时不用改大面积 UI。

### 4.3 C++ 线扫拼块和 tile 切分

迁移顺序：

1. C++ `LineScanBlockBuilder`
2. C++ `TileGenerator`
3. Python 和 C++ 对同一批测试输入做结果对拍
4. 再接真实相机

验收标准：

- block ID、tile ID、坐标、米数区间一致。
- 允许浮点误差，但必须明确阈值。
- 单元测试不依赖相机。

### 4.4 C++ TensorRT / ONNX Runtime 推理

迁移顺序：

1. engine metadata 校验
2. 输入预处理
3. GPU buffer 管理
4. 推理执行
5. YOLO 输出解析
6. NMS
7. 坐标映射
8. `DefectEvent` 输出

验收标准：

- TensorRT 不存在时不崩溃，返回稳定错误码。
- GPU 不匹配时明确报错。
- fake engine 测试不需要真实 GPU。
- 真实 engine 只在目标机器验收。

---

## 阶段 5：接入现有 C++ 平台

### 目标

让你们现有平台能启动、停止、查询 runtime，并收到缺陷事件。

### 交付物

```text
docs/cpp_platform_integration.md
packaging/cpp_runtime_package.ps1
```

### 平台包内容

```text
cx_vision_runtime_package/
  cx_vision_runtime.exe
  models/
    best.engine
    best.onnx
  config/
    runtime_config.json
    class_mapping.json
  reports/
    benchmark_report.json
  manifest.json
```

### manifest 必须包含

- runtime version
- contract version
- source model id
- model backend
- model path
- class mapping
- confidence / iou
- CUDA version
- TensorRT version
- GPU name
- benchmark summary
- fallback backend

### 验收标准

- C++ 平台能启动 runtime。
- C++ 平台能查询 status。
- C++ 平台能 stop runtime。
- C++ 平台能收到一个 fake defect event。
- 后续再切真实 camera / TensorRT。

---

## 推荐执行顺序

### 第 1 轮

只做：

```text
Phase 1: Python Runtime Contract
```

不要碰：

```text
camera_adapters/
model_runners/
desktop_app/
core/storage.py
```

### 第 2 轮

做：

```text
Phase 2: Fake runtime + Python client
```

目标是让 Python 侧能模拟 C++ runtime。

### 第 3 轮

做：

```text
Phase 3: C++ runtime skeleton
```

只要求能编译和输出 status。

### 第 4 轮

做：

```text
去掉 Python 推理临时文件
```

这是现有 Python 链路也会受益的优化。

### 第 5 轮

开始迁移：

```text
line scan block
tile generator
TensorRT inference
postprocess
```

---

## 测试命令

Python focused tests：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py -q
```

Python broader smoke：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests -q -x --tb=short
```

Ruff：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core\runtime_contracts.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py
```

C++ build：

```powershell
cmake -S cpp_runtime -B cpp_runtime\build
cmake --build cpp_runtime\build --config Release
cpp_runtime\build\Release\cx_vision_runtime.exe status
```

---

## 给 Claude Code 的执行提示

第一轮建议直接发：

```text
Read docs/superpowers/plans/2026-06-03-cpp-runtime-migration.md and docs/superpowers/plans/2026-06-03-cpp-runtime-migration-zh.md.
Use superpowers:executing-plans.
Implement Phase 1 only: Python Runtime Contract.
Do not modify camera_adapters, model_runners, desktop_app, or core/storage.py.
Run the focused tests listed in the plan and report results.
Do not commit.
```

如果第一轮成功，再发：

```text
Continue with Phase 2 only: Fake C++ Runtime and Python Client.
Do not implement the C++ runtime yet.
Do not touch camera or TensorRT code.
Run focused tests and report results.
Do not commit.
```

---

## 最终路线总结

一句话：

**C++ 平台负责现场实时生产，Python 负责模型研发和工程工具，中间用稳定 runtime contract 和 deployment package 连接。**

这条路线能统一到你们现有 C++ 软件体系，同时保留 Python 在 AI 训练和快速迭代上的优势。
