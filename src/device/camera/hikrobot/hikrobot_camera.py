"""Hikrobot GigE line scan camera adapter using MVS SDK."""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import c_bool, cast, POINTER, c_ubyte
from threading import Event, Thread
from typing import override

import numpy as np

from src.device.camera.hikrobot.error_code import get_error_message
from src.device.camera.hikrobot.sdk_loader import load_sdk
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _bytes_to_str(data: bytes | ctypes.Array[ctypes.c_ubyte]) -> str:
    """Convert a c_ubyte array field to a null-terminated ASCII string."""
    raw = bytes(data) if isinstance(data, ctypes.Array) else data
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def _ip_int_to_str(ip: int) -> str:
    """Convert a 32-bit integer IP to dotted-decimal string."""
    return f"{(ip >> 24) & 0xFF}.{(ip >> 16) & 0xFF}.{(ip >> 8) & 0xFF}.{ip & 0xFF}"


def _mac_to_str(high: int, low: int) -> str:
    """Convert MAC address high/low uint to hex string."""
    return (
        f"{(high >> 8) & 0xFF:02X}:{high & 0xFF:02X}"
        f":{(low >> 24) & 0xFF:02X}:{(low >> 16) & 0xFF:02X}"
        f":{(low >> 8) & 0xFF:02X}:{low & 0xFF:02X}"
    )


class HikrobotLineScanCamera(LineScanDevice):
    """GigE line scan camera adapter using Hikrobot MVS SDK."""

    _sdk_initialized: bool = False

    def __init__(self) -> None:
        self._handle: ctypes.c_void_p | None = None  # will be set to MvCamera instance
        self._camera: object | None = None  # MvCamera instance
        self._connected: bool = False
        self._grabbing: bool = False
        self._serial: str = ""
        self._callback: Callable[[FramePacket], None] | None = None
        self._grab_thread: Thread | None = None
        self._stop_event = Event()
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
        self._int_params = {"Width", "Height", "OffsetX", "OffsetY", "LineRate", "PayloadSize"}
        self._bool_params = {"ReverseX", "ReverseY"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_error(self, code: int, context: str = "") -> None:
        self._last_error_code = code
        self._last_error_msg = (
            f"{context}: {get_error_message(code)}" if context else get_error_message(code)
        )
        logger.error("MVS error 0x%08X: %s", code, self._last_error_msg)

    def _clear_error(self) -> None:
        self._last_error_code = 0
        self._last_error_msg = ""

    # ------------------------------------------------------------------
    # enumerate_devices (static)
    # ------------------------------------------------------------------

    @staticmethod
    @override
    def enumerate_devices() -> list[DeviceInfo]:
        """Discover available GigE line scan cameras."""
        if not load_sdk():
            return []

        # These are only importable after load_sdk() succeeds.
        from CameraParams_const import MV_GIGE_DEVICE  # noqa: F811
        from CameraParams_header import MV_CC_DEVICE_INFO, MV_CC_DEVICE_INFO_LIST  # noqa: F811
        from MvCameraControl_class import MvCamera  # noqa: F811
        from MvErrorDefine_const import MV_OK  # noqa: F811

        st_dev_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, st_dev_list)
        if ret != MV_OK or st_dev_list.nDeviceNum == 0:
            logger.debug(
                "EnumDevices returned 0x%08X, device count=%d", ret, st_dev_list.nDeviceNum
            )
            return []

        devices: list[DeviceInfo] = []
        for i in range(st_dev_list.nDeviceNum):
            try:
                p_dev = cast(st_dev_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO))
                info = p_dev.contents
                gig = info.SpecialInfo.stGigEInfo

                serial = _bytes_to_str(gig.chSerialNumber)
                ip = _ip_int_to_str(gig.nCurrentIp)
                mac = _mac_to_str(info.nMacAddrHigh, info.nMacAddrLow)
                model = _bytes_to_str(gig.chModelName)
                vendor = _bytes_to_str(gig.chManufacturerName)
                user_name = _bytes_to_str(gig.chUserDefinedName)

                devices.append(
                    DeviceInfo(
                        vendor=vendor,
                        model=model,
                        serial_number=serial,
                        ip_address=ip,
                        mac_address=mac,
                        transport_layer="GigE",
                        user_defined_name=user_name,
                    )
                )
            except Exception:
                logger.debug("Failed to parse device info at index %d", i, exc_info=True)

        return devices

    # ------------------------------------------------------------------
    # open / close
    # ------------------------------------------------------------------

    @override
    def open(self, serial_number: str) -> bool:
        """Connect to a GigE line scan camera by serial number."""
        if not load_sdk():
            self._last_error_msg = "MVS SDK not loaded"
            return False

        try:
            from CameraParams_const import MV_ACCESS_Exclusive, MV_GIGE_DEVICE  # noqa: F811
            from CameraParams_header import MV_CC_DEVICE_INFO, MV_CC_DEVICE_INFO_LIST  # noqa: F811
            from MvCameraControl_class import MvCamera  # noqa: F811
            from MvErrorDefine_const import MV_OK  # noqa: F811

            # Initialize SDK once (class-level)
            if not HikrobotLineScanCamera._sdk_initialized:
                ret = MvCamera.MV_CC_Initialize()
                if ret != MV_OK:
                    self._record_error(ret, "MV_CC_Initialize")
                    return False
                HikrobotLineScanCamera._sdk_initialized = True
                logger.info("MVS SDK initialized (version 0x%X)", MvCamera.MV_CC_GetSDKVersion())

            # Enumerate devices
            st_dev_list = MV_CC_DEVICE_INFO_LIST()
            ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, st_dev_list)
            if ret != MV_OK or st_dev_list.nDeviceNum == 0:
                self._record_error(ret if ret != MV_OK else -1, "No devices found")
                return False

            # Find device by serial
            target_dev = None
            target_info = None
            for i in range(st_dev_list.nDeviceNum):
                p_dev = cast(st_dev_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO))
                info = p_dev.contents
                gig = info.SpecialInfo.stGigEInfo
                serial = _bytes_to_str(gig.chSerialNumber)
                if serial == serial_number:
                    target_dev = p_dev.contents  # MV_CC_DEVICE_INFO instance
                    ip = _ip_int_to_str(gig.nCurrentIp)
                    target_info = DeviceInfo(
                        vendor=_bytes_to_str(gig.chManufacturerName),
                        model=_bytes_to_str(gig.chModelName),
                        serial_number=serial,
                        ip_address=ip,
                        mac_address=_mac_to_str(info.nMacAddrHigh, info.nMacAddrLow),
                        transport_layer="GigE",
                        user_defined_name=_bytes_to_str(gig.chUserDefinedName),
                    )
                    break

            if target_dev is None:
                self._last_error_msg = f"Device with serial {serial_number} not found"
                self._last_error_code = -1
                return False

            # Create handle
            self._camera = MvCamera()
            ret = self._camera.MV_CC_CreateHandle(target_dev)
            if ret != MV_OK:
                self._record_error(ret, "MV_CC_CreateHandle")
                self._camera = None
                return False

            # Open device
            ret = self._camera.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
            if ret != MV_OK:
                self._record_error(ret, "MV_CC_OpenDevice")
                self._camera.MV_CC_DestroyHandle()
                self._camera = None
                return False

            self._connected = True
            self._serial = serial_number
            self._device_info = target_info
            self._clear_error()
            logger.info("Camera connected: serial=%s, ip=%s", serial_number, target_info.ip_address)
            return True

        except Exception as e:
            self._last_error_msg = f"Open exception: {e}"
            self._last_error_code = -1
            logger.error("Failed to open camera", exc_info=True)
            self._cleanup_camera()
            return False

    @override
    def close(self) -> None:
        """Disconnect and release all SDK resources."""
        self._grabbing = False
        self._connected = False

        # Stop grabbing best-effort
        try:
            if self._camera is not None:
                self._camera.MV_CC_StopGrabbing()
        except Exception:
            pass

        self._cleanup_camera()
        self._serial = ""
        self._device_info = None

    def _cleanup_camera(self) -> None:
        """Release camera handle (best-effort)."""
        try:
            if self._camera is not None:
                self._camera.MV_CC_CloseDevice()
                self._camera.MV_CC_DestroyHandle()
        except Exception:
            pass
        finally:
            self._camera = None

    @staticmethod
    def _finalize_sdk() -> None:
        """Finalize SDK. Best-effort, safe to call any time."""
        if not HikrobotLineScanCamera._sdk_initialized:
            return
        try:
            from MvCameraControl_class import MvCamera  # noqa: F811

            MvCamera.MV_CC_Finalize()
            HikrobotLineScanCamera._sdk_initialized = False
            logger.info("MVS SDK finalized")
        except Exception:
            logger.warning("Failed to finalize SDK", exc_info=True)

    # ------------------------------------------------------------------
    # start_grabbing / stop_grabbing
    # ------------------------------------------------------------------

    @override
    def start_grabbing(self) -> bool:
        """Start line scan acquisition."""
        if not self._connected or self._camera is None:
            self._last_error_msg = "Camera not connected"
            self._last_error_code = -1
            return False
        if self._grabbing:
            return True

        try:
            from MvErrorDefine_const import MV_OK  # noqa: F811

            ret = self._camera.MV_CC_StartGrabbing()
            if ret != MV_OK:
                self._record_error(ret, "MV_CC_StartGrabbing")
                return False

            self._grabbing = True
            self._stop_event.clear()
            self._grab_thread = Thread(target=self._grab_loop, daemon=True)
            self._grab_thread.start()
            self._clear_error()
            logger.info("Grabbing started")
            return True
        except Exception as e:
            self._last_error_msg = f"StartGrabbing exception: {e}"
            self._last_error_code = -1
            return False

    @override
    def stop_grabbing(self) -> None:
        """Stop line scan acquisition."""
        self._grabbing = False
        self._stop_event.set()
        try:
            if self._camera is not None:
                self._camera.MV_CC_StopGrabbing()
        except Exception:
            pass
        if self._grab_thread is not None:
            self._grab_thread.join(timeout=2.0)
            self._grab_thread = None

    # ------------------------------------------------------------------
    # get_status
    # ------------------------------------------------------------------

    @override
    def get_status(self) -> CameraStatus:
        """Return current camera status."""
        status = CameraStatus(
            vendor="Hikrobot" if self._device_info is None else self._device_info.vendor,
            model="" if self._device_info is None else self._device_info.model,
            serial_number=self._serial,
            ip_address="" if self._device_info is None else self._device_info.ip_address,
            connected=self._connected,
            grabbing=self._grabbing,
            line_rate=float(self._params.get("LineRate", 0)),
            received_line_count=self._line_count,
            last_error_code=self._last_error_code,
            last_error_message=self._last_error_msg,
        )
        return status

    # ------------------------------------------------------------------
    # set_param / get_param
    # ------------------------------------------------------------------

    @override
    def set_param(self, name: str, value: object) -> None:
        """Set a camera parameter. Stores locally; applies to camera if connected."""
        self._params[name] = value

        if not self._connected or self._camera is None:
            return

        try:
            from MvErrorDefine_const import MV_OK  # noqa: F811

            ret: int = MV_OK
            if name in self._bool_params and isinstance(value, bool):
                ret = self._camera.MV_CC_SetBoolValue(name, value)
            elif isinstance(value, str):
                ret = self._camera.MV_CC_SetEnumValueByString(name, value)
            elif name in self._int_params and isinstance(value, (int, float)):
                ret = self._camera.MV_CC_SetIntValueEx(name, int(value))
            elif isinstance(value, (int, float)):
                ret = self._camera.MV_CC_SetFloatValue(name, float(value))
            else:
                logger.warning("Unsupported param type for %s: %s", name, type(value).__name__)
                return

            if ret != MV_OK:
                self._record_error(ret, f"set_param({name})")
        except Exception as e:
            self._last_error_code = -1
            self._last_error_msg = f"set_param({name}) exception: {e}"
            logger.error("set_param(%s) failed", name, exc_info=True)

    @override
    def get_param(self, name: str) -> object:
        """Get a camera parameter. Tries camera hardware first, falls back to local cache."""
        if self._connected and self._camera is not None:
            try:
                from MvErrorDefine_const import MV_OK  # noqa: F811
                from CameraParams_header import MVCC_FLOATVALUE, MVCC_INTVALUE_EX  # noqa: F811

                if name in self._int_params:
                    iv = MVCC_INTVALUE_EX()
                    ret = self._camera.MV_CC_GetIntValueEx(name, iv)
                    if ret == MV_OK:
                        return int(iv.nCurValue)
                if name in self._bool_params:
                    bv = c_bool()
                    ret = self._camera.MV_CC_GetBoolValue(name, bv)
                    if ret == MV_OK:
                        return bool(bv.value)
                fv = MVCC_FLOATVALUE()
                ret = self._camera.MV_CC_GetFloatValue(name, fv)
                if ret == MV_OK:
                    return float(fv.fCurValue)
            except Exception:
                logger.debug("get_param(%s) from camera failed, using cached", name, exc_info=True)

        return self._params.get(name, 0)

    # ------------------------------------------------------------------
    # register_line_callback / unregister_line_callback
    # ------------------------------------------------------------------

    @override
    def register_line_callback(self, callback: Callable[[FramePacket], None]) -> None:
        """Register a callback invoked for each line received."""
        self._callback = callback

    @override
    def unregister_line_callback(self) -> None:
        """Remove the current line callback."""
        self._callback = None

    # ------------------------------------------------------------------
    # get_last_error
    # ------------------------------------------------------------------

    def get_last_error(self) -> tuple[int, str]:
        """Return (error_code, error_message) tuple."""
        return (self._last_error_code, self._last_error_msg)

    def _grab_loop(self) -> None:
        """Poll MVS frames and convert them into FramePacket callbacks."""
        try:
            from CameraParams_header import MV_FRAME_OUT_INFO_EX  # noqa: F811
            from MvErrorDefine_const import MV_OK  # noqa: F811
        except Exception as e:
            self._last_error_code = -1
            self._last_error_msg = f"grab_loop import exception: {e}"
            return

        payload_size = int(self.get_param("PayloadSize") or 0)
        width = int(self.get_param("Width") or self._params.get("Width", 2048))
        height = int(self.get_param("Height") or 1)
        buffer_size = max(payload_size, width * max(height, 1) * 2, 4096)
        data_buf = (c_ubyte * buffer_size)()
        frame_info = MV_FRAME_OUT_INFO_EX()

        while not self._stop_event.is_set():
            if self._camera is None:
                break
            ret = self._camera.MV_CC_GetOneFrameTimeout(
                data_buf, buffer_size, frame_info, 1000
            )
            if ret != MV_OK:
                self._record_error(ret, "MV_CC_GetOneFrameTimeout")
                time.sleep(0.01)
                continue

            frame_width = int(frame_info.nExtendWidth or frame_info.nWidth or width)
            frame_height = int(frame_info.nExtendHeight or frame_info.nHeight or 1)
            frame_len = int(frame_info.nFrameLen or frame_info.nFrameLenEx)
            if frame_width <= 0 or frame_height <= 0 or frame_len <= 0:
                continue

            raw = np.frombuffer(data_buf, dtype=np.uint8, count=min(frame_len, buffer_size))
            expected = frame_width * frame_height
            if raw.size < expected:
                self._record_error(-1, "Frame buffer smaller than expected Mono8 image")
                continue
            image = raw[:expected].reshape(frame_height, frame_width).copy()
            encoder_count = int(
                getattr(frame_info, "nFirstLineEncoderCount", 0)
                or frame_info.nFrameNum
            )
            self._line_count += frame_height
            callback = self._callback
            if callback is not None:
                packet = FramePacket(
                    camera_id=self._serial,
                    frame_id=int(frame_info.nFrameNum),
                    timestamp_ns=time.time_ns(),
                    encoder_count=encoder_count,
                    width=frame_width,
                    height=frame_height,
                    pixel_format=str(self._params.get("PixelFormat", "Mono8")),
                    line_data=image,
                    metadata={
                        "frame_len": frame_len,
                        "pixel_type": int(frame_info.enPixelType),
                        "last_line_encoder_count": int(
                            getattr(frame_info, "nLastLineEncoderCount", encoder_count)
                        ),
                    },
                )
                try:
                    callback(packet)
                except Exception:
                    logger.exception("Line callback failed")
