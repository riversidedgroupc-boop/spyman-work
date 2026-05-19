"""Basler Pylon camera adapter — skeleton."""
from __future__ import annotations

from camera_adapters.base import BaseCameraAdapter


class BaslerPylonAdapter(BaseCameraAdapter):
    adapter_name = "basler_pylon"

    def __init__(self):
        self._connected = False

    def list_devices(self) -> list[dict]:
        return []

    def connect(self, config: dict) -> bool:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。请安装 pypylon 后重试。")

    def disconnect(self) -> None:
        pass

    def start_acquisition(self) -> None:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。")

    def stop_acquisition(self) -> None:
        pass

    def get_frame(self):
        return None

    def get_status(self) -> dict:
        return {"connected": False, "acquiring": False, "note": "Pylon SDK 未安装"}

    def set_exposure(self, exposure_us: float) -> None:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。请安装 pypylon 后重试。")

    def set_gain(self, gain_db: float) -> None:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。请安装 pypylon 后重试。")

    def set_trigger_mode(self, mode: str) -> None:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。请安装 pypylon 后重试。")

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        raise NotImplementedError("Basler Pylon SDK 未安装或未配置。请安装 pypylon 后重试。")
