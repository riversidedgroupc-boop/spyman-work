# 示例数据集说明

此目录用于存放示例数据，帮助快速验证工具流程。

## 放置真实数据的方法

### 1. 图片

将铜管表面图片放入 `data/images/` 目录：

```
data/images/
├── tube_001.jpg
├── tube_002.jpg
├── tube_003.png
└── ...
```

支持的格式：`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`

### 2. YOLO 标注（可选）

每张图片对应一个同名的 `.txt` 文件，放入 `data/labels/` 目录：

```
data/labels/
├── tube_001.txt
├── tube_002.txt
└── ...
```

标注格式：
```
class_id x_center y_center width height
```

示例 `tube_001.txt`：
```
3 0.45 0.32 0.08 0.12
4 0.72 0.55 0.05 0.05
```

### 3. 数据集划分（可选）

在 `data/splits/test.txt` 中列出测试集图片文件名（每行一个）：

```
tube_001.jpg
tube_002.jpg
tube_003.jpg
```

### 4. YOLO 模型

将 `.pt` 模型文件放入 `models/yolo/` 目录：

```
models/yolo/
└── best.pt
```

可以使用 Ultralytics 预训练模型快速测试：
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.save("models/yolo/best.pt")
```

### 5. 异常检测结果导入（可选）

将已有推理结果 CSV 放入 `outputs/cache/`：

```csv
image_path,anomaly_score,heatmap_path,mask_path
data/images/tube_001.jpg,0.23,,
data/images/tube_002.jpg,0.87,,
```

## 无真实数据时

即使没有真实数据和模型文件，工具也可以：

1. **OpenCV 规则检测**：基于传统图像处理的缺陷候选区域提取，不需要模型文件
2. **Mock 模式**：PatchCore/EfficientAD/FastFlow 可以生成模拟异常分数用于流程验证
3. **界面预览**：查看工具 UI 布局和功能结构

只需准备几张任意图片（甚至纯色图片）放入 `data/images/` 即可体验完整流程。
