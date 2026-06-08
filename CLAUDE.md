# copper-defect-eval-tool — AI 辅助开发入口

工业视觉在线检测系统，PySide6 桌面应用 + Streamlit 辅助模块。铜管表面缺陷检测评估。

## 目录结构

```
core/           ← 数据模型 + 存储(CRUD/SQLite) + 评估指标，无 Qt 依赖
src/            ← 推理管线 / 融合引擎 / 后处理 / 可视化 / 报告
desktop_app/    ← PySide6 桌面应用（pages/dialogs/widgets/workers）
runtime/        ← 采集 / 推理 / 编码器运行时
camera_adapters/ ← 相机适配层（海康 MVS/巴斯勒/文件夹监视）
model_runners/  ← 模型推理器（YOLO/ONNX/PatchCore/EfficientAD/FastFlow/TensorRT）
trainers/       ← 训练器（YOLO/PatchCore/Hybrid）
ui/             ← Streamlit 辅助可视化模块
integration/    ← 外部集成（TCP/HTTP）
benchmark/      ← 压测框架
retrieval/      ← 图像检索（embeddings + FAISS）
tests/          ← pytest，1058 个测试
```

## 构建与测试

```bash
uv sync --dev                    # 安装依赖
pytest tests/ -x                 # 运行测试（跳过 device 硬件测试）
pytest tests/ --cov=core         # 覆盖率
ruff check                       # linting
mypy core/                       # 类型检查
bandit -r core/                  # 安全扫描
python main.py                   # 启动桌面应用
```

## 关键约定

- **数据模型**：`core/schema.py`（DetectionBox/ImagePrediction）和 `src/fusion/decision_types.py`（BBoxPrediction/UnifiedPrediction/DefectCandidate）是两套并行的检测框模型。区别说明见 `docs/architecture.md`。
- **异常体系**：`core/exceptions.py` 定义 `CopperVisionError` 层级。新代码请捕获具体异常类型，不用 `except Exception: pass`。
- **存储**：`core/storage.py` 提供 SQLite CRUD + 迁移。通过 `COPPER_VISION_DB_PATH` 环境变量指定数据库路径。
- **测试**：共享 fixtures 在 `tests/conftest.py`。数据库测试用 `setup_db`（autouse）创建临时 DB。工厂函数 `make_detection_box()` 替代各文件中的 `_box()`。
- **类型标注**：`pyproject.toml` 中有 mypy 配置（宽松模式）。新函数必须加完整类型标注。
- **Python 3.12+** + **uv** 包管理。配置文件唯一入口：`pyproject.toml`。

## 当前技术债务

详见审查报告 Top 10 问题列表。主要关注点：
- core/ 和 src/ 的架构分叉（双检测框模型）
- 三套并行的融合引擎
- 测试缺少共享 fixtures

## 红线

- 不修改 `.env`、密钥、token
- 不执行 `git push`、`git rebase --hard`
- 删除文件前先确认
