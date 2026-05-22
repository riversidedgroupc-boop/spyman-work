# Phase C：现场复核结果到 YOLO 首训集成开发说明

本文档给 Claude Code 使用。请只实现 Phase C，不要扩展到 Phase D/E。

## 1. 背景

当前软件定位是首次客户现场交付工具，核心流程是：

```text
采集少量现场数据
-> 用异常检测发现未知异常
-> 人工复核并建立缺陷字典
-> 生成首个可用 YOLO 模型
-> 再次产线复测
```

Phase A 已实现核心数据模型：

```text
core/field_session.py
core/defect_dictionary.py
core/anomaly_review.py
core/hybrid_strategy.py
```

Phase B 已实现现场交付流程 UI：

```text
desktop_app/pages/field_workflow_page.py
```

Phase C 的任务是把 Phase B 的人工复核结果转成 YOLO 首训数据集，并让训练结果可以追溯到现场会话、缺陷字典、数据集版本和训练任务。

## 2. Phase C 目标

Phase C 只解决三件事：

1. **只用人工确认的缺陷训练 YOLO**
   - 只有 `review_status == "confirmed_defect"` 且 `assigned_defect_type_id` 不为空的样本可以进入 YOLO 正样本。
   - `unknown_pending` 绝不能进入 YOLO 训练集。
   - `normal`、`acceptable_texture`、`noise_or_reflection` 默认不作为缺陷类别。

2. **训练前有数据质量闸门**
   - 没有 confirmed defect 时不能生成 YOLO 首训数据集。
   - confirmed defect 未绑定缺陷类型时不能进入训练。
   - confirmed defect 缺少 bbox 标注时不能进入 YOLO detection 训练。
   - 类别数、样本数、bbox 完整性要有明确报告。

3. **模型版本可追溯**
   - 训练出的 `best.pt` 需要能追溯：
     - `field_session_id`
     - `dataset_version_id`
     - `training_job_id`
     - 缺陷字典/class mapping
     - 源复核记录摘要

## 3. 非目标

不要在 Phase C 做这些事：

- 不做真实 anomaly 模型推理。
- 不做自动聚类。
- 不做 Hybrid Retest UI。
- 不做产线实时推理。
- 不做 TensorRT 导出或加载。
- 不做部署包。
- 不重写现有训练页面。
- 不删除项目数据。

## 4. 推荐架构

新增一个桥接模块：

```text
core/field_training_dataset.py
```

职责：

```text
anomaly_reviews + defect_types
-> 过滤可训练样本
-> 校验 defect type / bbox / image path
-> 生成 YOLO class mapping
-> 构建 YOLO dataset 目录
-> 写 data.yaml 和 dataset_summary.json
-> 创建 dataset_version
-> 返回构建结果
```

不要把这个逻辑直接塞进 `core/dataset_builder.py`。现有 `dataset_builder.py` 继续服务普通 capture session；Phase C 是从人工复核结果生成首训数据集，数据来源不同，应单独建模块。

## 5. 建议文件范围

主要新增：

```text
core/field_training_dataset.py
tests/test_field_training_dataset.py
tests/test_field_workflow_training_integration.py
```

可能需要小范围修改：

```text
desktop_app/pages/field_workflow_page.py
desktop_app/workers/training_worker.py
core/model_version.py
core/training_job.py
core/storage.py
desktop_app/i18n.py
```

修改原则：

- 尽量复用现有 `core/training_job.py`、`core/model_version.py`、`core/dataset_version.py`。
- 如必须增加字段，优先做兼容迁移。
- 如果训练任务表暂时不适合加字段，可把 Phase C 源信息写入 `training_config` 或 `notes` JSON，但 `model_versions.dataset_version_id` 已存在，应优先写入。

## 6. 数据流

目标数据流：

```text
field_session
    |
    v
anomaly_reviews
    |
    | filter:
    |   review_status == confirmed_defect
    |   assigned_defect_type_id is not null
    v
defect_types
    |
    | build class_mapping
    v
field_training_dataset builder
    |
    | output:
    |   images/train
    |   images/val
    |   labels/train
    |   labels/val
    |   data.yaml
    |   dataset_summary.json
    v
dataset_versions
    |
    v
training_jobs
    |
    v
TrainingWorker
    |
    v
model_versions
```

## 7. 训练样本过滤规则

### 7.1 可以进入 YOLO 正样本

满足全部条件：

```text
review_status == "confirmed_defect"
assigned_defect_type_id is not null
image_path exists
bbox label exists
```

缺陷类别来自 `defect_types`：

```text
class name = defect_type.code 优先
如果 code 为空，用 display_name_en
如果 display_name_en 也为空，用 display_name_zh
```

### 7.2 必须排除

这些状态不得作为 YOLO 正样本：

```text
unreviewed
unknown_pending
normal
acceptable_texture
noise_or_reflection
```

### 7.3 负样本策略

Phase C 默认不强制加入负样本。

如果要加入负样本，只允许这些来源作为空 label 文件：

```text
normal
acceptable_texture
noise_or_reflection
```

但需要在结果报告里明确：

```text
negative_sample_count
```

不要把 `unknown_pending` 当负样本。

## 8. bbox 标签要求

YOLO detection 必须有 bbox 标签。

建议支持两种来源：

1. 与图片同名的 sidecar `.txt`

```text
image_path = xxx/image001.png
label_path = xxx/image001.txt
```

2. 如果项目已有 bbox 标注存储模块，则复用现有读取逻辑。

如果 confirmed defect 缺少 bbox：

- 不复制进训练集。
- 在结果里计入：

```text
missing_bbox_count
skipped_confirmed_count
```

- 如果所有 confirmed defect 都缺 bbox，直接抛出明确错误：

```text
No confirmed defects with bbox labels are available for YOLO training.
```

## 9. `core/field_training_dataset.py` 建议 API

建议实现：

```python
@dataclass
class FieldTrainingDatasetResult:
    dataset_dir: str
    yaml_path: str
    dataset_version_id: str | None
    field_session_id: str
    image_count: int
    positive_count: int
    negative_count: int
    skipped_unknown_count: int
    skipped_missing_bbox_count: int
    skipped_unassigned_count: int
    class_names: list[str]
    class_mapping: dict[str, int]
    source_review_ids: list[str]
    summary_path: str


def build_yolo_dataset_from_field_reviews(
    field_session_id: str,
    dataset_dir: str,
    *,
    project_id: str,
    spec_id: str = "",
    version_name: str = "",
    val_ratio: float = 0.2,
    include_negative_samples: bool = False,
    progress_callback: Callable[[str, float], None] | None = None,
) -> FieldTrainingDatasetResult:
    ...
```

必要行为：

- 读取指定 `field_session_id` 的 anomaly reviews。
- 读取当前 project 的 defect types。
- 构建稳定 class mapping。
- 复制图片到 YOLO 目录。
- 复制或生成 label 文件。
- 写 `data.yaml`。
- 写 `dataset_summary.json`。
- 创建 `dataset_version` 记录。
- 返回完整结果。

## 10. YOLO 数据集目录格式

生成目录：

```text
<dataset_dir>/
  images/
    train/
    val/
  labels/
    train/
    val/
  data.yaml
  dataset_summary.json
```

`data.yaml` 示例：

```yaml
path: D:/work/copper-defect-eval-tool/project_data/...
train: images/train
val: images/val
nc: 2
names:
  0: SCRATCH
  1: PIT
```

`dataset_summary.json` 至少包含：

```json
{
  "field_session_id": "...",
  "project_id": "...",
  "spec_id": "...",
  "positive_count": 10,
  "negative_count": 0,
  "skipped_unknown_count": 3,
  "skipped_missing_bbox_count": 2,
  "skipped_unassigned_count": 1,
  "class_mapping": {"SCRATCH": 0, "PIT": 1},
  "source_review_ids": ["..."]
}
```

## 11. DatasetVersion 要求

生成数据集成功后创建 `dataset_versions` 记录。

建议字段：

```text
project_id = project_id
spec_id = spec_id
capture_session_id = ""
version_name = version_name or auto generated
source_type = "field_reviews"
dataset_path = dataset_dir
yaml_path = data.yaml path
image_count = positive_count + negative_count
class_names = JSON list
quality_report = JSON summary
```

如果现有 `dataset_version.py` 不允许 `capture_session_id` 为空，做兼容处理，不要破坏旧流程。

## 12. TrainingWorker / ModelVersion 集成

训练完成后注册 `model_versions` 时，应写入：

```text
spec_id
dataset_version_id
training_job_id
class_mapping
metrics
model_path
base_model
```

如果 `TrainingWorker` 当前拿不到 `dataset_version_id`，建议：

1. 从 `training_job.training_config` 读取。
2. 或扩展 `TrainingWorker.__init__` 可选参数：

```python
dataset_version_id: str = ""
class_mapping: dict[str, int] | None = None
spec_id: str = ""
```

保持向后兼容，不能破坏已有训练入口。

## 13. Field Workflow UI 集成

在 `desktop_app/pages/field_workflow_page.py` 增加 “首次 YOLO 训练准备” 区块。

建议显示：

```text
confirmed defect count
defect type count
missing bbox count
unknown pending count
training readiness
dataset yaml path
```

建议按钮：

```text
生成 YOLO 首训数据集
刷新训练准备状态
```

按钮行为：

1. 检查当前 project/spec/session。
2. 调用 `build_yolo_dataset_from_field_reviews(...)`。
3. 显示结果摘要。
4. 不直接强行开始训练，先生成数据集并让用户看到路径。

是否启动训练可以留给现有训练页面，或者提供一个轻量入口创建 training job，但不要在 Phase C 里重写训练页面。

## 14. 错误提示要求

必须明确提示：

- 未选择项目/规格。
- 未选择现场会话。
- 没有 confirmed defect。
- confirmed defect 未绑定 defect type。
- confirmed defect 缺 bbox。
- 图片路径不存在。
- 数据集生成失败。

不要吞掉异常。

## 15. 测试要求

新增测试：

```text
tests/test_field_training_dataset.py
tests/test_field_workflow_training_integration.py
```

至少覆盖：

1. 只有 `confirmed_defect + assigned_defect_type_id + bbox` 会进入 YOLO 数据集。
2. `unknown_pending` 不会进入训练集。
3. `normal / acceptable_texture / noise_or_reflection` 不会变成缺陷类别。
4. confirmed defect 缺 bbox 会被计入 `skipped_missing_bbox_count`。
5. 全部 confirmed defect 都缺 bbox 时抛出明确错误。
6. `data.yaml` 的 `names` 来自 `defect_types`。
7. `dataset_summary.json` 包含 `field_session_id`、`class_mapping`、`source_review_ids`。
8. 创建 `dataset_version`，且 `source_type == "field_reviews"`。
9. `TrainingWorker` 注册 model version 时写入 `dataset_version_id` 和 `class_mapping`。
10. Field Workflow 页面能显示训练准备状态。

## 16. 必跑命令

先跑新增测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_field_training_dataset.py tests\test_field_workflow_training_integration.py -q
```

再跑 Phase A/B/C 相关测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_field_session.py tests\test_defect_dictionary.py tests\test_anomaly_review.py tests\test_field_workflow_page.py tests\test_training_job.py tests\test_training_worker.py -q
```

跑 targeted ruff：

```powershell
.\.venv\Scripts\python.exe -m ruff check core\field_training_dataset.py core\dataset_builder.py core\model_version.py core\training_job.py desktop_app\pages\field_workflow_page.py desktop_app\workers\training_worker.py tests\test_field_training_dataset.py tests\test_field_workflow_training_integration.py
```

如果时间允许，跑全量：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 17. 验收标准

Phase C 完成标准：

- 可以从 field session 的人工复核结果生成 YOLO 数据集。
- 只包含 confirmed defect 正样本。
- unknown pending 被排除。
- normal/noise/acceptable texture 不会成为缺陷类别。
- 缺 bbox 的 confirmed defect 有明确统计和阻断。
- `data.yaml` 正确。
- `dataset_summary.json` 正确。
- `dataset_versions` 记录正确。
- 训练完成后的 `model_versions` 能追溯到 dataset/training/class mapping。
- Field Workflow 页面能显示训练准备状态并触发数据集生成。
- 新增测试通过。
- targeted ruff 通过。

## 18. 开发约束

- 默认使用 UTF-8。
- 不要删除文件或项目数据。
- 不要修改 `.env`、密钥、CI/CD 配置。
- 不要 `git commit` 或 `git push`。
- 不要安装 TensorRT。
- 不要把 `.engine` 当作训练输出。
- 保持 `.pt` 为 canonical model asset。
- 修改范围控制在 Phase C。
