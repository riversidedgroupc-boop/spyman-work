# Phase 4 C++ Runtime Migration — 变更分组审计

**审计日期**: 2026-06-05
**分支**: 当前工作区（含 Phase 3/4 + 前期业务重构）
**变更规模**: 131 文件，+7159 / -3821 行

---

## 分类说明

| 标记 | 含义 |
|------|------|
| ✅ 应提交 | C++ runtime Phase 3/4 核心变更 |
| ⚡ 应提交 | 前期业务重构（独立于 C++ runtime） |
| ❌ 不应提交 | 本地配置、构建产物、缓存 |
| ⚠️ 需确认 | 需要用户判断归属 |

---

## A. C++ Runtime Phase 3/4 必须保留（✅ 应提交）

### A1. C++ 源码与构建

| 文件 | 状态 | 说明 |
|------|------|------|
| `cpp_runtime/CMakeLists.txt` | new | CMake 构建配置 |
| `cpp_runtime/src/main.cpp` | new | 入口文件（one-shot CLI） |
| `cpp_runtime/src/runtime_contracts.cpp` | new | JSON 解析器 + config 验证 |
| `cpp_runtime/include/cx_vision/runtime_contracts.hpp` | new | 头文件（`cx_vision` 命名空间） |

### A2. Python Runtime Contract 层

| 文件 | 状态 | 说明 |
|------|------|------|
| `core/runtime_contracts.py` | new | Pydantic v2 RuntimeConfig/RuntimeStatus/CameraRuntimeConfig |
| `core/runtime_mode.py` | new | RuntimeMode enum + 模式辅助函数 |
| `runtime/runtime_backend.py` | new | Protocol-based RuntimeBackend + create_backend() 工厂 |
| `runtime/cpp_runtime_client.py` | new | CppRuntimeProcessBackend（subprocess 驱动） |
| `runtime/fake_cpp_runtime.py` | new | FakeCppRuntimeBackend（测试用） |

### A3. UI 改造（外部 runtime 模式隔离）

| 文件 | 状态 | 说明 |
|------|------|------|
| `desktop_app/pages/production_run_page.py` | M | 核心修改：`_uses_external_runtime_backend()`、`_build_runtime_config()`、外部模式早期返回、`_refresh_external_runtime_display()`、stop 跳过 Python pipeline |

### A4. config_backup 修复

| 文件 | 状态 | 说明 |
|------|------|------|
| `core/config_backup.py` | M | `restore_backup()` 增加 `restore_root` 参数；`_safe_restore_target` 返回值修复；`_audit` 精确异常捕获 |

### A5. 测试

| 文件 | 状态 | 说明 |
|------|------|------|
| `tests/test_production_runtime_modes.py` | new | 28 tests：外部模式隔离、Python 模式、backend 选择 |
| `tests/test_cpp_runtime_config_cli.py` | new | 15 tests：C++ exe CLI JSON 解析、类型验证（需可执行 exe） |
| `tests/test_cpp_runtime_client.py` | new | CppRuntimeProcessBackend 单元测试 |
| `tests/test_runtime_backend.py` | new | create_backend() 工厂 + backend 协议测试 |
| `tests/test_runtime_contracts.py` | new | Pydantic 模型序列化/反序列化 |
| `tests/test_fake_cpp_runtime.py` | new | FakeCppRuntimeBackend 行为验证 |
| `tests/test_cpp_runtime_package.py` | new | 打包脚本存在性验证 |
| `tests/test_config_backup.py` | M | `test_restore_backup` 适配 `restore_root` |
| `tests/test_config_backup_full.py` | M | `_audit` monkeypatch 防止写真实 audit.log |
| `tests/test_defect_trace_upgrade.py` | M | `tmp_output` fixture + `output_root` 隔离 |

### A6. 文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `docs/cpp_runtime_contract.md` | new | 合同文档：协议、命令、状态结构、配置 schema |
| `docs/cpp_platform_integration.md` | new | 平台集成：构建、打包、部署 |
| `docs/superpowers/plans/2026-06-03-cpp-runtime-migration.md` | new | Phase 1 计划 |
| `docs/superpowers/plans/2026-06-03-cpp-runtime-migration-zh.md` | new | Phase 1 计划（中文） |
| `docs/superpowers/plans/2026-06-03-cpp-runtime-phase2-multiagent-zh.md` | new | Phase 2 计划 |
| `docs/superpowers/plans/2026-06-04-cpp-runtime-phase3-multiagent-zh.md` | new | Phase 3 计划 |
| `docs/superpowers/plans/2026-06-04-cpp-runtime-phase4-multiagent-zh.md` | new | Phase 4 计划 |

### A7. 打包

| 文件 | 状态 | 说明 |
|------|------|------|
| `packaging/cpp_runtime_package.ps1` | new | PowerShell 打包脚本 |

### A8. 依赖

| 文件 | 状态 | 说明 |
|------|------|------|
| `pyproject.toml` | M | `pydantic>=2.0.0`、`qt-material`、`qtawesome`、ruff/mypy/bandit 配置 |
| `.gitignore` | M | 添加 `cpp_runtime/build/`、`dist/`、`focus_runs/` |

---

## B. 前期业务重构（⚡ 应提交，独立于 C++ runtime）

这些变更在 C++ runtime 之前就存在，涉及项目管理、UI 重构、工作流改动。

### B1. 核心数据模型

| 文件 | 状态 | 说明 |
|------|------|------|
| `core/customer.py` | M | 客户模型扩展 |
| `core/project.py` | M | 项目模型扩展（级联删除） |
| `core/product_spec.py` | M | 规格模型扩展 |
| `core/storage.py` | M | Schema 迁移 |
| `core/project_cascade.py` | new | 级联删除逻辑 |
| `core/project_workflow.py` | new | 项目工作流状态机 |
| `core/sample_library.py` | new | 样本库模型 |
| `core/schema_adapters.py` | new | 模型适配层 |
| `core/schema_pydantic.py` | new | Pydantic 模型 |
| `core/workspace_paths.py` | new | 工作区路径规范 |
| `core/detection_protocol.py` | new | 检测协议 |
| `core/exceptions.py` | new | 异常体系 |
| `core/capture_session.py` | M | 采集会话扩展 |
| `core/field_session.py` | M | 现场会话扩展 |
| `core/hybrid_strategy.py` | M | 混合策略扩展 |
| `core/hybrid_retest.py` | M | 混合复检扩展 |
| `core/deployment_package.py` | M | 部署包扩展 |

### B2. UI 页面重构

| 文件 | 状态 | 说明 |
|------|------|------|
| `desktop_app/main_window.py` | M | 主窗口重构（导航切换） |
| `desktop_app/navigation.py` | M | 导航系统重构 |
| `desktop_app/app_context.py` | M | 应用上下文 |
| `desktop_app/constants.py` | M | 常量 |
| `desktop_app/theme.py` | M | 主题系统 |
| `desktop_app/i18n.py` | M | 国际化（大幅扩展） |
| `desktop_app/ui_state.py` | M | UI 状态 |
| `desktop_app/ui_loader.py` | new | UI 加载器 |
| `desktop_app/theme_manager.py` | new | 主题管理器 |
| `desktop_app/ui/` | new | UI 资源目录 |

### B3. 页面删除与新增

| 文件 | 状态 | 说明 |
|------|------|------|
| `desktop_app/pages/camera_config_page.py` | D | 删除（被 camera_management_page 替代） |
| `desktop_app/pages/dataset_page.py` | D | 删除 |
| `desktop_app/pages/device/commissioning_panel.py` | D | 删除 |
| `desktop_app/pages/device_config_page.py` | D | 删除 |
| `desktop_app/pages/encoder_config_page.py` | D | 删除 |
| `desktop_app/pages/plc_config_page.py` | D | 删除 |
| `desktop_app/pages/camera_workbench_page.py` | new | 相机工作台 |
| `desktop_app/pages/project_workbench_page.py` | new | 项目工作台 |
| `desktop_app/pages/production_line_com_page.py` | new | 生产线通信 |
| `desktop_app/pages/auto_focus_page.py` | new | 自动对焦 |
| `desktop_app/pages/sample_library_page.py` | new | 样本库 |

### B4. 其他 UI 修改

所有 `desktop_app/pages/*.py`、`desktop_app/dialogs/*.py`、`desktop_app/widgets/*.py`、`desktop_app/workers/*.py` 均有修改，主要是：
- i18n 翻译集成
- 导航链接更新
- 新 workflow 支持
- 导入路径调整

### B5. 相机适配器

| 文件 | 状态 | 说明 |
|------|------|------|
| `camera_adapters/hikvision_mvs.py` | M | 海康 MVS 适配器扩展（277 行变更） |

### B6. 其他模块

| 文件 | 状态 | 说明 |
|------|------|------|
| `benchmark/benchmark_runner.py` | M | 基准测试扩展 |
| `benchmark/report_exporter.py` | M | 报告导出扩展 |
| `retrieval/embeddings.py` | M | 嵌入模型扩展 |
| `retrieval/index.py` | M | 检索索引扩展 |
| `runtime/inference_pipeline.py` | M | 推理管线扩展 |
| `line_scan_af/` | new | 线扫自动对焦正式功能模块（被 AutoFocusPage/AutofocusWorker import） |
| `config/autofocus/` | new | 线扫自动对焦默认配置（config_loader 默认读取目录） |
| `main.py` | M | 入口扩展 |
| `configs/models.yaml` | M | 模型配置 |

### B7. 文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `docs/architecture.md` | new | 架构文档 |
| `docs/camera_workbench_*` | new | 相机工作台相关文档 |
| `docs/phase_*` | new | 各阶段迁移/删除计划文档 |
| `docs/project_workbench_*` | new | 项目工作台相关 |
| `docs/workbench_redesign_preview.html` | new | 工作台重设计预览 |
| `docs/phase4_change_audit.md` | new | 本文件 |
| `docs/cpp_runtime_phase4_verification.md` | new | Phase 4 验证文档 |
| `MODEL_AND_STRATEGY_GUIDE.md` | M | 模型策略指南 |
| `README.md` | M | README 更新 |
| `USER_GUIDE.md` | M | 用户指南更新 |
| `CLAUDE.md` | new | 项目级 Claude 配置 |

### B8. 测试（非 C++ 相关）

| 文件 | 状态 | 说明 |
|------|------|------|
| `tests/conftest.py` | new | 共享 fixtures |
| `tests/__init__.py` | M | 测试包初始化 |
| `tests/test_project_cascade_delete.py` | new | 级联删除测试 |
| `tests/test_project_workflow.py` | new | 项目工作流测试 |
| `tests/test_project_workbench_page.py` | new | 项目工作台页面测试 |
| `tests/test_camera_workbench_page.py` | new | 相机工作台页面测试 |
| `tests/test_sample_library.py` | new | 样本库测试 |
| `tests/test_workspace_paths.py` | new | 工作区路径测试 |
| `tests/test_help_and_i18n_page_text.py` | new | 帮助/i18n 测试 |
| `tests/test_sample_classification_workflow.py` | M | 样本分类工作流 |
| `tests/test_field_workflow_page.py` | M | 现场工作流页面 |
| `tests/test_model_version.py` | M | 模型版本测试 |
| 其他 `tests/test_*.py` | M | 各种小幅调整 |

### B9. 构建/打包

| 文件 | 状态 | 说明 |
|------|------|------|
| `packaging/build_windows.bat` | M | Windows 构建脚本 |
| `packaging/pyinstaller.spec` | M | PyInstaller spec |
| `requirements.txt` | M | 依赖 |
| `uv.lock` | M | uv 锁文件 |

---

## C. 本地配置文件（❌ 不应提交）

| 文件 | 状态 | 说明 |
|------|------|------|
| `config/language.json` | M | 语言配置（本地） |

**建议**: `config/ui_state.json` 与 `config/class_labels.json` 已恢复到基线内容；`config/language.json` 如仍显示为修改，需要用户确认是否为本地语言状态还是应提交配置。

---

## D. 构建/缓存/生成物（❌ 不应提交）

| 文件/目录 | 状态 | 说明 |
|-----------|------|------|
| `.ruff_cache/` | ignored | Ruff 缓存（已在 .gitignore） |
| `.pytest_cache/` | ignored | pytest 缓存（已在 .gitignore） |
| `cpp_runtime/build/` | ignored | CMake 构建产物（已在 .gitignore） |
| `dist/` | ignored | 打包输出（已在 .gitignore） |
| `focus_runs/` | ignored | 自动对焦运行产物（已在 .gitignore） |

---

## E. 汇总

| 类别 | 计数（约） | 处理 |
|------|-----------|------|
| A. C++ Runtime Phase 3/4 | ~30 文件 | ✅ 应提交 |
| B. 前期业务重构 | ~90 文件 | ⚡ 应提交（独立提交） |
| C. 本地配置 | ~6 文件 | ❌ 不应提交，建议还原 |
| D. 构建/缓存/生成物 | ~5 目录 | ❌ 不应提交，补充 .gitignore |

## F. 建议操作

1. **还原本地配置文件**：
   ```
   git checkout -- config/ui_state.json config/class_labels.json config/language.json
   ```
   或在 `.gitignore` 中添加 `config/ui_state.json`（如确认为纯本地文件）。

2. **`.gitignore` 状态**：`dist/`、`focus_runs/`、`cpp_runtime/build/` 已添加。`line_scan_af/` 与 `config/autofocus/` 是正式自动对焦模块相关内容，不应加入 `.gitignore`。

3. **确认 `config/language.json`**：如只是本地语言状态，恢复或忽略；如是产品默认语言配置，随业务重构提交。

4. **建议分两次提交**：
   - Commit 1: 前期业务重构（B 类）
   - Commit 2: C++ Runtime Phase 3/4（A 类）
   避免混在一起导致 diff 难以审查。
