# Phase H — Round 4 Delete Plan

**Date:** 2026-05-29
**Scope:** 旧页面删除前最终确认包 — 不执行删除，仅输出确认清单
**Status:** 用户已确认，删除执行完成

> 初始版本为删除前最终核对清单。用户确认后，已删除第 5 节确认清单中的 6 个旧页面文件；`camera_management_page.py` 仍保留。

## 0. 执行结果

2026-05-29 用户确认“可以删除”后，已删除：

```text
desktop_app/pages/dataset_page.py
desktop_app/pages/camera_config_page.py
desktop_app/pages/plc_config_page.py
desktop_app/pages/encoder_config_page.py
desktop_app/pages/device/commissioning_panel.py
desktop_app/pages/device_config_page.py
```

保留：

```text
desktop_app/pages/camera_management_page.py
```

原因：`tests/test_camera_management_page.py` 仍直接 import 并实例化 `CameraManagementPage`。

---

## 1. 待确认删除文件清单

### 1.1 `desktop_app/pages/dataset_page.py` (class `DatasetPage`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 全仓库搜索，无任何 `import dataset_page` 或 `from desktop_app.pages.dataset_page import` |
| 测试 import | **否** — `tests/test_dataset_page.py` 不存在 |
| 文档引用 | 是 — 仅在历史设计文档（`docs/phase_g_delete_candidates.md` 等）中提到，无实时指导价值 |
| 替代页面 | `DatasetVersionPage` in `sample_review` (MainWindow._sample_review_tabs[4]) |
| 模块内 deprecated 标记 | 有 — `_DEPRECATED: bool = True` |
| ruff 状态 | 通过 |

> **建议：删除。**

---

### 1.2 `desktop_app/pages/camera_config_page.py` (class `CameraConfigPage`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 注意 `tests/test_camera_config.py` 导入的是 `core.camera_config`（数据模型），不是页面 widget |
| 测试 import | **否** — `tests/test_camera_config_page.py` 不存在 |
| 文档引用 | 是 — 仅在历史设计文档（`docs/camera_workbench_merge_claudecode.md` 等）中提到 |
| 替代页面 | `CameraWorkbenchPage` in `device_setup` (MainWindow._device_tabs[0]) |
| 模块内 deprecated 标记 | 有 — `_DEPRECATED: bool = True` |
| ruff 状态 | 通过 |

> **建议：删除。**

---

### 1.3 `desktop_app/pages/plc_config_page.py` (class `PlcConfigPage`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 全仓库搜索零引用 |
| 测试 import | **否** — `tests/test_plc_config_page.py` 不存在 |
| 文档引用 | 是 — 仅在 `docs/phase_g_product_workflow_restructure_multi_agent_claudecode.md` 中提到 |
| 替代页面 | `ProductionLineComPage` in `device_setup` (MainWindow._device_tabs[1]) |
| 模块内 deprecated 标记 | 有 — `_DEPRECATED: bool = True` |
| ruff 状态 | 通过 |

> **建议：删除。**

---

### 1.4 `desktop_app/pages/encoder_config_page.py` (class `EncoderConfigPage`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 全仓库搜索零引用 |
| 测试 import | **否** — `tests/test_encoder_config_page.py` 不存在 |
| 文档引用 | 是 — 仅在历史设计文档中提到 |
| 替代页面 | `ProductionLineComPage` in `device_setup` (MainWindow._device_tabs[1]) |
| 模块内 deprecated 标记 | 有 — `_DEPRECATED: bool = True` |
| ruff 状态 | 通过 |

> **建议：删除。**

---

### 1.5 `desktop_app/pages/device/commissioning_panel.py` (class `CommissioningPanel`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 全仓库搜索零引用。docstring 自带 `.. deprecated::` 标记 |
| 测试 import | **否** — `tests/test_commissioning_panel.py` 不存在 |
| 文档引用 | 是 — 仅在 `docs/superpowers/specs/2026-05-20-v7-line-scan-camera-design.md` 中提到 |
| 替代页面 | `CameraWorkbenchPage` in `device_setup` (MainWindow._device_tabs[0]) |
| 模块内 deprecated 标记 | 有 — `_DEPRECATED: bool = True` + RST `.. deprecated::` |
| ruff 状态 | 通过 |

> **建议：删除。**

---

### 1.6 `desktop_app/pages/device_config_page.py` (class `DeviceConfigPage`) ⚠️

| 证据项 | 结论 |
|---------|------|
| 当前磁盘状态 | 存在（第二轮结束后从 HEAD 恢复） |
| 生产代码 import | **否** — 全仓库搜索零引用 |
| 测试 import | **否** — `tests/test_device_config_page.py` 不存在 |
| 文档引用 | 是 — 5 处历史文档引用（`docs/phase_g_delete_candidates.md` 等） |
| 替代页面 | `CameraWorkbenchPage` + `ProductionLineComPage` in `device_setup` |
| 模块内 deprecated 标记 | **无** — 该文件没有 deprecated 标记，目前保持原始状态 |
| 特殊说明 | 第三轮启动前此文件处于工作区 D（deleted）状态。第三轮已从 HEAD 恢复以遵守"不删除文件"约束。当前磁盘存在、git 干净。 |

> **建议：需要用户单独确认。** 选项：A) 加入删除清单一并删除；B) 保留并补加 deprecated 标记；C) 单独处理。

---

## 2. 暂不删除文件

### 2.1 `desktop_app/pages/camera_management_page.py` (class `CameraManagementPage`)

| 证据项 | 结论 |
|---------|------|
| 生产代码 import | **否** — 逻辑已迁移至 CameraWorkbenchPage |
| 测试 import | **是** — `tests/test_camera_management_page.py` 在 5 处直接 import 并实例化 |
| 测试覆盖内容 | adapter table rendering / scan & discovery / bind-connect / param apply / showEvent |
| 阻塞原因 | 删除此文件会导致 `tests/test_camera_management_page.py` import 失败 |
| 解除阻塞方式 | A) 将测试逻辑迁移到 test_camera_workbench_page.py（需要 CameraWorkbenchPage 有对等的可测 API）；B) 删除测试文件；C) 保留文件作为历史诊断参考 |

> **建议：暂不删除。** 等后续决定如何处理对应测试后再操作。

---

## 3. 删除后验证命令

### 3.1 测试

```bash
pytest tests/test_project_workbench_page.py \
       tests/test_production_runtime_modes.py \
       tests/test_camera_management_page.py \
       -q -ra --tb=short
```

预期：全部通过（`test_camera_management_page.py` 继续 work，因为该文件不删）。

### 3.2 Ruff

```bash
ruff check \
  desktop_app/main_window.py \
  desktop_app/navigation.py \
  desktop_app/constants.py \
  desktop_app/app_context.py \
  desktop_app/i18n.py \
  tests/test_project_workbench_page.py \
  tests/test_production_runtime_modes.py \
  tests/test_camera_management_page.py
```

预期：零错误。

### 3.3 残留引用扫描

删除文件后，执行以下搜索确认无残留引用：

```bash
# 检查已删除类名
rg "DatasetPage|CameraConfigPage[^W]|PlcConfigPage|EncoderConfigPage|CommissioningPanel|DeviceConfigPage" \
   desktop_app/ core/ runtime/ src/ integration/ camera_adapters/ model_runners/ main.py tests/

# 检查已删除模块名
rg "from desktop_app\.pages\.(dataset_page|camera_config_page|plc_config_page|encoder_config_page) import" \
   desktop_app/ core/ runtime/ tests/

rg "from desktop_app\.pages\.device\.commissioning_panel import" \
   desktop_app/ core/ runtime/ tests/
```

预期：零结果，或仅在历史注释/docstring 中有提及。

---

## 4. 回滚方式

如删除后出现问题（如 import 错误、测试失败），按以下步骤回滚：

```
git restore desktop_app/pages/<deleted_file>.py
pytest ...  # 确认恢复
```

**不要使用 `git reset --hard`**，以免丢失同轮次其他文件的正确改动。

---

## 5. 确认清单

请对以下每项回复 Y/N：

| # | 文件 | 删除？ |
|---|------|--------|
| 1 | `desktop_app/pages/dataset_page.py` | [ ] |
| 2 | `desktop_app/pages/camera_config_page.py` | [ ] |
| 3 | `desktop_app/pages/plc_config_page.py` | [ ] |
| 4 | `desktop_app/pages/encoder_config_page.py` | [ ] |
| 5 | `desktop_app/pages/device/commissioning_panel.py` | [ ] |
| 6 | `desktop_app/pages/device_config_page.py` | [ ] 需单独确认（选项 A/B/C） |

---

## 6. 总结

| 分类 | 数量 | 文件 |
|------|------|------|
| 可删 | 5 | dataset_page, camera_config_page, plc_config_page, encoder_config_page, commissioning_panel |
| 需单独确认 | 1 | device_config_page（来源非本轮，状态特殊） |
| 暂不删 | 1 | camera_management_page（阻塞于测试引用） |
