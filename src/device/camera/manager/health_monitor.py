"""Camera health monitor — periodic status check, auto-reconnect on disconnect."""
from __future__ import annotations

import logging
import time
from threading import Thread, Event
from collections.abc import Callable

from src.device.camera.manager.camera_manager import CameraManager

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors connected cameras and attempts reconnection on failure."""

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
        self._serial_map = serial_map

    def set_on_disconnect(self, callback: Callable[[str], None]) -> None:
        self._on_disconnect = callback

    def set_on_reconnect(self, callback: Callable[[str], None]) -> None:
        self._on_reconnect = callback

    def start(self) -> None:
        self._running.set()
        self._thread = Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
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
                    serial = self._serial_map.get(cam_id)
                    if serial:
                        attempts = self._reconnect_attempts.get(cam_id, 0)
                        if attempts < self._max_reconnect_attempts:
                            logger.info("Reconnecting %s (attempt %d/%d)", cam_id, attempts + 1, self._max_reconnect_attempts)
                            if device.open(serial):
                                device.start_grabbing()
                                logger.info("Camera %s reconnected", cam_id)
                                self._reconnect_attempts[cam_id] = 0
                                if self._on_reconnect:
                                    self._on_reconnect(cam_id)
                            else:
                                self._reconnect_attempts[cam_id] = attempts + 1
            time.sleep(self._check_interval)
