"""Mock Z-axis stage controller for development without hardware."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from line_scan_af.controllers.stage_controller_base import StageControllerBase

logger = logging.getLogger(__name__)


class MockStageController(StageControllerBase):
    """Simulates a Z-axis stage for offline development and testing.

    Features:
    - Simulated movement with configurable speed
    - Configurable failure injection (timeout, limit error)
    - Thread-safe position tracking
    """

    def __init__(
        self,
        stage_id: str = "mock_stage",
        z_min_mm: float = 0.0,
        z_max_mm: float = 30.0,
        move_speed_mm_s: float = 5.0,
        simulate_timeout: bool = False,
        simulate_limit_error: bool = False,
    ) -> None:
        self._stage_id = stage_id
        self._z_min = z_min_mm
        self._z_max = z_max_mm
        self._speed = move_speed_mm_s
        self._simulate_timeout = simulate_timeout
        self._simulate_limit_error = simulate_limit_error

        self._connected = False
        self._homed = False
        self._position: float = -1.0
        self._target: float = -1.0
        self._moving = False
        self._error: str | None = None
        self._lock = threading.Lock()
        self._move_thread: threading.Thread | None = None

    # ---- Connection ----

    def connect(self) -> bool:
        self._connected = True
        self._position = self._z_min
        logger.info("[%s] Mock stage connected at %.3f mm", self._stage_id, self._position)
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._homed = False
        logger.info("[%s] Mock stage disconnected", self._stage_id)

    # ---- Homing ----

    def home(self) -> bool:
        if not self._connected:
            return False
        # Simulate homing by moving to z_min
        time.sleep(0.3)
        self._homed = True
        self._position = self._z_min
        self._target = self._z_min
        logger.info("[%s] Mock stage homed at %.3f mm", self._stage_id, self._position)
        return True

    def is_homed(self) -> bool:
        return self._homed

    # ---- Movement ----

    def move_to(self, z_mm: float) -> bool:
        if not self._connected:
            return False

        # Soft limit check
        if z_mm < self._z_min or z_mm > self._z_max:
            if self._simulate_limit_error:
                self._error = f"Limit error: {z_mm} out of [{self._z_min}, {self._z_max}]"
                logger.error("[%s] %s", self._stage_id, self._error)
                return False
            z_mm = max(self._z_min, min(self._z_max, z_mm))
            logger.warning("[%s] Position clamped to %.3f mm", self._stage_id, z_mm)

        if self._simulate_timeout:
            self._error = "Simulated timeout"
            logger.error("[%s] %s", self._stage_id, self._error)
            return False

        self._target = z_mm
        self._moving = True

        # Simulate async movement in background thread
        self._move_thread = threading.Thread(
            target=self._simulate_move, daemon=True
        )
        self._move_thread.start()
        return True

    def move_relative(self, dz_mm: float) -> bool:
        return self.move_to(self._position + dz_mm)

    def wait_until_done(self, timeout_s: float) -> bool:
        if self._move_thread and self._move_thread.is_alive():
            self._move_thread.join(timeout=timeout_s)
            return not self._move_thread.is_alive()
        return True

    def _simulate_move(self) -> None:
        """Simulate gradual movement from current to target."""
        start = self._position
        end = self._target
        distance = abs(end - start)
        duration = distance / self._speed if self._speed > 0 else 0.1
        steps = max(int(duration * 20), 5)
        step_time = duration / steps

        for i in range(1, steps + 1):
            time.sleep(step_time)
            with self._lock:
                self._position = start + (end - start) * i / steps

        with self._lock:
            self._position = end
            self._moving = False
        logger.debug("[%s] Move complete: %.3f mm", self._stage_id, self._position)

    # ---- Position ----

    def get_position(self) -> float:
        with self._lock:
            return self._position

    # ---- Stop ----

    def stop(self) -> None:
        self._moving = False
        logger.info("[%s] Normal stop", self._stage_id)

    def emergency_stop(self) -> None:
        self._moving = False
        if self._move_thread and self._move_thread.is_alive():
            self._move_thread.join(timeout=0.5)
        logger.warning("[%s] Emergency stop!", self._stage_id)

    # ---- State ----

    def is_moving(self) -> bool:
        return self._moving

    def get_status(self) -> dict[str, Any]:
        return {
            "stage_id": self._stage_id,
            "connected": self._connected,
            "homed": self._homed,
            "position_mm": round(self._position, 3),
            "target_mm": round(self._target, 3),
            "moving": self._moving,
            "error": self._error,
            "driver_type": "mock",
        }
