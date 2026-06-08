# Phase G：整体产品流程重构多 Agent 开发说明

> 本文档给 Claude Code 使用。请按多 agent 方式开发。
>
> 默认中文沟通；代码、命令、字段名、路径保持英文。
>
> 不要 `git commit`、不要 `git push`，除非项目负责人明确要求。

## 1. 目标

Phase F 已经补充了工作区外置、项目流程状态、样本库、生产运行模式等底层能力，但当前软件界面仍然是“功能模块菜单集合”：

```text
项目中心
现场数据
训练中心
验证中心
生产运行
设备配置
现场交付流程
混合复检
压测中心
报告中心
日志中心
备份恢复
系统设置
帮助
```

这不是最终产品形态。

Phase G 的目标是把整个软件重构为一条统一的现场建模闭环：

```text
项目工作台
-> 设备配置
-> 现场采集
-> 样本复核与样本库
-> 模型训练与迭代
-> 联合检测运行
-> 性能验证与硬件推荐
-> 报告交付
-> 系统维护
```

核心判断：

```text
现场交付流程不再是一个独立页面。
它应该升级为整个软件的主流程和项目工作台。
所有页面、按钮、入口都必须服务这条主流程。
```

## 2. 产品原则

### 2.1 主流程优先

用户不应该面对一堆并列功能入口，而应该看到：

```text
当前项目处于哪个阶段
下一步应该做什么
哪些条件已经满足
哪些操作还被阻止
当前数据、模型、设备、报告状态如何
```

### 2.2 现有模块优先复用

不要重写已有模块。优先复用：

```text
desktop_app/pages/project_center_page.py
desktop_app/pages/device_config_page.py
desktop_app/pages/camera_config_page.py
desktop_app/pages/capture_page.py
desktop_app/pages/sample_classification_page.py
desktop_app/pages/bbox_annotation_page.py
desktop_app/pages/dataset_version_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/pages/training_page.py
desktop_app/pages/training_jobs_page.py
desktop_app/pages/model_version_page.py
desktop_app/pages/model_export_page.py
desktop_app/pages/production_run_page.py
desktop_app/pages/hybrid_retest_page.py
desktop_app/pages/benchmark_page.py
desktop_app/pages/report_page.py
desktop_app/pages/log_center_page.py
desktop_app/pages/backup_restore_page.py
desktop_app/pages/system_settings_page.py
```

Phase G 主要做：

```text
重排入口
合并视图
隐藏重复入口
按流程挂载已有页面
补足项目工作台
明确删除候选
```

### 2.3 先隐藏，再删除

不要直接删除页面文件。第一阶段只从主导航移除或隐藏入口。

删除必须满足：

```text
没有主流程入口依赖
没有测试依赖
没有核心业务调用
功能已被其他页面完整覆盖
项目负责人确认
```

## 3. 目标主导航

左侧主导航最终只保留这些一级入口：

```text
项目工作台
设备配置
现场采集
样本复核
模型训练
联合检测
性能验证
报告交付
系统维护
```

建议 `NAV_ITEMS`：

```python
NAV_ITEMS = [
    {"id": "workbench", "label": "项目工作台", "icon": "W"},
    {"id": "device_setup", "label": "设备配置", "icon": "D"},
    {"id": "site_capture", "label": "现场采集", "icon": "C"},
    {"id": "sample_review", "label": "样本复核", "icon": "S"},
    {"id": "model_iteration", "label": "模型训练", "icon": "M"},
    {"id": "hybrid_runtime", "label": "联合检测", "icon": "H"},
    {"id": "performance", "label": "性能验证", "icon": "P"},
    {"id": "delivery", "label": "报告交付", "icon": "R"},
    {"id": "maintenance", "label": "系统维护", "icon": "T"},
]
```

图标可以后续统一调整，当前阶段优先保证结构正确。

## 4. 页面重组关系

### 4.1 项目工作台

新建或重命名：

```text
desktop_app/pages/project_workbench_page.py
```

可以复用 `FieldWorkflowPage` 的逻辑，但不要继续把它叫“现场交付流程”。

项目工作台应显示：

```text
当前客户 / 项目 / 产品规格
当前 workflow state
下一步动作
设备配置状态
采集会话数量
OK / NG / Uncertain 样本数量
历史样本引用/导入数量
无监督模型状态
YOLO 模型状态
联合检测状态
benchmark 状态
报告状态
```

项目工作台提供主要动作按钮：

```text
去设备配置
开始现场采集
进入样本复核
训练无监督模型
训练 YOLO
进入联合检测
运行性能验证
生成报告
```

这些按钮通过 `AppContext` 或主窗口路由跳转到对应主页面。

### 4.2 设备配置

一级入口：

```text
设备配置
```

内部 tabs：

```text
设备总览
相机配置
相机管理
PLC 配置
编码器配置
```

复用文件：

```text
desktop_app/pages/device_config_page.py
desktop_app/pages/camera_config_page.py
desktop_app/pages/camera_management_page.py
desktop_app/pages/plc_config_page.py
desktop_app/pages/encoder_config_page.py
```

要求：

```text
项目创建后，项目工作台应把设备配置作为第一步。
未完成设备配置，不阻止用户查看其他页面，但阻止正式现场采集。
```

### 4.3 现场采集

一级入口：

```text
现场采集
```

内部 tabs：

```text
采集会话
实时运行
样本分类
数据集版本
```

复用文件：

```text
desktop_app/pages/capture_page.py
desktop_app/pages/production_run_page.py
desktop_app/pages/sample_classification_page.py
desktop_app/pages/dataset_version_page.py
```

要求：

```text
ProductionRunPage 是现场采集的核心实时视图。
CapturePage 只负责创建/管理采集会话。
每个采集会话都应该能进入实时运行视图。
```

运行模式对应：

```text
baseline_capture            # 第一次没有模型，手动 OK/NG/Uncertain
anomaly_assisted_capture    # 无监督模型辅助采集
hybrid_capture              # YOLO + 无监督联合采集
stable_production           # 稳定生产运行
```

### 4.4 样本复核

一级入口：

```text
样本复核
```

内部 tabs：

```text
样本分类
异常复核
缺陷字典
bbox 标注
历史样本库
数据集版本
```

复用文件：

```text
desktop_app/pages/sample_classification_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/pages/bbox_annotation_page.py
desktop_app/pages/dataset_version_page.py
core/sample_library.py
```

要求：

```text
FieldWorkflowPage 中的异常复核、缺陷字典、YOLO 首训准备可以拆成复用组件或保留在样本复核页内部。
历史样本库必须在这里有入口。
```

### 4.5 模型训练

一级入口：

```text
模型训练
```

内部 tabs：

```text
无监督训练
YOLO 训练
训练任务
模型版本
模型导出
```

复用文件：

```text
desktop_app/pages/training_page.py
desktop_app/pages/training_jobs_page.py
desktop_app/pages/model_version_page.py
desktop_app/pages/model_export_page.py
```

要求：

```text
TrainingPage 需要明确区分无监督训练和 YOLO 训练。
无监督训练主要使用确认 OK 样本。
YOLO 训练只能使用已复核、已定义缺陷类型、已 bbox 标注的样本。
```

### 4.6 联合检测

一级入口：

```text
联合检测
```

内部 tabs：

```text
实时联合检测
混合复检记录
未知异常回流
生产事件
```

复用文件：

```text
desktop_app/pages/production_run_page.py
desktop_app/pages/hybrid_retest_page.py
core/hybrid_retest.py
core/production_event.py
```

要求：

```text
HybridRetestPage 不再作为主导航独立入口。
它并入联合检测。
ProductionRunPage 在 hybrid_capture / stable_production 模式下作为主视图。
```

### 4.7 性能验证

一级入口：

```text
性能验证
```

内部 tabs：

```text
模型推理测试
模型对比
benchmark
stress test
硬件推荐
```

复用文件：

```text
desktop_app/pages/inference_page.py
desktop_app/pages/evaluation_page.py
desktop_app/pages/model_comparison_page.py
desktop_app/pages/benchmark_page.py
benchmark/hardware_advisor.py
```

要求：

```text
原来的验证中心、模型对比、benchmark 不再是分散入口。
统一服务于部署前性能确认和硬件推荐。
```

### 4.8 报告交付

一级入口：

```text
报告交付
```

内部内容：

```text
项目报告
benchmark 报告
模型版本摘要
硬件推荐
部署交付包
```

复用文件：

```text
desktop_app/pages/report_page.py
desktop_app/pages/model_export_page.py
core/deployment_package.py
```

### 4.9 系统维护

一级入口：

```text
系统维护
```

内部 tabs：

```text
日志中心
备份恢复
路径设置
系统设置
帮助
```

复用文件：

```text
desktop_app/pages/log_center_page.py
desktop_app/pages/backup_restore_page.py
desktop_app/pages/system_settings_page.py
desktop_app/pages/help_page.py
```

## 5. 应隐藏的旧入口

以下旧入口不应再出现在主导航中：

```text
project_center
capture
training
evaluation
production
device_config
field_workflow
hybrid_retest
benchmark
reports
log_center
backup
settings
help
```

它们不一定删除，只是作为新一级入口的内部 tab 或组件使用。

## 6. 删除候选清单

### 6.1 第一阶段只隐藏，不删除

以下页面先从主导航移除，但保留代码：

```text
desktop_app/pages/hybrid_retest_page.py
desktop_app/pages/inference_page.py
desktop_app/pages/evaluation_page.py
desktop_app/pages/model_comparison_page.py
desktop_app/pages/help_page.py
desktop_app/pages/backup_restore_page.py
desktop_app/pages/log_center_page.py
```

### 6.2 第二阶段可以评估删除

满足以下条件后再删除：

```text
已并入新入口
没有单独业务价值
没有测试依赖
没有外部调用
负责人确认
```

候选：

```text
desktop_app/pages/evaluation_page.py
desktop_app/pages/model_comparison_page.py
desktop_app/pages/device_config_page.py
```

注意：

```text
ProductionRunPage 不删除。
CapturePage 不删除。
TrainingPage 不删除。
FieldWorkflowPage 不直接删除，先重命名/拆分/复用。
```

## 7. 多 Agent 分工

### Agent A：主导航和主窗口重排

负责文件：

```text
desktop_app/constants.py
desktop_app/main_window.py
desktop_app/navigation.py
desktop_app/i18n.py
tests/test_app_navigation.py
```

任务：

```text
1. 将 NAV_ITEMS 改为 Phase G 目标主导航。
2. 在 MainWindow 中建立新的一级页面容器。
3. 把旧页面挂到新容器 tabs 中。
4. 保留旧页面类，不删除文件。
5. 更新中英文 i18n key。
6. 增加导航测试，确认 9 个新入口都能切换。
```

验收：

```text
左侧主导航只显示 9 个 Phase G 入口。
旧入口不再作为主导航出现。
所有旧核心页面仍可通过新 tabs 访问。
```

### Agent B：项目工作台

负责文件：

```text
desktop_app/pages/project_workbench_page.py
desktop_app/pages/field_workflow_page.py
core/project_workflow.py
desktop_app/app_context.py
desktop_app/i18n.py
tests/test_project_workbench_page.py
tests/test_project_workflow.py
```

任务：

```text
1. 新建 ProjectWorkbenchPage。
2. 复用 derive_workflow_status(project_id)。
3. 显示项目当前阶段、下一步动作、关键证据。
4. 显示设备、样本、模型、benchmark、报告摘要。
5. 提供跳转按钮：设备配置、现场采集、样本复核、模型训练、联合检测、性能验证、报告交付。
6. FieldWorkflowPage 不再作为一级入口；若仍需保留，改为样本复核内部 tab。
```

验收：

```text
选择项目后，项目工作台能显示当前 workflow state。
无项目时显示明确空状态。
按钮能通过 MainWindow 跳转到对应新一级页面。
```

### Agent C：现场采集整合

负责文件：

```text
desktop_app/pages/capture_page.py
desktop_app/pages/production_run_page.py
desktop_app/main_window.py
desktop_app/i18n.py
tests/test_capture_session.py
tests/test_production_runtime_modes.py
```

任务：

```text
1. 建立 SiteCaptureContainer 或在 MainWindow 中建立现场采集 tabs。
2. tabs 包含采集会话、实时运行、样本分类、数据集版本。
3. CapturePage 的“实景运行”按钮跳到现场采集页内的 ProductionRunPage。
4. ProductionRunPage 保持 runtime_mode 参数化。
5. baseline_capture 支持无模型、手动 OK/NG/Uncertain。
6. anomaly_assisted_capture 必须选择无监督/异常模型。
7. hybrid_capture 至少选择一个模型。
```

验收：

```text
现场采集入口能完成第一次无模型采集。
手动分类结果写入 captured_images。
无监督辅助采集不能只选 YOLO。
```

### Agent D：样本复核与样本库整合

负责文件：

```text
desktop_app/pages/sample_classification_page.py
desktop_app/pages/bbox_annotation_page.py
desktop_app/pages/dataset_version_page.py
desktop_app/pages/field_workflow_page.py
core/sample_library.py
desktop_app/i18n.py
tests/test_sample_library.py
tests/test_field_workflow_page.py
tests/test_dataset_version_integration.py
```

任务：

```text
1. 建立 SampleReviewContainer。
2. tabs 包含样本分类、异常复核、缺陷字典、bbox 标注、历史样本库、数据集版本。
3. 将 FieldWorkflowPage 中异常复核/缺陷字典/Yolo 首训准备拆为可复用区域，或整体挂到样本复核内部。
4. 暴露历史样本搜索、引用、导入入口。
5. 显示样本来源：当前采集、历史导入、历史引用。
```

验收：

```text
样本复核入口能处理 OK/NG/Uncertain。
历史样本进入当前项目时保留 provenance。
未知 pending 样本不能进入 YOLO 正样本。
```

### Agent E：模型训练与迭代整合

负责文件：

```text
desktop_app/pages/training_page.py
desktop_app/pages/training_jobs_page.py
desktop_app/pages/model_version_page.py
desktop_app/pages/model_export_page.py
core/anomaly_dataset_builder.py
core/field_training_dataset.py
core/model_version.py
desktop_app/i18n.py
tests/test_training_page.py
tests/test_anomaly_dataset_builder.py
tests/test_field_training_dataset.py
tests/test_model_version.py
```

任务：

```text
1. 建立 ModelIterationContainer。
2. tabs 包含无监督训练、YOLO 训练、训练任务、模型版本、模型导出。
3. TrainingPage 文案明确区分无监督和 YOLO。
4. 无监督训练只能使用确认 OK 样本作为 train/good。
5. YOLO 训练只能使用 confirmed_defect + defect_type + bbox。
6. 模型版本继续记录 dataset_version_id、training_job_id、class_mapping。
```

验收：

```text
NG 不会污染无监督 train/good。
unknown_pending 不会进入 YOLO 训练正样本。
训练后模型版本链路完整。
```

### Agent F：联合检测整合

负责文件：

```text
desktop_app/pages/production_run_page.py
desktop_app/pages/hybrid_retest_page.py
core/hybrid_retest.py
core/production_event.py
desktop_app/i18n.py
tests/test_hybrid_retest.py
tests/test_hybrid_retest_page.py
tests/test_production_event_v6.py
```

任务：

```text
1. 建立 HybridRuntimeContainer。
2. tabs 包含实时联合检测、混合复检记录、未知异常回流、生产事件。
3. HybridRetestPage 不再作为主导航独立页面。
4. ProductionRunPage 在 hybrid_capture / stable_production 模式下作为主视图。
5. 未知异常和 needs_review 样本能回流到样本复核。
```

验收：

```text
联合检测入口能选择 YOLO、无监督或两者组合。
融合结果能产生 OK / NG / Suspect / Unknown / Needs Review。
复核回流路径清晰。
```

### Agent G：性能验证与报告交付

负责文件：

```text
desktop_app/pages/benchmark_page.py
desktop_app/pages/inference_page.py
desktop_app/pages/evaluation_page.py
desktop_app/pages/model_comparison_page.py
desktop_app/pages/report_page.py
desktop_app/workers/report_worker.py
benchmark/benchmark_runner.py
benchmark/report_exporter.py
benchmark/hardware_advisor.py
desktop_app/i18n.py
tests/test_benchmark_runner.py
tests/test_report_exporter.py
tests/test_report_formats.py
```

任务：

```text
1. 建立 PerformanceValidationContainer。
2. tabs 包含模型推理测试、模型对比、benchmark、stress test、硬件推荐。
3. benchmark 必须绑定 project_id、dataset_version_id、model_version_id、backend。
4. 建立 DeliveryContainer。
5. 报告交付入口包含项目报告、benchmark 报告、硬件推荐、模型导出/交付包。
6. 报告内容包含 workflow state。
```

验收：

```text
性能验证不再是孤立 demo。
硬件推荐基于 benchmark 结果。
报告交付能输出项目当前阶段和证据。
```

### Agent H：系统维护和删除候选审计

负责文件：

```text
desktop_app/pages/log_center_page.py
desktop_app/pages/backup_restore_page.py
desktop_app/pages/system_settings_page.py
desktop_app/pages/help_page.py
docs/phase_g_delete_candidates.md
desktop_app/i18n.py
tests/test_source_encoding.py
```

任务：

```text
1. 建立 MaintenanceContainer。
2. tabs 包含日志中心、备份恢复、路径设置、系统设置、帮助。
3. 生成 docs/phase_g_delete_candidates.md。
4. 对每个删除候选说明：
   - 当前入口
   - 是否仍被新流程使用
   - 是否有测试覆盖
   - 是否建议删除、隐藏、合并
5. 不实际删除文件。
```

验收：

```text
系统维护只作为辅助入口。
删除候选文档清晰，便于负责人确认。
```

### Agent I：集成测试与回归

负责文件：

```text
tests/test_app_navigation.py
tests/test_project_workbench_page.py
tests/test_production_runtime_modes.py
tests/test_sample_library.py
tests/test_training_page.py
tests/test_benchmark_runner.py
```

任务：

```text
1. 补充新导航测试。
2. 补充项目工作台空状态和有项目状态测试。
3. 补充页面容器创建测试。
4. 补充旧入口隐藏测试。
5. 运行完整测试和 ruff。
```

验收命令：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests -q --junitxml=C:\tmp\phase_g_pytest.xml
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check .
```

如果完整 `ruff check .` 因历史文件失败，则至少运行：

```powershell
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check desktop_app core benchmark tests
```

## 8. 推荐执行顺序

### Step 1：只做导航重排骨架

由 Agent A 完成。

结果：

```text
主导航变成 9 个入口。
旧页面仍可通过新容器访问。
不改变业务逻辑。
```

### Step 2：项目工作台替代现场交付流程

由 Agent B 完成。

结果：

```text
用户进入项目后第一眼看到项目阶段和下一步动作。
FieldWorkflowPage 不再是主导航入口。
```

### Step 3：现场采集和生产运行合并

由 Agent C 完成。

结果：

```text
现场采集入口内可以进入实时运行。
第一次采集、无监督辅助采集、联合采集都走 ProductionRunPage。
```

### Step 4：样本复核、训练、联合检测整合

由 Agent D、E、F 并行完成，但不要改同一个文件。

结果：

```text
样本、训练、联合检测各自成为流程节点。
```

### Step 5：性能验证、报告、系统维护收口

由 Agent G、H 完成。

结果：

```text
benchmark、硬件推荐、报告交付、维护工具都归位。
```

### Step 6：集成验证

由 Agent I 完成。

结果：

```text
完整测试通过。
ruff 通过。
删除候选文档完成。
```

## 9. 明确不要做的事

```text
不要直接删除旧页面文件。
不要重新写一个全新的 UI 框架。
不要把 FieldWorkflowPage 继续作为主流程以外的附属页面。
不要让 ProductionRunPage 只服务生产末端。
不要让 benchmark 脱离项目/数据集/模型版本。
不要把日志、备份、帮助放在主业务导航里。
不要自动 git commit。
不要移动或删除真实样本、模型、报告文件。
```

## 10. 验收标准

Phase G 完成后，软件主界面应该体现如下逻辑：

```text
项目工作台
告诉用户当前阶段和下一步。

设备配置
是项目建立后的第一步。

现场采集
统一承载第一次采集、无监督辅助采集、联合采集。

样本复核
统一承载人工分类、异常复核、缺陷字典、bbox、历史样本库。

模型训练
统一承载无监督、YOLO、模型版本、导出。

联合检测
统一承载 YOLO + 无监督运行和未知异常回流。

性能验证
统一承载 benchmark、stress test、硬件推荐。

报告交付
输出客户现场交付材料。

系统维护
只保留日志、备份、路径和帮助。
```

## 11. 最终交付物

Claude Code 完成后需要给出：

```text
1. 变更文件列表
2. 新导航结构截图或文字说明
3. 删除候选文档路径
4. 测试命令和结果
5. ruff 命令和结果
6. 未完成风险
```

不要提交 git。
