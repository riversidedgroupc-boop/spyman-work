"""Camera manager — manages 1-6 camera lifecycle."""
from __future__ import annotations

import logging

from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus

logger = logging.getLogger(__name__)


class CameraManager:
    MAX_CAMERAS = 6

    def __init__(self) -> None:
        self._cameras: dict[str, LineScanDevice] = {}
        self._enabled: dict[str, bool] = {}

    def add_camera(self, camera_id: str, device: LineScanDevice, enabled: bool = True) -> None:
        if len(self._cameras) >= self.MAX_CAMERAS:
            raise RuntimeError(f"Maximum {self.MAX_CAMERAS} cameras reached")
        self._cameras[camera_id] = device
        self._enabled[camera_id] = enabled

    def remove_camera(self, camera_id: str) -> None:
        if camera_id in self._cameras:
            self._cameras[camera_id].stop_grabbing()
            self._cameras[camera_id].close()
            del self._cameras[camera_id]
            del self._enabled[camera_id]

    def connect_all(self, serial_map: dict[str, str]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for cam_id, serial in serial_map.items():
            if cam_id in self._cameras and self._enabled[cam_id]:
                results[cam_id] = self._cameras[cam_id].open(serial)
            else:
                results[cam_id] = False
        return results

    def disconnect_all(self) -> None:
        for cam_id, device in self._cameras.items():
            try:
                device.stop_grabbing()
                device.close()
            except Exception:
                logger.exception("Error closing camera %s", cam_id)

    def start_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for cam_id, device in self._cameras.items():
            if self._enabled.get(cam_id, False):
                results[cam_id] = device.start_grabbing()
            else:
                results[cam_id] = False
        return results

    def stop_all(self) -> None:
        for device in self._cameras.values():
            device.stop_grabbing()

    def get_all_status(self) -> list[CameraStatus]:
        return [d.get_status() for d in self._cameras.values()]

    def get_camera(self, camera_id: str) -> LineScanDevice | None:
        return self._cameras.get(camera_id)

    def get_enabled_camera_ids(self) -> list[str]:
        return [cid for cid, enabled in self._enabled.items() if enabled]

    def set_enabled(self, camera_id: str, enabled: bool) -> None:
        if camera_id in self._enabled:
            self._enabled[camera_id] = enabled

    @property
    def camera_count(self) -> int:
        return len([e for e in self._enabled.values() if e])
