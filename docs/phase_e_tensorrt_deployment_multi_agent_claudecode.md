# Phase E：TensorRT 部署与加速闭环多 Agent 开发说明

本文档给 Claude Code 使用。请按多 agent 并行开发方式推进 Phase E。默认中文沟通；代码、命令、字段名保持英文。

## 1. 背景

当前项目已经完成：

- Phase A：现场会话、缺陷字典、异常复核、混合策略基础。
- Phase B：现场交付流程 UI，支持少量采集、异常复核、人工标注和缺陷类型确认。
- Phase C：现场复核样本生成 YOLO 首训数据集，训练后模型版本记录 `dataset_version_id` 和 `class_mapping`。
- Phase D：混合推理复检，支持 YOLO + anomaly 融合判定，并将 `UNKNOWN / NEEDS_REVIEW / SUSPECT` 回流到复核队列。

Phase E 的目标是把 Phase D 验证通过的模型变成现场可部署、可加速、可回退、可追溯的模型交付形态。

## 2. Phase E 总目标

实现模型部署与加速闭环：

1. 支持从 `model_versions.model_path` 导出 ONNX 和 TensorRT FP16 `.engine`。
2. 记录每个导出产物的来源、环境、状态、路径和指标。
3. 统一 `.pt / .onnx / .engine` 推理后端选择。
4. 支持 PyTorch 回退，禁止 TensorRT 失败后静默误用。
5. 对同一图集做速度和一致性 benchmark。
6. 生成现场部署包，包含模型、配置、阈值、类别映射、benchmark 报告和 manifest。

TensorRT `.engine` 与 GPU 架构强绑定，不能承诺跨机器通用。Phase E 必须把这个信息写入导出记录和部署包。

## 3. 多 Agent 分工

请用 5 个 agent 并行开发，但要遵守依赖顺序。各 agent 不要互相覆盖文件；共享接口先按本文档定稿。

### Agent A：模型导出与数据库

负责核心导出记录、环境探测、ONNX/TensorRT 导出服务。

主要文件：

- `core/model_export.py`
- `core/export_environment.py`
- `core/storage.py`
- `tests/test_model_export.py`
- `tests/test_export_environment.py`

交付内容：

- 新增 `model_export_artifacts` 表。
- 新增 `ModelExportArtifact` dataclass。
- 新增环境探测函数。
- 新增导出服务函数：
  - `detect_export_environment()`
  - `create_export_artifact(...)`
  - `update_export_artifact(...)`
  - `list_export_artifacts(...)`
  - `export_yolo_to_onnx(...)`
  - `export_yolo_to_tensorrt(...)`

### Agent B：统一推理后端

负责 `.pt / .onnx / .engine` runner 工厂和 TensorRT runner 接入。

主要文件：

- `model_runners/backend_factory.py`
- `model_runners/tensorrt_runner.py`
- `model_runners/onnx_runner.py`
- `model_runners/yolo_runner.py`
- `tests/test_backend_factory.py`
- `tests/test_tensorrt_runner.py`

交付内容：

- 定义 `RuntimeBackend`：`pytorch`, `onnx`, `tensorrt`。
- 新增 `create_runner_for_artifact(...)`。
- 新增 `select_best_backend(...)`。
- TensorRT 不可用时给明确错误。
- `.engine` GPU 不匹配时禁止默认使用。

### Agent C：导出 UI 与后台 Worker

负责桌面端“模型导出/加速”页面和后台任务。

主要文件：

- `desktop_app/pages/model_export_page.py`
- `desktop_app/workers/model_export_worker.py`
- `desktop_app/main_window.py`
- `desktop_app/constants.py`
- `desktop_app/i18n.py`
- `tests/test_model_export_page.py`

交付内容：

- 在训练中心或模型中心增加“模型导出/加速”页。
- 支持选择模型版本。
- 支持导出 ONNX、TensorRT FP16。
- INT8 只做 UI 占位和条件检查，不默认启用。
- Worker 后台导出，UI 不阻塞。
- 显示导出环境、状态、错误和产物路径。

### Agent D：Benchmark 与一致性校验

负责同图集对比 `.pt / .onnx / .engine` 的速度和结果一致性。

主要文件：

- `core/export_benchmark.py`
- `tests/test_export_benchmark.py`
- 可复用现有 `benchmark/` 模块，但不要破坏现有压测中心。

交付内容：

- 对同一图片目录执行多后端推理。
- 记录：
  - 平均耗时
  - P95 / P99
  - 检出数量差异
  - bbox IoU 差异
  - confidence 差异
  - OK/NG 判定一致率
- 输出 `benchmark_report.json` 和可读摘要。

### Agent E：部署包生成

负责生成现场可交付目录。

主要文件：

- `core/deployment_package.py`
- `tests/test_deployment_package.py`
- `desktop_app/pages/model_export_page.py` 可由 Agent C 合并入口

交付内容：

- 生成部署包目录：

```text
deployment_packages/
  customer_project_spec_YYYYMMDD_HHMMSS/
    models/
    config/
    reports/
    manifest.json
```

- `manifest.json` 必须包含：
  - customer/project/spec
  - source_model_id
  - training_job_id
  - dataset_version_id
  - class_mapping
  - backend artifacts
  - GPU name
  - CUDA version
  - TensorRT version
  - recommended_backend
  - fallback_backend
  - benchmark summary

## 4. 数据库设计

在 `core/storage.py` 增加表：

```sql
CREATE TABLE IF NOT EXISTS model_export_artifacts (
    export_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    spec_id TEXT NOT NULL DEFAULT '',
    source_model_id TEXT NOT NULL,
    backend TEXT NOT NULL,
    precision TEXT NOT NULL DEFAULT 'fp32',
    artifact_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    device_name TEXT NOT NULL DEFAULT '',
    cuda_version TEXT NOT NULL DEFAULT '',
    tensorrt_version TEXT NOT NULL DEFAULT '',
    input_shape TEXT NOT NULL DEFAULT '',
    export_config_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (source_model_id) REFERENCES model_versions(model_id)
);
```

字段约束：

- `backend` 只能使用：`pytorch`, `onnx`, `tensorrt`。
- `precision` 只能使用：`fp32`, `fp16`, `int8`。
- `status` 只能使用：`created`, `running`, `completed`, `failed`, `invalid`。
- ID 使用 `core.id_utils.generate_id("EXP")`。

## 5. 核心接口约定

### 5.1 环境探测

```python
@dataclass
class ExportEnvironment:
    gpu_name: str
    cuda_available: bool
    cuda_version: str
    torch_version: str
    ultralytics_version: str
    tensorrt_available: bool
    tensorrt_version: str
    device_capability: str
```

```python
def detect_export_environment() -> ExportEnvironment:
    ...
```

要求：

- 不要因为 TensorRT 不存在导致整个程序崩溃。
- TensorRT 不存在时 `tensorrt_available=False`。
- 环境信息要写入导出记录。

### 5.2 导出服务

```python
def export_yolo_to_onnx(
    model_id: str,
    output_dir: str,
    imgsz: int = 640,
    opset: int = 12,
    simplify: bool = True,
) -> ModelExportArtifact:
    ...
```

```python
def export_yolo_to_tensorrt(
    model_id: str,
    output_dir: str,
    imgsz: int = 640,
    precision: str = "fp16",
    workspace_gb: int = 4,
    calibration_dir: str = "",
) -> ModelExportArtifact:
    ...
```

要求：

- `.pt` 文件不存在时必须抛出明确错误。
- TensorRT 不可用时导出状态为 `failed`，错误写入 `error_message`。
- INT8 没有 `calibration_dir` 时禁止导出。
- 不允许静默生成空文件或伪成功记录。

### 5.3 后端选择

```python
def select_best_backend(
    model_id: str,
    preferred_backend: str = "auto",
    current_gpu_name: str = "",
) -> ModelExportArtifact | None:
    ...
```

选择逻辑：

1. 用户显式选择可用后端，则使用显式后端。
2. `auto` 模式优先 TensorRT FP16。
3. TensorRT artifact 的 `device_name` 必须匹配当前 GPU。
4. 不匹配则回退 ONNX。
5. ONNX 不可用则回退 PyTorch `.pt`。
6. 所有回退必须写日志或返回原因，不能悄悄换后端。

## 6. UI 设计要求

建议把 Phase E 页面放入“训练中心”tab，名称：

- 中文：`模型导出/加速`
- 英文：`Model Export`

页面结构：

- 顶部：模型版本选择、刷新按钮。
- 环境区：GPU、CUDA、PyTorch、Ultralytics、TensorRT 状态。
- 导出配置区：
  - backend：ONNX / TensorRT
  - precision：FP32 / FP16 / INT8
  - imgsz
  - workspace GB
  - calibration dir
- 操作区：
  - 导出 ONNX
  - 导出 TensorRT FP16
  - Benchmark
  - 生成部署包
- 结果区：
  - artifact table
  - status
  - artifact path
  - error message

UI 要求：

- 没有项目时禁用导出。
- 没有模型时禁用导出。
- TensorRT 不可用时禁用 TensorRT 导出按钮，并显示原因。
- INT8 没校准目录时禁用 INT8。
- 导出运行时禁用配置项。
- 导出失败必须显示错误，不允许只写日志。

## 7. Benchmark 验收规则

同一图片目录，比较 PyTorch 和导出后端：

FP16 建议阈值：

- `decision_match_rate >= 0.99`
- `mean_bbox_iou >= 0.98`
- `mean_confidence_delta <= 0.03`
- `avg_latency_ms` 优于 PyTorch

INT8 建议阈值：

- 默认不自动推荐。
- 必须有校准数据。
- 必须在报告中明确精度损失。

Benchmark 输出：

```json
{
  "source_model_id": "...",
  "candidate_export_id": "...",
  "image_count": 100,
  "avg_latency_ms": 4.2,
  "p95_latency_ms": 6.8,
  "p99_latency_ms": 8.1,
  "decision_match_rate": 0.995,
  "mean_bbox_iou": 0.982,
  "mean_confidence_delta": 0.018,
  "recommended": true
}
```

## 8. 部署包要求

目录结构：

```text
deployment_packages/
  <customer>_<project>_<spec>_<timestamp>/
    models/
      best.pt
      model.onnx
      model_fp16.engine
    config/
      class_mapping.json
      thresholds.json
      hybrid_strategy.json
      runtime_backend.json
    reports/
      benchmark_report.json
      benchmark_report.md
    manifest.json
```

要求：

- `manifest.json` 是部署包的唯一总入口。
- 路径使用相对路径，避免换机器后路径失效。
- `runtime_backend.json` 必须包含推荐后端和回退后端。
- `.engine` 必须记录生成机器 GPU 名称和 TensorRT 版本。

## 9. 测试要求

每个 agent 必须补自己的测试。最终合并前运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_model_export.py tests\test_export_environment.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_backend_factory.py tests\test_tensorrt_runner.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_model_export_page.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_export_benchmark.py tests\test_deployment_package.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_hybrid_retest.py tests\test_hybrid_retest_page.py tests\test_training_page.py tests\test_model_version.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_source_encoding.py -q
.\.venv\Scripts\python.exe -m ruff check core model_runners desktop_app tests
.\.venv\Scripts\python.exe -m pytest -q
```

测试中不要依赖真实 TensorRT。需要用 monkeypatch/fake runner 覆盖：

- TensorRT 不存在。
- TensorRT 存在但导出失败。
- `.engine` GPU 不匹配。
- 导出成功。
- benchmark 结果一致。

## 10. 合并顺序

建议按以下顺序集成：

1. Agent A：数据库 + 导出记录 + 环境探测。
2. Agent B：runner factory + TensorRT runner。
3. Agent D：benchmark 核心。
4. Agent E：部署包生成。
5. Agent C：UI 和 worker 最后接入。

不要让 UI 先落地空按钮。核心服务和测试先过，再接页面。

## 11. 红线

- 不要删除现有 Phase A-D 文件。
- 不要改 `.env`、密钥、CI/CD。
- 不要自动 `git commit` 或 `git push`。
- 不要要求测试机必须安装 TensorRT 才能跑单元测试。
- 不要把 TensorRT 失败静默回退成 PyTorch，并在 UI 上显示成功。
- 不要默认启用 INT8。
- 不要承诺 `.engine` 跨 GPU/跨机器可用。

## 12. 最小可交付版本

如果时间有限，Phase E 第一轮只交付：

1. `model_export_artifacts` 表。
2. 环境探测。
3. ONNX 导出。
4. TensorRT FP16 导出入口，缺环境时明确失败。
5. 后端 factory 支持 PyTorch + ONNX + TensorRT artifact 选择。
6. UI 能看到 artifact 状态。
7. 全量测试通过。

Benchmark 和部署包可以作为 Phase E 第二轮，但接口要预留。
