# Phase 4 最终提交前检查报告

**日期**: 2026-06-08
**状态**: config/ui_state.json 已恢复基线（diff 为空）；删除页面引用检查已通过；待用户确认删除意图后可进入 commit 阶段

---

## 1. 当前变更总览

| 类别 | 文件数 | 说明 |
|------|--------|------|
| Commit 1: 业务/UI 重构 | ~130 | 含新增 workbench、autofocus、i18n、core models、删除旧页面、line_scan_af、config/autofocus |
| Commit 2: C++ Runtime | ~25 | 含 C++ 源码、Python 合约层、backend、生产页面隔离、测试、文档 |
| Commit 3: 可选 | 1 | CLAUDE.md |
| 不应提交 | 2 | config/ui_state.json、config/class_labels.json（无实质 diff） |

---

## 2. Commit 1: 前期业务与 UI 重构

### 2.1 新增 core 模型

```
core/detection_protocol.py
core/exceptions.py
core/project_cascade.py
core/project_workflow.py
core/sample_library.py
core/schema_adapters.py
core/schema_pydantic.py
core/workspace_paths.py
```

### 2.2 修改 core 模型

```
core/capture_session.py
core/customer.py
core/dataset_builder.py
core/anomaly_dataset_builder.py
core/deployment_package.py
core/field_session.py
core/hybrid_retest.py
core/hybrid_strategy.py
core/product_spec.py
core/project.py
core/storage.py
```

### 2.3 新增 UI 页面

```
desktop_app/pages/camera_workbench_page.py
desktop_app/pages/project_workbench_page.py
desktop_app/pages/production_line_com_page.py
desktop_app/pages/auto_focus_page.py
desktop_app/pages/sample_library_page.py
```

### 2.4 新增 UI 组件/对话框

```
desktop_app/dialogs/camera_bind_dialog.py
desktop_app/theme_manager.py
desktop_app/ui_loader.py
desktop_app/ui/
desktop_app/workers/autofocus_worker.py
```

### 2.5 删除旧页面（6 个，已确认无生产代码引用）

```
desktop_app/pages/camera_config_page.py (D)
desktop_app/pages/dataset_page.py (D)
desktop_app/pages/device/commissioning_panel.py (D)
desktop_app/pages/device_config_page.py (D)
desktop_app/pages/encoder_config_page.py (D)
desktop_app/pages/plc_config_page.py (D)
```

### 2.6 修改的 UI 文件（排除 production_run_page.py）

```
desktop_app/app_context.py
desktop_app/constants.py
desktop_app/dialogs/*.py (4 files)
desktop_app/display.py
desktop_app/i18n.py
desktop_app/label_config.py
desktop_app/main_window.py
desktop_app/navigation.py
desktop_app/pages/*.py (~25 files, excluding production_run_page.py)
desktop_app/theme.py
desktop_app/ui_state.py
desktop_app/widgets/*.py (6 files)
desktop_app/workers/*.py (10 files)
```

### 2.7 新增功能模块

```
line_scan_af/                  ← 正式功能模块（线扫自动对焦），被 AutoFocusPage/AutofocusWorker import
config/autofocus/              ← 自动对焦默认配置
```

### 2.8 其他业务模块修改

```
camera_adapters/hikvision_mvs.py
benchmark/benchmark_runner.py
benchmark/report_exporter.py
retrieval/embeddings.py
retrieval/index.py
runtime/inference_pipeline.py
main.py
configs/models.yaml
packaging/build_windows.bat
packaging/pyinstaller.spec
requirements.txt
uv.lock
pyproject.toml
```

### 2.9 业务测试（修改）

```
tests/__init__.py
tests/conftest.py
tests/test_anomaly_dataset_builder.py
tests/test_anomaly_review.py
tests/test_benchmark_runner.py
tests/test_camera_config.py
tests/test_camera_management_page.py
tests/test_capture_session.py
tests/test_confusion.py
tests/test_core_metrics.py
tests/test_customer.py
tests/test_dataset_version.py
tests/test_dataset_version_integration.py
tests/test_defect_dictionary.py
tests/test_defect_rules.py
tests/test_deployment_metrics.py
tests/test_encoder_integration.py
tests/test_encoder_reader.py
tests/test_field_session.py
tests/test_field_workflow_page.py
tests/test_fusion.py
tests/test_global_regressions.py
tests/test_gpu_scheduler.py
tests/test_hybrid_retest_page.py
tests/test_matcher.py
tests/test_metrics_collector.py
tests/test_model_activation_guard.py
tests/test_model_version.py
tests/test_multi_camera_production.py
tests/test_phase5_closure.py
tests/test_position_analysis.py
tests/test_product_spec.py
tests/test_production_event_v6.py
tests/test_project.py
tests/test_report_exporter.py
tests/test_sample_classification_workflow.py
tests/test_training_job.py
tests/test_v6_integration.py
tests/test_v8_integration_regressions.py
```

### 2.10 业务测试（新增）

```
tests/test_camera_workbench_page.py
tests/test_help_and_i18n_page_text.py
tests/test_project_cascade_delete.py
tests/test_project_workbench_page.py
tests/test_project_workflow.py
tests/test_sample_library.py
tests/test_workspace_paths.py
```

### 2.11 业务文档

```
docs/architecture.md
docs/camera_workbench_merge_claudecode.md
docs/camera_workbench_preview.html
docs/camera_workbench_ui_loader_plan.md
docs/phase_f_existing_module_map.md
docs/phase_f_field_workflow_workspace_multi_agent_claudecode.md
docs/phase_f_migration_guide.md
docs/phase_g_delete_candidates.md
docs/phase_g_product_workflow_restructure_multi_agent_claudecode.md
docs/phase_h_round3_cleanup_audit.md
docs/phase_h_round4_delete_plan.md
docs/project_workbench_guided_testing_claudecode.md
docs/workbench_redesign_preview.html
MODEL_AND_STRATEGY_GUIDE.md
README.md
USER_GUIDE.md
```

---

## 3. Commit 2: C++ Runtime Phase 1-4

### 3.1 C++ 源码

```
cpp_runtime/CMakeLists.txt
cpp_runtime/src/main.cpp
cpp_runtime/src/runtime_contracts.cpp
cpp_runtime/include/cx_vision/runtime_contracts.hpp
```

### 3.2 Python 合约层

```
core/runtime_contracts.py
core/runtime_mode.py
core/config_backup.py
runtime/runtime_backend.py
runtime/cpp_runtime_client.py
runtime/fake_cpp_runtime.py
```

### 3.3 UI 外部模式隔离

```
desktop_app/pages/production_run_page.py
```

### 3.4 打包

```
packaging/cpp_runtime_package.ps1
```

### 3.5 C++ Runtime 测试

```
tests/test_production_runtime_modes.py
tests/test_cpp_runtime_config_cli.py
tests/test_cpp_runtime_client.py
tests/test_runtime_backend.py
tests/test_runtime_contracts.py
tests/test_fake_cpp_runtime.py
tests/test_cpp_runtime_package.py
tests/test_config_backup.py
tests/test_config_backup_full.py
tests/test_defect_trace_upgrade.py
```

### 3.6 C++ Runtime 文档

```
docs/cpp_runtime_contract.md
docs/cpp_platform_integration.md
docs/cpp_runtime_phase4_verification.md
docs/phase4_change_audit.md
docs/phase4_pre_commit_report.md
docs/phase4_final_pre_commit_check.md
docs/superpowers/plans/2026-06-03-cpp-runtime-migration.md
docs/superpowers/plans/2026-06-03-cpp-runtime-migration-zh.md
docs/superpowers/plans/2026-06-03-cpp-runtime-phase2-multiagent-zh.md
docs/superpowers/plans/2026-06-04-cpp-runtime-phase3-multiagent-zh.md
docs/superpowers/plans/2026-06-04-cpp-runtime-phase4-multiagent-zh.md
docs/superpowers/plans/2026-06-05-cpp-runtime-phase5-zh.md
```

### 3.7 其他

```
.gitignore
```

---

## 4. Commit 3: 可选 — CLAUDE.md

```
CLAUDE.md  ← 项目级 AI 配置，按需提交或跳过
```

---

## 5. 不应提交的文件

| 文件 | 原因 | 当前状态 |
|------|------|----------|
| `config/ui_state.json` | 本地 UI 状态 | `git diff` 为空，无需操作 |
| `config/class_labels.json` | 仅 CRLF 行尾变更 | `git diff` 为空，无需操作 |
| `.ruff_cache/` | 缓存 | 已在 .gitignore |
| `.pytest_cache/` | 缓存 | 已在 .gitignore |
| `.mypy_cache/` | 缓存 | 已在 .gitignore |
| `cpp_runtime/build/` | 构建产物 | 已在 .gitignore |
| `dist/` | 打包输出 | 已在 .gitignore |
| `focus_runs/` | 运行产物 | 已在 .gitignore |
| `outputs/` | 生成输出 | 已在 .gitignore |

---

## 6. 删除页面引用检查结果

| 删除文件 | 生产 import | 导航注册 | 测试引用 | i18n 残留 | 结论 |
|----------|------------|---------|---------|----------|------|
| camera_config_page.py | 无 | 无 | 无 | 1 死键 | ✅ 可提交 |
| dataset_page.py | 无 | 无 | 删除确认断言 | 无 | ✅ 可提交 |
| commissioning_panel.py | 无 | 无 | 无 | 无 | ✅ 可提交 |
| device_config_page.py | 无 | 无 | 删除确认断言 | 1 死键 | ✅ 可提交 |
| encoder_config_page.py | 无 | 无 | 无 | 无 | ✅ 可提交 |
| plc_config_page.py | 无 | 无 | 无 | 无 | ✅ 可提交 |

**总体判定**: 6 个删除页面**零生产代码引用**，但提交删除前仍需用户确认删除意图。

仅有两个无害残留：
- `desktop_app/i18n.py:249` `"nav.device_config"` — 无调用方（死键，非阻塞）
- `desktop_app/i18n.py:1048` `"nav.camera_config"` — 无调用方（死键，非阻塞）

---

## 7. line_scan_af/ 和 config/autofocus/ 正式功能归属

| 路径 | 说明 |
|------|------|
| `line_scan_af/` | 完整 Python 模块（acquisition/, autofocus/, controllers/, product/, ui/, utils/），被 `desktop_app/pages/auto_focus_page.py` 和 `desktop_app/workers/autofocus_worker.py` import。**已确认为正式功能代码**。 |
| `config/autofocus/` | 默认校准配置（autofocus_config.json、camera_stage_binding.json、stage_driver_config.json），被 line_scan_af 模块加载。**已确认为正式默认配置**。 |

两者纳入 Commit 1（业务/UI 重构）。

---

## 8. 测试结果

| 测试集 | 通过 | 耗时 | 状态 |
|--------|------|------|------|
| C++ exe smoke (`status`) | n/a | <1s | ✅ 正常返回 JSON |
| C++ runtime Python (7 files) | 89 | 215s | ✅ |
| Workbench + config (10 files) | 166 | 303s | ✅ |
| ruff (Phase 3/4 + workbench) | — | — | ✅ All clean |
| 全量 pytest | 1137 | ~804s | ✅ 上轮通过 |

---

## 9. .gitignore 覆盖率

| 模式 | 状态 |
|------|------|
| `.ruff_cache/` | ✅ 已覆盖 |
| `.pytest_cache/` | ✅ 已覆盖 |
| `.mypy_cache/` | ✅ 已覆盖 |
| `cpp_runtime/build/` | ✅ 已覆盖 |
| `dist/` | ✅ 已覆盖 |
| `focus_runs/` | ✅ 已覆盖 |
| `outputs/` | ✅ 已覆盖 |
| `.venv/` | ✅ 已覆盖 |
| `__pycache__/` | ✅ 已覆盖 |

**覆盖率 9/9**，无缺失项。无构建产物被误追踪。

---

## 10. 剩余风险

| 风险 | 等级 | 说明 |
|------|------|------|
| i18n 有两个死键 | LOW | `nav.device_config`、`nav.camera_config` 无调用方；非阻塞，后续清理 |
| 全量 pytest 本次未复跑 | LOW | 上轮 1137 passed；C++ runtime + workbench 重点测试均已独立复跑通过 |
| C++ exe 未签名 | MEDIUM | 产线部署需签名（Phase 5 规划） |
| 无实际相机/GPU | MEDIUM | 外部 runtime 仅协议层验证（Phase 5 规划） |

---

## 11. 下一步

1. **配置已恢复**：`config/ui_state.json` 已通过 `git checkout` 恢复基线，`git diff -- config/ui_state.json` 为空。`config/class_labels.json` diff 为空（仅 CRLF 行尾标记）。
2. **待用户确认**：
   - 6 个删除旧页面的意图（已确认零生产代码引用，但删除是永久操作）
   - CLAUDE.md 是否纳入 Commit 3 或跳过
3. **配置恢复 + 用户确认删除后可进入 commit 阶段**。建议操作顺序：
   - Commit 1: `git add <Commit 1 file list>` → `git commit -m "refactor: ..."`
   - Commit 2: `git add <Commit 2 file list>` → `git commit -m "feat: ..."`
   - Commit 3 (可选): `git add CLAUDE.md` → `git commit -m "chore: add project-level Claude config"`
4. 可选清理：删除 `desktop_app/i18n.py` 中的两个死键（`nav.device_config`、`nav.camera_config`），不影响提交。
