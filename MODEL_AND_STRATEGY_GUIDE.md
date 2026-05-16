# 模型方法、融合策略与使用说明

> 适用场景：铜管表面缺陷模型研发评测、规则验证、误判分析与报告导出。

本文说明本工具支持的几类检测方法、各自优劣势、融合策略含义，以及推荐使用流程。它不是最终产线方案说明，而是研发阶段的评测和验证指南。

---

## 1. 总体思路

本工具把每张图片的检测信息统一成两类结果：

- **目标检测结果**：例如 YOLO 输出的缺陷框、类别、置信度。
- **异常检测结果**：例如 PatchCore / EfficientAD / FastFlow 输出的整图异常分数、热力图、异常区域 mask。

随后融合引擎根据模型结果、几何特征和规则阈值给出最终判定：

- `OK`：未发现明显异常。
- `ACCEPTABLE_MICRO_DEFECT`：可接受微缺陷。
- `SUSPECT`：可疑，需要复核。
- `NG`：不合格。

建议把本工具当作“实验台”使用：先分别观察每种方法的表现，再用融合策略验证业务规则是否符合质量目标。

---

## 2. 方法一：YOLO 目标检测

### 2.1 方法说明

YOLO 是监督式目标检测模型。它需要带框标注的数据训练，推理时输出缺陷框、类别和置信度。

本项目默认配置：

```yaml
yolo:
  enabled: true
  model_path: "models/yolo/best.pt"
  conf_threshold: 0.6
  iou_threshold: 0.5
  device: "auto"
```

`device: "auto"` 会自动选择 CUDA；如果没有 GPU，会回退到 CPU。

### 2.2 优势

- **类别明确**：能直接输出 `NG_scratch`、`NG_pit`、`NG_dent` 等类别。
- **定位直观**：检测框适合可视化和人工复核。
- **推理速度快**：适合实时或准实时场景。
- **指标解释性强**：可以按类别统计召回、误报和漏检。

### 2.3 劣势

- **依赖标注数据**：需要足够多且质量稳定的框标注。
- **未知缺陷能力弱**：训练集中没见过的缺陷可能漏检。
- **对边界样本敏感**：轻微划伤、油污、反光等容易受阈值影响。
- **类别定义会影响结果**：如果标注标准不一致，模型会学到混乱边界。

### 2.4 适用场景

- 已知缺陷类型明确。
- 有历史标注数据。
- 需要输出缺陷类别和位置。
- 重点关注 NG 类缺陷召回。

### 2.5 使用方法

1. 将 YOLO 权重放到 `models/yolo/best.pt`。
2. 在左侧 sidebar 勾选 **启用 YOLO**。
3. 设置 YOLO 模型路径和 `conf` 阈值。
4. 点击 **加载模型**。
5. 在 **单图测试** 或 **批量评测** 中运行推理。

### 2.6 调参建议

- 漏检多：降低 `YOLO conf 阈值`，例如从 `0.6` 调到 `0.4`。
- 误报多：提高 `YOLO conf 阈值`，例如从 `0.6` 调到 `0.75`。
- 框太密：适当提高 NMS IOU 或在训练阶段优化数据。

---

## 3. 方法二：OpenCV 规则检测

### 3.1 方法说明

OpenCV 规则检测不依赖训练模型，主要基于亮点、暗点、局部对比度、形态学和轮廓特征寻找异常区域。

配置示例：

```yaml
opencv:
  enabled: true
  bright_threshold: 220
  dark_threshold: 35
  min_area_px: 8
  max_area_px: 5000
  scratch_aspect_ratio: 5.0
  local_contrast_threshold: 30
  morphology_kernel_size: 3
```

### 3.2 优势

- **无需训练数据**：没有模型也能启动基础检测。
- **解释性强**：每条规则和阈值都能对应到图像特征。
- **部署简单**：依赖少，推理成本低。
- **适合 baseline**：可以快速验证图像质量和缺陷显著性。

### 3.3 劣势

- **泛化能力有限**：光照、反光、背景纹理变化会显著影响结果。
- **阈值维护成本高**：换产线、相机、曝光后可能需要重新调参。
- **复杂缺陷识别弱**：难以稳定区分油污、划伤、反光和纹理。
- **类别能力弱**：通常只能给出规则类别，不如 YOLO 精细。

### 3.4 适用场景

- 没有足够训练数据。
- 需要快速建立可运行 baseline。
- 图像采集条件稳定。
- 希望用规则辅助深度模型复核。

### 3.5 使用方法

1. 左侧 sidebar 勾选 **启用 OpenCV 规则检测**。
2. 根据图片亮度和缺陷形态调整阈值。
3. 点击 **加载模型**。
4. 运行单图或批量评测。

### 3.6 调参建议

- 亮斑误报多：提高 `bright_threshold` 或提高 `min_area_px`。
- 暗坑漏检多：提高 `dark_threshold`，让更多暗区域进入候选。
- 划伤漏检多：降低 `scratch_aspect_ratio` 或 `local_contrast_threshold`。
- 噪声太多：提高 `min_area_px`，增大 `morphology_kernel_size`。

---

## 4. 方法三：PatchCore 异常检测

### 4.1 方法说明

PatchCore 是无监督/少监督异常检测方法。典型训练方式是只使用 OK 样本，建立正常特征库；推理时判断新图像是否偏离正常分布。

本项目已安装 anomalib，并缓存了原生骨干依赖。但 **还没有铜管训练后的 `model.ckpt`**。

### 4.2 优势

- **适合未知缺陷**：不需要提前穷举所有 NG 类型。
- **只需 OK 样本训练**：在 NG 样本少时尤其有价值。
- **热力图友好**：可以辅助定位异常区域。
- **工业异常检测常用 baseline**。

### 4.3 劣势

- **依赖 OK 样本质量**：OK 样本混入异常会污染正常库。
- **类别能力弱**：通常只能说“异常”，不能稳定说是哪一类缺陷。
- **对采集分布敏感**：相机、光照、材质变化会影响异常分数。
- **模型体积和内存可能较大**：特征库越大，推理资源越高。

### 4.4 适用场景

- 想发现训练集中没有见过的异常。
- NG 样本稀缺，但 OK 样本较多。
- 目标是降低未知缺陷漏检。

### 4.5 使用方法

当前推荐先准备训练数据：

```text
data/anomaly_train/ok/
  ok_001.jpg
  ok_002.jpg
  ...
```

训练完成后导出：

```text
models/patchcore/model.ckpt
```

然后将配置切为：

```yaml
patchcore:
  enabled: true
  mode: "real"
  model_path: "models/patchcore/model.ckpt"
```

如果已有外部推理结果，可使用 `import` 模式。

---

## 5. 方法四：EfficientAD 异常检测

### 5.1 方法说明

EfficientAD 是高效异常检测方法，通常通过 teacher-student 或相关结构学习正常样本分布。它适合做较快的异常检测 baseline。

本项目已安装 anomalib，原生模型可实例化；但同样需要铜管 OK 样本训练后才有业务意义。

### 5.2 优势

- **推理效率较好**：适合对速度敏感的场景。
- **适合 OK-only 训练**。
- **能输出异常分数和异常图**。

### 5.3 劣势

- **仍需目标域训练**：不能直接把公开示例权重用于铜管结论。
- **对训练分布敏感**。
- **类别解释不如 YOLO**。
- **训练配置比 OpenCV/YOLO 推理更复杂**。

### 5.4 适用场景

- 想做快速异常检测。
- 需要比 PatchCore 更轻的异常模型候选。
- 后续准备比较多种 anomaly 方法。

### 5.5 使用方法

1. 准备 `data/anomaly_train/ok/`。
2. 训练并导出 `models/efficientad/model.ckpt`。
3. 将配置切到：

```yaml
efficientad:
  enabled: true
  mode: "real"
  model_path: "models/efficientad/model.ckpt"
```

---

## 6. 方法五：FastFlow 异常检测

### 6.1 方法说明

FastFlow 基于 normalizing flow 做异常检测，常用于图像异常定位与分数估计。

本项目已缓存 FastFlow 默认 `resnet18` 骨干，可用于后续训练。

### 6.2 优势

- **能建模正常特征分布**。
- **异常定位能力较好**。
- **适合作为 PatchCore/EfficientAD 的对比模型**。

### 6.3 劣势

- **训练和调参成本较高**。
- **对 OK 样本分布敏感**。
- **推理分数需要重新标定阈值**。
- **类别解释能力弱**。

### 6.4 适用场景

- 想比较不同异常检测算法。
- 需要热力图或异常区域辅助复核。
- 有稳定 OK 样本用于训练。

### 6.5 使用方法

训练后导出：

```text
models/fastflow/model.ckpt
```

配置：

```yaml
fastflow:
  enabled: true
  mode: "real"
  model_path: "models/fastflow/model.ckpt"
```

---

## 7. import 与 mock 模式

### 7.1 import 模式

`import` 模式用于导入外部算法或离线批处理结果。CSV 格式：

```csv
image_path,anomaly_score,heatmap_path,mask_path
data/images/sample_001.jpg,0.23,,
data/images/sample_002.jpg,0.87,,
```

优势：

- 不需要在本工具中接入真实模型。
- 适合已有离线推理流水线。
- 便于快速比较不同算法分数。

劣势：

- 不能实时推理新图片。
- CSV 路径必须和项目图片路径匹配。
- 热力图和 mask 需要额外维护。

### 7.2 mock 模式

`mock` 模式基于图片路径生成稳定伪随机异常分数，只用于验证流程。

优势：

- 无模型也能测试 UI、报告、策略对比。
- 同一图片分数稳定，方便复现。

劣势：

- 没有任何检测意义。
- 不能用于判断模型效果。
- 不能用于真实质量结论。

---

## 8. 融合策略详解

### 8.1 YOLO Only

只使用 YOLO 检测结果。

判定逻辑概括：

- 无 YOLO 检出：`OK`
- 高置信严重缺陷：`NG`
- 有普通检出但未达直接 NG：`SUSPECT`

优点：

- 简单直接，容易解释。
- 适合验证 YOLO 单模型效果。
- 类别和位置清楚。

缺点：

- 不能发现 YOLO 未学过的未知异常。
- 对标注质量和训练集覆盖依赖强。
- 对微弱缺陷和反光边界样本可能不稳定。

推荐用途：

- YOLO 模型验收。
- 查看类别检测能力。
- 与其他策略做 baseline 对比。

---

### 8.2 Anomaly Only

只使用 PatchCore / EfficientAD / FastFlow 的异常分数。

判定逻辑概括：

- 异常分数低：`OK`
- 异常分数高：`SUSPECT`
- 极高未知异常分数：仍以 `SUSPECT` 为主，等待复核。

优点：

- 能发现未知异常。
- 不依赖 NG 类别标注。
- 适合 OK-only 训练模型评估。

缺点：

- 不直接给出缺陷类别。
- 阈值需要用铜管数据标定。
- 容易受光照、纹理、采集差异影响。

推荐用途：

- 验证异常检测模型是否能发现偏离 OK 的样本。
- 评估未知缺陷召回能力。

---

### 8.3 YOLO Priority

YOLO 优先，异常检测用于补充确认。

判定逻辑概括：

- YOLO 高置信严重缺陷：`NG`
- YOLO 有缺陷且异常分数高：`NG`
- YOLO 有缺陷但异常分数低：`SUSPECT`
- YOLO 干净但异常很高：`SUSPECT`
- YOLO 干净且异常低：`OK`

优点：

- 保留 YOLO 的类别解释能力。
- 异常检测可以补充未知缺陷。
- 适合以已知缺陷为主的产线。

缺点：

- YOLO 偏差仍会主导结果。
- 异常阈值不准时会影响复核量。
- 对未知缺陷通常更偏向 `SUSPECT`，需要人工闭环。

推荐用途：

- YOLO 已经比较成熟，但希望增加未知异常兜底。

---

### 8.4 Anomaly Priority

异常检测优先，YOLO 用于类别确认。

判定逻辑概括：

- 异常分数极高且 YOLO 也命中：`NG`
- 异常分数极高但 YOLO 未命中：`SUSPECT`
- 异常分数中高：`SUSPECT`
- 异常低但 YOLO 命中：`SUSPECT`
- 两者都干净：`OK`

优点：

- 对未知异常更敏感。
- 适合 NG 类别不完整或持续出现新缺陷的阶段。
- YOLO 可用于解释异常来源。

缺点：

- 如果异常模型未训练好，误报会明显增加。
- 很少直接给出强类别结论。
- 需要较好的 OK 样本覆盖。

推荐用途：

- 研发早期、未知缺陷多、宁可多复核也不想漏检。

---

### 8.5 Double Confirm

YOLO 和异常检测都确认时才判 `NG`，只有一方触发则判 `SUSPECT`。

判定逻辑概括：

- YOLO 命中且异常分数高：`NG`
- 只有 YOLO 或只有异常触发：`SUSPECT`
- 都未触发：`OK`

优点：

- 能降低单模型误报导致的直接 NG。
- 适合对误杀 OK 很敏感的场景。
- 单方异常会进入复核池，不会直接放行。

缺点：

- 可能降低直接 NG 的召回。
- 两个模型如果都漏同一类缺陷，仍会漏检。
- 对人工复核流程有依赖。

推荐用途：

- 产能损失敏感，OK 误报代价高。
- 希望先建立稳健保守的自动判定。

---

### 8.6 Rule Based Fusion

综合 YOLO、异常分数、OpenCV 候选、几何特征和密度规则。

主要规则包括：

- YOLO 高置信严重缺陷直接判 `NG`。
- 长连续划伤且异常分数高判 `NG`。
- 大面积未知异常判 `SUSPECT`。
- 小面积异常可判 `ACCEPTABLE_MICRO_DEFECT`。
- 密集微缺陷超阈值判 `SUSPECT`。
- YOLO 命中但异常低判 `SUSPECT`。
- 全部干净判 `OK`。

优点：

- 最贴近工业质检规则。
- 可以同时利用类别、异常、面积、长度、密度。
- 适合做策略验证和阈值实验。

缺点：

- 规则较多，调参成本更高。
- 需要像素尺寸和阈值定义准确。
- 如果候选生成质量差，几何规则会受影响。

推荐用途：

- 默认推荐策略。
- 需要把质量工程经验编码成可验证规则。
- 需要输出误判样本池和报告。

---

## 9. 推荐策略选择

| 阶段 | 推荐方法 | 推荐融合策略 | 目标 |
|------|----------|--------------|------|
| 无模型早期 | OpenCV + mock | Rule Based / Double Confirm | 验证流程和报告 |
| YOLO 初版 | YOLO + OpenCV | YOLO Only / Rule Based | 看已知缺陷检测效果 |
| 有 OK 样本 | PatchCore / EfficientAD / FastFlow | Anomaly Only / Anomaly Priority | 评估未知异常召回 |
| YOLO 较成熟 | YOLO + anomaly | YOLO Priority / Rule Based | 已知缺陷为主，异常兜底 |
| 误报代价高 | YOLO + anomaly | Double Confirm | 降低直接 NG 误判 |
| 研发综合评估 | 全部启用 | Rule Based Fusion | 综合指标和误判分析 |

---

## 10. 推荐使用流程

### 10.1 快速流程验证

1. 启动应用：

```bash
streamlit run app.py
```

2. 左侧勾选 OpenCV，异常检测保持 mock。
3. 点击 **扫描数据集**。
4. 点击 **加载模型**。
5. 运行 **单图测试**。
6. 运行 **批量评测**。
7. 导出 Excel 报告。

### 10.2 YOLO 评估流程

1. 放入 YOLO 权重：

```text
models/yolo/best.pt
```

2. 勾选 **启用 YOLO**。
3. `device` 使用 `auto`，无 GPU 会自动使用 CPU。
4. 选择 `YOLO Only` 先看单模型效果。
5. 再切到 `Rule Based Fusion` 看规则融合效果。
6. 在 **误判样本池** 中检查漏检和误报。

### 10.3 异常检测训练前准备

1. 收集稳定 OK 样本：

```text
data/anomaly_train/ok/
```

2. 确保样本覆盖不同批次、光照、正常纹理和轻微可接受变化。
3. 不要把明显 NG 样本混入 OK 训练集。
4. 训练后导出 checkpoint 到 `models/<model>/model.ckpt`。
5. 将对应模型从 `mock` 切到 `real`。

### 10.4 import 模式评估流程

1. 将外部推理 CSV 放到：

```text
outputs/cache/patchcore_results.csv
```

2. 配置：

```yaml
patchcore:
  enabled: true
  mode: "import"
  result_file: "outputs/cache/patchcore_results.csv"
```

3. 点击 **加载模型**。
4. 运行批量评测和策略对比。

---

## 11. 阈值调参建议

| 问题 | 优先调整项 |
|------|------------|
| NG 漏检多 | 降低 YOLO conf、降低 anomaly threshold、使用 Anomaly Priority |
| OK 误报多 | 提高 YOLO conf、提高 anomaly threshold、使用 Double Confirm |
| 微缺陷误判 NG | 增大 `acceptable_micro_area_px` 或降低直接 NG 阈值敏感度 |
| 长划伤漏检 | 降低 `ng_scratch_length_mm` 或 `scratch_aspect_ratio` |
| 噪点太多 | 提高 `min_defect_area_px`，增大形态学核 |
| 未知缺陷漏检 | 训练 anomaly 模型，并使用 Anomaly Priority / Rule Based |

---

## 12. 注意事项

- `mock` 只能验证流程，不能代表模型效果。
- public MVTec 示例权重不能直接作为铜管检测结论。
- 异常检测模型需要用铜管 OK 样本训练。
- 标注质量直接决定 YOLO 评估可信度。
- 像素尺寸 `pixel_size_mm` 会影响长度和面积规则。
- 每次调整策略或阈值后，建议重新导出报告并保存版本。
