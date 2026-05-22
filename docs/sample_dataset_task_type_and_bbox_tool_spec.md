# 样本集任务类型与 bbox 标注工具开发说明

## 背景问题

当前桌面端样本流程把“整图分类标签”和“YOLO 检测训练”混在了一起：

- 样本分类页可以给整张图片打标签，例如 `OK`、`NG-裂纹`、`油污`。
- 训练页默认走 YOLO 检测训练。
- YOLO 检测训练需要 bbox 框标注，但当前样本分类流程没有提供 bbox 工具。
- 结果是：NG 图片只有整图标签、没有 YOLO bbox 时，训练页才发现问题并阻断训练。

这属于流程设计问题。应该在样本集制作阶段先确认任务类型，再按任务类型加载对应工具和校验规则。

## 开发目标

新增“样本集任务类型”概念，并让样本制作流程按任务类型切换：

1. `YOLO 检测`
   - NG 图片必须有 bbox 标注。
   - 页面应提供 bbox 标注工具入口。
   - 导出/训练前强校验 bbox 完整性。

2. `整图分类`
   - 每张图只需要一个整图标签。
   - 使用现有样本分类工具。
   - 不要求 bbox。

3. `异常检测`
   - OK 图片用于训练。
   - NG 图片用于验证/测试。
   - 不要求 bbox，但需要明确 OK/NG 分组。

## 建议改动范围

优先改以下模块：

- `desktop_app/pages/sample_classification_page.py`
- `desktop_app/pages/dataset_page.py`
- `desktop_app/pages/training_page.py`
- `core/dataset_builder.py`
- `core/anomaly_dataset_builder.py`
- `core/capture_session.py` 或新增数据集配置模块
- `tests/`

如果需要新增 bbox 标注界面，建议新建：

- `desktop_app/widgets/bbox_annotation_widget.py`
- `desktop_app/pages/bbox_annotation_page.py`
- `core/yolo_annotation.py`

## 数据模型建议

为采集会话或数据集版本增加任务类型字段：

```python
DatasetTaskType = Literal["yolo_detection", "image_classification", "anomaly_detection"]
```

建议落库字段：

- `dataset_task_type`
- 默认值可以是空或 `image_classification`
- UI 中必须显式选择后才能生成训练数据集

如果当前表结构不方便改，可先在配置 JSON 中保存：

```json
{
  "session_id": "...",
  "dataset_task_type": "yolo_detection"
}
```

## UI 设计要求

### 样本集配置区

在样本相关页面顶部增加任务类型选择：

- `YOLO 检测`
- `整图分类`
- `异常检测`

选择后显示对应提示：

#### YOLO 检测提示

```text
用于训练目标检测模型。每张 NG 图片必须画出缺陷 bbox，并指定类别。
只有整图标签不够，缺少 bbox 的 NG 图片不能进入 YOLO 训练。
```

按钮：

- `打开 bbox 标注`
- `检查 bbox 完整性`
- `生成 YOLO 数据集`

#### 整图分类提示

```text
用于训练整图分类模型。每张图片只需要一个类别标签，不需要 bbox。
```

按钮：

- `继续整图分类`
- `生成分类数据集`

#### 异常检测提示

```text
用于训练异常检测模型。训练集只使用 OK 图片，NG 图片用于验证和测试。
```

按钮：

- `检查 OK/NG 分组`
- `生成异常检测数据集`

## bbox 标注工具最小功能

第一版只需要完成可用闭环，不追求复杂标注平台。

必需功能：

- 加载当前采集会话图片。
- 左侧图片列表支持筛选：
  - 未画框
  - 已画框
  - 当前类别
- 右侧显示大图。
- 鼠标拖拽画矩形框。
- 每个框绑定类别。
- 支持删除选中框。
- 支持保存为 YOLO `.txt`。
- 切换图片时自动保存或明确提示保存。

YOLO txt 格式：

```text
class_id x_center y_center width height
```

坐标必须是归一化值，范围 `0.0-1.0`。

## 类别映射规则

YOLO 检测数据集需要稳定的 class id。

建议按当前标签配置顺序生成：

```python
class_names = ["NG-裂纹", "油污", "NG-点伤"]
```

跳过背景类：

- `OK`
- `UNKNOWN`
- `IGNORE`
- 空标签

注意：不要把 `OK` 写成 YOLO 检测类别。YOLO 中无框图片就是背景/正常样本。

## 数据集生成规则

### YOLO 检测

输入：

- 图片文件
- 同名 `.txt` bbox 文件
- 当前标签配置

规则：

- OK 图片允许空 `.txt`。
- NG 图片必须至少有一个 bbox。
- NG 图片没有 bbox 时必须阻断生成/训练。
- 生成 `data.yaml`：

```yaml
path: <dataset_dir>
train: images/train
val: images/val
nc: <num_classes>
names:
  0: NG-裂纹
  1: 油污
```

### 整图分类

建议输出目录结构：

```text
dataset_classification/
  train/
    OK/
    NG-裂纹/
    油污/
  val/
    OK/
    NG-裂纹/
    油污/
```

规则：

- 每张图片必须有整图标签。
- 不要求 bbox。
- 未标注图片不能进入训练集。

### 异常检测

建议输出目录结构：

```text
dataset_anomaly/
  train/
    OK/
  test/
    OK/
    NG/
```

规则：

- 训练集只放 OK。
- NG 只放 test/val。
- 如果没有足够 OK 样本，阻断生成。

## 训练页改动

训练页不要默认只显示 YOLO 参数。

应根据数据集任务类型切换训练入口：

- `yolo_detection`：显示 YOLO 参数，调用 YOLO 训练。
- `image_classification`：显示分类训练参数，调用分类训练器。
- `anomaly_detection`：显示异常检测参数，调用 PatchCore/异常检测训练。

最小实现可以先做到：

- YOLO 检测：保留现有训练。
- 整图分类：先显示“分类训练暂未实现”，但允许生成分类数据集。
- 异常检测：接入已有 `anomaly_dataset_builder`，训练可后续接。

## 校验规则

新增统一校验函数，建议放在 `core/dataset_builder.py` 或新建 `core/dataset_validation.py`。

### YOLO 检测校验

必须返回：

- 总图片数
- NG 图片数
- 缺 bbox 的 NG 图片数
- 缺 bbox 图片列表
- 是否允许训练

伪代码：

```python
def validate_yolo_detection_dataset(session_id: str) -> DatasetValidationResult:
    ...
```

阻断条件：

- `missing_bbox_count > 0`
- 没有任何有效 bbox
- 类别映射为空

### 整图分类校验

阻断条件：

- 存在未标注图片
- 类别数小于 2
- 某类别图片数为 0

### 异常检测校验

阻断条件：

- OK 训练图片数量不足
- 没有 NG 验证图片时给警告，但不一定阻断

## 测试要求

新增或更新以下测试：

### YOLO 检测

- NG 图片无 bbox 时，校验失败。
- OK 图片无 bbox 时，校验通过。
- NG 图片有 bbox 时，生成 YOLO `.txt` 和 `data.yaml`。
- 缺 bbox 时训练页不创建 training job。

### 整图分类

- 未标注图片存在时，分类数据集生成失败。
- 分类数据集按类别目录输出。
- OK/NG 标签都能正确进入目录。

### 异常检测

- OK 图片进入 train。
- NG 图片进入 test/val。
- NG 不进入 train。

### UI 行为

- 选择 `YOLO 检测` 后显示 bbox 工具入口。
- 选择 `整图分类` 后隐藏 bbox 要求。
- 选择 `异常检测` 后显示 OK/NG 分组提示。

## 验收标准

完成后应满足：

1. 用户在样本制作阶段必须选择任务类型。
2. 选择 YOLO 检测时，系统明确要求 bbox。
3. 缺 bbox 的 NG 图片不能进入 YOLO 训练。
4. 整图分类样本不会误走 YOLO 检测训练。
5. 异常检测样本不会把 NG 放进训练集。
6. 训练页根据任务类型显示正确入口和提示。
7. 所有新增逻辑有测试覆盖。

## 推荐实现顺序

1. 增加任务类型字段和 UI 选择。
2. 增加数据集校验函数。
3. 让训练页根据任务类型阻断错误训练。
4. 实现 YOLO bbox 标注工具最小版。
5. 实现 YOLO 数据集生成强校验。
6. 再补整图分类数据集生成。
7. 最后完善异常检测数据集流程。

## 当前优先级

先做 P0：

- 任务类型选择
- YOLO 缺 bbox 阻断
- bbox 标注工具入口
- YOLO bbox 完整性检查

P1 再做：

- 整图分类数据集生成
- 异常检测数据集生成 UI 优化
- 分类训练器接入

