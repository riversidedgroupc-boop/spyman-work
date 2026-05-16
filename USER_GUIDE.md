# 铜管表面缺陷模型评测与融合验证工具 — 使用手册

> 版本 0.1.0 | 2026-05-16

---

## 目录

1. [快速上手](#1-快速上手)
2. [数据准备](#2-数据准备)
3. [配置文件说明](#3-配置文件说明)
4. [模型加载](#4-模型加载)
5. [界面操作指南](#5-界面操作指南)
6. [融合策略详解](#6-融合策略详解)
7. [指标说明](#7-指标说明)
8. [报告导出](#8-报告导出)
9. [扩展开发](#9-扩展开发)
10. [常见问题](#10-常见问题)

---

## 1. 快速上手

### 1.1 环境要求

- Python 3.10+
- Windows / Linux / macOS
- 建议 8GB+ 内存（YOLO 推理需 GPU 或至少 4GB 内存）

### 1.2 安装

```bash
cd copper-defect-eval-tool
pip install -r requirements.txt
```

核心依赖：

| 包 | 用途 | 必需 |
|---|------|------|
| `streamlit` | Web 界面 | ✅ |
| `opencv-python` | 传统视觉检测、图像处理 | ✅ |
| `numpy` | 数值计算 | ✅ |
| `pandas` | 数据表格 | ✅ |
| `pyyaml` | 配置文件解析 | ✅ |
| `matplotlib` | 图表生成 | ✅ |
| `openpyxl` | Excel 报告导出 | ✅ |
| `torch` | 深度学习运行时 | YOLO 推理需要 |
| `ultralytics` | YOLO 模型加载与推理 | YOLO 推理需要 |
| `anomalib` | PatchCore/EfficientAD 真实推理 | 可选 |

### 1.3 最小运行

即使没有任何模型文件，也可以启动并体验完整流程：

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

### 1.4 首次使用流程

1. 准备几张测试图片放入 `data/images/`
2. 在左侧 sidebar 点击 **"扫描数据集"**
3. 点击 **"加载模型"**（OpenCV 规则检测默认启用，YOLO 找不到模型会有提示）
4. 切换到 **"单图测试"** Tab，选择图片，点击"运行推理"
5. 查看检测结果和融合判定
6. 切换到 **"批量评测"** Tab，点击"运行批量测试"
7. 切换到 **"报告导出"** Tab，导出 Excel 报告

---

## 2. 数据准备

### 2.1 图片

支持的格式：`.jpg` `.jpeg` `.png` `.bmp` `.tif` `.tiff`

```
data/images/
├── tube_scan_001.jpg
├── tube_scan_002.jpg
├── tube_scan_003.png
└── ...
```

工具会自动扫描目录下所有支持的图片文件。**标注是可选的**，没有标注的图片仍然可以进行推理和可视化。

### 2.2 YOLO 标注格式

每张图片对应一个同名的 `.txt` 文件，放在 `data/labels/` 目录下：

```
data/labels/
├── tube_scan_001.txt
├── tube_scan_002.txt
└── ...
```

标注文件格式（YOLO 格式，归一化坐标）：

```
class_id x_center y_center width height
```

- 所有坐标归一化到 `[0, 1]` 区间
- 每行一个目标
- `class_id` 对应 `configs/dataset.yaml` 中定义的类别编号

**示例** `tube_scan_001.txt`（包含 1 个划伤和 1 个凹坑）：

```
3 0.45 0.32 0.08 0.12
4 0.72 0.55 0.05 0.05
```

### 2.3 类别体系

| class_id | 标签名 | 含义 | 分组 |
|----------|--------|------|------|
| 0 | `OK_clean` | 表面正常，无明显缺陷 | OK |
| 1 | `OK_micro_defect` | 微小点状/划痕，工艺可接受 | acceptable_micro |
| 2 | `OK_oil_stain` | 轻微油污/色差，工艺可接受 | OK |
| 3 | `NG_scratch` | 明显划伤 | NG |
| 4 | `NG_pit` | 明显凹坑/麻坑 | NG |
| 5 | `NG_dent` | 压伤/压痕 | NG |
| 6 | `NG_dense_micro_defect` | 密集微小缺陷 | NG |
| 7 | `NG_stain` | 严重油污/污染/异物 | NG |
| 8 | `NG_unknown` | 未知异常缺陷 | NG |
| 9 | `Borderline` | 临界样本，需人工复判 | borderline |

### 2.4 数据集划分文件（可选）

在 `data/splits/test.txt` 中指定测试集，每行一个图片文件名：

```
tube_scan_001.jpg
tube_scan_002.jpg
tube_scan_010.jpg
```

如果在 sidebar 中指定了划分文件，批量评测将只对划分内的图片进行推理。

### 2.5 无标注数据的处理

- 没有标注的图片：可以进行推理和可视化，显示检测框和热力图
- 但**不参与监督指标计算**（OK 误报率、NG 漏检率等），因为没有 ground truth
- 未标注图片在"数据集概览"中标记为"未标注"

---

## 3. 配置文件说明

### 3.1 dataset.yaml — 数据集配置

```yaml
dataset:
  image_dir: "data/images"        # 图片目录路径
  label_dir: "data/labels"        # 标注目录路径
  split_file: "data/splits/test.txt"  # 数据集划分文件（可选）
  valid_extensions:               # 支持的图片格式
    - .jpg
    - .jpeg
    - .png
    - .bmp
    - .tif
    - .tiff

classes:                          # 类别 ID → 名称映射
  0: OK_clean
  1: OK_micro_defect
  # ... (共 10 类)

label_groups:                     # 类别分组（用于统计和筛选）
  ok:
    - OK_clean
    - OK_micro_defect
    - OK_oil_stain
  ng:
    - NG_scratch
    - NG_pit
    - NG_dent
    - NG_dense_micro_defect
    - NG_stain
    - NG_unknown
  borderline:
    - Borderline

pixel_size_mm:                    # 像素→毫米转换系数
  x: 0.01
  y: 0.01

line_speed_m_per_min: 80          # 产线速度（预留）
encoder_resolution:               # 编码器分辨率（预留）
  pulses_per_meter: 10000
```

### 3.2 models.yaml — 模型配置

```yaml
yolo:
  enabled: true                   # 是否启用
  model_path: "models/yolo/best.pt"  # 模型文件路径
  conf_threshold: 0.6             # 检测置信度阈值
  iou_threshold: 0.5              # NMS IOU 阈值
  device: "auto"                  # 设备：auto / cpu / cuda:0
  task: "detect"                  # 任务类型：detect / segment

patchcore:
  enabled: false                  # 是否启用
  mode: "mock"                    # 运行模式：real / import / mock
  model_path: "models/patchcore/model.ckpt"
  result_file: "outputs/cache/patchcore_results.csv"  # import 模式的 CSV 路径
  score_threshold: 0.65           # 异常分数阈值
  input_size: [256, 256]          # 模型输入尺寸

efficientad:
  enabled: false
  mode: "mock"
  # ... 同上

fastflow:
  enabled: false
  mode: "mock"
  # ... 同上

opencv:
  enabled: true                   # 传统规则检测默认启用
  bright_threshold: 220           # 亮点检测灰度阈值 (0-255)
  dark_threshold: 35              # 暗点检测灰度阈值 (0-255)
  min_area_px: 8                  # 最小缺陷面积 (px)
  max_area_px: 5000               # 最大缺陷面积 (px)
  scratch_aspect_ratio: 5.0       # 划伤判定长宽比
  local_contrast_threshold: 30    # 局部对比度异常阈值
  morphology_kernel_size: 3       # 形态学核大小
```

#### 模型模式说明

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `real` | 加载真实模型进行推理 | 已有 anomalib 环境和模型文件 |
| `import` | 从 CSV 文件导入已有推理结果 | 已有离线推理结果，只需评测 |
| `mock` | 生成确定性随机分数（基于图片路径 hash） | 快速验证软件流程、无模型文件时 |

### 3.3 fusion_rules.yaml — 融合规则配置

```yaml
yolo:
  conf_threshold: 0.6             # YOLO 检测有效的最低置信度
  major_defect_classes:           # 严重缺陷类别（直接判 NG）
    - NG_scratch
    - NG_pit
    - NG_dent
    - NG_stain
  direct_ng_conf_threshold: 0.75  # 严重缺陷直接判 NG 的置信度阈值

anomaly:
  patchcore_score_threshold: 0.65     # PatchCore 异常阈值
  efficientad_score_threshold: 0.65   # EfficientAD 异常阈值
  fastflow_score_threshold: 0.65      # FastFlow 异常阈值
  unknown_ng_score_threshold: 0.85    # 未知异常高分阈值

geometry:
  min_defect_area_px: 8               # 最小缺陷面积 (px)，小于此值忽略
  acceptable_micro_area_px: 30        # 可接受微缺陷最大面积
  ng_area_px: 200                     # 大缺陷面积阈值
  acceptable_scratch_length_mm: 0.5   # 可接受划伤长度
  ng_scratch_length_mm: 2.0           # NG 划伤长度阈值
  long_scratch_aspect_ratio: 5.0      # 长划伤长宽比判断

density:
  enable_density_rule: true           # 是否启用密度规则
  max_micro_defect_count_per_meter: 50    # 每米最大可接受微缺陷数量
  max_micro_defect_area_per_meter: 500     # 每米最大可接受微缺陷总面积

fusion:
  strategy: rule_based                # 默认融合策略
  yolo_priority: true                 # YOLO 是否优先
  anomaly_for_unknown: true           # 异常检测处理未知缺陷
  require_double_confirm_for_ng: false # 是否需要双重确认才判 NG
```

### 3.4 app_config.yaml — 应用配置

```yaml
app:
  title: "铜管表面缺陷模型评测与融合验证工具"
  page_layout: "wide"
  debug: false
  max_preview_images: 100         # 预览最大图片数
  page_size: 50                   # 表格每页行数

inference:
  batch_size: 8                   # 批量推理大小
  num_workers: 2                  # 数据加载线程数
  save_predictions: true          # 是否保存推理结果
  save_visualizations: true       # 是否保存可视化图片
  cache_results: true             # 是否缓存推理结果

display:
  show_confidence: true           # 是否显示置信度
  show_runtime: true              # 是否显示推理耗时
  bbox_line_thickness: 2          # 检测框线宽
  heatmap_alpha: 0.5              # 热力图透明度
  mask_alpha: 0.4                 # 掩码透明度

export:
  excel_include_images: false     # Excel 是否包含图片
  html_include_plots: true        # HTML 是否包含图表
  max_export_images: 200          # 最大导出图片数
```

---

## 4. 模型加载

### 4.1 加载 YOLO 模型

**方式一：使用自己训练的模型**

1. 将 `.pt` 文件放入 `models/yolo/` 目录
2. 在 `configs/models.yaml` 中设置路径：
   ```yaml
   yolo:
     model_path: "models/yolo/copper_defect_yolov8n.pt"
   ```
3. 在界面上拖动 YOLO conf 滑块调整阈值

**方式二：使用 Ultralytics 预训练模型测试流程**

```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # 下载预训练模型
model.save("models/yolo/best.pt")
```

注意：预训练模型使用 COCO 类别名，与铜管缺陷类别不匹配，仅用于验证推理流程。

**YOLO 推理参数说明：**

| 参数 | 说明 | 建议值 |
|------|------|--------|
| `conf_threshold` | 检测置信度阈值 | 0.5-0.7，值越高误报越少但漏检可能增加 |
| `iou_threshold` | NMS 重叠阈值 | 0.4-0.6 |
| `device` | 推理设备 | `auto` 自动选择 CUDA/CPU |

### 4.2 异常检测模型（PatchCore / EfficientAD / FastFlow）

**Mock 模式（默认）**

不需要任何模型文件，自动生成基于图片路径 hash 的确定性随机分数：

```yaml
patchcore:
  enabled: true
  mode: "mock"
```

- 同一张图片每次 mock 推理返回相同分数
- 分数范围 0.1 ~ 0.95
- 可用于验证完整软件流程

**Import 模式**

从已有推理结果 CSV 导入：

```yaml
patchcore:
  enabled: true
  mode: "import"
  result_file: "outputs/cache/patchcore_results.csv"
```

CSV 格式：

```csv
image_path,anomaly_score,heatmap_path,mask_path
data/images/tube_001.jpg,0.23,,
data/images/tube_002.jpg,0.87,outputs/debug/heatmap_002.png,outputs/debug/mask_002.png
```

- `heatmap_path` 和 `mask_path` 可以为空
- `image_path` 需与实际路径匹配

**Real 模式（待实现）**

需要安装 anomalib 并提供模型文件：

```bash
pip install anomalib
```

```yaml
patchcore:
  enabled: true
  mode: "real"
  model_path: "models/patchcore/model.ckpt"
```

当前 real 模式下如果 anomalib 未安装，会自动回退到 mock 模式并给出提示。

### 4.3 OpenCV 规则检测

不需要模型文件，基于传统图像处理：

| 检测类型 | 方法 | 参数 |
|----------|------|------|
| 亮点检测 | 全局阈值 `THRESH_BINARY` | `bright_threshold` (默认 220) |
| 暗点检测 | 全局阈值 `THRESH_BINARY_INV` | `dark_threshold` (默认 35) |
| 划伤检测 | 形态学梯度 + 长宽比过滤 | `scratch_aspect_ratio` (默认 5.0) |
| 局部对比度异常 | 高斯模糊差分 | `local_contrast_threshold` (默认 30) |

OpenCV 输出的候选区域会标记为 `opencv_bright`、`opencv_dark`、`opencv_scratch`、`opencv_anomaly`。

---

## 5. 界面操作指南

### 5.1 左侧 Sidebar

| 区域 | 功能 |
|------|------|
| 📁 数据路径 | 设置图片目录、标注目录、划分文件 |
| 🤖 模型设置 | 启停各模型、调整阈值、选择运行模式 |
| 🔗 融合策略 | 选择 6 种融合策略之一 |
| 📏 阈值参数 | Anomaly 分数阈值、几何阈值、密度阈值 |
| 🔄 加载模型 | 初始化所有启用的模型 |
| 📊 扫描数据集 | 扫描图片目录并解析标注 |
| ⚡ 快捷操作 | 一键批量测试 / 导出报告 |

### 5.2 Tab 1 — 项目说明

显示工具简介、判定逻辑、使用流程、当前配置。

### 5.3 Tab 2 — 数据集概览

- **统计卡片**：总图片数、已标注数、未标注数、标注率
- **类别分布表**：每个类别的样本数量
- **分组统计图**：OK / NG / Borderline 分组柱状图
- **图片列表**：可按 OK / NG / acceptable_micro / borderline / unannotated 筛选

### 5.4 Tab 3 — 单图测试

逐张验证模型效果的核心页面：

1. 从下拉框选择图片
2. 点击"运行推理"
3. 查看：
   - **左侧**：融合结果可视化（原图 + 检测框 + 热力图 + 决策水印）
   - **右侧**：判定结果、推理耗时、标注信息、各模型检测详情
   - **下方**：候选缺陷特征表（面积、长宽比、异常分、形态分类等）

颜色编码：

| 颜色 | 含义 |
|------|------|
| 🟢 绿色框 | YOLO 检测 |
| 🔵 蓝色框 | PatchCore 异常区域 |
| 🟠 橙色框 | Ground truth 标注 |
| 🟣 紫色框 | OpenCV 规则检出 |
| 🟢 绿色横幅 | OK |
| 🟡 黄色横幅 | ACCEPTABLE_MICRO_DEFECT |
| 🟠 橙色横幅 | SUSPECT |
| 🔴 红色横幅 | NG |

### 5.5 Tab 4 — 批量评测

1. 点击"运行批量测试"
2. 进度条显示推理进度
3. 完成后显示：
   - **指标汇总**：OK 误报率、NG 漏检率、微缺陷误报率、未知缺陷召回率、临界缺陷检出率、平均推理时间
   - **结果明细表**：每张图的判定结果，可按 正确/误判/OK/NG/SUSPECT/ACCEPTABLE 筛选
   - **推理耗时统计**：每个模型的平均耗时

### 5.6 Tab 5 — 融合策略对比

1. 点击"运行所有策略对比"
2. 对同一批结果用 6 种策略分别计算指标
3. 输出：
   - **策略对比表**：每种策略的所有工业指标
   - **策略对比图**：分组柱状图直观比较
   - **最优策略推荐**：各指标的最优策略

### 5.7 Tab 6 — 误判样本池

自动分类展示以下误判类型：

| 类型 | 含义 |
|------|------|
| OK 误报 | 真实 OK → 被判 NG 或 SUSPECT |
| NG 漏检 | 真实 NG → 被判 OK 或 ACCEPTABLE |
| 微缺陷误报 | 真实 OK_micro_defect → 被判 NG |
| 未知缺陷漏检 | 真实 NG_unknown → 被判 OK |
| 临界样本 | Borderline 样本（天然边界） |
| YOLO 未识别但异常高分 | YOLO 无检出但 PatchCore 分数高 |
| YOLO 命中但异常低分 | YOLO 检出但 PatchCore 分数低（可能是误检） |

点击错误类型查看对应样本缩略图，帮助分析模型弱点。

### 5.8 Tab 7 — 报告导出

- **Excel 报告**：多 Sheet 工作簿，点击下载
- **可视化图片导出**：批量保存带标注的检测结果图
- **HTML 报告**：自包含网页格式报告

---

## 6. 融合策略详解

### 6.1 策略对比一览

| 策略 | 逻辑 | 优点 | 缺点 |
|------|------|------|------|
| **YOLO Only** | 仅根据 YOLO 检测结果判定 | 速度快，已知缺陷准确 | 对未知缺陷无能为力 |
| **Anomaly Only** | 仅根据异常检测分数判定 | 可发现未知异常 | 容易误报微小可接受缺陷 |
| **YOLO Priority** | YOLO 优先；YOLO 不确定时参考异常检测 | 兼顾已知和未知 | YOLO 误检会影响结果 |
| **Anomaly Priority** | 异常检测优先；YOLO 用于类别确认 | 对未知缺陷敏感 | 微小缺陷可能被放大 |
| **Rule Based** | 综合所有模型 + 几何/密度规则 | 全面、可配置 | 规则需要调优 |
| **Double Confirm** | YOLO 和异常检测同时确认才判 NG | 误报率最低 | 漏检率可能增加 |

### 6.2 Rule Based 融合策略详细规则

**规则 1 — YOLO 已知严重缺陷直接判 NG**

```
IF YOLO 检出 major_defect_classes 中的类别
   AND confidence >= direct_ng_conf_threshold (0.75)
THEN → NG
REASON: "YOLO known major defect: {class_name}"
```

**规则 2 — 长划伤 + 异常确认 → NG**

```
IF 候选缺陷 is_long_scratch_like
   AND length_mm >= ng_scratch_length_mm (2.0mm)
   AND max_anomaly_score >= patchcore_score_threshold (0.65)
THEN → NG
REASON: "Long continuous scratch with anomaly"
```

**规则 3 — 大面积未知异常 → SUSPECT**

```
IF 候选缺陷 area_px >= ng_area_px (200)
   AND max_anomaly_score >= patchcore_score_threshold
   AND YOLO 未检出
THEN → SUSPECT
REASON: "Unknown anomaly - large area, YOLO no detection"
```

**规则 4 — 微小缺陷 → ACCEPTABLE**

```
IF max_anomaly_score >= patchcore_score_threshold
   AND 所有候选缺陷 area_px <= acceptable_micro_area_px (30)
THEN → ACCEPTABLE_MICRO_DEFECT
REASON: "Acceptable micro defect"
```

**规则 5 — 密集微小缺陷 → SUSPECT**

```
IF enable_density_rule
   AND (候选数量 >= max_micro_defect_count_per_meter (50)
        OR 候选总面积 >= max_micro_defect_area_per_meter (500))
THEN → SUSPECT
REASON: "Dense micro defects"
```

**规则 6 — 全部干净 → OK**

```
IF YOLO 无检出 AND max_anomaly_score < threshold
THEN → OK
REASON: "Low anomaly and no defect"
```

### 6.3 策略选择建议

| 场景 | 推荐策略 |
|------|----------|
| 已知缺陷种类齐全，YOLO 训练充分 | YOLO Only 或 YOLO Priority |
| 需要发现未知新缺陷 | Anomaly Priority 或 Rule Based |
| 要求极低误报率 | Double Confirm |
| 研发阶段全面评估 | Rule Based（通过规则调优平衡各项指标） |

---

## 7. 指标说明

### 7.1 工业检测核心指标

| 指标 | 公式 | 含义 | 期望值 |
|------|------|------|--------|
| **OK 误报率** | (OK→NG+SUSPECT) / 总OK数 | 合格品被判为不合格的比例 | < 5% |
| **NG 漏检率** | (NG→OK+ACCEPTABLE) / 总NG数 | 不合格品被判为合格的比例 | < 1% |
| **可接受微缺陷误报率** | (OK_micro→NG) / 总OK_micro数 | 工艺可接受缺陷被判 NG 的比例 | < 10% |
| **未知缺陷召回率** | (NG_unknown→SUSPECT+NG) / 总NG_unknown数 | 未知异常被检出的比例 | > 80% |
| **临界缺陷检出率** | (Borderline→SUSPECT+NG) / 总Borderline数 | 临界样本被关注的比例 | > 90% |
| **平均推理时间** | 总推理时间 / 图片数 | 单张图片平均处理耗时 | < 100ms |

### 7.2 关键业务理解

- **OK 误报率**和 **NG 漏检率**是最重要的两个指标
- **可接受微缺陷误报率**衡量模型是否过度敏感
- **未知缺陷召回率**衡量模型对未见过的缺陷类型的泛化能力
- 这四个指标之间存在 trade-off，需要根据产线要求平衡

### 7.3 指标计算前提

- 上述指标计算**依赖标注数据**
- 未标注图片不参与指标计算（但仍参与推理和可视化）
- 指标在"批量评测"Tab 中自动计算
- "融合策略对比"Tab 可以对同一批数据用不同策略计算指标

---

## 8. 报告导出

### 8.1 Excel 报告

报告文件保存在 `outputs/reports/` 目录。

**Sheet 结构：**

| Sheet | 内容 | 说明 |
|-------|------|------|
| **Summary** | 总体指标 | 总图像数、OK误报率、NG漏检率、未知召回率、平均推理时间等 |
| **Image Results** | 逐图结果 | 每张图的真实标签、各模型结果、融合策略、最终判定、原因、是否正确 |
| **Defect Candidates** | 候选缺陷 | 每个候选缺陷的特征：来源模型、类别、面积、长宽比、异常分等 |
| **Misclassified Samples** | 误判样本 | 所有误判图片及其错误类型、真实标签和判定结果 |
| **Strategy Comparison** | 策略对比 | 6 种策略的指标对比（如果在界面中运行过策略对比） |

### 8.2 可视化图片导出

保存在 `outputs/visualizations/export/` 目录。

每张图片包含：
- 原图
- 异常热力图叠加
- YOLO 检测框
- OpenCV 规则检出框
- 最终判定水印

### 8.3 HTML 报告

自包含的 HTML 文件，可在浏览器中直接打开。包含指标卡片和结果表格。

---

## 9. 扩展开发

### 9.1 添加新的模型 Runner

1. 在 `src/inference/` 下创建新文件，如 `my_model_runner.py`

2. 继承 `BaseRunner`：

```python
from src.inference.base_runner import BaseRunner
from src.fusion.decision_types import UnifiedPrediction, BBoxPrediction, AnomalyResult

class MyModelRunner(BaseRunner):
    def __init__(self, config=None):
        super().__init__("my_model", config)

    def load_model(self):
        # 加载模型
        self._is_loaded = True

    def predict(self, image_path):
        import time
        t0 = time.perf_counter()

        # === 推理逻辑 ===
        predictions = []  # list of BBoxPrediction
        anomaly = AnomalyResult(image_score=0.0)

        elapsed = (time.perf_counter() - t0) * 1000
        return UnifiedPrediction(
            image_path=str(image_path),
            model_name="my_model",
            predictions=predictions,
            anomaly=anomaly,
            runtime_ms=elapsed,
        )
```

3. 在 `configs/models.yaml` 中添加配置段
4. 在 `app.py` 的 `load_all_runners()` 函数中添加加载逻辑

### 9.2 添加新的融合策略

1. 在 `src/fusion/decision_types.py` 的 `FusionStrategy` 枚举中添加：

```python
class FusionStrategy(str, Enum):
    # ...existing...
    MY_STRATEGY = "my_strategy"
```

2. 在 `src/fusion/rule_engine.py` 的 `decide()` 方法中添加分支：

```python
elif strategy == FusionStrategy.MY_STRATEGY:
    return self._decide_my_strategy(image_path, ...)
```

3. 实现 `_decide_my_strategy()` 方法，返回 `FusionDecision`

4. 在 `src/fusion/fusion_strategies.py` 中注册名称和描述

### 9.3 添加新的缺陷类别

1. 在 `configs/dataset.yaml` 的 `classes` 中添加新的 class_id
2. 在 `src/dataset/label_schema.py` 中更新：
   - `DefectClass` 枚举
   - `CLASS_ID_MAP`
   - 相应的类别集合（`OK_CLASSES` / `NG_CLASSES` / `ACCEPTABLE_MICRO_CLASSES` 等）
3. 在 `configs/fusion_rules.yaml` 的 `major_defect_classes` 中决定是否加入

---

## 10. 常见问题

### Q: 没有 YOLO 模型文件能运行吗？

可以。OpenCV 规则检测不需要模型文件。PatchCore/EfficientAD/FastFlow 使用 mock 模式。界面和所有功能都可以正常工作。

### Q: 没有 anomalib 能用吗？

可以。默认 mock 模式。如需真实推理，先 `pip install anomalib`，然后将模式改为 `real`。

### Q: 没有标注数据能用吗？

可以推理和可视化，但不参与监督指标计算。标注是可选的。

### Q: 如何调整误报率和漏检率的平衡？

- 提高 `conf_threshold` / `anomaly_score_threshold` → 降低误报率，可能增加漏检率
- 降低阈值 → 降低漏检率，可能增加误报率
- 使用 `Double Confirm` 策略 → 最大程度降低误报率
- 调整几何阈值（`acceptable_micro_area_px`、`ng_scratch_length_mm`）→ 细粒度控制

### Q: Mock 模式的随机分数稳定吗？

稳定。Mock 分数基于图片路径的 hash 生成，同一张图片每次推理返回相同分数。

### Q: 支持 GPU 推理吗？

YOLO 自动检测 CUDA 设备。设置 `device: "auto"` 或 `device: "cuda:0"`。

### Q: 大型数据集（10000+ 图片）会卡吗？

批量推理时逐张处理，不会一次性加载所有图片到内存。但 Streamlit 界面在处理大量结果时可能会有性能瓶颈，建议分批处理。

### Q: OpenCV 规则检测效果如何？

这是基础的传统视觉方法，用于辅助、不是主力检测器。它的作用是：
- 在没有 YOLO 模型时提供一个 baseline
- 捕捉一些 YOLO 可能漏掉的规律性缺陷
- 作为融合策略中的补充信号

### Q: 如何备份评测结果？

- `outputs/reports/` — Excel 报告
- `outputs/visualizations/export/` — 可视化图片
- `outputs/cache/` — 推理结果缓存（如果有保存）

建议定期备份 `outputs/` 目录。

### Q: 工具能在产线上直接使用吗？

不推荐。这是研发评估工具，设计目标是：
- 快速比较不同模型和策略
- 辅助确定技术路线
- 分析误判模式

产线部署需要额外的：实时性优化、稳定性保障、异常处理、日志系统、与 PLC/MES 集成等。
