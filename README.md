# CX-vision — 工业视觉在线检测系统

Copper Tube Surface Defect Online Inspection System — V6 桌面版

## 项目简介

CX-vision 是面向铜管（及其他金属材料）表面缺陷检测的工业视觉系统，基于 PySide6 桌面应用框架。

**V6 定位**：现场试运行版 / 工程化交付版。支持项目管理、多相机实时采集、YOLO 训练推理、缺陷追溯、日志中心、配置备份恢复。

## 系统架构

```
copper-defect-eval-tool/
├── main.py                 # 桌面应用入口
├── core/                   # 数据模型 + CRUD（纯 Python，无 Qt 依赖）
│   ├── customer.py / project.py / product_spec.py
│   ├── capture_session.py / model_version.py
│   ├── camera_config.py / dataset_version.py
│   ├── production_event.py / sampling_controller.py
│   ├── log_manager.py / config_backup.py
│   └── storage.py          # SQLite 数据库层 + 迁移
├── runtime/                # 采集 / 推理 / 编码器运行时
│   ├── acquisition_pipeline.py
│   ├── inference_pipeline.py
│   ├── frame_buffer.py
│   ├── encoder_reader.py
│   └── health_monitor.py
├── camera_adapters/        # 相机适配器（FolderWatcher / Hikvision / Basler）
├── trainers/               # 训练器（YOLO / PatchCore / Hybrid）
├── model_runners/          # 模型推理器
├── desktop_app/            # PySide6 桌面 UI
│   ├── main_window.py      # 主窗口 + 导航
│   ├── pages/              # 10 个功能页面
│   ├── dialogs/            # 对话框
│   ├── workers/            # QThread 后台任务
│   ├── widgets/            # 可复用组件
│   └── i18n.py             # 中英文国际化
├── config/                 # 运行时配置
├── data/                   # SQLite 数据库
├── tests/                  # pytest 测试（核心层约 200 个）
└── packaging/              # 打包脚本
```

## V6 功能列表

| 模块 | 功能 |
|------|------|
| 项目中心 | 客户 / 项目 / 产品规格 CRUD |
| 现场数据 | 采集会话 + 样本分类 + 数据集版本管理 |
| 训练中心 | 训练配置 + 训练任务 + 模型版本（激活/回滚守卫） |
| 验证中心 | 模型推理 + 评估报告 + 模型对比 |
| 生产运行 | 多相机实时检测 + 编码器位置追踪 + 5 种采样模式 |
| 设备配置 | 相机配置（动态 N 路）+ PLC 配置 + 编码器配置 |
| 报告中心 | 多格式导出（Markdown / HTML / PDF / CSV / JSON） |
| 缺陷追溯 | 采集样本查询 + 生产缺陷事件查询 + 位置分布直方图 |
| 日志中心 | 6 类日志（应用/相机/推理/系统/错误/审计）+ 级别过滤 |
| 备份恢复 | 创建/恢复/删除备份（DB + 配置 + 模型） |
| 系统设置 | 语言切换、目录配置、系统健康 |

### 采样模式

- **连续采集** — 目录监听，每帧都处理
- **按时间** — 固定时间间隔采集
- **按距离** — 固定距离间隔采集（需编码器）
- **疑似异常** — 异常检测触发（V7 路线图）
- **手动触发** — 手动按钮抓图

### 模型管理

- 注册模型版本（YOLO / ONNX / PatchCore）
- 模型状态流转（created → training → completed → evaluated → verified → candidate → active → rolled_back → archived）
- 上线唯一性守卫：同一项目同时只有一个 active 模型
- 回滚功能

## 环境安装

```bash
cd copper-defect-eval-tool
pip install -r requirements.txt
```

核心依赖：
- Python 3.12+
- PySide6 — Qt 桌面框架
- ultralytics — YOLO 训练/推理
- opencv-python — 图像处理
- numpy — 数值计算

可选依赖：
- fpdf2 — PDF 报告导出
- openpyxl — Excel 报告导出
- anomalib — PatchCore 训练（V7）
- pypylon / MVS SDK — 工业相机（V7）

## 运行命令

```bash
# 桌面应用
python main.py

# 运行测试
pytest tests/ -q

# 打包（需要 .venv 中安装 PyInstaller）
packaging\build_windows.bat
```

## 国际化

界面支持中文 / English 实时切换，无需重启。语言偏好保存在 `config/language.json`。

添加新翻译键在 `desktop_app/i18n.py` 的 `_STRINGS` 字典中，使用 `tr("key")` 和 `bind(widget, "key")` 进行绑定。

## 数据库

SQLite 单文件数据库 `data/app.db`，通过 `core/storage.py` 访问。V6 使用迁移函数 `migrate_v6()` 增量添加列，向后兼容。

## 测试

```bash
pytest tests/ -q                     # 全部核心测试
pytest tests/test_sampling_controller.py -v  # 特定模块
```

核心层测试不依赖 PySide6，可在无 GUI 环境运行。

## V7 路线图

- [ ] HybridTrainer 完整实现（YOLO + PatchCore 复合训练）
- [ ] PatchCore 完整训练（anomalib 集成 + coreset 构建）
- [ ] RS422 编码器实机对接
- [ ] 海康 MVS / Basler Pylon 工业相机实机驱动
- [ ] 实时 PLC 通讯（Modbus TCP）
- [ ] 疑似异常采样策略
- [ ] GPU 推理加速（CUDA / TensorRT）
- [ ] Web 远程监控面板

## 许可

内部研发工具，未公开发布。
