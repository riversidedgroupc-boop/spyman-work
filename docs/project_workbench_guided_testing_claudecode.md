# Project Workbench Guided Testing Redesign for ClaudeCode

## 目标

把当前“项目工作台”从一个信息较少、空间利用率低的状态看板，改造成“项目测试引导界面”。

这个页面面向刚接手项目的现场工程师和测试工程师，核心作用是回答三个问题：

1. 当前项目处在测试流程的哪一步。
2. 这一步为什么要做，完成标准是什么。
3. 下一步应该进入哪个功能页面。

同时修复当前工作台信息不同步的问题：项目配置中客户、项目、产品规格被新增、编辑、删除后，工作台必须及时显示最新状态，不能继续显示旧项目名、旧规格名或已删除对象。

## 当前问题

### 页面设计问题

当前 `desktop_app/pages/project_workbench_page.py` 主要包含：

- 项目/规格标题。
- 当前 workflow 状态。
- 4 个摘要卡片：设备、采集、样本、模型。

问题：

- 页面剩余空间过大，信息密度低。
- 对新工程师不友好，只知道“有没有”，不知道“为什么”和“下一步怎么做”。
- `U/Y` 这种缩写不适合新手，应改成“无监督模型 / YOLO 模型”。
- 已移除快捷入口后，页面缺少明确的测试流程导航。

### 刷新同步问题

当前工作台刷新链路不完整：

- `ProjectWorkbenchPage` 只监听 `AppContext.project_changed`。
- 没有监听 `customer_changed` 和 `spec_changed`。
- header 使用 `AppContext.current_project_name/current_spec_name`，名称可能是旧缓存。
- 项目配置页 `data_changed` 后只确保顶部选择器刷新，工作台不一定刷新。
- 当前项目或规格被删除后，如果 `AppContext` 或 `ui_state` 没有清理，工作台可能继续显示已删除对象。

## 推荐方案

采用“流程引导式工作台”。

页面不再只是状态卡片，而是一个项目测试流程导航器：

```text
顶部项目概览
客户 / 项目 / 产品规格 / 当前阶段 / 完成度

左侧主区域
完整测试流程步骤列表

右侧详情区域
当前选中步骤的用途、操作说明、完成条件、进入按钮

底部提示区域
当前阻塞原因 + 推荐下一步
```

## 测试流程步骤

工作台固定展示以下 8 个阶段：

| 顺序 | 阶段 | 用途 | 完成条件 | 对应页面 |
| --- | --- | --- | --- | --- |
| 1 | 项目配置 | 建立客户、项目、产品规格关系 | 已选择客户、项目、产品规格 | `workbench` 容器内的“项目配置”tab |
| 2 | 设备配置 | 配置相机、触发、采集参数 | 当前规格下存在相机配置 | `device_setup` |
| 3 | 现场采集 | 采集真实 OK/NG 或待复核样本 | 存在采集会话和采集图像 | `site_capture` |
| 4 | 样本复核 | 确认样本标签、缺陷类型、标注质量 | 样本完成分类或标注 | `sample_review` |
| 5 | 模型训练 | 训练无监督模型或 YOLO 检测模型 | 存在可用模型版本 | `model_iteration` |
| 6 | 联合检测 | 使用模型执行现场检测或复测 | 存在检测记录或复测记录 | `hybrid_runtime` |
| 7 | 性能验证 | 验证速度、准确率、稳定性 | 存在 benchmark 或评估结果 | `performance` |
| 8 | 报告交付 | 输出测试结论和交付材料 | 已生成报告或模型导出物 | `delivery` |

## 页面布局要求

### 顶部项目概览

位置：页面顶部，紧凑显示，不要占用大面积高度。

内容：

- 客户名称
- 项目名称
- 产品规格名称
- 当前流程阶段
- 完成度，例如 `3/8`

要求：

- 每次刷新时从数据库读取最新客户、项目、规格名称。
- 不要只使用 `AppContext` 中缓存的 name。
- 如果当前项目不存在，显示“请先选择项目”。
- 如果当前项目存在但没有规格，显示“当前项目未选择产品规格”。

### 左侧流程步骤列表

位置：页面主体左侧，约占 65% 到 70% 宽度。

每个步骤显示：

- 图标
- 阶段名称
- 状态标签
- 一句话用途
- 完成条件摘要
- 阻塞提示

步骤状态：

- `done`：已完成，绿色勾。
- `current`：当前推荐处理步骤，蓝色高亮。
- `blocked`：被前置条件阻塞，黄色提醒。
- `pending`：未开始，灰色。

交互：

- 点击步骤只切换右侧详情，不自动跳转页面。
- 点击右侧主按钮才跳转页面。

### 右侧步骤详情

位置：页面主体右侧，约占 30% 到 35% 宽度。

显示当前选中步骤：

- 阶段名称
- 这一步的用途
- 操作步骤
- 完成标准
- 常见问题或缺失项
- 主操作按钮

示例：现场采集

```text
用途：
采集当前产品规格下的真实图像，为样本复核和模型训练提供数据基础。

操作：
1. 确认设备配置已完成。
2. 创建或选择采集会话。
3. 采集 OK/NG/待复核样本。
4. 检查图像数量和清晰度。

完成标准：
- 当前项目存在采集会话。
- 采集会话下存在图像。
- 后续训练所需的 OK/NG 样本已进入复核流程。

主按钮：
进入现场采集
```

### 底部下一步提示

位置：页面底部，单行或紧凑两行。

内容：

- 当前阻塞原因。
- 推荐下一步。
- 可选主按钮。

示例：

```text
当前阻塞：当前项目还没有产品规格。
推荐下一步：进入项目配置，先创建产品规格。
```

## 数据与状态来源

继续复用现有 `core.project_workflow.derive_workflow_status(project_id)` 作为当前阶段判断基础。

但展示层不能只依赖 `WorkflowStatus.state`，需要在工作台内部建立一层 UI step mapping：

```text
WorkflowState.NEW_PROJECT -> 项目配置 current
WorkflowState.DEVICE_CONFIG_REQUIRED -> 设备配置 current
WorkflowState.DEVICE_CONFIGURED -> 现场采集 current
WorkflowState.INITIAL_CAPTURE_READY -> 样本复核 current
WorkflowState.INITIAL_CAPTURE_DONE -> 样本复核 current
WorkflowState.MANUAL_TRIAGE_DONE -> 模型训练 current
WorkflowState.UNSUPERVISED_READY -> 模型训练 current
WorkflowState.UNSUPERVISED_TRAINED -> 现场采集或样本复核 current
WorkflowState.ASSISTED_CAPTURE_READY -> 联合检测或样本复核 current
WorkflowState.ANOMALY_REVIEW_PENDING -> 样本复核 current
WorkflowState.YOLO_ANNOTATION_READY -> 样本复核 current
WorkflowState.YOLO_TRAINING_READY -> 模型训练 current
WorkflowState.YOLO_TRAINED -> 联合检测 current
WorkflowState.HYBRID_CAPTURE_READY -> 联合检测 current
WorkflowState.ITERATION_ACTIVE -> 性能验证 current
WorkflowState.BENCHMARK_READY -> 性能验证 current
WorkflowState.ACCEPTANCE_READY -> 报告交付 current
```

注意：

- 如果没有 project：所有步骤 pending，项目配置 current。
- 如果有 project 但没有 spec：项目配置 current，后续步骤 blocked。
- 如果有 spec 但没有设备配置：设备配置 current，后续步骤 blocked。
- 不要新增数据库字段保存流程状态，流程状态继续从现有数据推导。

## 刷新同步设计

### ProjectWorkbenchPage

修改文件：

- `desktop_app/pages/project_workbench_page.py`

要求：

1. 监听以下信号：
   - `AppContext.customer_changed`
   - `AppContext.project_changed`
   - `AppContext.spec_changed`

2. `refresh()` 每次执行时：
   - 使用当前 `customer_id/project_id/spec_id` 重新查数据库。
   - 如果对象存在，使用数据库最新名称刷新页面。
   - 如果对象不存在，展示空状态或缺失状态。
   - 重新调用 `derive_workflow_status(project_id)`。
   - 重建 8 步流程状态。

3. 不要只依赖：
   - `self._ctx.current_project_name`
   - `self._ctx.current_spec_name`

4. 保留公开方法：
   - `refresh()`

现有测试依赖这个方法，不要破坏。

### ProjectSelector

修改文件：

- `desktop_app/widgets/project_selector.py`

要求：

1. `refresh()` 中校验当前上下文是否仍然有效：
   - 当前 customer 不存在：清空 customer/project/spec。
   - 当前 project 不存在：清空 project/spec。
   - 当前 spec 不存在：清空 spec。

2. 如果对象存在但名称变化：
   - 更新 `AppContext` 中对应 name。
   - 更新 combo 选中项显示。

3. 刷新完成后写回 `ui_state`：
   - 防止下次启动恢复已删除或已改名对象。

4. `refreshed` 信号保持不变。

### MainWindow

修改文件：

- `desktop_app/main_window.py`

当前已有：

```python
self._project_center.data_changed.connect(self._selector.refresh)
self._selector.refreshed.connect(self._project_center.refresh)
```

需要补充：

```python
self._selector.refreshed.connect(self._workbench_page.refresh)
```

同时在 `_on_context_changed()` 中调用：

```python
self._workbench_page.refresh()
```

这样用户切换客户、项目、规格后，工作台即时更新。

### ProjectCenterPage

修改文件：

- `desktop_app/pages/project_center_page.py`

要求：

1. 新增、编辑、删除客户/项目/规格成功后统一：

```python
self.refresh()
self.data_changed.emit()
```

2. 不要只刷新单个表，例如只调用 `_refresh_customers()` 或 `_refresh_specs()`。

3. 删除后配合 `ProjectSelector.refresh()` 清理当前上下文。

## 导航按钮设计

工作台的右侧详情按钮通过 `AppContext.navigate_to_page.emit(page_id)` 跳转。

映射关系：

| 阶段 | page_id |
| --- | --- |
| 项目配置 | `workbench` |
| 设备配置 | `device_setup` |
| 现场采集 | `site_capture` |
| 样本复核 | `sample_review` |
| 模型训练 | `model_iteration` |
| 联合检测 | `hybrid_runtime` |
| 性能验证 | `performance` |
| 报告交付 | `delivery` |

项目配置比较特殊：

- `page_id = "workbench"` 只能进入工作台容器。
- 还需要把 `self._workbench_tabs` 切到“项目配置”tab。
- 可新增一个 `MainWindow` 私有方法，或扩展现有导航处理逻辑。
- 不要新增侧边栏入口。

## 不要做的事情

- 不要恢复“快捷操作”按钮区，侧边栏已经有入口。
- 不要用定时器轮询刷新。
- 不要新增数据库字段保存工作流状态。
- 不要在工作台里复制完整帮助文档。
- 不要使用 `U/Y` 之类缩写。
- 不要把页面做成营销式大卡片或大留白布局。

## i18n 文案

修改文件：

- `desktop_app/i18n.py`

建议新增 key：

```text
workbench.overview
workbench.progress
workbench.step_project_config
workbench.step_device_config
workbench.step_site_capture
workbench.step_sample_review
workbench.step_model_training
workbench.step_hybrid_detection
workbench.step_performance
workbench.step_delivery
workbench.status_done
workbench.status_current
workbench.status_blocked
workbench.status_pending
workbench.step_purpose
workbench.completion_criteria
workbench.operation_steps
workbench.blocker
workbench.recommended_next
workbench.enter_step
workbench.project_missing
workbench.spec_missing
```

中文文案要面向工程师，避免太口语化。

## 样式建议

修改文件：

- `desktop_app/theme_manager.py`

建议新增对象名：

```text
QFrame#workbenchOverview
QFrame#workbenchStepItem
QFrame#workbenchStepItemCurrent
QFrame#workbenchStepItemDone
QFrame#workbenchStepItemBlocked
QFrame#workbenchStepDetail
QFrame#workbenchNextHint
```

视觉要求：

- 主色只用于当前步骤。
- 已完成用绿色状态点或勾。
- 阻塞用黄色状态点或警告图标。
- 未开始用低对比灰色。
- 卡片圆角保持项目现有风格，不要做大圆角。
- 文本大小要适合桌面工具，不要使用 hero 级大标题。

## 测试计划

### 单元/组件测试

修改或新增：

- `tests/test_project_workbench_page.py`
- `tests/test_project_selector.py`，如果已有相近文件则复用。
- `tests/test_app_context.py`

必须覆盖：

1. 无项目时：
   - 工作台显示项目配置为当前步骤。
   - 后续步骤为 pending 或 blocked。

2. 有项目但无规格时：
   - 项目配置为 current。
   - 显示“当前项目未选择产品规格”。

3. 有规格但无设备配置时：
   - 设备配置为 current。
   - 右侧详情显示设备配置用途和完成条件。

4. 项目名编辑后：
   - 不重启软件。
   - 调用配置页 `data_changed` 链路。
   - 工作台显示最新项目名。

5. 规格名编辑后：
   - 工作台显示最新规格名。

6. 删除当前规格后：
   - `ProjectSelector.refresh()` 清理当前 spec。
   - 工作台不显示旧规格名。
   - 工作台提示需要选择或创建规格。

7. 删除当前项目后：
   - `ProjectSelector.refresh()` 清理当前 project/spec。
   - 工作台进入未选择项目状态。

8. 点击步骤：
   - 只切换详情，不自动导航。

9. 点击主按钮：
   - 发出正确 `navigate_to_page` 信号或触发对应页面切换。

### 建议运行命令

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_project_workbench_page.py tests/test_app_context.py -q -ra --tb=short
```

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check desktop_app\pages\project_workbench_page.py desktop_app\widgets\project_selector.py desktop_app\pages\project_center_page.py desktop_app\main_window.py desktop_app\i18n.py desktop_app\theme_manager.py tests\test_project_workbench_page.py
```

如果相关测试文件被新增，也加入对应 pytest/ruff 命令。

## 验收标准

功能验收：

- 项目工作台不再是大面积空白看板，而是完整测试流程引导界面。
- 新工程师能从页面上看出当前阶段、步骤用途、完成条件和下一步入口。
- 修改客户、项目、产品规格后，工作台不需要重启或手动刷新即可显示最新信息。
- 删除当前项目或规格后，工作台不会显示旧对象。
- 当前推荐步骤与 `derive_workflow_status(project_id)` 推导结果一致。

交互验收：

- 点击流程步骤只切换右侧说明。
- 点击右侧主按钮才跳转页面。
- 项目配置按钮能进入 workbench 容器内的“项目配置”tab。
- 侧边栏入口保持现状，不新增重复入口。

代码验收：

- 不新增数据库字段。
- 不使用定时刷新。
- 不恢复快捷操作区。
- 不破坏现有 `ProjectWorkbenchPage.refresh()`、`ProjectSelector.refreshed`、`ProjectCenterPage.data_changed` 外部调用。
- 所有新增 UI 文案通过 `desktop_app/i18n.py` 管理。

## 实施顺序建议

1. 先补刷新链路，确保工作台能拿到最新项目配置。
2. 再改工作台布局和 8 步流程展示。
3. 再补右侧详情与导航按钮。
4. 最后补 i18n、样式和测试。

原因：

- 如果刷新链路不先修，新的引导界面会继续显示旧数据。
- 工作台布局可以在刷新链路稳定后独立调整。
- 导航按钮依赖页面结构和步骤 mapping，最后补更稳。
