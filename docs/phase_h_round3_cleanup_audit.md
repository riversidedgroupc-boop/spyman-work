# Phase H — Round 3 Cleanup Audit

**Date:** 2026-05-29
**Scope:** 旧页面 / 旧 i18n key / 重复历史模块引用审计（审计 + 低风险 ruff 清理，不执行文件删除）
**Status:** 审计完成，等待用户确认后才能进入删除阶段

> **本轮约束：** 第三轮只做审计和低风险清理（未使用变量/import 移除、ruff F841 修复）。**不删除任何文件。** 任何文件删除、i18n key 删除、大范围重构必须在后续轮次由用户明确确认。

---

## 1. 旧页面文件引用审计

### 审计方法
全程 rg 搜索全仓库（code + tests + docs），确认每个文件是否被 import 或引用。

### 1.1 `desktop_app/pages/dataset_page.py` (DatasetPage)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 无任何 import。DatasetVersionPage 已替代 |
| 测试引用 | **否** — test_project_workbench_page 断言 `_site_dataset_page` 不存在 |
| 文档引用 | 是 — phase_g_delete_candidates.md 等历史设计文档 |
| **建议动作** | ✅ **safe-to-delete-later** |

### 1.2 `desktop_app/pages/camera_config_page.py` (CameraConfigPage)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 无任何 import。CameraWorkbenchPage 已替代 |
| 测试引用 | **否** |
| 文档引用 | 是 — camera_workbench_merge 等历史设计文档 |
| **建议动作** | ✅ **safe-to-delete-later** |

### 1.3 `desktop_app/pages/camera_management_page.py` (CameraManagementPage)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 逻辑已迁移至 CameraWorkbenchPage（注释: "ported from CameraManagementPage"）|
| 测试引用 | **是** — `tests/test_camera_management_page.py` 在 5 处 import 并实例化 |
| 文档引用 | 是 — camera_workbench_merge_claudecode.md |
| **建议动作** | ⚠️ **blocked-by-tests** — 先删除/迁移测试，再删除文件 |

### 1.4 `desktop_app/pages/plc_config_page.py` (PlcConfigPage)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 无任何 import。ProductionLineComPage 已替代 |
| 测试引用 | **否** |
| 文档引用 | 是 — phase_g 历史文档 |
| **建议动作** | ✅ **safe-to-delete-later** |

### 1.5 `desktop_app/pages/encoder_config_page.py` (EncoderConfigPage)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 无任何 import。ProductionLineComPage 已替代 |
| 测试引用 | **否** |
| 文档引用 | 是 — v7-line-scan-camera 设计文档 |
| **建议动作** | ✅ **safe-to-delete-later** |

### 1.6 `desktop_app/pages/device/commissioning_panel.py` (CommissioningPanel)

| 维度 | 结论 |
|------|------|
| 磁盘存在 | 是 |
| 生产代码引用 | **否** — 无任何 import。文件自带 `.. deprecated::` 标记 |
| 测试引用 | **否** |
| 文档引用 | 是 — v7-line-scan-camera 设计文档 |
| **建议动作** | ✅ **safe-to-delete-later** |

### 1.7 `desktop_app/pages/device_config_page.py` (DeviceConfigPage)

| 维度 | 结论 |
|------|------|
| 当前状态 | **工作区 D（deleted）** — 第三轮启动前已处于删除状态，非本轮操作导致 |
| 生产代码引用 | **否** — 零残留。仅内部自引用 |
| 测试引用 | **否** — `tests/test_device_config_page.py` 不存在 |
| 文档引用 | 是 — phase_g 历史文档中有 5 处残留引用 |
| **建议动作** | ⚠️ **pending-user-confirmation** — 第三轮不执行删除。当前工作区删除来自之前 session，需要用户确认：保留删除或恢复文件。第三轮已从 HEAD 恢复该文件到磁盘以遵守"不要删除文件"约束 |

### 汇总表

| # | 文件 | 生产引用 | 测试引用 | 可删除 |
|---|------|---------|---------|--------|
| 1 | dataset_page.py | 否 | 否 | ✅ |
| 2 | camera_config_page.py | 否 | 否 | ✅ |
| 3 | camera_management_page.py | 否 | **是** | ⚠️ 需先处理测试 |
| 4 | plc_config_page.py | 否 | 否 | ✅ |
| 5 | encoder_config_page.py | 否 | 否 | ✅ |
| 6 | device/commissioning_panel.py | 否 | 否 | ✅ |
| 7 | device_config_page.py | 当前 D（非本轮） | 否 | ⚠️ 待确认 |

---

## 2. i18n Key 审计

### 2.1 旧导航 key（Phase G 之前的扁平菜单）

| Key | i18n.py 行号 | 代码引用 | 分类 |
|-----|-------------|---------|------|
| `nav.capture` | 243 | 零 | compatibility-only |
| `nav.training` | 244 | 零 | compatibility-only |
| `nav.evaluation` | 245 | 零 | compatibility-only |
| `nav.production` | 246 | 零 | compatibility-only |
| `nav.device_config` | 247 | 零 | compatibility-only |
| `nav.reports` | 248 | 零 | compatibility-only |
| `nav.settings` | 249 | 零 | compatibility-only |
| `nav.field_workflow` | 1211 | 零 | compatibility-only |
| `nav.monitor` | 819 | 零 | compatibility-only |

> 以上 9 个 key 位于 i18n.py "Legacy nav keys (kept for backward compatibility)" 注释块，无任何代码引用。

### 2.2 其他 compatibility-only key

| Key | i18n.py 行号 | 代码引用 | 分类 |
|-----|-------------|---------|------|
| `nav.log_center` | 816 | 零 | compatibility-only |
| `nav.backup` | 817 | 零 | compatibility-only |
| `nav.help` | 1063 | 零 | compatibility-only |
| `nav.bbox_annotation` | 1208 | 零 | compatibility-only |

### 2.3 仍在使用的新导航 key

| Key | 使用位置 |
|-----|---------|
| `nav.workbench` | constants.py NAV_ITEMS, main_window.py tab label, navigation.py sidebar |
| `nav.device_setup` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.site_capture` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.sample_review` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.model_iteration` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.hybrid_runtime` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.performance` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.delivery` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.maintenance` | constants.py NAV_ITEMS, navigation.py sidebar |
| `nav.project_center` | main_window.py workbench 子 tab |
| `nav.camera_config` | camera_config_page.py title label (deprecated page itself) |
| `nav.benchmark` | main_window.py performance tab |
| `nav.hybrid_retest` | main_window.py hybrid_runtime tab |
| `nav.sample_library` | main_window.py sample_review tab |
| `nav.defect_trace` | main_window.py hybrid_runtime tab |
| `nav.brand` | navigation.py 品牌标识绑定 |

---

## 3. 低风险清理（已完成）

### 3.1 Ruff F841 修复

| 文件 | 修复内容 |
|------|---------|
| dataset_page.py | 移除未使用的 `output_root`、`raw_dir` 变量；移除 unused import `session_output_root` |
| encoder_config_page.py | 移除未使用的 `status_text`、`speed` 变量 |

### 3.2 Deprecated 标记一致性

所有 6 个 deprecated 文件已统一使用模块常量：
```python
_DEPRECATED: bool = True
_DEPRECATED_REPLACEMENT: str = "ReplacementPageName in container"
```
不使用 `warnings.warn()` import-time 触发。

---

## 4. 下一轮删除候选清单

> **第三轮不执行任何文件删除。** 本轮仅做审计和低风险 ruff 清理（未使用变量/import 移除）。任何文件删除必须在下一轮由用户明确确认后执行。

以下 5 个文件零代码引用、零测试引用，可以在下一轮安全删除：

```
desktop_app/pages/dataset_page.py
desktop_app/pages/camera_config_page.py
desktop_app/pages/plc_config_page.py
desktop_app/pages/encoder_config_page.py
desktop_app/pages/device/commissioning_panel.py
```

以下文件已处于工作区 D（deleted）状态（非第三轮操作），等用户确认：

```
desktop_app/pages/device_config_page.py
  → 当前工作区删除来源：之前 session 误删，非本轮产生
  → 第三轮已从 HEAD 恢复以遵守"不删除文件"约束
  → 需要用户确认：保留删除 / 恢复并标注 deprecated / 加入下轮删除清单
```

以下文件需要前置工作才能删除：

```
desktop_app/pages/camera_management_page.py
  → 需先删除或迁移 tests/test_camera_management_page.py
  → 当前测试覆盖: adapter table rendering, scan/discovery, bind/connect, param apply, showEvent
```

---

## 5. 验证结果

```bash
# 60 tests passed
pytest tests/test_project_workbench_page.py tests/test_production_runtime_modes.py -q

# ruff all-clear on 14 target files
ruff check desktop_app/main_window.py navigation.py constants.py app_context.py i18n.py \
  dataset_page.py camera_config_page.py camera_management_page.py plc_config_page.py \
  encoder_config_page.py commissioning_panel.py \
  test_project_workbench_page.py test_production_runtime_modes.py
```
