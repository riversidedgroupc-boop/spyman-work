# Camera Workbench UI Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `CameraWorkbenchPage` 的静态界面骨架迁移到 Qt Designer 可编辑的 `.ui` 文件，同时保留 Python 中的相机绑定、动态槽位、预览、诊断和配置保存逻辑。

**Architecture:** 采用运行时加载 `.ui` 的方案 A：`desktop_app/ui/camera_workbench_page.ui` 管理静态布局和控件尺寸，`desktop_app/pages/camera_workbench_page.py` 通过 `QUiLoader` 加载界面并用 `findChild()` 绑定关键控件。动态槽位卡片仍由 Python 运行时生成，挂载到 `.ui` 预留的容器布局中。

**Tech Stack:** Python 3.12, PySide6, Qt Designer `.ui`, `QUiLoader`, pytest, ruff。

---

## 设计边界

这次不要把整页所有逻辑都搬进 `.ui`。`.ui` 只负责可视化布局；Python 继续负责状态和业务行为。

`.ui` 负责：

- 顶部上下文栏布局：客户、项目、规格、相机数、配置状态徽标。
- 相机槽位区域的静态容器：标题、扫描按钮、已发现数量、槽位挂载容器、全部连接按钮。
- 参数区域：曝光、增益、触发、触发源、行频、块高、像素格式、宽度、包大小、包间隔、缓存、翻转选项、应用/保存/加载按钮。
- 预览与诊断区域：预览画面标签、预览信息、预览按钮、诊断文本框。
- 控件大小、间距、拉伸比例、文字初始值、`objectName`。

Python 继续负责：

- `AppContext` 当前客户/项目/规格读取。
- `camera_count` 决定动态生成多少 `_SlotCardWidget`。
- `BindingStore` 读写。
- Hikrobot SDK 加载、扫描、连接、取流、预览刷新。
- `camera_configs` 创建、更新、加载。
- 语言切换和主题刷新。
- 测试和异常提示。

## 文件结构

新增文件：

- `desktop_app/ui/camera_workbench_page.ui`  
  Qt Designer 管理的页面静态布局文件。

- `desktop_app/ui_loader.py`  
  统一封装 `.ui` 运行时加载，避免页面里重复写 `QFile` / `QUiLoader` 代码。

修改文件：

- `desktop_app/pages/camera_workbench_page.py`  
  删除或弱化 `_build_context_bar()`、`_build_param_section()`、`_build_preview_diag_section()` 的手写布局，改为加载 `.ui` 并绑定控件。

- `tests/test_camera_workbench_page.py`  
  增加 `.ui` 加载、关键控件存在、动态槽位挂载、参数控件绑定、信号连接的测试。

可选修改：

- `pyproject.toml`  
  如果当前项目没有把 `desktop_app/ui/*.ui` 纳入打包，需要补充打包规则。先检查现有打包方式再决定。

## Qt Designer 命名规范

所有需要 Python 访问的控件必须设置稳定 `objectName`。建议使用以下名称，不要用 Designer 默认的 `pushButton`、`label_3`。

顶部上下文栏：

```text
contextBar
ctxCustomerLabel
ctxCustomerValue
ctxProjectLabel
ctxProjectValue
ctxSpecLabel
ctxSpecValue
ctxCountLabel
ctxCountValue
ctxBadge
```

槽位区域：

```text
slotGroup
slotTitle
scanButton
foundLabel
slotGridHost
connectAllButton
```

参数区域：

```text
paramGroup
paramTitle
paramGrid
exposureSpin
gainSpin
triggerCombo
triggerSourceCombo
lineRateSpin
blockHeightSpin
pixelFormatCombo
widthSpin
packetSizeSpin
interDelaySpin
bufferSpin
reverseXCheck
reverseYCheck
applyButton
saveButton
loadButton
```

预览与诊断区域：

```text
previewDiagSplitter
previewGroup
previewLabel
previewInfo
previewStartButton
previewStopButton
snapshotButton
diagGroup
diagText
```

空状态：

```text
emptyPlaceholder
```

## UI 文件布局建议

`camera_workbench_page.ui` 根控件使用 `QWidget`，主布局使用 `QVBoxLayout`。

推荐层级：

```text
CameraWorkbenchPageUi QWidget
└── mainLayout QVBoxLayout
    ├── contextBar QFrame
    ├── slotGroup QGroupBox
    │   └── slotGroupLayout QVBoxLayout
    │       ├── slotHeaderLayout QHBoxLayout
    │       ├── slotGridHost QWidget
    │       └── connectAllRow QHBoxLayout
    ├── paramGroup QGroupBox
    │   └── paramGroupLayout QVBoxLayout
    │       ├── paramTitle QLabel
    │       ├── paramGrid QGridLayout
    │       └── paramButtonRow QHBoxLayout
    ├── previewDiagSplitter QSplitter
    └── emptyPlaceholder QLabel
```

`slotGridHost` 只作为动态槽位卡片的挂载点。Python 初始化时给它安装 `QGridLayout`，然后继续复用 `_rebuild_slots()` 的动态创建逻辑。

## Task 1: 新增 UI Loader

**Files:**

- Create: `desktop_app/ui_loader.py`
- Test: `tests/test_camera_workbench_page.py`

- [ ] **Step 1: 新增运行时 UI 加载器**

创建 `desktop_app/ui_loader.py`：

```python
"""Runtime Qt Designer .ui loader helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QWidget


def load_ui(ui_path: Path, parent: QWidget | None = None) -> QWidget:
    """Load a Qt Designer .ui file at runtime."""
    ui_file = QFile(str(ui_path))
    if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Unable to open UI file: {ui_path}")
    try:
        loaded = QUiLoader().load(ui_file, parent)
    finally:
        ui_file.close()

    if loaded is None:
        raise RuntimeError(f"Unable to load UI file: {ui_path}")
    return loaded
```

- [ ] **Step 2: 运行静态检查**

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check desktop_app\ui_loader.py
```

Expected:

```text
All checks passed!
```

## Task 2: 创建 Designer 可编辑的 `.ui` 骨架

**Files:**

- Create: `desktop_app/ui/camera_workbench_page.ui`
- Modify: `tests/test_camera_workbench_page.py`

- [ ] **Step 1: 用 Qt Designer 创建 UI 文件**

在 Qt Designer 中创建 `Widget` 类型窗体，保存为：

```text
desktop_app/ui/camera_workbench_page.ui
```

如果先不用 Designer，也可以先创建一个最小可加载骨架，后续再用 Designer 打开微调。根控件必须叫：

```text
CameraWorkbenchPageUi
```

- [ ] **Step 2: 设置关键 objectName**

按照上面的“Qt Designer 命名规范”设置所有 Python 会访问的控件。最少必须先有：

```text
contextBar
slotGroup
slotGridHost
paramGroup
paramTitle
exposureSpin
gainSpin
triggerCombo
applyButton
saveButton
loadButton
previewDiagSplitter
previewLabel
diagText
emptyPlaceholder
```

- [ ] **Step 3: 增加 UI 文件存在测试**

在 `tests/test_camera_workbench_page.py` 中增加：

```python
from pathlib import Path


def test_camera_workbench_ui_file_exists():
    ui_path = Path("desktop_app/ui/camera_workbench_page.ui")
    assert ui_path.exists()
    assert ui_path.read_text(encoding="utf-8").lstrip().startswith("<?xml")
```

- [ ] **Step 4: 运行测试**

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_camera_workbench_page.py::test_camera_workbench_ui_file_exists -q
```

Expected:

```text
1 passed
```

## Task 3: 在页面中加载 `.ui`

**Files:**

- Modify: `desktop_app/pages/camera_workbench_page.py`
- Test: `tests/test_camera_workbench_page.py`

- [ ] **Step 1: 导入 loader 和 Path**

在 `camera_workbench_page.py` 顶部加入：

```python
from pathlib import Path

from desktop_app.ui_loader import load_ui
```

如果文件里已有 `Path`，不要重复导入。

- [ ] **Step 2: 改造 `_setup_ui()`**

目标结构：

```python
def _setup_ui(self) -> None:
    outer = QVBoxLayout(self)
    outer.setContentsMargins(8, 8, 8, 8)
    outer.setSpacing(8)

    ui_path = Path(__file__).resolve().parents[1] / "ui" / "camera_workbench_page.ui"
    self._ui = load_ui(ui_path, self)
    outer.addWidget(self._ui)

    self._bind_ui_objects()
    self._install_dynamic_layouts()
    self._wire_ui_signals()
```

- [ ] **Step 3: 新增 `_bind_ui_objects()`**

示例：

```python
def _require_child(self, widget_type: type[QWidget], name: str):
    child = self._ui.findChild(widget_type, name)
    if child is None:
        raise RuntimeError(f"Missing widget in camera_workbench_page.ui: {name}")
    return child


def _bind_ui_objects(self) -> None:
    self._context_bar = self._require_child(QFrame, "contextBar")
    self._slot_group = self._require_child(QGroupBox, "slotGroup")
    self._slot_title = self._require_child(QLabel, "slotTitle")
    self._scan_btn = self._require_child(QPushButton, "scanButton")
    self._found_label = self._require_child(QLabel, "foundLabel")
    self._slot_grid_host = self._require_child(QWidget, "slotGridHost")
    self._connect_all_btn = self._require_child(QPushButton, "connectAllButton")

    self._param_group = self._require_child(QGroupBox, "paramGroup")
    self._param_title = self._require_child(QLabel, "paramTitle")
    self._exposure_spin = self._require_child(QDoubleSpinBox, "exposureSpin")
    self._gain_spin = self._require_child(QDoubleSpinBox, "gainSpin")
    self._trigger_combo = self._require_child(QComboBox, "triggerCombo")
    self._trigger_src_combo = self._require_child(QComboBox, "triggerSourceCombo")
    self._line_rate_spin = self._require_child(QSpinBox, "lineRateSpin")
    self._block_h_spin = self._require_child(QSpinBox, "blockHeightSpin")
    self._pixel_fmt_combo = self._require_child(QComboBox, "pixelFormatCombo")
    self._width_spin = self._require_child(QSpinBox, "widthSpin")
    self._pkt_size_spin = self._require_child(QSpinBox, "packetSizeSpin")
    self._inter_delay_spin = self._require_child(QSpinBox, "interDelaySpin")
    self._buffer_spin = self._require_child(QSpinBox, "bufferSpin")
    self._reverse_x_cb = self._require_child(QCheckBox, "reverseXCheck")
    self._reverse_y_cb = self._require_child(QCheckBox, "reverseYCheck")
    self._apply_btn = self._require_child(QPushButton, "applyButton")
    self._save_btn = self._require_child(QPushButton, "saveButton")
    self._load_btn = self._require_child(QPushButton, "loadButton")

    self._preview_diag_splitter = self._require_child(QSplitter, "previewDiagSplitter")
    self._preview_label = self._require_child(QLabel, "previewLabel")
    self._preview_info = self._require_child(QLabel, "previewInfo")
    self._preview_start_btn = self._require_child(QPushButton, "previewStartButton")
    self._preview_stop_btn = self._require_child(QPushButton, "previewStopButton")
    self._snapshot_btn = self._require_child(QPushButton, "snapshotButton")
    self._diag_text = self._require_child(QTextEdit, "diagText")
    self._empty_placeholder = self._require_child(QLabel, "emptyPlaceholder")
```

- [ ] **Step 4: 新增 `_install_dynamic_layouts()`**

```python
def _install_dynamic_layouts(self) -> None:
    self._slot_grid = QGridLayout(self._slot_grid_host)
    self._slot_grid.setSpacing(10)
```

- [ ] **Step 5: 新增 `_wire_ui_signals()`**

```python
def _wire_ui_signals(self) -> None:
    self._scan_btn.clicked.connect(self._on_scan)
    self._connect_all_btn.clicked.connect(self._on_connect_all)
    self._apply_btn.clicked.connect(self._on_apply_params)
    self._save_btn.clicked.connect(self._on_save_to_spec)
    self._load_btn.clicked.connect(self._on_load_from_spec)
    self._preview_start_btn.clicked.connect(self._on_start_preview)
    self._preview_stop_btn.clicked.connect(self._on_stop_preview)
    self._snapshot_btn.clicked.connect(self._on_snapshot)
```

- [ ] **Step 6: 运行现有测试**

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_camera_workbench_page.py -q -ra --tb=short
```

Expected:

```text
all tests passed
```

## Task 4: 把参数默认值从 Python 迁移到 `.ui`

**Files:**

- Modify: `desktop_app/ui/camera_workbench_page.ui`
- Modify: `desktop_app/pages/camera_workbench_page.py`
- Test: `tests/test_camera_workbench_page.py`

- [ ] **Step 1: 在 Qt Designer 设置参数控件属性**

设置这些默认值：

```text
exposureSpin: min=1.0, max=1000000.0, value=5000.0, decimals=1, suffix=" us"
gainSpin: min=0.0, max=40.0, value=1.0, decimals=1, suffix=" dB"
lineRateSpin: min=100, max=200000, value=20000, suffix=" Hz"
blockHeightSpin: min=64, max=8192, value=1024
widthSpin: min=256, max=8192, value=2048
packetSizeSpin: min=1500, max=65535, value=9000
interDelaySpin: min=0, max=10000, value=0, suffix=" us"
bufferSpin: min=1, max=256, value=16
```

ComboBox 默认选项：

```text
triggerCombo: Off, On
triggerSourceCombo: Line0, Line1, Line2, Line3, Software
pixelFormatCombo: Mono8, Mono10, Mono12, BayerRG8, RGB8
```

- [ ] **Step 2: 删除 `_add_param_field()` 动态创建逻辑**

迁移完成后，`_build_param_section()` 和 `_add_param_field()` 不再需要。删除前先确认没有其他方法调用：

```powershell
rg -n "_build_param_section|_add_param_field" desktop_app\pages\camera_workbench_page.py
```

Expected:

```text
only obsolete definitions remain
```

- [ ] **Step 3: 保留业务读取字段名**

不要改这些成员名，因为保存/加载参数逻辑依赖它们：

```text
self._exposure_spin
self._gain_spin
self._trigger_combo
self._trigger_src_combo
self._line_rate_spin
self._block_h_spin
self._pixel_fmt_combo
self._width_spin
self._pkt_size_spin
self._inter_delay_spin
self._buffer_spin
self._reverse_x_cb
self._reverse_y_cb
```

- [ ] **Step 4: 补参数默认值测试**

在 `tests/test_camera_workbench_page.py` 中增加：

```python
def test_param_controls_loaded_from_ui_have_expected_defaults(workbench_page_with_spec):
    page = workbench_page_with_spec

    assert page._exposure_spin.value() == 5000.0
    assert page._gain_spin.value() == 1.0
    assert page._trigger_combo.count() == 2
    assert page._trigger_combo.itemText(0) == "Off"
    assert page._trigger_src_combo.itemText(4) == "Software"
    assert page._line_rate_spin.value() == 20000
    assert page._block_h_spin.value() == 1024
    assert page._pixel_fmt_combo.itemText(0) == "Mono8"
    assert page._width_spin.value() == 2048
    assert page._pkt_size_spin.value() == 9000
    assert page._buffer_spin.value() == 16
```

- [ ] **Step 5: 运行测试**

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_camera_workbench_page.py -q -ra --tb=short
```

Expected:

```text
all tests passed
```

## Task 5: 处理主题和语言刷新

**Files:**

- Modify: `desktop_app/pages/camera_workbench_page.py`
- Test: `tests/test_camera_workbench_page.py`

- [ ] **Step 1: 保留 `_refresh_text()`，但只更新运行时文本**

`.ui` 里的初始文字可以作为 Designer 预览用。程序运行时仍由 `tr()` 刷新：

```python
def _refresh_text(self) -> None:
    self._scan_btn.setText("🔍 " + tr("camera_workbench.scan_devices"))
    self._connect_all_btn.setText(tr("camera.connect_all"))
    self._apply_btn.setText(tr("camera_workbench.apply_to_camera"))
    self._save_btn.setText(tr("camera_workbench.save_to_spec"))
    self._load_btn.setText(tr("camera_workbench.load_from_spec"))
    self._preview_start_btn.setText(tr("camera.start_preview"))
    self._preview_stop_btn.setText(tr("camera.stop_preview"))
    self._snapshot_btn.setText(tr("camera.snapshot"))
    self._empty_placeholder.setText(tr("camera_workbench.empty_spec"))
    self._refresh_context_bar()
```

如果原方法还负责槽位卡片文本，保留那部分逻辑。

- [ ] **Step 2: 主题刷新不要重建 UI**

`_on_theme_changed()` 只刷新样式和动态卡片状态，不重新 load `.ui`。否则会丢失已连接信号和运行时状态。

- [ ] **Step 3: 运行语言刷新相关测试**

如果已有语言测试，运行对应测试；否则至少运行：

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_camera_workbench_page.py -q -ra --tb=short
```

## Task 6: 打包检查

**Files:**

- Possibly Modify: `packaging/pyinstaller.spec`
- Possibly Modify: `pyproject.toml`

- [ ] **Step 1: 检查打包配置是否包含 `.ui`**

```powershell
rg -n "datas|desktop_app.*ui|\\.ui|pyinstaller" packaging pyproject.toml
```

- [ ] **Step 2: 如果 PyInstaller 没有包含 `.ui`，补 datas**

在 `packaging/pyinstaller.spec` 的 `datas` 中加入类似配置：

```python
datas=[
    ("desktop_app/ui/*.ui", "desktop_app/ui"),
]
```

实际写法要遵循当前 spec 文件已有风格，不要覆盖已有 `datas`。

- [ ] **Step 3: 本地验证 UI 文件路径**

增加一个路径解析函数会更稳：

```python
def ui_file_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "ui" / name
```

如果项目已有资源路径工具，优先复用项目现有工具。

## Task 7: 人工 Designer 微调流程

**Files:**

- Modify: `desktop_app/ui/camera_workbench_page.ui`

- [ ] **Step 1: 用 Qt Designer 打开**

```powershell
pyside6-designer desktop_app\ui\camera_workbench_page.ui
```

如果命令不存在，先确认当前 Python 环境是否安装 PySide6 Designer 工具：

```powershell
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pip show PySide6
```

- [ ] **Step 2: 可安全调整的内容**

可以在 Designer 中直接调整：

- 控件文字。
- label 宽度。
- spinbox 宽度和高度。
- grid layout 行列间距。
- groupbox 标题。
- splitter 默认比例。
- 按钮顺序。
- stretch factor。

- [ ] **Step 3: 不要在 Designer 中破坏这些内容**

不要改：

- 已列出的 `objectName`。
- 控件类型，例如不要把 `exposureSpin` 从 `QDoubleSpinBox` 改成 `QLineEdit`。
- `slotGridHost` 的用途。
- 动态槽位卡片相关 Python 类 `_SlotCardWidget`。

## 验收标准

迁移完成后必须满足：

- Qt Designer 可以直接打开 `desktop_app/ui/camera_workbench_page.ui`。
- 修改 `.ui` 中控件尺寸后，重新启动应用即可生效，不需要运行 `pyside6-uic`。
- 相机槽位仍按当前产品规格 `camera_count` 动态生成。
- 扫描、绑定、连接、预览、诊断、保存到当前规格、从规格加载行为不变。
- `tests/test_camera_workbench_page.py` 全部通过。
- `ruff check desktop_app/pages/camera_workbench_page.py desktop_app/ui_loader.py tests/test_camera_workbench_page.py` 通过。

## 风险和处理

### 风险 1: `.ui` objectName 被手动改掉

处理：`_require_child()` 启动时直接报明确错误，例如：

```text
Missing widget in camera_workbench_page.ui: exposureSpin
```

### 风险 2: 打包后找不到 `.ui`

处理：优先修正 PyInstaller `datas`，不要退回到 `pyside6-uic`。你想用 Designer 直接微调，运行时 `.ui` 是核心能力。

### 风险 3: 动态槽位很难放进 Designer

处理：不要把槽位卡片做成固定 `.ui` 控件。Designer 只提供 `slotGridHost`，Python 继续动态添加 `_SlotCardWidget`。

### 风险 4: 语言切换和 Designer 初始文字冲突

处理：Designer 初始文字只用于预览；运行时由 `_refresh_text()` 覆盖。

## 建议执行顺序

1. 先完成 `ui_loader.py`。
2. 创建最小 `.ui` 骨架并确保能加载。
3. 迁移上下文栏和参数区。
4. 迁移预览/诊断区。
5. 保留动态槽位逻辑，只改挂载点。
6. 最后处理打包和 Designer 微调。

不要一次性删除原手写布局。每迁移一个区域，就跑一次 `tests/test_camera_workbench_page.py`，确认没有破坏现有相机逻辑。
