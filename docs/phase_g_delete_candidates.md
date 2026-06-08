# Phase G 删除候选审计

> **原则**：先隐藏，再删除。以下所有候选当前均保留，待 Phase G 稳定后由负责人确认。

生成日期：2026-05-23

---

## 1. 页面文件

### 1.1 `desktop_app/pages/dataset_page.py` — **建议删除**

- **当前入口**：无。不被任何文件导入（`DatasetVersionPage` 的 docstring 已写明 "Replaces old DatasetPage"）
- **是否仍被新流程使用**：否。已被 `DatasetVersionPage` 完全替代
- **测试覆盖**：无（`tests/test_dataset_page.py` 不存在）
- **建议**：删除文件 + 类定义

### 1.2 `desktop_app/pages/monitor_page.py` — **保留，不删除**

- **当前入口**：仅被 `benchmark_page.py` 内部使用
- **是否仍被新流程使用**：是。benchmark 运行时展示实时系统指标
- **测试覆盖**：无
- **建议**：保留。作为 benchmark_page 的嵌入式组件

---

## 2. 旧导航入口 (i18n keys)

以下 14 个旧导航 key 已从 `NAV_ITEMS` 移除，但 i18n 表中仍保留以兼容历史引用：

| Key | 中文 | 状态 |
|-----|------|------|
| `nav.project_center` | 项目中心 | 保留（workbench 容器内 tab） |
| `nav.capture` | 现场数据 | 保留（site_capture 容器） |
| `nav.training` | 训练中心 | 保留（model_iteration 容器） |
| `nav.evaluation` | 验证中心 | 保留（performance 容器） |
| `nav.production` | 生产运行 | 保留（hybrid_runtime/site_capture 容器） |
| `nav.device_config` | 设备配置 | 保留（device_setup 容器） |
| `nav.reports` | 报告中心 | 保留（delivery 容器） |
| `nav.settings` | 系统设置 | 保留（maintenance 容器） |
| `nav.field_workflow` | 现场交付流程 | 保留（sample_review 容器内 tab） |
| `nav.log_center` | 日志中心 | 保留（maintenance 容器内 tab） |
| `nav.backup` | 备份恢复 | 保留（maintenance 容器内 tab） |
| `nav.benchmark` | 压测中心 | 保留（performance 容器内 tab） |
| `nav.monitor` | 性能监控 | 保留（benchmark 内嵌） |
| `nav.camera_config` | 相机配置 | 保留（device_setup 容器内 tab） |

**建议**：所有旧 nav key 继续保留。Phase G 稳定后（预计 2-3 周），若确认无外部引用，可以安全删除。

---

## 3. 页面文件 — 无独立测试覆盖

以下页面有实际功能入口但无对应单元测试文件。不是删除候选，但建议后续补充测试：

| 文件 | 容器 | 测试状态 |
|------|------|---------|
| `benchmark_page.py` | performance[3] | 无 `test_benchmark_page.py` |
| `capture_page.py` | site_capture[0] | 无 `test_capture_page.py` |
| `dataset_version_page.py` | site_capture[3], sample_review[4] | 无 `test_dataset_version_page.py` |
| `evaluation_page.py` | performance[1] | 无 `test_evaluation_page.py` |
| `inference_page.py` | performance[0] | 无 `test_inference_page.py` |
| `model_comparison_page.py` | performance[2] | 无 `test_model_comparison_page.py` |
| `production_run_page.py` | site_capture[1], hybrid_runtime[0] | 无 `test_production_run_page.py` |
| `project_center_page.py` | workbench[1] | 无 `test_project_center_page.py` |
| `project_workbench_page.py` | workbench[0] | 无 `test_project_workbench_page.py` |
| `report_page.py` | delivery[0] | 无 `test_report_page.py` |
| `sample_classification_page.py` | site_capture[2], sample_review[0] | 无 `test_sample_classification_page.py` |
| `sample_library_page.py` | sample_review[3] | 无 `test_sample_library_page.py` |
| `defect_trace_page.py` | hybrid_runtime[2] | 无 `test_defect_trace_page.py` |
| `device_config_page.py` | device_setup[0] | 无 `test_device_config_page.py` |
| `backup_restore_page.py` | maintenance[1] | 无 `test_backup_restore_page.py` |
| `system_settings_page.py` | maintenance[2] | 无 `test_system_settings_page.py` |

---

## 4. 已确认不删除的文件

- **所有页面 `.py` 文件**：除 `dataset_page.py` 外，所有页面均在新 9 容器体系中有明确入口
- **`FieldWorkflowPage`**：保留在 sample_review 容器内，作为现场交付流程的组成部分
- **`ProductionRunPage`**：保留并参数化，服务于 baseline_capture / anomaly_assisted_capture / hybrid_capture / stable_production 四种模式
- **旧 NAV_ITEMS 中的 label 常量**：`constants.py` 中的 `NAV_ITEMS` 已是新的 9 条目列表，旧列表已替换

---

## 5. 建议操作时间线

| 阶段 | 操作 | 条件 |
|------|------|------|
| 当前 (Phase G) | 隐藏旧入口，不删除文件 | ✅ 已完成 |
| Phase G + 1 周 | 删除 `dataset_page.py` | 确认无其他引用 |
| Phase G + 2 周 | 清理旧 i18n nav keys | 确认无外部引用 |
| Phase H | 为无测试页面补充测试 | 按优先级逐个补充 |
