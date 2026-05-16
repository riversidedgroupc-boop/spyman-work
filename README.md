# 铜管表面缺陷模型评测与融合验证工具

Copper Tube Surface Defect Model Evaluation & Fusion Verification Tool

## 项目简介

用于铜管表面缺陷检测研发阶段的快速评测工具。支持 YOLO、PatchCore、EfficientAD、FastFlow、OpenCV 传统规则检测，以及多模型融合策略的效果对比。

**重要：本工具用于研发评估，不是最终在线检测软件。**

## 功能列表

- 数据集管理与标注解析（YOLO 格式）
- 多模型推理：YOLO、PatchCore、EfficientAD、FastFlow、OpenCV
- 后处理特征计算（几何特征、密度、形态学）
- 6 种融合策略（YOLO Only、Anomaly Only、YOLO Priority、Anomaly Priority、Rule Based、Double Confirm）
- 工业检测指标：OK 误报率、NG 漏检率、可接受微缺陷误报率、未知缺陷召回率、临界缺陷检出率
- 误判样本池自动分类
- 可视化：检测框、热力图、决策标记
- Excel 报告导出

## 环境安装

```bash
cd copper-defect-eval-tool
pip install -r requirements.txt
```

如需 YOLO 推理：
```bash
pip install ultralytics
```

异常检测模型使用 anomalib 原生实现；依赖已写入 requirements。PatchCore/EfficientAD/FastFlow 需要用铜管 OK 样本训练后再切换到 real 模式。

## 运行命令

```bash
streamlit run app.py
```

启动后浏览器访问 http://localhost:8501。

## 数据集目录格式

```
data/
├── images/          # 图片文件 (.jpg, .jpeg, .png, .bmp, .tif, .tiff)
│   ├── sample_001.jpg
│   ├── sample_002.jpg
│   └── ...
├── labels/          # YOLO 格式标注（可选，未标注图片也可推理）
│   ├── sample_001.txt
│   ├── sample_002.txt
│   └── ...
└── splits/          # 数据集划分文件（可选）
    └── test.txt     # 每行一个图片文件名
```

## YOLO 标注格式说明

每张图片对应一个同名的 `.txt` 文件：

```
class_id x_center y_center width height
```

- 所有坐标归一化到 [0, 1]
- class_id 对应类别编号（见 dataset.yaml）
- 每个目标一行

示例（一张图有 1 个划伤和 1 个凹坑）：
```
3 0.45 0.32 0.08 0.12
4 0.72 0.55 0.05 0.05
```

## 配置文件说明

详细的方法优劣势、融合策略和使用建议见：

- [模型方法、融合策略与使用说明](MODEL_AND_STRATEGY_GUIDE.md)

### configs/dataset.yaml
数据集路径、类别定义、像素尺寸配置。

### configs/models.yaml
各模型开关、模型路径、阈值配置。
- `enabled: true/false` — 是否启用该模型
- `mode: "real" | "import" | "mock"` — 推理模式

### configs/fusion_rules.yaml
融合规则参数：置信度阈值、几何阈值、密度规则。

### configs/app_config.yaml
应用界面和导出设置。

## 如何加载 YOLO 模型

1. 将训练好的 `.pt` 模型放入 `models/yolo/` 目录
2. 在 `configs/models.yaml` 中设置 `model_path`
3. 在 Streamlit 界面左侧 sidebar 中确认 `启用 YOLO` 已勾选

或使用 Ultralytics 预训练模型：
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.save("models/yolo/best.pt")
```

## 如何导入 PatchCore / EfficientAD 结果

在没有 anomalib 或模型文件时，可通过 CSV 导入已有推理结果：

### CSV 格式
```csv
image_path,anomaly_score,heatmap_path,mask_path
data/images/sample_001.jpg,0.23,,
data/images/sample_002.jpg,0.87,,
```

### 配置步骤
1. 将 CSV 文件放入 `outputs/cache/`
2. 在 `configs/models.yaml` 中设置 `mode: "import"` 和 `result_file` 路径
3. 或在界面中直接选择导入文件

### Mock 模式
`mode: "mock"` 将使用确定性随机分数（基于图片路径 hash），用于测试完整流程。

## 如何运行批量评测

1. 在左侧 sidebar 设置数据集路径和模型路径
2. 选择融合策略
3. 调整阈值参数
4. 切换到「批量评测」Tab
5. 点击「运行批量测试」
6. 查看结果表格和指标统计

## 如何查看误判样本

切换到「误判样本池」Tab，自动展示：
- OK 被判 NG 的样本
- OK_micro_defect 被判 NG 的样本
- NG 被判 OK 的样本
- YOLO 未识别但异常检测高分的样本
- YOLO 命中但异常检测低分的样本
- Borderline 样本

## 如何导出报告

切换到「报告导出」Tab：
1. 点击「导出 Excel 报告」— 保存到 `outputs/reports/`
2. 可选导出带标注的可视化图片
3. 可选导出 HTML 报告

## 如何扩展新的模型 Runner

1. 在 `src/inference/` 下创建新的 runner 文件
2. 继承 `BaseRunner` 并实现 `load_model()` 和 `predict()`
3. 输出统一格式 `UnifiedPrediction`
4. 在 `src/inference/__init__.py` 中注册
5. 在 app.py 中引入

示例：
```python
from src.inference.base_runner import BaseRunner
from src.fusion.decision_types import UnifiedPrediction, BBoxPrediction

class MyRunner(BaseRunner):
    def __init__(self, config=None):
        super().__init__("my_model", config)

    def load_model(self):
        # Load your model here
        self._is_loaded = True

    def predict(self, image_path):
        # Run inference
        return UnifiedPrediction(
            image_path=str(image_path),
            model_name="my_model",
            predictions=[...],
        )
```

## 如何扩展新的融合策略

1. 在 `src/fusion/decision_types.py` 的 `FusionStrategy` 枚举中添加新策略
2. 在 `src/fusion/rule_engine.py` 中添加对应的 `_decide_xxx` 方法
3. 在 `decide()` 方法的分发逻辑中添加新分支
4. 在 `src/fusion/fusion_strategies.py` 中注册名称和描述

## 常见问题

**Q: 没有 YOLO 模型文件能运行吗？**
A: 可以。YOLO 加载失败会有提示，OpenCV 规则检测和异常检测 mock 模式不受影响。

**Q: 没有 anomalib 能用吗？**
A: 可以。PatchCore/EfficientAD/FastFlow 默认使用 mock 模式，生成模拟异常分数用于流程验证。

**Q: 没有标注能用吗？**
A: 可以推理和可视化，但不参与监督指标计算。标注是可选的。

**Q: 支持哪些图片格式？**
A: jpg, jpeg, png, bmp, tif, tiff。

**Q: 支持 GPU 推理吗？**
A: YOLO 自动检测 CUDA 设备，可设置 `device: "auto"` 或 `device: "cuda"`。

**Q: 如何添加新的缺陷类别？**
A: 修改 `configs/dataset.yaml` 的 `classes` 部分，同时更新 `src/dataset/label_schema.py`。
