"""Hikvision MVS camera adapter — skeleton."""
from __future__ import annotations

from camera_adapters.base import BaseCameraAdapter


class HikvisionMVSAdapter(BaseCameraAdapter):
    adapter_name = "hikvision_mvs"

    def __init__(self):
        self._connected = False

    def list_devices(self) -> list[dict]:
        try:
            # Attempt to import MVS SDK
            import importlib
            importlib.import_module("MvCameraControl_class")
            return [{"id": "hik_0", "name": "海康 MVS 相机 (待实现)"}]
        except ImportError:
            pass
        return []

    def connect(self, config: dict) -> bool:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。请安装 MVS SDK 后重试。")

    def disconnect(self) -> None:
        pass

    def start_acquisition(self) -> None:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。")

    def stop_acquisition(self) -> None:
        pass

    def get_frame(self):
        return None

    def get_status(self) -> dict:
        return {"connected": False, "acquiring": False, "note": "MVS SDK 未安装"}

    def set_exposure(self, exposure_us: float) -> None:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。")

    def set_gain(self, gain_db: float) -> None:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。")

    def set_trigger_mode(self, mode: str) -> None:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。")

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        raise NotImplementedError("海康 MVS SDK 未安装或未配置。")
