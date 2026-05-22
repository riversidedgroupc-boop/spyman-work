# 样本分类、bbox 队列、训练中心修复开发文档

本文档用于交给 Claude Code 开发。目标是修复当前现场首训流程中的三个问题：

1. 样本分类后，OK 图片不应进入 bbox 标注队列，只有 NG/缺陷图片需要 bbox。
2. 训练完成后生成的模型不能自动刷新到模型版本历史。
3. 训练中心目前实际只能训练 YOLO，未接入无监督异常检测训练。

## 一、当前问题判断

### 1. 分类到 bbox 的流转不正确

当前分类页只负责保存 `classification_label`。bbox 标注页加载会话图片时，会把 raw 目录和 `captured_images` 中的全部图片加入列表，再按“有无 bbox”和 bbox class 过滤。

这导致：

- OK 图片也出现在 bbox 标注工作区。
- 现场人员需要在大量 OK 图片里找 NG 图，工作量过大。
- 实际流程应该是：先整图分类，只有 NG/缺陷图进入 bbox 细标。

正确流程：

```text
采集图片
  -> 样本分类
      -> OK / IGNORE / INTERFERENCE：直接放过，不进入 bbox
      -> NG / 自定义缺陷类型：进入 bbox 待标注队列
      -> UNKNOWN / UNCERTAIN：进入待复核队列，不直接当 OK 背景
  -> bbox 标注
      -> 只处理 NG/缺陷图
  -> 生成 YOLO 数据集
      -> OK 图生成空 label，作为背景样本
      -> NG 图必须有 bbox label
```

### 2. 模型版本历史不自动刷新

`TrainingWorker` 训练完成后会创建 `model_version`，但 UI 层只在训练页发出 `data_changed`。如果模型版本历史页没有监听这个信号，或者主窗口没有把训练完成事件转发给模型页，就会出现“模型已经生成，但版本历史不自动刷新”的问题。

需要检查：

- `desktop_app/workers/training_worker.py` 是否成功调用 `create_model_version(...)`。
- 训练页 `_on_finished()` 发出的 `data_changed` 是否被主窗口连接。
- 模型版本页面是否有 `refresh()` / `showEvent()` / `data_changed` 响应。
- 训练完成后是否需要直接调用模型页刷新。

### 3. 训练中心只支持 YOLO

当前训练中心 UI 能识别：

- `yolo_detection`
- `image_classification`
- `anomaly_detection`

但实际逻辑中：

- YOLO 可以训练。
- 整图分类训练提示“暂未实现”。
- 异常检测训练提示“暂未实现”。

同时，样本集版本页已经能生成异常检测数据集：

```text
dataset/
  train/good/
  test/good/
  test/defect/
  ground_truth/defect/
```

因此当前缺口是：异常检测数据集已经能生成，但训练中心不能训练无监督模型，也不能注册异常检测模型版本。

## 二、开发目标

### 目标 A：分类驱动 bbox 队列

实现后，bbox 页默认只显示需要 bbox 的 NG/缺陷图片。

需要支持以下过滤模式：

| 模式 | 作用 |
|------|------|
| 待 bbox | 默认模式。只显示 NG/缺陷标签且尚无 bbox 的图片 |
| 全部缺陷图 | 显示所有 NG/缺陷标签图片 |
| 已标 bbox | 显示 NG/缺陷标签且已有 bbox 的图片 |
| 待复核 | 显示 `UNKNOWN` / `UNCERTAIN` 图片 |
| 全部图片 | 调试模式，显示所有图片 |

OK 图片不进入默认 bbox 队列。

### 目标 B：训练完成后模型版本历史自动刷新

训练完成并创建模型版本后，模型版本历史页面应立即刷新，不需要用户手动切换页面或点击刷新。

### 目标 C：训练中心接入无监督异常检测训练

训练中心应支持：

- 选择异常检测数据集版本。
- 配置异常检测训练参数。
- 启动异常检测训练 worker。
- 训练完成后注册模型版本。
- 模型版本可在生产复测 / 混合复测中选择。

## 三、建议代码改动

### 1. 新增统一标签策略

建议新增文件：

```text
core/label_policy.py
```

建议接口：

```python
BACKGROUND_LABELS = {"OK", "IGNORE", "INTERFERENCE"}
REVIEW_LABELS = {"UNKNOWN", "UNCERTAIN"}


def normalize_label(label: str) -> str:
    ...


def is_background_label(label: str) -> bool:
    ...


def is_review_label(label: str) -> bool:
    ...


def is_defect_label(label: str) -> bool:
    ...


def needs_bbox(label: str) -> bool:
    return is_defect_label(label)
```

注意：

- 不要继续在多个文件里手写 `BACKGROUND_LABELS`。
- `UNKNOWN` / `UNCERTAIN` 不建议默认作为 OK 背景进入训练。
- 若为了兼容旧数据需要保留旧行为，必须在 UI 或训练前明确提示。

需要替换引用位置：

- `core/dataset_validation.py`
- `core/dataset_builder.py`
- `core/anomaly_dataset_builder.py`
- `desktop_app/pages/bbox_annotation_page.py`
- 其它手写 `BACKGROUND_LABELS` 的地方。

### 2. 修改 bbox 标注页加载和过滤

目标文件：

```text
desktop_app/pages/bbox_annotation_page.py
```

当前 `_load_images()` 只保存 `self._image_paths`，缺少每张图的分类标签映射。建议新增：

```python
self._image_labels: dict[str, str] = {}
```

加载 `captured_images` 时保存：

```python
self._image_labels[image_path] = image.get("classification_label", "")
```

默认过滤模式改为：

```python
self._filter_mode = "needs_bbox"
```

`_get_filtered_paths()` 应按分类标签判断：

```python
label = self._image_labels.get(path, "")

if self._filter_mode == "needs_bbox":
    if not needs_bbox(label) or self._has_bbox(path):
        continue

if self._filter_mode == "all_defects":
    if not is_defect_label(label):
        continue

if self._filter_mode == "has_bbox":
    if not is_defect_label(label) or not self._has_bbox(path):
        continue

if self._filter_mode == "review":
    if not is_review_label(label):
        continue

if self._filter_mode == "all":
    pass
```

列表项建议显示：

```text
◇ image_001.jpg    NG_A
◆ image_002.jpg    NG_B
? image_003.jpg    UNKNOWN
```

### 3. 分类页增加 bbox 待办入口

目标文件：

```text
desktop_app/pages/sample_classification_page.py
```

建议在分类统计区域增加：

- `NG 待 bbox: N`
- `NG 已 bbox: N`
- `待复核: N`

“打开 bbox 标注”按钮文案建议改为：

```text
进入 bbox 标注：N 张待处理
```

点击后跳转 bbox 页，并保持 bbox 页默认筛选为 `待 bbox`。

### 4. 修复模型版本历史自动刷新

重点检查文件：

```text
desktop_app/workers/training_worker.py
desktop_app/pages/training_page.py
desktop_app/pages/model_version_page.py
desktop_app/main_window.py
```

要求：

1. `TrainingWorker` 训练完成后创建 `model_version` 成功。
2. `TrainingPage._on_finished()` 发出 `data_changed`。
3. 主窗口收到训练页 `data_changed` 后刷新模型版本页面。
4. 模型版本页提供明确刷新方法，例如：

```python
def refresh(self) -> None:
    self._refresh_versions()
```

如果当前页面类名不是 `ModelVersionPage`，按项目实际命名处理。

验收标准：

- 训练完成后，不切换页面、不手动刷新，模型版本历史表自动出现新模型。
- `model_type`、`model_path`、`training_job_id`、`dataset_version_id` 字段完整。

### 5. 接入异常检测训练

建议新增 worker：

```text
desktop_app/workers/anomaly_training_worker.py
```

或在现有训练 worker 中做任务类型分发，但建议单独 worker，避免 YOLO 逻辑继续膨胀。

训练中心需要支持：

```text
YOLO 检测训练
异常检测训练
```

异常检测训练输入：

- `DatasetVersion.source_type == "anomaly"`
- `dataset_path` 指向异常检测数据集目录

异常检测模型输出：

```text
outputs/train_anomaly/<job_name>_<timestamp>/
```

模型版本注册：

```python
create_model_version(
    project_id=job.project_id,
    model_name=f"{job.job_name} (anomaly)",
    training_job_id=job.job_id,
    model_type="patchcore",
    model_path=model_path,
    base_model="patchcore",
    metrics=json.dumps(metrics),
    status="completed",
    spec_id=...,
    dataset_version_id=...,
)
```

如果当前项目已有 PatchCore runner 或无监督推理入口，优先复用已有实现。不要新引入大框架，除非项目已经依赖或用户明确同意。

若暂时不能真实训练 PatchCore，也要避免做假训练。可以先实现：

- 异常检测训练任务 UI。
- 训练前依赖检查。
- 明确报错说明缺少训练后端。

但不要生成假的模型文件。

## 四、测试要求

至少新增或更新以下测试：

### bbox 工作流测试

- OK 图片不出现在 bbox 默认队列。
- NG 图片出现在 bbox 默认队列。
- NG 图片已有 bbox 后从 `待 bbox` 队列消失。
- NG 图片已有 bbox 后仍出现在 `全部缺陷图` 或 `已标 bbox`。
- `UNKNOWN` / `UNCERTAIN` 出现在 `待复核` 队列。

### 数据集构建测试

- YOLO 数据集构建时，OK 图生成空 label 文件。
- NG 图缺 bbox 时计入 `missing_bbox_count`。
- `UNKNOWN` / `UNCERTAIN` 不应静默作为 OK 背景训练，除非有显式兼容策略和测试覆盖。

### 训练中心测试

- `source_type="anomaly"` 的数据集版本能在训练中心识别为异常检测数据。
- YOLO 数据集版本仍走 YOLO worker。
- 异常检测数据集版本走 anomaly worker。
- 异常检测训练完成后创建 `model_version`。

### UI 刷新测试

- `TrainingPage.data_changed` 能触发模型版本页刷新。
- 训练完成后模型版本历史出现新模型。

## 五、验收命令

优先运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_dataset_validation.py tests\test_training_page.py tests\test_yolo_bbox_io.py -q
```

然后运行相关新增测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

如果修改了 UI 页面，至少做一次页面实例化 smoke test，确认 PySide 页面能创建、不报导入错误。

## 六、开发边界

- 不要做大规模 UI 重构。
- 不要改数据库历史数据，除非有迁移和兼容测试。
- 不要删除已有数据集、模型文件或输出目录。
- 不要做假的异常检测训练结果。
- 不要自动 `git commit` 或 `git push`。

## 七、推荐实施顺序

1. 先做 `core/label_policy.py`，统一标签判断。
2. 修改 bbox 页默认队列和过滤模式。
3. 修改分类页统计和跳转文案。
4. 修复训练完成后的模型版本历史刷新。
5. 接入异常检测训练 worker。
6. 补测试并跑全量 pytest。

这三个问题是同一条现场首训链路上的问题，优先保证流程闭环：

```text
分类减少 bbox 工作量
  -> YOLO / 异常检测数据集都能生成
  -> YOLO / 异常检测都能训练
  -> 训练完成模型版本自动出现
  -> 后续生产复测能选择模型
```
