"""Motion control card Z-axis stage controller skeleton.

Reserved for future motion control card integration (e.g., Galil, ACS, PMAC).
Currently a minimal skeleton — the actual card-specific API must be configured
per deployment.
"""

from __future__ import annotations

import logging
from typing import Any

from line_scan_af.controllers.stage_controller_base import StageControllerBase

logger = logging.getLogger(__name__)


class MotionCardStageController(StageControllerBase):
    """Stage controller via dedicated motion control card.

    TODO: Implement motion-card-specific API (Galil, ACS, PMAC, etc.).
    The controller interface remains identical — only the driver layer
    changes when switching from serial to motion card.
    """

    def __init__(
        self,
        stage_id: str,
        card_type: str = "galil",
        axis: int = 0,
        z_min_mm: float = 0.0,
        z_max_mm: float = 30.0,
    ) -> None:
        self._stage_id = stage_id
        self._card_type = card_type
        self._axis = axis
        self._z_min = z_min_mm
        self._z_max = z_max_mm

        self._connected = False
        self._homed = False
        self._position: float = -1.0
        self._moving = False

    def connect(self) -> bool:
        # TODO: Initialize motion card and claim axis
        logger.warning("[%s] Motion card connect: type '%s' not implemented (TODO)", self._stage_id, self._card_type)
        return False

    def disconnect(self) -> None:
        self._connected = False
        self._homed = False

    def home(self) -> bool:
        logger.warning("[%s] Motion card home: not implemented (TODO)", self._stage_id)
        return False

    def is_homed(self) -> bool:
        return self._homed

    def move_to(self, z_mm: float) -> bool:
        logger.warning("[%s] Motion card move_to: not implemented (TODO)", self._stage_id)
        return False

    def move_relative(self, dz_mm: float) -> bool:
        return False

    def wait_until_done(self, timeout_s: float) -> bool:
        return False

    def get_position(self) -> float:
        return self._position

    def stop(self) -> None:
        pass

    def emergency_stop(self) -> None:
        logger.warning("[%s] Motion card emergency stop (TODO)", self._stage_id)

    def is_moving(self) -> bool:
        return self._moving

    def get_status(self) -> dict[str, Any]:
        return {
            "stage_id": self._stage_id,
            "connected": self._connected,
            "homed": self._homed,
            "position_mm": round(self._position, 3),
            "moving": self._moving,
            "error": None,
            "driver_type": "motion_card",
            "card_type": self._card_type,
            "axis": self._axis,
        }
