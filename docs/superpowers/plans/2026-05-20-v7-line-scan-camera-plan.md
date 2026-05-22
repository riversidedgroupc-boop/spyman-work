# V7 海康线扫相机接入 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 copper-defect-eval-tool (v0.6.0) 升级为支持 1-6 台海康 GigE 线扫相机稳定接入的现场联调版

**Architecture:** 新建 `src/device/camera/` 设备层（LineScanDevice 接口 + 海康实现 + 拼图/切片 + 多相机管理），重构 `runtime/` 流水线支持独立线程采集和 Tile 推理，UI 改为自适应网格

**Tech Stack:** Python 3.12+, PySide6, ctypes (MVS SDK), NumPy, OpenCV, SQLite

---

## 文件结构总览

```
新增:
  src/device/__init__.py
  src/device/camera/__init__.py
  src/device/camera/line_scan/__init__.py
  src/device/camera/line_scan/interface.py
  src/device/camera/line_scan/types.py
  src/device/camera/line_scan/block_builder.py
  src/device/camera/line_scan/tile_generator.py
  src/device/camera/line_scan/encoder_mapper.py
  src/device/camera/hikrobot/__init__.py
  src/device/camera/hikrobot/sdk_loader.py
  src/device/camera/hikrobot/hikrobot_camera.py
  src/device/camera/hikrobot/error_code.py
  src/device/camera/hikrobot/MvImport/  (复制自 bolt, ~50 files)
  src/device/camera/manager/__init__.py
  src/device/camera/manager/camera_manager.py
  src/device/camera/manager/health_monitor.py
  src/device/camera/simulator/__init__.py
  src/device/camera/simulator/virtual_line_scan.py
  desktop_app/pages/device/__init__.py
  desktop_app/pages/device/commissioning_panel.py
  tests/device/__init__.py
  tests/device/test_line_scan_interface.py
  tests/device/test_block_builder.py
  tests/device/test_tile_generator.py
  tests/device/test_virtual_camera.py
  tests/device/test_camera_manager.py

修改:
  runtime/acquisition_pipeline.py
  runtime/inference_pipeline.py
  runtime/encoder_reader.py
  desktop_app/pages/production_run_page.py
  desktop_app/pages/camera_config_page.py
  core/camera_config.py
  core/storage.py
  pyproject.toml
```

---

## Phase 1: 海康单相机 MVP

### Task 1.1: 复制 MVS SDK Python 绑定到项目

**Files:**
- Create: `src/device/camera/hikrobot/MvImport/` (目录，从 bolt 复制)

- [ ] **Step 1: 复制 MvImport 文件**

```bash
cp -r "D:/work/bolt/src/MvImport" "D:/work/copper-defect-eval-tool/src/device/camera/hikrobot/MvImport"
```

- [ ] **Step 2: 验证文件复制成功**

```bash
ls "D:/work/copper-defect-eval-tool/src/device/camera/hikrobot/MvImport/MvCameraControl_class.py"
ls "D:/work/copper-defect-eval-tool/src/device/camera/hikrobot/MvImport/MvCameraControl.dll"
```

Expected: 两个文件都存在。

- [ ] **Step 3: Commit**

```bash
git add src/device/camera/hikrobot/MvImport/
git commit -m "feat: copy MVS SDK Python bindings from bolt project"
```

---

### Task 1.2: 创建设备数据类型定义

**Files:**
- Create: `src/device/__init__.py`
- Create: `src/device/camera/__init__.py`
- Create: `src/device/camera/line_scan/__init__.py`
- Create: `src/device/camera/line_scan/types.py`

- [ ] **Step 1: 创建设备层目录和 __init__.py**

```bash
mkdir -p "D:/work/copper-defect-eval-tool/src/device/camera/line_scan"
mkdir -p "D:/work/copper-defect-eval-tool/src/device/camera/hikrobot"
mkdir -p "D:/work/copper-defect-eval-tool/src/device/camera/manager"
mkdir -p "D:/work/copper-defect-eval-tool/src/device/camera/simulator"
```

Write `src/device/__init__.py`:
```python
"""Device abstraction layer — cameras, encoders, PLC, etc."""
```

Write `src/device/camera/__init__.py`:
```python
"""Camera device abstraction — line scan, area scan, virtual."""
```

Write `src/device/camera/line_scan/__init__.py`:
```python
"""Line scan camera interfaces and image block construction."""
```

- [ ] **Step 2: 写 types.py**

Write `src/device/camera/line_scan/types.py`:
```python
"""Shared types for line scan camera device layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DeviceInfo:
    """Information about a discovered camera device."""
    vendor: str = ""
    model: str = ""
    serial_number: str = ""
    ip_address: str = ""
    mac_address: str = ""
    transport_layer: str = ""  # "GigE", "USB", etc.
    user_defined_name: str = ""


@dataclass
class CameraStatus:
    """Real-time status of a connected camera."""
    camera_id: str = ""
    vendor: str = ""
    model: str = ""
    serial_number: str = ""
    ip_address: str = ""
    connected: bool = False
    grabbing: bool = False
    line_rate: float = 0.0
    received_line_count: int = 0
    dropped_line_count: int = 0
    timeout_count: int = 0
    block_count: int = 0
    last_error_code: int = 0
    last_error_message: str = ""
    fps_or_line_rate: float = 0.0
    last_frame_time: float = 0.0


@dataclass
class FramePacket:
    """A single line (or few lines) of data from a line scan camera."""
    camera_id: str = ""
    frame_id: int = 0
    timestamp_ns: int = 0
    encoder_count: int = 0
    width: int = 0
    height: int = 1  # usually 1 for line scan
    pixel_format: str = "Mono8"
    line_data: np.ndarray | None = None  # shape: (height, width)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineScanImageBlock:
    """A 2D image block stitched from consecutive line scan lines."""
    block_id: str = ""
    camera_id: str = ""
    start_frame_id: int = 0
    end_frame_id: int = 0
    start_encoder_count: int = 0
    end_encoder_count: int = 0
    start_meter: float = 0.0
    end_meter: float = 0.0
    width: int = 0
    height: int = 0
    image: np.ndarray | None = None  # shape: (height, width)
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0


@dataclass
class ImageTile:
    """A fixed-size tile sliced from a LineScanImageBlock for model input."""
    tile_id: str = ""
    block_id: str = ""
    camera_id: str = ""
    x0: int = 0
    y0: int = 0
    width: int = 320
    height: int = 320
    image: np.ndarray | None = None  # shape: (320, 320, 3)
    meter_start: float = 0.0
    meter_end: float = 0.0
```

- [ ] **Step 3: Commit**

```bash
git add src/device/ src/device/camera/ src/device/camera/line_scan/
git commit -m "feat: add line scan device types (DeviceInfo, FramePacket, LineScanImageBlock, ImageTile)"
```

---

### Task 1.3: 创建 LineScanDevice 抽象接口

**Files:**
- Create: `src/device/camera/line_scan/interface.py`
- Test: `tests/device/test_line_scan_interface.py`

- [ ] **Step 1: 写 interface.py**

Write `src/device/camera/line_scan/interface.py`:
```python
"""Line scan camera abstract interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket


class LineScanDevice(ABC):
    """Unified interface for line scan cameras (Hikrobot, Basler, virtual, etc.)."""

    @staticmethod
    @abstractmethod
    def enumerate_devices() -> list[DeviceInfo]:
        """Discover available devices. Returns list of DeviceInfo."""
        ...

    @abstractmethod
    def open(self, serial_number: str) -> bool:
        """Connect to device by serial number. Return True on success."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Disconnect and release resources."""
        ...

    @abstractmethod
    def start_grabbing(self) -> bool:
        """Start line data acquisition. Return True on success."""
        ...

    @abstractmethod
    def stop_grabbing(self) -> None:
        """Stop line data acquisition."""
        ...

    @abstractmethod
    def get_status(self) -> CameraStatus:
        """Return current camera status."""
        ...

    @abstractmethod
    def set_param(self, name: str, value: object) -> None:
        """Set a camera parameter by name (e.g. 'ExposureTime', 'LineRate')."""
        ...

    @abstractmethod
    def get_param(self, name: str) -> object:
        """Get a camera parameter value."""
        ...

    @abstractmethod
    def register_line_callback(
        self, callback: Callable[[FramePacket], None]
    ) -> None:
        """Register a callback invoked for each line (or block of lines) received."""
        ...

    @abstractmethod
    def unregister_line_callback(self) -> None:
        """Remove the current line callback."""
        ...
```

- [ ] **Step 2: 写接口一致性测试**

Write `tests/device/test_line_scan_interface.py`:
```python
"""Verify LineScanDevice ABC enforces interface contract."""
import pytest

from src.device.camera.line_scan.interface import LineScanDevice


def test_cannot_instantiate_abc_directly():
    """LineScanDevice is abstract and cannot be instantiated."""
    with pytest.raises(TypeError):
        LineScanDevice()  # type: ignore[abstract]


class PartialImpl(LineScanDevice):
    """Missing all abstract methods — should not be instantiable."""

    @staticmethod
    def enumerate_devices():
        return []


def test_partial_implementation_still_abstract():
    """Implementing only some methods is not enough."""
    with pytest.raises(TypeError):
        PartialImpl()  # type: ignore[abstract]


def test_full_implementation_instantiates():
    """A class implementing all abstract methods can be created."""

    class FullImpl(LineScanDevice):
        @staticmethod
        def enumerate_devices():
            return []

        def open(self, serial_number):
            return True

        def close(self):
            pass

        def start_grabbing(self):
            return True

        def stop_grabbing(self):
            pass

        def get_status(self):
            from src.device.camera.line_scan.types import CameraStatus
            return CameraStatus(connected=True)

        def set_param(self, name, value):
            pass

        def get_param(self, name):
            return None

        def register_line_callback(self, callback):
            pass

        def unregister_line_callback(self):
            pass

    cam = FullImpl()
    assert cam is not None
```

- [ ] **Step 3: 运行接口测试**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/device/test_line_scan_interface.py -v
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/device/camera/line_scan/interface.py tests/device/test_line_scan_interface.py
git commit -m "feat: add LineScanDevice abstract interface with tests"
```

---

### Task 1.4: 创建虚拟线扫相机（开发/测试用）

**Files:**
- Create: `src/device/camera/simulator/__init__.py`
- Create: `src/device/camera/simulator/virtual_line_scan.py`
- Test: `tests/device/test_virtual_camera.py`

- [ ] **Step 1: 写 virtual_line_scan.py**

Write `src/device/camera/simulator/__init__.py`:
```python
"""Virtual/simulated line scan cameras for development and testing."""
```

Write `src/device/camera/simulator/virtual_line_scan.py`:
```python
"""Virtual line scan camera — generates synthetic line data for development/testing.

Simulates a line scan camera producing 2048-pixel-wide lines with optional defects.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from threading import Thread, Event

import numpy as np

from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket


class VirtualLineScanCamera(LineScanDevice):
    """Simulated line scan camera with configurable width, line rate, and defects."""

    def __init__(self, width: int = 2048, line_rate: float = 20000.0) -> None:
        self._width = width
        self._line_rate = line_rate
        self._connected = False
        self._grabbing = False
        self._serial = f"VIRTUAL_{id(self):08X}"
        self._line_count = 0
        self._callback: Callable[[FramePacket], None] | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()
        self._params: dict[str, object] = {
            "ExposureTime": 20.0,
            "Gain": 0.0,
            "LineRate": line_rate,
            "PixelFormat": "Mono8",
            "Width": width,
            "TriggerMode": "Off",
            "TriggerSource": "Line0",
        }

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]:
        return [
            DeviceInfo(
                vendor="Virtual",
                model="VirtualLineScan-2048",
                serial_number="VIRTUAL_00000001",
                ip_address="127.0.0.1",
                mac_address="00:00:00:00:00:01",
                transport_layer="Virtual",
                user_defined_name="Virtual Line Scan Camera",
            )
        ]

    def open(self, serial_number: str) -> bool:
        self._serial = serial_number
        self._connected = True
        self._line_count = 0
        return True

    def close(self) -> None:
        self.stop_grabbing()
        self._connected = False

    def start_grabbing(self) -> bool:
        if not self._connected:
            return False
        self._grabbing = True
        self._stop_event.clear()
        self._thread = Thread(target=self._acquisition_loop, daemon=True)
        self._thread.start()
        return True

    def stop_grabbing(self) -> None:
        self._grabbing = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id="Camera_Virtual",
            vendor="Virtual",
            model="VirtualLineScan-2048",
            serial_number=self._serial,
            ip_address="127.0.0.1",
            connected=self._connected,
            grabbing=self._grabbing,
            line_rate=self._line_rate,
            received_line_count=self._line_count,
        )

    def set_param(self, name: str, value: object) -> None:
        self._params[name] = value
        if name == "LineRate":
            self._line_rate = float(value)

    def get_param(self, name: str) -> object:
        return self._params.get(name)

    def register_line_callback(
        self, callback: Callable[[FramePacket], None]
    ) -> None:
        self._callback = callback

    def unregister_line_callback(self) -> None:
        self._callback = None

    def _acquisition_loop(self) -> None:
        """Generate synthetic line data at the configured line rate."""
        interval = 1.0 / max(self._line_rate, 1.0)
        line_data = np.zeros((1, self._width), dtype=np.uint8)  # reusable buffer

        while not self._stop_event.is_set():
            # Generate synthetic line with random noise + optional defect
            line_data[0, :] = np.random.randint(0, 5, size=self._width, dtype=np.uint8)

            # Occasionally inject a synthetic "defect" pattern
            if self._line_count % 500 == 0 and self._line_count > 0:
                defect_start = self._width // 2 - 50
                defect_end = self._width // 2 + 50
                line_data[0, defect_start:defect_end] = np.clip(
                    np.random.normal(180, 30, defect_end - defect_start), 0, 255
                ).astype(np.uint8)

            self._line_count += 1

            if self._callback is not None:
                packet = FramePacket(
                    camera_id=self._serial,
                    frame_id=self._line_count,
                    timestamp_ns=time.time_ns(),
                    encoder_count=self._line_count,
                    width=self._width,
                    height=1,
                    pixel_format="Mono8",
                    line_data=line_data.copy(),
                )
                try:
                    self._callback(packet)
                except Exception:
                    pass

            time.sleep(interval)
```

- [ ] **Step 2: 写虚拟相机测试**

Write `tests/device/test_virtual_camera.py`:
```python
"""Tests for VirtualLineScanCamera."""
import time

import numpy as np

from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera


def test_enumerate_returns_device():
    devices = VirtualLineScanCamera.enumerate_devices()
    assert len(devices) == 1
    assert devices[0].vendor == "Virtual"


def test_open_and_close():
    cam = VirtualLineScanCamera()
    assert cam.open("TEST_001")
    assert cam.get_status().connected
    cam.close()
    assert not cam.get_status().connected


def test_start_and_stop_grabbing():
    cam = VirtualLineScanCamera(width=1024, line_rate=1000.0)
    cam.open("TEST_002")
    assert cam.start_grabbing()
    assert cam.get_status().grabbing
    time.sleep(0.05)
    cam.stop_grabbing()
    assert not cam.get_status().grabbing


def test_line_callback_receives_packets():
    cam = VirtualLineScanCamera(width=512, line_rate=5000.0)
    received: list = []

    def on_line(packet):
        received.append(packet)

    cam.open("TEST_003")
    cam.register_line_callback(on_line)
    cam.start_grabbing()
    time.sleep(0.1)  # ~500 lines at 5000 Hz
    cam.stop_grabbing()

    assert len(received) > 10
    pkt = received[0]
    assert pkt.width == 512
    assert pkt.height == 1
    assert pkt.line_data.shape == (1, 512)
    assert pkt.line_data.dtype == np.uint8


def test_set_and_get_param():
    cam = VirtualLineScanCamera()
    cam.open("TEST_004")
    cam.set_param("ExposureTime", 50.0)
    assert cam.get_param("ExposureTime") == 50.0
    cam.set_param("LineRate", 10000.0)
    assert cam.get_param("LineRate") == 10000.0
```

- [ ] **Step 3: 运行测试**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/device/test_virtual_camera.py -v
```

Expected: 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/device/camera/simulator/ tests/device/test_virtual_camera.py
git commit -m "feat: add VirtualLineScanCamera for development/testing"
```

---

### Task 1.5: 创建 MVS SDK 加载器和错误码映射

**Files:**
- Create: `src/device/camera/hikrobot/__init__.py`
- Create: `src/device/camera/hikrobot/sdk_loader.py`
- Create: `src/device/camera/hikrobot/error_code.py`

- [ ] **Step 1: 写 sdk_loader.py**

Write `src/device/camera/hikrobot/__init__.py`:
```python
"""Hikrobot (Hikvision) MVS GigE line scan camera adapter."""
```

Write `src/device/camera/hikrobot/sdk_loader.py`:
```python
"""MVS SDK DLL loader — loads MvCameraControl.dll and initializes SDK.

The DLL search path is the MvImport directory adjacent to this file.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_MV_IMPORT = Path(__file__).parent / "MvImport"
_MV_IMPORT_STR = str(_MV_IMPORT.resolve())

logger = logging.getLogger(__name__)

SDK_LOADED = False
SDK_ERROR: str | None = None


def load_sdk() -> bool:
    """Load MVS SDK DLLs and make Python bindings importable.

    Returns True if SDK is ready. On first failure, sets SDK_ERROR.
    Caller may call repeatedly; subsequent calls return cached result.
    """
    global SDK_LOADED, SDK_ERROR

    if SDK_LOADED:
        return True
    if SDK_ERROR is not None:
        return False

    if not _MV_IMPORT.is_dir():
        SDK_ERROR = f"MVS SDK MvImport directory not found: {_MV_IMPORT_STR}"
        logger.error(SDK_ERROR)
        return False

    dll_path = _MV_IMPORT / "MvCameraControl.dll"
    if not dll_path.is_file():
        SDK_ERROR = f"MvCameraControl.dll not found in {_MV_IMPORT_STR}"
        logger.error(SDK_ERROR)
        return False

    # Add to sys.path so Python bindings can be imported
    if _MV_IMPORT_STR not in sys.path:
        sys.path.insert(0, _MV_IMPORT_STR)

    # chdir so WinDLL resolves dependency DLLs
    old_cwd = os.getcwd()
    try:
        os.chdir(_MV_IMPORT_STR)

        from MvCameraControl_class import MvCamera  # noqa: F401
        from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO  # noqa: F401
        from CameraParams_const import (  # noqa: F401
            MV_GIGE_DEVICE,
            MV_USB_DEVICE,
            MV_OK,
            MV_ACCESS_Exclusive,
            MV_TRIGGER_MODE_OFF,
            MV_TRIGGER_MODE_ON,
        )
        from MvErrorDefine_const import *  # noqa: F401

        SDK_LOADED = True
        logger.info("MVS SDK loaded successfully from %s", _MV_IMPORT_STR)
        return True
    except (ImportError, OSError) as e:
        SDK_ERROR = f"Failed to load MVS SDK: {e}"
        logger.error(SDK_ERROR)
        return False
    finally:
        try:
            os.chdir(old_cwd)
        except OSError:
            pass


def get_mv_import_path() -> str:
    """Return the absolute path to the MvImport directory."""
    return _MV_IMPORT_STR
```

Write `src/device/camera/hikrobot/error_code.py`:
```python
"""MVS SDK error code to human-readable Chinese message mapping."""
from __future__ import annotations

# Selected common error codes — full list in MvErrorDefine_const.py
ERROR_MAP: dict[int, str] = {
    0x00000000: "成功",
    0x80000001: "错误或无效的句柄",
    0x80000002: "不支持的相机操作",
    0x80000003: "函数参数错误",
    0x80000004: "函数调用顺序错误",
    0x80000005: "不允许的函数调用",
    0x80000006: "资源申请失败",
    0x80000007: "无权限",
    0x80000008: "超时",
    0x80000009: "缓冲区不足",
    0x8000000A: "无效的地址",
    0x8000000B: "重复操作",
    0x8000000C: "操作被取消",
    0x8000000D: "数据不足",
    0x80001000: "通用异常",
    0x80001001: "GigE 网络异常",
    0x80001002: "设备未连接",
    0x80001003: "设备已被其他程序占用",
    0x80001004: "设备断开连接",
    0x80001005: "设备连接失败",
    0x80001006: "取流失败",
    0x80001007: "参数设置失败",
    0x80001008: "参数读取失败",
    0x80001009: "触发失败",
    0x8000100A: "采集未开始",
    0x8000100B: "写入参数失败",
    0x8000100C: "读取参数失败",
}


def get_error_message(error_code: int) -> str:
    """Return Chinese error message for an MVS SDK error code."""
    return ERROR_MAP.get(error_code, f"未知错误 (0x{error_code:08X})")
```

- [ ] **Step 2: Commit**

```bash
git add src/device/camera/hikrobot/__init__.py src/device/camera/hikrobot/sdk_loader.py src/device/camera/hikrobot/error_code.py
git commit -m "feat: add MVS SDK loader and error code mapping"
```

---

### Task 1.6: 实现 HikrobotLineScanCamera

**Files:**
- Create: `src/device/camera/hikrobot/hikrobot_camera.py`

- [ ] **Step 1: 写 hikrobot_camera.py**

Write `src/device/camera/hikrobot/hikrobot_camera.py`:
```python
"""Hikrobot GigE line scan camera adapter implementing LineScanDevice."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from collections.abc import Callable
from ctypes import byref, c_ubyte, memset, sizeof
from pathlib import Path

import numpy as np

from src.device.camera.hikrobot.error_code import get_error_message
from src.device.camera.hikrobot.sdk_loader import SDK_LOADED, SDK_ERROR, load_sdk
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket

logger = logging.getLogger(__name__)


class HikrobotLineScanCamera(LineScanDevice):
    """Hikrobot GigE line scan camera via MVS SDK."""

    def __init__(self) -> None:
        self._handle: ctypes.c_void_p | None = None
        self._sdk_initialized: bool = False
        self._connected: bool = False
        self._grabbing: bool = False
        self._serial: str = ""
        self._callback: Callable[[FramePacket], None] | None = None
        self._line_count: int = 0
        self._last_error_code: int = 0
        self._last_error_msg: str = ""
        self._device_info: DeviceInfo | None = None
        self._params: dict[str, object] = {
            "ExposureTime": 20.0,
            "Gain": 0.0,
            "LineRate": 20000,
            "PixelFormat": "Mono8",
            "Width": 2048,
            "TriggerMode": "On",
            "TriggerSource": "Line0",
        }

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]:
        """Enumerate all GigE devices via MVS SDK."""
        if not load_sdk():
            return []

        try:
            from MvCameraControl_class import MvCamera
            from CameraParams_header import MV_CC_DEVICE_INFO_LIST
            from CameraParams_const import MV_GIGE_DEVICE, MV_OK
        except ImportError:
            return []

        st_dev_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, st_dev_list)

        if ret != MV_OK or st_dev_list.nDeviceNum == 0:
            return []

        devices: list[DeviceInfo] = []
        from ctypes import cast, POINTER
        from CameraParams_header import MV_CC_DEVICE_INFO

        for i in range(st_dev_list.nDeviceNum):
            pst_dev = cast(
                st_dev_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)
            ).contents

            if hasattr(pst_dev, "SpecialInfo") and hasattr(
                pst_dev.SpecialInfo, "stGigEInfo"
            ):
                gige = pst_dev.SpecialInfo.stGigEInfo
                ip_bytes = bytearray(gige.nCurrentIp)
                mac_bytes = bytearray(gige.nCurrentSubNetMask)  # actually MAC

                devices.append(
                    DeviceInfo(
                        vendor="Hikrobot",
                        model="HikrobotLineScan",
                        serial_number=str(getattr(gige, "chSerialNumber", b"")).strip(
                            "\x00"
                        ),
                        ip_address=".".join(
                            str(b) for b in ip_bytes[:4] if b != 0
                        ),
                        mac_address="",
                        transport_layer="GigE",
                        user_defined_name=str(
                            getattr(gige, "chUserDefinedName", b"")
                        ).strip("\x00"),
                    )
                )

        return devices

    def open(self, serial_number: str) -> bool:
        """Connect to the camera with the given serial number."""
        if not load_sdk():
            self._last_error_code = -1
            self._last_error_msg = SDK_ERROR or "MVS SDK not available"
            return False

        try:
            from MvCameraControl_class import MvCamera
            from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO
            from CameraParams_const import (
                MV_GIGE_DEVICE,
                MV_OK,
                MV_ACCESS_Exclusive,
            )

            # Initialize SDK (once)
            if not self._sdk_initialized:
                ret = MvCamera.MV_CC_Initialize()
                if ret != MV_OK:
                    self._last_error_code = ret
                    self._last_error_msg = get_error_message(ret)
                    return False
                self._sdk_initialized = True
                logger.info(
                    "MVS SDK initialized, version=0x%X",
                    MvCamera.MV_CC_GetSDKVersion(),
                )

            # Enumerate and find target
            st_dev_list = MV_CC_DEVICE_INFO_LIST()
            ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, st_dev_list)
            if ret != MV_OK or st_dev_list.nDeviceNum == 0:
                self._last_error_code = ret
                self._last_error_msg = "未发现 GigE 相机，请检查网线连接和 IP 配置"
                return False

            from ctypes import cast, POINTER

            target_dev = None
            for i in range(st_dev_list.nDeviceNum):
                pst_dev = cast(
                    st_dev_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)
                ).contents
                if hasattr(pst_dev, "SpecialInfo") and hasattr(
                    pst_dev.SpecialInfo, "stGigEInfo"
                ):
                    gige = pst_dev.SpecialInfo.stGigEInfo
                    serial = (
                        str(getattr(gige, "chSerialNumber", b"")).strip("\x00")
                    )
                    if serial == serial_number:
                        target_dev = pst_dev
                        break

            if target_dev is None:
                self._last_error_code = -1
                self._last_error_msg = (
                    f"未找到序列号为 {serial_number} 的相机"
                )
                return False

            # Create handle
            camera = MvCamera()
            ret = camera.MV_CC_CreateHandle(target_dev)
            if ret != MV_OK:
                self._last_error_code = ret
                self._last_error_msg = get_error_message(ret)
                return False

            # Open device
            ret = camera.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
            if ret != MV_OK:
                self._last_error_code = ret
                self._last_error_msg = get_error_message(ret)
                camera.MV_CC_DestroyHandle()
                return False

            self._handle = camera.handle
            self._serial = serial_number
            self._connected = True
            logger.info("Camera connected: serial=%s", serial_number)
            return True

        except Exception as e:
            self._last_error_code = -1
            self._last_error_msg = str(e)
            logger.exception("Camera open failed")
            return False

    def close(self) -> None:
        """Disconnect and release resources."""
        self.stop_grabbing()

        if self._handle is not None:
            try:
                from MvCameraControl_class import MvCamera
                MvCamera.MV_CC_CloseDevice(self._handle)
                MvCamera.MV_CC_DestroyHandle(self._handle)
            except Exception:
                logger.warning("Error during device close", exc_info=True)
            self._handle = None

        if self._sdk_initialized:
            try:
                from MvCameraControl_class import MvCamera
                MvCamera.MV_CC_Finalize()
            except Exception:
                pass
            self._sdk_initialized = False

        self._connected = False
        self._grabbing = False

    def start_grabbing(self) -> bool:
        """Start line data acquisition."""
        if not self._connected or self._handle is None:
            return False

        try:
            from MvCameraControl_class import MvCamera
            from CameraParams_const import MV_OK

            ret = MvCamera.MV_CC_StartGrabbing(self._handle)
            if ret != MV_OK:
                self._last_error_code = ret
                self._last_error_msg = get_error_message(ret)
                return False

            self._grabbing = True
            return True
        except Exception as e:
            self._last_error_code = -1
            self._last_error_msg = str(e)
            return False

    def stop_grabbing(self) -> None:
        """Stop line data acquisition."""
        if self._grabbing and self._handle is not None:
            try:
                from MvCameraControl_class import MvCamera
                MvCamera.MV_CC_StopGrabbing(self._handle)
            except Exception:
                pass
        self._grabbing = False

    def get_status(self) -> CameraStatus:
        """Return current camera status."""
        return CameraStatus(
            camera_id=f"Camera_{self._serial}",
            vendor="Hikrobot",
            model=self._device_info.model if self._device_info else "",
            serial_number=self._serial,
            connected=self._connected,
            grabbing=self._grabbing,
            line_rate=float(self._params.get("LineRate", 0)),
            received_line_count=self._line_count,
            last_error_code=self._last_error_code,
            last_error_message=self._last_error_msg,
        )

    def set_param(self, name: str, value: object) -> None:
        """Set a camera parameter."""
        self._params[name] = value
        if not self._connected or self._handle is None:
            return

        try:
            from MvCameraControl_class import MvCamera
            from CameraParams_const import MV_OK

            if isinstance(value, (int, float)):
                ret = MvCamera.MV_CC_SetFloatValue(
                    self._handle, name.encode(), ctypes.c_float(float(value))
                )
            elif isinstance(value, str):
                ret = MvCamera.MV_CC_SetEnumValue(
                    self._handle, name.encode(), value.encode()
                )
            elif isinstance(value, bool):
                ret = MvCamera.MV_CC_SetBoolValue(
                    self._handle, name.encode(), value
                )
            else:
                ret = MvCamera.MV_CC_SetStringValue(
                    self._handle, name.encode(), str(value).encode()
                )

            if ret != MV_OK:
                self._last_error_code = ret
                self._last_error_msg = f"设置 {name} 失败: {get_error_message(ret)}"
        except Exception as e:
            self._last_error_code = -1
            self._last_error_msg = str(e)

    def get_param(self, name: str) -> object:
        """Get a camera parameter value."""
        from MvCameraControl_class import MvCamera
        from CameraParams_const import MV_OK

        try:
            cf = ctypes.c_float()
            ret = MvCamera.MV_CC_GetFloatValue(
                self._handle, name.encode(), byref(cf)
            )
            if ret == MV_OK:
                return cf.value
        except Exception:
            pass
        return self._params.get(name)

    def register_line_callback(
        self, callback: Callable[[FramePacket], None]
    ) -> None:
        """Register callback for each line received."""
        self._callback = callback

    def unregister_line_callback(self) -> None:
        """Remove current line callback."""
        self._callback = None

    def get_last_error(self) -> tuple[int, str]:
        """Return (error_code, error_message) of last operation."""
        return self._last_error_code, self._last_error_msg
```

- [ ] **Step 2: Commit**

```bash
git add src/device/camera/hikrobot/hikrobot_camera.py
git commit -m "feat: implement HikrobotLineScanCamera with MVS SDK integration"
```

---

### Task 1.7: 单相机简单图像显示验证

**Files:**
- 不新增文件，通过脚本验证

- [ ] **Step 1: 写临时验证脚本 `scripts/verify_single_camera.py`**

Write `scripts/verify_single_camera.py`:
```python
"""Quick verification: enumerate cameras and test basic capture via virtual camera."""
import time
import cv2
import numpy as np

from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera

def main():
    print("=== 虚拟线扫相机单相机验证 ===\n")

    # Enumerate
    devices = VirtualLineScanCamera.enumerate_devices()
    print(f"枚举到 {len(devices)} 台设备:")
    for d in devices:
        print(f"  - {d.model} ({d.serial_number}) @ {d.ip_address}")

    # Connect
    cam = VirtualLineScanCamera(width=2048, line_rate=20000)
    cam.open(devices[0].serial_number)
    print(f"\n已连接: {cam.get_status().connected}")

    # Collect lines and build image block
    block = np.zeros((512, 2048), dtype=np.uint8)
    line_idx = 0
    target_height = 512

    def on_line(packet):
        nonlocal line_idx
        if line_idx < target_height and packet.line_data is not None:
            block[line_idx, :] = packet.line_data[0, :]
            line_idx += 1

    cam.register_line_callback(on_line)
    cam.start_grabbing()
    print("采集已启动，等待 512 行...")

    # Wait for enough lines
    start = time.time()
    while line_idx < target_height and (time.time() - start) < 5.0:
        time.sleep(0.01)

    cam.stop_grabbing()
    cam.close()

    print(f"收集了 {line_idx} 行")
    print(f"图像块尺寸: {block.shape}")

    if line_idx >= target_height:
        cv2.imwrite("D:/work/copper-defect-eval-tool/outputs/verify_block.png", block)
        print("图像块已保存到 outputs/verify_block.png")
    else:
        print("WARNING: 未收集到足够行数")

    print("\n=== 单相机验证完成 ===")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证脚本**

```bash
cd D:/work/copper-defect-eval-tool && python scripts/verify_single_camera.py
```

Expected: 枚举 1 台虚拟设备，收集 512 行，保存图像块到 outputs/verify_block.png。

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_single_camera.py
git commit -m "test: add single camera smoke test script"
```

---

## Phase 2: 线扫图像块生成

### Task 2.1: 实现 LineScanBlockBuilder

**Files:**
- Create: `src/device/camera/line_scan/block_builder.py`
- Test: `tests/device/test_block_builder.py`

- [ ] **Step 1: 写 block_builder.py**

Write `src/device/camera/line_scan/block_builder.py`:
```python
"""Line scan block builder — accumulates lines into fixed-height 2D image blocks."""
from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from src.device.camera.line_scan.types import FramePacket, LineScanImageBlock


class LineScanBlockBuilder:
    """Accumulates line scan data and emits fixed-height LineScanImageBlock objects.

    Each block has height = block_height (e.g. 1024 lines). When enough lines
    are accumulated, the block is emitted via on_block callback and the buffer resets.
    """

    def __init__(self, camera_id: str, block_height: int = 1024) -> None:
        if block_height < 1:
            raise ValueError(f"block_height must be >= 1, got {block_height}")

        self._camera_id = camera_id
        self._block_height = block_height
        self._on_block: Callable[[LineScanImageBlock], None] | None = None

        self._buffer: np.ndarray | None = None
        self._row = 0
        self._start_frame_id = 0
        self._end_frame_id = 0
        self._start_encoder_count = 0
        self._end_encoder_count = 0
        self._block_id = 0
        self._width = 0

    @property
    def camera_id(self) -> str:
        return self._camera_id

    @property
    def block_height(self) -> int:
        return self._block_height

    @property
    def current_row(self) -> int:
        return self._row

    def set_on_block(self, callback: Callable[[LineScanImageBlock], None]) -> None:
        self._on_block = callback

    def push_line(self, packet: FramePacket) -> None:
        """Push one line (or few lines) of data. May trigger a block emission."""
        if packet.line_data is None:
            return

        data = packet.line_data  # shape: (H', W) where H' is typically 1
        h, w = data.shape

        # Initialize or reinitialize buffer if width changed
        if self._buffer is None or self._width != w:
            self._buffer = np.zeros((self._block_height, w), dtype=np.uint8)
            self._width = w
            self._row = 0

        if self._row == 0:
            self._start_frame_id = packet.frame_id
            self._start_encoder_count = packet.encoder_count

        # Copy lines
        remaining = self._block_height - self._row
        lines_to_copy = min(h, remaining)
        self._buffer[self._row : self._row + lines_to_copy, :] = data[:lines_to_copy, :]
        self._row += lines_to_copy

        if self._row >= self._block_height:
            self._emit_block(packet)

    def _emit_block(self, last_packet: FramePacket) -> None:
        """Emit a completed block and reset."""
        if self._buffer is None:
            return

        self._end_frame_id = last_packet.frame_id
        self._end_encoder_count = last_packet.encoder_count

        block = LineScanImageBlock(
            block_id=f"{self._camera_id}_BLK_{self._block_id:06d}",
            camera_id=self._camera_id,
            start_frame_id=self._start_frame_id,
            end_frame_id=self._end_frame_id,
            start_encoder_count=self._start_encoder_count,
            end_encoder_count=self._end_encoder_count,
            start_meter=0.0,  # to be set by encoder mapper
            end_meter=0.0,
            width=self._width,
            height=self._block_height,
            image=self._buffer.copy(),
            timestamp_start=time.time(),
            timestamp_end=time.time(),
        )

        self._block_id += 1
        self._row = 0

        if self._on_block is not None:
            try:
                self._on_block(block)
            except Exception:
                pass

    def flush(self) -> LineScanImageBlock | None:
        """Emit any partial block. Returns None if buffer is empty."""
        if self._buffer is None or self._row == 0:
            return None

        partial = self._buffer[: self._row, :].copy()
        block = LineScanImageBlock(
            block_id=f"{self._camera_id}_BLK_{self._block_id:06d}_partial",
            camera_id=self._camera_id,
            start_frame_id=self._start_frame_id,
            end_frame_id=self._end_frame_id,
            start_encoder_count=self._start_encoder_count,
            end_encoder_count=self._end_encoder_count,
            start_meter=0.0,
            end_meter=0.0,
            width=self._width,
            height=self._row,
            image=partial,
            timestamp_start=time.time(),
            timestamp_end=time.time(),
        )
        self._row = 0
        return block

    def reset(self) -> None:
        """Reset buffer to empty state."""
        self._row = 0
        self._buffer = None
```

- [ ] **Step 2: 写 block_builder 测试**

Write `tests/device/test_block_builder.py`:
```python
"""Tests for LineScanBlockBuilder."""
import numpy as np

from src.device.camera.line_scan.block_builder import LineScanBlockBuilder
from src.device.camera.line_scan.types import FramePacket


def make_packet(frame_id: int, width: int = 100) -> FramePacket:
    data = np.full((1, width), fill_value=frame_id % 256, dtype=np.uint8)
    return FramePacket(
        camera_id="TEST",
        frame_id=frame_id,
        encoder_count=frame_id,
        width=width,
        height=1,
        line_data=data,
    )


def test_block_emitted_at_correct_height():
    """Block is emitted when block_height lines are accumulated."""
    builder = LineScanBlockBuilder(camera_id="C1", block_height=10)
    blocks: list = []
    builder.set_on_block(lambda b: blocks.append(b))

    for i in range(25):
        builder.push_line(make_packet(i, width=80))

    # 25 lines with block_height=10 -> 2 full blocks
    assert len(blocks) == 2
    assert blocks[0].height == 10
    assert blocks[0].width == 80
    assert blocks[0].start_frame_id == 0
    assert blocks[0].end_frame_id == 9  # last line in first block
    assert blocks[1].start_frame_id == 10
    assert blocks[1].end_frame_id == 19


def test_buffer_shape_correct():
    """Block image has correct shape."""
    builder = LineScanBlockBuilder(camera_id="C1", block_height=50)
    blocks: list = []
    builder.set_on_block(lambda b: blocks.append(b))

    for i in range(50):
        builder.push_line(make_packet(i, width=200))

    assert len(blocks) == 1
    assert blocks[0].image.shape == (50, 200)
    assert blocks[0].image.dtype == np.uint8


def test_flush_returns_partial_block():
    """flush() returns remaining lines as partial block."""
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)

    for i in range(5):
        builder.push_line(make_packet(i, width=50))

    partial = builder.flush()
    assert partial is not None
    assert partial.height == 5
    assert partial.image.shape == (5, 50)


def test_flush_returns_none_when_empty():
    """flush() returns None if no data accumulated."""
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)
    assert builder.flush() is None


def test_reset_clears_buffer():
    """reset() clears accumulated lines."""
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)

    for i in range(8):
        builder.push_line(make_packet(i))

    builder.reset()
    assert builder.current_row == 0
    assert builder.flush() is None
```

- [ ] **Step 3: 运行测试**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/device/test_block_builder.py -v
```

Expected: 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/device/camera/line_scan/block_builder.py tests/device/test_block_builder.py
git commit -m "feat: add LineScanBlockBuilder for line-to-image-block stitching"
```

---

### Task 2.2: 实现 ImageTileGenerator

**Files:**
- Create: `src/device/camera/line_scan/tile_generator.py`
- Test: `tests/device/test_tile_generator.py`

- [ ] **Step 1: 写 tile_generator.py**

Write `src/device/camera/line_scan/tile_generator.py`:
```python
"""Image tile generator — slices LineScanImageBlock into fixed-size model-input tiles."""
from __future__ import annotations

import numpy as np

from src.device.camera.line_scan.types import ImageTile, LineScanImageBlock


class TileGenerator:
    """Slices a LineScanImageBlock into fixed-size tiles with optional overlap.

    Tiles are square (tile_size × tile_size). Supports stride for overlapping windows.
    Origin is top-left of the block image.
    """

    def __init__(self, tile_size: int = 320, stride: int | None = None) -> None:
        if tile_size < 1:
            raise ValueError(f"tile_size must be >= 1, got {tile_size}")
        self._tile_size = tile_size
        self._stride = stride if stride is not None else tile_size
        if self._stride < 1:
            raise ValueError(f"stride must be >= 1, got {self._stride}")

    @property
    def tile_size(self) -> int:
        return self._tile_size

    @property
    def stride(self) -> int:
        return self._stride

    def slice_block(self, block: LineScanImageBlock) -> list[ImageTile]:
        """Slice a single block into tiles. Returns list of ImageTile."""
        if block.image is None:
            return []

        img = block.image  # shape: (H, W)
        h, w = img.shape

        # Convert grayscale to 3-channel if needed (model expects BGR)
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)

        tiles: list[ImageTile] = []
        y_positions = list(range(0, h - self._tile_size + 1, self._stride))
        x_positions = list(range(0, w - self._tile_size + 1, self._stride))

        # Ensure we cover the right/bottom edge
        if not y_positions or y_positions[-1] + self._tile_size < h:
            y_positions.append(max(0, h - self._tile_size))
        if not x_positions or x_positions[-1] + self._tile_size < w:
            x_positions.append(max(0, w - self._tile_size))

        block_meter_range = block.end_meter - block.start_meter

        for y0 in y_positions:
            for x0 in x_positions:
                tile_img = img[y0 : y0 + self._tile_size, x0 : x0 + self._tile_size].copy()

                # Calculate meter positions for this tile
                meter_start = block.start_meter + (y0 / max(h, 1)) * block_meter_range
                meter_end = block.start_meter + ((y0 + self._tile_size) / max(h, 1)) * block_meter_range

                tile_id = f"{block.block_id}_T_{y0:04d}_{x0:04d}"

                tiles.append(
                    ImageTile(
                        tile_id=tile_id,
                        block_id=block.block_id,
                        camera_id=block.camera_id,
                        x0=x0,
                        y0=y0,
                        width=self._tile_size,
                        height=self._tile_size,
                        image=tile_img,
                        meter_start=round(meter_start, 3),
                        meter_end=round(meter_end, 3),
                    )
                )

        return tiles

    def tile_to_original_coords(
        self, tile: ImageTile, det_x: int, det_y: int
    ) -> tuple[int, int]:
        """Convert a detection point in tile coords back to block coords.

        Args:
            tile: The ImageTile.
            det_x: X coordinate within the tile.
            det_y: Y coordinate within the tile.

        Returns:
            (x_in_block, y_in_block) coordinates.
        """
        return (tile.x0 + det_x, tile.y0 + det_y)
```

- [ ] **Step 2: 写 tile_generator 测试**

Write `tests/device/test_tile_generator.py`:
```python
"""Tests for TileGenerator."""
import numpy as np

from src.device.camera.line_scan.tile_generator import TileGenerator
from src.device.camera.line_scan.types import LineScanImageBlock


def make_block(width: int = 640, height: int = 640) -> LineScanImageBlock:
    img = np.random.randint(0, 255, (height, width), dtype=np.uint8)
    return LineScanImageBlock(
        block_id="BLK_000",
        camera_id="C1",
        start_frame_id=0,
        end_frame_id=height,
        width=width,
        height=height,
        image=img,
        start_meter=0.0,
        end_meter=1.0,
    )


def test_640_by_640_yields_4_tiles():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    tiles = gen.slice_block(block)
    assert len(tiles) == 4  # 2x2 grid


def test_exact_fit_produces_one_tile():
    gen = TileGenerator(tile_size=320)
    block = make_block(320, 320)
    tiles = gen.slice_block(block)
    assert len(tiles) == 1
    assert tiles[0].x0 == 0
    assert tiles[0].y0 == 0
    assert tiles[0].width == 320
    assert tiles[0].height == 320


def test_small_image_still_produces_one_tile():
    gen = TileGenerator(tile_size=320)
    block = make_block(200, 200)
    tiles = gen.slice_block(block)
    assert len(tiles) == 1  # padded to cover edge


def test_tile_image_is_3_channel():
    gen = TileGenerator(tile_size=320)
    block = make_block(320, 320)
    tiles = gen.slice_block(block)
    assert tiles[0].image.shape == (320, 320, 3)


def test_coordinate_conversion():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    tiles = gen.slice_block(block)

    # Tile at position (320, 320), detection at (50, 100) in tile
    tile = [t for t in tiles if t.x0 == 320 and t.y0 == 320][0]
    bx, by = gen.tile_to_original_coords(tile, 50, 100)
    assert bx == 370  # 320 + 50
    assert by == 420  # 320 + 100


def test_meter_position_monotonic():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    block.start_meter = 10.0
    block.end_meter = 12.0
    tiles = gen.slice_block(block)

    for t in tiles:
        assert t.meter_start <= t.meter_end
        assert 10.0 <= t.meter_start <= 12.0
```

- [ ] **Step 3: 运行测试**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/device/test_tile_generator.py -v
```

Expected: 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/device/camera/line_scan/tile_generator.py tests/device/test_tile_generator.py
git commit -m "feat: add TileGenerator for block-to-model-input slicing with coordinate mapping"
```

---

### Task 2.3: 实现 EncoderMapper（编码器→米数转换）

**Files:**
- Create: `src/device/camera/line_scan/encoder_mapper.py`

- [ ] **Step 1: 写 encoder_mapper.py**

Write `src/device/camera/line_scan/encoder_mapper.py`:
```python
"""Encoder-to-meter position mapper."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EncoderConfig:
    """Encoder configuration for line scan positioning."""
    enabled: bool = True
    pulses_per_revolution: int = 1000
    roller_diameter_mm: float = 100.0
    direction: int = 1  # 1 = forward, -1 = reverse
    meter_offset: float = 0.0
    zero_count: int = 0  # encoder count at zero position

    @property
    def pulses_per_mm(self) -> float:
        """Calculate pulses per millimeter from roller geometry."""
        import math
        circumference_mm = math.pi * self.roller_diameter_mm
        return self.pulses_per_revolution / circumference_mm

    @property
    def mm_per_pulse(self) -> float:
        return 1.0 / max(self.pulses_per_mm, 1e-9)


class EncoderMapper:
    """Converts encoder pulse counts to meter positions."""

    def __init__(self, config: EncoderConfig | None = None) -> None:
        self._config = config or EncoderConfig()
        self._zero_count = self._config.zero_count

    def reset_zero(self, current_count: int = 0) -> None:
        """Set the zero position to the given encoder count."""
        self._zero_count = current_count
        self._config.zero_count = current_count

    def set_meter_offset(self, offset: float) -> None:
        """Set a fixed meter offset (e.g. to align with mechanical reference)."""
        self._config.meter_offset = offset

    def count_to_meter(self, encoder_count: int) -> float:
        """Convert an encoder pulse count to meter position."""
        delta = (encoder_count - self._zero_count) * self._config.direction
        return delta / max(self._config.pulses_per_mm, 1e-9) / 1000.0 + self._config.meter_offset

    def meter_to_count(self, meter: float) -> int:
        """Convert meter position back to approximate encoder count."""
        delta_m = max(meter - self._config.meter_offset, 0.0)
        return self._zero_count + int(delta_m * 1000.0 * self._config.pulses_per_mm) * self._config.direction

    def calibrate(self, known_length_mm: float, measured_pulses: int) -> float:
        """Calibrate pulses_per_mm from a known distance and measured pulse count.

        Args:
            known_length_mm: Known physical length in millimeters.
            measured_pulses: Number of encoder pulses observed over that distance.

        Returns:
            Calculated pulses_per_mm value.
        """
        ppm = measured_pulses / known_length_mm
        # Update roller_diameter to match
        import math
        self._config.roller_diameter_mm = (
            self._config.pulses_per_revolution / (ppm * math.pi)
        )
        return ppm

    def meters_per_pixel(self, block_height: int) -> float:
        """Calculate meter distance represented by one pixel row in a block.

        Args:
            block_height: Number of pixel rows in the image block.

        Returns:
            Meters per pixel row.
        """
        return (
            block_height / max(self._config.pulses_per_mm, 1e-9) / 1000.0
        )

    @property
    def config(self) -> EncoderConfig:
        return self._config
```

- [ ] **Step 2: Commit**

```bash
git add src/device/camera/line_scan/encoder_mapper.py
git commit -m "feat: add EncoderMapper for encoder-count-to-meter-position conversion"
```

---

## Phase 3: 多相机管理

### Task 3.1: 实现 CameraManager

**Files:**
- Create: `src/device/camera/manager/__init__.py`
- Create: `src/device/camera/manager/camera_manager.py`
- Test: `tests/device/test_camera_manager.py`

- [ ] **Step 1: 写 camera_manager.py**

Write `src/device/camera/manager/__init__.py`:
```python
"""Multi-camera lifecycle management and health monitoring."""
```

Write `src/device/camera/manager/camera_manager.py`:
```python
"""Camera manager — manages 1-6 camera lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Callable

from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus, FramePacket, LineScanImageBlock

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages 1-6 line scan cameras: connect, start/stop, monitor.

    Each camera gets a slot indexed by camera_id (e.g. "Camera_01" through "Camera_06").
    Only enabled slots participate in acquisition.
    """

    MAX_CAMERAS = 6

    def __init__(self) -> None:
        self._cameras: dict[str, LineScanDevice] = {}
        self._enabled: dict[str, bool] = {}
        self._on_block: Callable[[LineScanImageBlock], None] | None = None

    def add_camera(self, camera_id: str, device: LineScanDevice, enabled: bool = True) -> None:
        """Register a camera device under the given camera_id."""
        if len(self._cameras) >= self.MAX_CAMERAS:
            raise RuntimeError(f"Maximum {self.MAX_CAMERAS} cameras reached")
        self._cameras[camera_id] = device
        self._enabled[camera_id] = enabled

    def remove_camera(self, camera_id: str) -> None:
        """Remove a camera and stop it if running."""
        if camera_id in self._cameras:
            self._cameras[camera_id].stop_grabbing()
            self._cameras[camera_id].close()
            del self._cameras[camera_id]
            del self._enabled[camera_id]

    def connect_all(self, serial_map: dict[str, str]) -> dict[str, bool]:
        """Connect all registered cameras by serial number.

        Args:
            serial_map: {camera_id: serial_number} mapping.

        Returns:
            {camera_id: success} mapping.
        """
        results: dict[str, bool] = {}
        for cam_id, serial in serial_map.items():
            if cam_id in self._cameras and self._enabled[cam_id]:
                results[cam_id] = self._cameras[cam_id].open(serial)
            else:
                results[cam_id] = False
        return results

    def disconnect_all(self) -> None:
        """Close all cameras."""
        for cam_id, device in self._cameras.items():
            try:
                device.stop_grabbing()
                device.close()
            except Exception:
                logger.exception("Error closing camera %s", cam_id)

    def start_all(self) -> dict[str, bool]:
        """Start grabbing on all enabled cameras."""
        results: dict[str, bool] = {}
        for cam_id, device in self._cameras.items():
            if self._enabled.get(cam_id, False):
                results[cam_id] = device.start_grabbing()
            else:
                results[cam_id] = False
        return results

    def stop_all(self) -> None:
        """Stop grabbing on all cameras."""
        for device in self._cameras.values():
            device.stop_grabbing()

    def get_all_status(self) -> list[CameraStatus]:
        """Return status for all registered cameras."""
        return [d.get_status() for d in self._cameras.values()]

    def get_camera(self, camera_id: str) -> LineScanDevice | None:
        """Get a specific camera by ID."""
        return self._cameras.get(camera_id)

    def get_enabled_camera_ids(self) -> list[str]:
        """Return list of enabled camera IDs."""
        return [cid for cid, enabled in self._enabled.items() if enabled]

    def set_enabled(self, camera_id: str, enabled: bool) -> None:
        if camera_id in self._enabled:
            self._enabled[camera_id] = enabled

    @property
    def camera_count(self) -> int:
        return len([e for e in self._enabled.values() if e])
```

- [ ] **Step 2: 写 camera_manager 测试**

Write `tests/device/test_camera_manager.py`:
```python
"""Tests for CameraManager."""
import pytest

from src.device.camera.manager.camera_manager import CameraManager
from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera


@pytest.fixture
def manager():
    mgr = CameraManager()
    for i in range(1, 4):  # 3 cameras
        cam = VirtualLineScanCamera(width=512, line_rate=1000)
        cam.open(f"VS_{i:03d}")
        mgr.add_camera(f"Camera_0{i}", cam, enabled=True)
    return mgr


def test_camera_count(manager):
    assert manager.camera_count == 3


def test_get_enabled_ids(manager):
    ids = manager.get_enabled_camera_ids()
    assert ids == ["Camera_01", "Camera_02", "Camera_03"]


def test_disable_camera(manager):
    manager.set_enabled("Camera_02", False)
    assert manager.camera_count == 2
    assert "Camera_02" not in manager.get_enabled_camera_ids()


def test_start_all(manager):
    results = manager.start_all()
    assert all(results.values())
    for s in manager.get_all_status():
        assert s.grabbing
    manager.stop_all()


def test_disconnect_all(manager):
    manager.disconnect_all()
    for s in manager.get_all_status():
        assert not s.connected


def test_get_camera(manager):
    cam = manager.get_camera("Camera_01")
    assert cam is not None
    assert manager.get_camera("Camera_99") is None


def test_remove_camera(manager):
    manager.remove_camera("Camera_03")
    assert manager.camera_count == 2
    assert manager.get_camera("Camera_03") is None


def test_max_cameras():
    mgr = CameraManager()
    for i in range(6):
        cam = VirtualLineScanCamera()
        cam.open(f"V_{i}")
        mgr.add_camera(f"Camera_{i+1:02d}", cam)

    with pytest.raises(RuntimeError):
        mgr.add_camera("Camera_07", VirtualLineScanCamera())
```

- [ ] **Step 3: 运行测试**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/device/test_camera_manager.py -v
```

Expected: 8 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/device/camera/manager/ tests/device/test_camera_manager.py
git commit -m "feat: add CameraManager for 1-6 camera lifecycle management"
```

---

### Task 3.2: 实现 HealthMonitor（断线检测 + 自动重连）

**Files:**
- Create: `src/device/camera/manager/health_monitor.py`

- [ ] **Step 1: 写 health_monitor.py**

Write `src/device/camera/manager/health_monitor.py`:
```python
"""Camera health monitor — periodic status check, auto-reconnect on disconnect."""
from __future__ import annotations

import logging
import time
from threading import Thread, Event
from collections.abc import Callable

from src.device.camera.manager.camera_manager import CameraManager

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors connected cameras and attempts reconnection on failure.

    Runs a background thread that checks each camera's status at a configurable
    interval. When a camera disconnects, it logs the event and optionally calls
    a user-provided callback. It will attempt auto-reconnect if serial numbers
    are known.
    """

    def __init__(
        self,
        manager: CameraManager,
        check_interval_sec: float = 2.0,
        max_reconnect_attempts: int = 5,
    ) -> None:
        self._manager = manager
        self._check_interval = check_interval_sec
        self._max_reconnect_attempts = max_reconnect_attempts
        self._serial_map: dict[str, str] = {}
        self._on_disconnect: Callable[[str], None] | None = None
        self._on_reconnect: Callable[[str], None] | None = None
        self._running = Event()
        self._thread: Thread | None = None
        self._reconnect_attempts: dict[str, int] = {}

    def set_serial_map(self, serial_map: dict[str, str]) -> None:
        """Set camera_id -> serial_number mapping for reconnection."""
        self._serial_map = serial_map

    def set_on_disconnect(self, callback: Callable[[str], None]) -> None:
        """Called with camera_id when a camera disconnects."""
        self._on_disconnect = callback

    def set_on_reconnect(self, callback: Callable[[str], None]) -> None:
        """Called with camera_id when a camera successfully reconnects."""
        self._on_reconnect = callback

    def start(self) -> None:
        """Start background health check loop."""
        self._running.set()
        self._thread = Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background health check loop."""
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _check_loop(self) -> None:
        while self._running.is_set():
            for cam_id in self._manager.get_enabled_camera_ids():
                device = self._manager.get_camera(cam_id)
                if device is None:
                    continue

                status = device.get_status()

                if not status.connected:
                    logger.warning("Camera %s disconnected", cam_id)
                    if self._on_disconnect:
                        self._on_disconnect(cam_id)

                    # Attempt reconnect
                    serial = self._serial_map.get(cam_id)
                    if serial:
                        attempts = self._reconnect_attempts.get(cam_id, 0)
                        if attempts < self._max_reconnect_attempts:
                            logger.info(
                                "Attempting reconnect for %s (attempt %d/%d)",
                                cam_id, attempts + 1, self._max_reconnect_attempts,
                            )
                            if device.open(serial):
                                device.start_grabbing()
                                logger.info("Camera %s reconnected", cam_id)
                                self._reconnect_attempts[cam_id] = 0
                                if self._on_reconnect:
                                    self._on_reconnect(cam_id)
                            else:
                                self._reconnect_attempts[cam_id] = attempts + 1

            time.sleep(self._check_interval)
```

- [ ] **Step 2: Commit**

```bash
git add src/device/camera/manager/health_monitor.py
git commit -m "feat: add HealthMonitor for camera disconnect detection and auto-reconnect"
```

---

## Phase 4: 运行时流水线适配

### Task 4.1: 重构 AcquisitionPipeline 支持线扫采集

**Files:**
- Modify: `runtime/acquisition_pipeline.py`

- [ ] **Step 1: 读取现有文件，确认改动点**

Read `runtime/acquisition_pipeline.py` (already known from exploration).

- [ ] **Step 2: 扩展 acquisition_pipeline.py**

Replace `runtime/acquisition_pipeline.py`:
```python
"""Acquisition pipeline — reads frames from camera adapters OR line scan devices."""
from __future__ import annotations

import time
from threading import Thread, Event
from typing import Any

from camera_adapters.base import BaseCameraAdapter
from runtime.frame_buffer import FrameBuffer

# Line scan support (optional, graceful degradation if not installed)
try:
    from src.device.camera.line_scan.interface import LineScanDevice
    from src.device.camera.line_scan.types import FramePacket, LineScanImageBlock
    from src.device.camera.line_scan.block_builder import LineScanBlockBuilder
    LINE_SCAN_AVAILABLE = True
except ImportError:
    LineScanDevice = None  # type: ignore
    FramePacket = None  # type: ignore
    LineScanImageBlock = None  # type: ignore
    LineScanBlockBuilder = None  # type: ignore
    LINE_SCAN_AVAILABLE = False


class AcquisitionPipeline:
    """Reads frames from area-scan adapters or line-scan devices into FrameBuffer.

    Supports mixed mode: area-scan cameras via BaseCameraAdapter and line-scan
    cameras via LineScanDevice with block builder integration.
    """

    def __init__(self, buffer_size: int = 100):
        # Area-scan adapters (existing)
        self._adapters: dict[str, BaseCameraAdapter] = {}
        # Line-scan devices (new)
        self._line_scan_cams: dict[str, LineScanDevice] = {}
        self._block_builders: dict[str, LineScanBlockBuilder] = {}

        self._buffer = FrameBuffer(max_size=buffer_size)
        self._running = Event()
        self._threads: list[Thread] = []
        self._interval = 0.05
        self._encoder: Any = None
        self._sampling: Any = None

    # ---- Area-scan (existing API, unchanged) ----

    def add_camera(self, camera_id: str, adapter: BaseCameraAdapter) -> None:
        self._adapters[camera_id] = adapter

    def remove_camera(self, camera_id: str) -> None:
        adapter = self._adapters.pop(camera_id, None)
        if adapter:
            adapter.stop_acquisition()

    # ---- Line-scan (new API) ----

    def add_line_scan_camera(
        self, camera_id: str, device: LineScanDevice, block_height: int = 1024
    ) -> None:
        """Register a line-scan camera with block builder.

        Line data is accumulated into fixed-height blocks internally.
        Completed blocks are pushed to FrameBuffer as individual frames.
        """
        if not LINE_SCAN_AVAILABLE:
            raise RuntimeError("Line scan support not available (src.device.camera not found)")

        self._line_scan_cams[camera_id] = device
        builder = LineScanBlockBuilder(camera_id=camera_id, block_height=block_height)
        self._block_builders[camera_id] = builder

        # When a block completes, push it to the FrameBuffer
        def on_block(block: LineScanImageBlock) -> None:
            if block.image is not None:
                frame_data: dict[str, Any] = {
                    "camera_id": camera_id,
                    "image": block.image,
                    "timestamp": time.time(),
                    "position_meter": block.start_meter,
                    "block": block,  # attach full metadata
                }
                self._buffer.put(frame_data)

        builder.set_on_block(on_block)

        # Wire device line callback to block builder
        device.register_line_callback(lambda pkt: builder.push_line(pkt))

    def remove_line_scan_camera(self, camera_id: str) -> None:
        device = self._line_scan_cams.pop(camera_id, None)
        if device:
            device.unregister_line_callback()
            device.stop_grabbing()

    def set_encoder(self, encoder: Any) -> None:
        self._encoder = encoder

    def set_sampling_controller(self, controller: Any) -> None:
        self._sampling = controller

    # ---- Lifecycle ----

    def start(self) -> None:
        self._running.set()

        # Start area-scan adapters (existing logic)
        for cam_id, adapter in self._adapters.items():
            adapter.start_acquisition()
            t = Thread(
                target=self._acquisition_loop, args=(cam_id, adapter), daemon=True
            )
            t.start()
            self._threads.append(t)

        # Start line-scan devices (new logic)
        for cam_id, device in self._line_scan_cams.items():
            device.start_grabbing()
            # No dedicated thread needed — device handles internal thread via callback

    def stop(self) -> None:
        self._running.clear()
        for adapter in self._adapters.values():
            adapter.stop_acquisition()
        for device in self._line_scan_cams.values():
            device.stop_grabbing()
        for t in self._threads:
            t.join(timeout=2)

    def _acquisition_loop(self, cam_id: str, adapter: BaseCameraAdapter) -> None:
        from datetime import datetime

        while self._running.is_set():
            frame = adapter.get_frame()
            if frame is not None:
                pos_m = 0.0
                if self._encoder is not None:
                    try:
                        pos_m = self._encoder.read_position_meter()
                    except Exception:
                        pos_m = 0.0

                if self._sampling is not None:
                    if not self._sampling.should_capture(position_m=pos_m, now=datetime.now()):
                        time.sleep(self._interval)
                        continue

                frame_data: dict[str, Any] = {
                    "camera_id": cam_id,
                    "image": frame,
                    "timestamp": time.time(),
                    "position_meter": pos_m,
                }
                self._buffer.put(frame_data)
            else:
                time.sleep(self._interval)

    def get_buffer(self) -> FrameBuffer:
        return self._buffer

    def get_encoder(self) -> Any:
        return self._encoder

    def get_status(self) -> list[dict]:
        statuses = []
        for cid, adapter in self._adapters.items():
            s = {"camera_id": cid, **adapter.get_status()}
            if self._encoder is not None:
                try:
                    s["encoder_position_m"] = round(self._encoder.read_position_meter(), 3)
                except Exception:
                    s["encoder_position_m"] = 0.0
            statuses.append(s)
        for cid, device in self._line_scan_cams.items():
            st = device.get_status()
            s = {
                "camera_id": cid,
                "connected": st.connected,
                "acquiring": st.grabbing,
                "fps": st.line_rate,
                "type": "line_scan",
            }
            statuses.append(s)
        return statuses
```

- [ ] **Step 3: Commit**

```bash
git add runtime/acquisition_pipeline.py
git commit -m "feat: extend AcquisitionPipeline for line-scan camera support with block builder integration"
```

---

### Task 4.2: 适配 InferencePipeline 处理 Tile 输入

**Files:**
- Modify: `runtime/inference_pipeline.py`

- [ ] **Step 1: 读取现有文件**

Read `runtime/inference_pipeline.py` (already known from exploration).

- [ ] **Step 2: 扩展 inference_pipeline.py 支持 tile 推理**

The key change: frames from FrameBuffer may be entire blocks from line scan. If a block contains tiles, slice and infer on each tile. Detect NG from any tile.

Read existing then insert after the frame-reading loop:
```python
# In _inference_loop, after reading a frame from buffer:
# Check if frame came from line-scan (has 'block' key)
if "block" in frame_data:
    block = frame_data["block"]  # LineScanImageBlock
    # Generate tiles and infer on each
    from src.device.camera.line_scan.tile_generator import TileGenerator
    tile_gen = TileGenerator(tile_size=320)
    tiles = tile_gen.slice_block(block)
    for tile in tiles:
        # Save tile image to temp, run inference
        import tempfile, cv2
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            cv2.imwrite(f.name, tile.image)
            result = runner.predict_image(f.name)
        # ... detect NG, record position
```

This is a structural change — the exact implementation depends on the current file content. Let's read it exactly first.

- [ ] **Step 3: 实现改动**

This task should be executed with the actual file open and visible.

- [ ] **Step 4: Commit**

```bash
git add runtime/inference_pipeline.py
git commit -m "feat: adapt InferencePipeline for tile-based line-scan inference"
```

---

## Phase 5: UI 改造

### Task 5.1: 改造 ProductionRunPage 为自适应网格布局

**Files:**
- Modify: `desktop_app/pages/production_run_page.py`

- [ ] **Step 1: 改造为 QGridLayout 自适应布局**

Change from single camera view to adaptive grid:
- QGridLayout with dynamic column count based on camera_count
- Each cell: Camera preview widget with status overlay (FPS, NG count, meter position)
- Bottom: global control bar (start/stop/reset + encoder reading)
- Only show enabled camera slots (no empty placeholders)

Implementation: Replace the central widget with a QWidget containing:
```
QVBoxLayout
  ├── QGridLayout (auto-columns based on camera_count)
  │   └── Per camera: CameraPreviewWidget (image + status overlay)
  └── QHBoxLayout (control bar)
      ├── QLabel: encoder position + line speed
      └── QPushButton: start / stop / reset alarm
```

- [ ] **Step 2: Commit**

```bash
git add desktop_app/pages/production_run_page.py
git commit -m "feat: redesign ProductionRunPage with adaptive grid layout for multi-camera support"
```

---

### Task 5.2: 创建 CommissioningPanel（联调面板）

**Files:**
- Create: `desktop_app/pages/device/__init__.py`
- Create: `desktop_app/pages/device/commissioning_panel.py`

- [ ] **Step 1: 写 commissioning_panel.py**

Write `desktop_app/pages/device/__init__.py`:
```python
"""Device configuration and commissioning pages."""
```

Write `desktop_app/pages/device/commissioning_panel.py`:
```python
"""Commissioning panel — camera connection diagnostics, tuning, encoder calibration."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QTextEdit,
)
from PySide6.QtCore import Qt, Signal


class CommissioningPanel(QWidget):
    """Camera commissioning and diagnostic panel.

    Provides:
    - Camera discovery and connection testing
    - Exposure/gain/line rate tuning sliders
    - Encoder calibration wizard
    - Real-time image quality check
    """

    scan_requested = Signal()
    connect_requested = Signal(str)  # serial_number
    disconnect_requested = Signal(str)  # camera_id
    param_changed = Signal(str, object)  # param_name, value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Camera Discovery
        discover_group = QGroupBox("相机发现")
        discover_layout = QVBoxLayout(discover_group)
        self._scan_btn = QPushButton("扫描设备")
        self._scan_btn.clicked.connect(self.scan_requested.emit)
        discover_layout.addWidget(self._scan_btn)
        self._device_list = QTextEdit()
        self._device_list.setReadOnly(True)
        self._device_list.setMaximumHeight(120)
        discover_layout.addWidget(self._device_list)
        layout.addWidget(discover_group)

        # Connection Test
        conn_group = QGroupBox("连接测试")
        conn_layout = QFormLayout(conn_group)
        self._serial_input = QLineEdit()
        self._serial_input.setPlaceholderText("输入相机序列号")
        conn_layout.addRow("序列号:", self._serial_input)
        btn_row = QHBoxLayout()
        self._connect_btn = QPushButton("连接")
        self._connect_btn.clicked.connect(
            lambda: self.connect_requested.emit(self._serial_input.text())
        )
        self._disconnect_btn = QPushButton("断开")
        self._disconnect_btn.clicked.connect(
            lambda: self.disconnect_requested.emit("Camera_01")
        )
        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._disconnect_btn)
        conn_layout.addRow(btn_row)
        self._conn_status = QLabel("未连接")
        conn_layout.addRow("状态:", self._conn_status)
        layout.addWidget(conn_group)

        # Parameter Tuning
        tuning_group = QGroupBox("相机调参")
        tuning_layout = QFormLayout(tuning_group)

        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1.0, 1000000.0)
        self._exposure_spin.setValue(20.0)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.valueChanged.connect(
            lambda v: self.param_changed.emit("ExposureTime", v)
        )
        tuning_layout.addRow("曝光时间:", self._exposure_spin)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.0, 40.0)
        self._gain_spin.setValue(0.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.valueChanged.connect(
            lambda v: self.param_changed.emit("Gain", v)
        )
        tuning_layout.addRow("增益:", self._gain_spin)

        self._line_rate_spin = QSpinBox()
        self._line_rate_spin.setRange(100, 200000)
        self._line_rate_spin.setValue(20000)
        self._line_rate_spin.setSuffix(" Hz")
        self._line_rate_spin.valueChanged.connect(
            lambda v: self.param_changed.emit("LineRate", v)
        )
        tuning_layout.addRow("行频:", self._line_rate_spin)

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["Off", "On"])
        self._trigger_combo.currentTextChanged.connect(
            lambda v: self.param_changed.emit("TriggerMode", v)
        )
        tuning_layout.addRow("触发模式:", self._trigger_combo)

        layout.addWidget(tuning_group)

        # Encoder Calibration
        encoder_group = QGroupBox("编码器标定")
        encoder_layout = QFormLayout(encoder_group)
        self._known_dist_spin = QDoubleSpinBox()
        self._known_dist_spin.setRange(100.0, 5000.0)
        self._known_dist_spin.setValue(1000.0)
        self._known_dist_spin.setSuffix(" mm")
        encoder_layout.addRow("已知距离:", self._known_dist_spin)
        self._calibrate_btn = QPushButton("开始标定")
        encoder_layout.addRow(self._calibrate_btn)
        self._cal_result = QLabel("--")
        encoder_layout.addRow("标定结果:", self._cal_result)
        layout.addWidget(encoder_group)

        layout.addStretch()
```

- [ ] **Step 2: Commit**

```bash
git add desktop_app/pages/device/
git commit -m "feat: add CommissioningPanel for camera diagnostics and tuning"
```

---

### Task 5.3: 更新相机配置页和 Recipe 管理

**Files:**
- Modify: `desktop_app/pages/camera_config_page.py`
- Modify: `core/camera_config.py`
- Modify: `core/storage.py`

- [ ] **Step 1: 扩展 CameraConfig 数据模型**

Add fields to `core/camera_config.py`:
```python
# Add to @dataclass fields:
line_rate: int | None = None
image_block_height: int | None = 1024
pixel_format: str = "Mono8"
# ... update to_dict and from_dict accordingly
```

- [ ] **Step 2: 扩展 camera_config_page.py 表单**

Add line-scan specific fields to the existing camera config form:
- LineRate spinbox
- Image Block Height spinbox
- Pixel Format combo (Mono8, Mono12, BayerRG8, etc.)

- [ ] **Step 3: Commit**

```bash
git add core/camera_config.py core/storage.py desktop_app/pages/camera_config_page.py
git commit -m "feat: extend camera config with line-scan parameters and recipe support"
```

---

### Task 5.4: 版本号和依赖更新

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新版本号**

```toml
[project]
name = "copper-vision"
version = "0.7.0"
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.7.0 for V7 line-scan camera integration"
```

---

## 附录: 各阶段 Commit 汇总

| Phase | Commits | 关键交付物 |
|-------|---------|-----------|
| 1: MVP | 7 commits | MvImport, types, interface, virtual cam, SDK loader, HikrobotLineScanCamera, smoke test |
| 2: Blocks+Tiles | 3 commits | BlockBuilder, TileGenerator, EncoderMapper |
| 3: Multi-camera | 2 commits | CameraManager, HealthMonitor |
| 4: Runtime | 2 commits | AcquisitionPipeline 重构, InferencePipeline 适配 |
| 5: UI | 3 commits | ProductionRunPage 自适应网格, CommissioningPanel, camera config 扩展 |

---

## 附录: 运行前环境检查

部署到现场前运行:
```bash
python -c "
from src.device.camera.hikrobot.sdk_loader import load_sdk
ok = load_sdk()
print('SDK:', 'OK' if ok else 'FAIL')
print('Error:', SDK_ERROR if not ok else 'None')
"
```
