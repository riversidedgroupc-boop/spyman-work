"""Hikvision MVS camera adapter — full implementation."""

from __future__ import annotations

import os
import sys
import time
from ctypes import POINTER, byref, c_ubyte, cast, memset

import numpy as np

from camera_adapters.base import BaseCameraAdapter

_MVS_SDK_PATH = os.path.join(
    os.environ.get("MVCAM_COMMON_RUNENV", ""),
    "Samples", "Python", "MvImport",
)

if _MVS_SDK_PATH not in sys.path:
    sys.path.insert(0, _MVS_SDK_PATH)

from CameraParams_header import *  # noqa: E402
from MvCameraControl_class import *  # noqa: E402


class HikvisionMVSAdapter(BaseCameraAdapter):
    adapter_name = "hikvision_mvs"

    def __init__(self) -> None:
        self._cam: MvCamera | None = None
        self._connected = False
        self._acquiring = False
        self._frame_count = 0
        self._last_fps = 0.0
        self._last_time = time.perf_counter()
        self._width = 0
        self._height = 0
        self._pixel_format: int | None = None
        self._devices: list[dict] = []

    # ------------------------------------------------------------------ list_devices
    def list_devices(self) -> list[dict]:
        """Enumerate Hikvision cameras on all supported transport layers."""
        result: list[dict] = []
        for layer_type, layer_name in [
            (MV_GIGE_DEVICE, "GigE"),
            (MV_USB_DEVICE, "USB"),
        ]:
            dev_list = MV_CC_DEVICE_INFO_LIST()
            memset(byref(dev_list), 0, sizeof(MV_CC_DEVICE_INFO_LIST))
            ret = MvCamCtrldll.MV_CC_EnumDevices(layer_type, byref(dev_list))
            if ret != 0:
                continue

            for i in range(dev_list.nDeviceNum):
                dev_info = cast(
                    dev_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)
                ).contents
                dev_id = self._extract_device_id(dev_info)
                dev_name = self._extract_device_name(dev_info)
                result.append({
                    "id": dev_id,
                    "name": dev_name,
                    "layer": layer_name,
                    "index": i,
                    "raw": dev_info,
                    "raw_list": dev_list,
                })

        self._devices = result
        return result

    # ------------------------------------------------------------------ connect
    def connect(self, config: dict) -> bool:
        """Connect to a camera by index or serial/id."""
        devices = self.list_devices()
        if not devices:
            raise RuntimeError("No Hikvision cameras found")

        idx = int(config.get("index", config.get("device_index", 0)))
        if idx >= len(devices):
            raise RuntimeError(
                f"Camera index {idx} out of range (found {len(devices)} devices)"
            )

        dev = devices[idx]
        dev_info = cast(
            dev["raw_list"].pDeviceInfo[idx], POINTER(MV_CC_DEVICE_INFO)
        ).contents

        self._cam = MvCamera()
        ret = self._cam.MV_CC_CreateHandle(dev_info)
        if ret != 0:
            self._cam.MV_CC_DestroyHandle()
            self._cam = None
            raise RuntimeError(f"CreateHandle failed: 0x{ret:08X}")

        ret = self._cam.MV_CC_OpenDevice()
        if ret != 0:
            self._cam.MV_CC_DestroyHandle()
            self._cam = None
            raise RuntimeError(f"OpenDevice failed: 0x{ret:08X}")

        # GigE: set optimal packet size
        if dev_info.nTLayerType == MV_GIGE_DEVICE:
            nPacketSize = self._cam.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                self._cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)

        # Default to continuous trigger mode
        self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

        # Get image dimensions
        stInt = MVCC_INTVALUE()
        memset(byref(stInt), 0, sizeof(MVCC_INTVALUE))
        self._cam.MV_CC_GetIntValue("Width", stInt)
        self._width = stInt.nCurValue
        self._cam.MV_CC_GetIntValue("Height", stInt)
        self._height = stInt.nCurValue
        self._cam.MV_CC_GetIntValue("PixelFormat", stInt)
        self._pixel_format = stInt.nCurValue

        self._connected = True
        self._device_index = idx
        return True

    # ------------------------------------------------------------------ disconnect
    def disconnect(self) -> None:
        if self._acquiring:
            self.stop_acquisition()
        if self._cam is not None:
            if self._connected:
                self._cam.MV_CC_CloseDevice()
            self._cam.MV_CC_DestroyHandle()
            self._cam = None
        self._connected = False

    # ------------------------------------------------------------------ start_acquisition
    def start_acquisition(self) -> None:
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")
        ret = self._cam.MV_CC_StartGrabbing()
        if ret != 0:
            raise RuntimeError(f"StartGrabbing failed: 0x{ret:08X}")
        self._acquiring = True
        self._frame_count = 0
        self._last_time = time.perf_counter()

    # ------------------------------------------------------------------ stop_acquisition
    def stop_acquisition(self) -> None:
        if self._cam is not None and self._acquiring:
            self._cam.MV_CC_StopGrabbing()
        self._acquiring = False

    # ------------------------------------------------------------------ get_frame
    def get_frame(self) -> np.ndarray | None:
        """Return next frame as numpy array (H, W, 3 BGR), or None if no frame."""
        if not self._acquiring or self._cam is None:
            return None

        stFrame = MV_FRAME_OUT()
        memset(byref(stFrame), 0, sizeof(stFrame))
        ret = self._cam.MV_CC_GetImageBuffer(stFrame, 500)
        if ret != 0:
            return None

        try:
            frame_info = stFrame.stFrameInfo
            width = frame_info.nWidth
            height = frame_info.nHeight
            pixel_type = frame_info.enPixelType
            data_len = frame_info.nFrameLen

            # Determine channels from pixel format
            is_color = (
                pixel_type == PixelType_Gvsp_BayerGR8
                or pixel_type == PixelType_Gvsp_BayerRG8
                or pixel_type == PixelType_Gvsp_BayerGB8
                or pixel_type == PixelType_Gvsp_BayerBG8
                or pixel_type >= PixelType_Gvsp_RGB8_Packed
            )

            # Read raw buffer
            raw = (c_ubyte * data_len)()
            memmove(raw, stFrame.pBufAddr, data_len)
            buf = bytes(raw)

            if is_color:
                # Bayer → BGR via OpenCV
                import cv2

                bayer_map = {
                    PixelType_Gvsp_BayerGR8: cv2.COLOR_BAYER_GR2BGR,
                    PixelType_Gvsp_BayerRG8: cv2.COLOR_BAYER_RG2BGR,
                    PixelType_Gvsp_BayerGB8: cv2.COLOR_BAYER_GB2BGR,
                    PixelType_Gvsp_BayerBG8: cv2.COLOR_BAYER_BG2BGR,
                }
                code = bayer_map.get(pixel_type, cv2.COLOR_BAYER_GR2BGR)
                img = np.frombuffer(buf, dtype=np.uint8).reshape((height, width))
                img = cv2.cvtColor(img, code)
            else:
                img = np.frombuffer(buf, dtype=np.uint8).reshape((height, width))
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            self._frame_count += 1
            elapsed = time.perf_counter() - self._last_time
            if elapsed >= 1.0:
                self._last_fps = self._frame_count / elapsed
                self._frame_count = 0
                self._last_time = time.perf_counter()

            return img
        finally:
            self._cam.MV_CC_FreeImageBuffer(stFrame)

    # ------------------------------------------------------------------ get_status
    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "acquiring": self._acquiring,
            "fps": round(self._last_fps, 1),
            "frame_count": self._frame_count,
            "width": self._width,
            "height": self._height,
            "pixel_format": self._pixel_format,
        }

    # ------------------------------------------------------------------ set_exposure
    def set_exposure(self, exposure_us: float) -> None:
        if self._cam is not None:
            self._cam.MV_CC_SetFloatValue("ExposureTime", float(exposure_us))

    # ------------------------------------------------------------------ set_gain
    def set_gain(self, gain_db: float) -> None:
        if self._cam is not None:
            self._cam.MV_CC_SetFloatValue("Gain", float(gain_db))

    # ------------------------------------------------------------------ set_trigger_mode
    def set_trigger_mode(self, mode: str) -> None:
        if self._cam is None:
            return
        _mode_map = {
            "continuous": MV_TRIGGER_MODE_OFF,
            "off": MV_TRIGGER_MODE_OFF,
            "external": MV_TRIGGER_MODE_ON,
            "on": MV_TRIGGER_MODE_ON,
            "software": MV_TRIGGER_MODE_ON,
        }
        enum_val = _mode_map.get(mode, MV_TRIGGER_MODE_OFF)
        self._cam.MV_CC_SetEnumValue("TriggerMode", enum_val)

    # -------------------------------------------------- helpers

    @staticmethod
    def _extract_device_id(dev_info: MV_CC_DEVICE_INFO) -> str:
        """Extract device serial/identifier from device info struct."""
        try:
            if dev_info.nTLayerType == MV_GIGE_DEVICE:
                gige = dev_info.SpecialInfo.stGigEInfo
                return gige.chSerialNumber.decode("ascii", errors="ignore").strip("\x00")
            elif dev_info.nTLayerType == MV_USB_DEVICE:
                usb = dev_info.SpecialInfo.stUsb3VInfo
                return usb.chSerialNumber.decode("ascii", errors="ignore").strip("\x00")
        except Exception:
            pass
        return f"hik_{id(dev_info):08X}"

    @staticmethod
    def _extract_device_name(dev_info: MV_CC_DEVICE_INFO) -> str:
        """Extract user-defined or model name from device info."""
        try:
            if dev_info.nTLayerType == MV_GIGE_DEVICE:
                gige = dev_info.SpecialInfo.stGigEInfo
                user = gige.chUserDefinedName.decode("ascii", errors="ignore").strip("\x00")
                model = gige.chModelName.decode("ascii", errors="ignore").strip("\x00")
                return user or model or "Hikvision GigE"
            elif dev_info.nTLayerType == MV_USB_DEVICE:
                usb = dev_info.SpecialInfo.stUsb3VInfo
                user = usb.chUserDefinedName.decode("ascii", errors="ignore").strip("\x00")
                model = usb.chModelName.decode("ascii", errors="ignore").strip("\x00")
                return user or model or "Hikvision USB"
        except Exception:
            pass
        return "Hikvision Camera"
