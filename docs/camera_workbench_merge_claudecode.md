# 相机管理与相机配置合并方案（给 ClaudeCode 执行）

## 背景

当前设备配置里存在两个容易混淆的页面：

- `相机管理`：负责已注册适配器、SDK 状态、扫描海康相机、绑定槽位、连接、预览、诊断、临时参数调试。
- `相机配置`：按当前产品规格创建相机卡片，并把相机参数保存到 `camera_configs`。

现在的问题是两个页面职责重叠：

- 两边都涉及曝光、增益、触发、相机数量、槽位/设备关系。
- 工程师不清楚哪个页面的参数最终生效。
- 生产运行页实际读取的是 `camera_configs`，但现场调试页的绑定和参数可能没有及时固化到规格配置。

目标是合并成一个清晰入口：**相机工作台 / 相机与采集配置**。

## 重要现状

本工作区可能已经存在未完成的改动：

- `desktop_app/pages/camera_management_page.py`
- `tests/test_camera_management_page.py`

这些改动来自一次被中断的布局优化，可能已经部分加入了：

- `_discovery_grid`
- `_slot_status_grid`
- `_param_grid` 测试期望
- 相机管理页的局部网格布局

执行前请先：

1. 查看 `git diff -- desktop_app/pages/camera_management_page.py tests/test_camera_management_page.py`。
2. 判断半成品改动是否可继续沿用。
3. 不要直接回滚用户已有改动，除非明确确认它们是错误方向。

## 合并后的页面定位

建议把原 `相机管理` 和 `相机配置` 合并为一个页面：

**相机工作台**（推荐名称）  
英文可用：`Camera Workbench`

这个页面应该承担完整流程：

```text
选择客户/项目/产品规格
  -> 读取当前规格 camera_count
  -> 扫描真实相机
  -> 绑定真实设备到规格相机槽位
  -> 连接预览与诊断
  -> 调整参数
  -> 保存到当前规格 camera_configs
  -> 生产运行页读取 camera_configs
```

## 核心原则

### 1. `camera_configs` 是最终配置来源

生产运行、现场采集、项目工作台的配置完成状态，都应该以 `camera_configs` 为准。

`BindingStore` 只能作为现场调试缓存或兼容层，不能成为另一套和 `camera_configs` 并列的最终来源。

### 2. 扫描连接和规格配置要在同一个相机槽位上完成

不要让用户先去一个页面绑定相机，再去另一个页面重新配置参数。

每个相机槽位卡片应该同时显示：

- 规格槽位：`camera_01` / `camera_02`
- 角色：上方 / 左侧 / 右侧 / 备用
- 是否启用
- 已绑定真实设备：SN / IP / Model
- 连接状态：未连接 / 已连接 / 采集中 / 错误
- 配置状态：未配置 / 已配置 / 参数未保存

### 3. 临时应用和保存配置必须区分

按钮语义要清楚：

- `扫描设备`：发现硬件。
- `绑定到槽位`：把选中的真实设备绑定到当前规格相机槽位。
- `连接预览`：现场调试。
- `应用到相机`：只把当前参数下发到已连接相机，不写数据库。
- `保存到当前规格`：写入 `camera_configs`，这是最终生效配置。
- `从规格加载`：从 `camera_configs` 读取并恢复到界面。
- `全部连接`：按当前规格配置连接所有启用相机。

## 推荐页面结构

### 顶部：当前上下文

显示当前：

- 客户
- 项目
- 产品规格
- 规格要求相机数量
- 已配置相机数量

如果没有选择产品规格，页面只显示空状态：

```text
请先在项目配置中选择客户、项目和产品规格。
```

### 左侧：设备发现与连接

包含：

- 已注册适配器
- SDK 状态
- 扫描设备按钮
- 已发现设备列表
- 设备详情：SN / IP / Model / Vendor / MAC

适配器展示建议保留真实链路：

- `folder_watcher`
- `hikrobot_line_scan`
- `basler_pylon`

不要把未完成的 `HikvisionMVSAdapter` 桩类作为主展示项。当前海康真实链路应以 `src.device.camera.hikrobot.hikrobot_camera.HikrobotLineScanCamera` 为准。

### 中间：规格相机槽位

根据当前产品规格的 `camera_count` 渲染槽位卡片：

```text
camera_01 | 上方 | 已绑定 SN-A | 已连接 | 已配置
camera_02 | 左侧 | 未绑定       | 未连接 | 未配置
```

槽位卡片操作：

- 选择当前槽位。
- 启用/禁用。
- 绑定扫描到的设备。
- 解绑。
- 连接/断开。

### 右侧或下方：当前槽位参数

选中某个槽位后显示参数表单：

- 相机类型：`line_scan` / `area_scan`
- 品牌
- 序列号
- IP
- adapter_type
- 曝光
- 增益
- 触发模式
- 触发源
- 行频
- 图像块高度
- 分辨率
- 像素格式
- ROI
- 是否保存 NG 图
- 模型绑定
- 备注

布局不要再把控件全部塞进一行。建议使用 `QGridLayout`，每行 2 到 4 个字段组，固定 label 宽度，输入控件等宽。

### 下方：预览与诊断

保留原相机管理页能力：

- 实时预览
- 快照
- 连接状态
- 采集状态
- 行频
- 已收行数
- 丢行数
- 超时次数
- 最后错误

预览和诊断只针对当前选中槽位。

## 数据流设计

### 加载页面

1. 从 `AppContext` 获取当前 `spec_id`。
2. 调用 `get_product_spec(spec_id)` 获取 `camera_count`。
3. 调用 `list_camera_configs(spec_id)` 加载已保存配置。
4. 根据 `camera_count` 生成槽位。
5. 把已保存的 `CameraConfig` 填到对应槽位。

### 扫描设备

1. 调用 `sdk_loader.load_sdk()`。
2. 调用 `HikrobotLineScanCamera.enumerate_devices()`。
3. 更新发现设备列表。
4. 不直接写入 `camera_configs`。

### 绑定设备到槽位

用户选中一个发现设备和一个槽位后：

1. 将 `serial_number`、`ip_address`、`model`、`brand` 填入当前槽位表单。
2. 设置 `adapter_type = hikrobot_line_scan`。
3. 标记该槽位为“参数未保存”。
4. 只有点击 `保存到当前规格` 才写入 `camera_configs`。

### 应用到相机

只对当前已连接相机调用 `set_param(...)`，不写数据库。

### 保存到当前规格

如果当前槽位已有 `CameraConfig`：

- 调用 `update_camera_config(...)`。

如果没有：

- 调用 `create_camera_config(spec_id=..., camera_index=...)`。

保存后：

- 刷新槽位卡片。
- 发出 `data_changed` 或项目上下文中的配置变更信号。
- 项目工作台配置完成状态要能及时刷新。

## 需要保留的后端模型

保留并继续使用：

- `core.camera_config.CameraConfig`
- `create_camera_config`
- `update_camera_config`
- `list_camera_configs`
- `delete_camera_configs_for_spec`

不要新建第二套相机配置表。

## 原页面处理建议

### 推荐方案

以 `CameraManagementPage` 为基础扩展成新页面，因为它已经有：

- SDK 加载
- 扫描设备
- 连接相机
- 参数下发
- 预览
- 诊断

然后把 `CameraConfigPage` 的按规格卡片和保存逻辑迁入。

最终：

- 导航入口只保留一个“相机工作台”。
- 原 `CameraConfigPage` 可以删除或变成兼容 wrapper，但不要在 UI 里继续作为并列入口。

### 保守过渡方案

如果一次合并风险太大：

1. 先新增 `CameraWorkbenchPage`。
2. 暂时保留旧页面但从导航隐藏。
3. 等测试通过后再删除旧页面。

## UI 布局要求

必须避免当前“所有控件挤到一起”的问题。

建议结构：

```text
┌ 当前规格信息 ─────────────────────────────┐
│ 客户 / 项目 / 产品规格 / 相机数量 / 配置状态 │
└──────────────────────────────────────────┘

┌ 设备发现 ───────────┐ ┌ 规格相机槽位 ─────────────┐
│ SDK 状态             │ │ camera_01 上方 已绑定      │
│ 扫描按钮             │ │ camera_02 左侧 未绑定      │
│ 已发现设备列表        │ │ ...                       │
└─────────────────────┘ └──────────────────────────┘

┌ 当前槽位参数 ─────────────────────────────┐
│ 曝光 | 增益 | 触发模式 | 触发源              │
│ 行频 | 块高 | 像素格式 | ROI                │
│ 应用到相机 | 保存到当前规格 | 从规格加载       │
└──────────────────────────────────────────┘

┌ 预览 ─────────────────┐ ┌ 诊断 ────────────┐
│ 当前槽位图像预览        │ │ 行频/丢行/错误     │
└───────────────────────┘ └─────────────────┘
```

布局实现建议：

- 顶层用 `QSplitter` 或左右 `QHBoxLayout`。
- 发现设备和槽位列表可以左右分栏。
- 参数区使用 `QGridLayout`，不要再使用长 `QHBoxLayout`。
- 槽位状态使用 2x3 或自适应网格，不要横向无限排列。
- 每个输入控件设置合理 `minimumWidth`，按钮不要过宽。
- 不要嵌套过多卡片；分区清晰即可。

## 测试要求

至少增加或调整以下测试：

1. 当前规格有 `camera_count=2` 时，只渲染两个槽位。
2. 扫描到海康设备后，可以把设备信息填入选中槽位。
3. 点击保存后，`camera_configs` 中写入 `serial_number`、`ip_address`、`adapter_type`、曝光、增益等字段。
4. 已保存配置重新进入页面后能恢复到对应槽位。
5. `应用到相机` 不写数据库，只调用设备参数下发。
6. 项目工作台判断“相机配置已完成”时使用最新 `camera_configs`。
7. 布局测试：参数区应使用网格布局，不能退回所有控件横向堆叠。

可参考现有测试：

- `tests/test_camera_management_page.py`
- `tests/test_camera_config.py`
- `tests/test_project_workflow.py`
- `tests/test_project_workbench_page.py`

## 验证命令

建议至少运行：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_camera_management_page.py tests/test_camera_config.py tests/test_project_workflow.py tests/test_project_workbench_page.py -q -ra --tb=short
```

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check desktop_app\pages\camera_management_page.py desktop_app\pages\camera_config_page.py desktop_app\dialogs\camera_config_dialog.py tests\test_camera_management_page.py tests\test_camera_config.py
```

## 完成标准

完成后应满足：

- 用户只需要进入一个相机页面即可完成发现、绑定、调试、保存规格配置。
- 生产运行页读取的配置和用户在页面保存的配置一致。
- 项目工作台能及时感知当前规格是否已有相机配置。
- 页面布局清楚，不再出现扫描、设备、槽位、角色、按钮、参数全部挤在一行的问题。
- 海康真实链路 `hikrobot_line_scan` 保留并作为主路径，不被旧桩类覆盖。
