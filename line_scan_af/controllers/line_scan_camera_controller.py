"""Real line-scan camera controller skeleton.

Currently a skeleton — actual camera SDK integration (e.g., Basler, Dalsa, Teledyne)
must be configured per deployment.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from line_scan_af.controllers.camera_controller_base import CameraControllerBase

logger = logging.getLogger(__name__)


class LineScanCameraController(CameraControllerBase):
    """Real line-scan camera controller.

    TODO: Integrate actual camera SDK. The interface is designed to work with
    GigE Vision / Camera Link / CoaXPress cameras via vendor SDKs.
    """

    def __init__(self, camera_id: str, camera_config: dict[str, Any] | None = None) -> None:
        self._camera_id = camera_id
        self._config = camera_config or {}
        self._connected = False
        self._exposure_locked = False
        self._focus_mode = False

    def connect(self) -> bool:
        # TODO: Initialize camera via SDK
        logger.warning("[%s] Camera SDK integration not implemented (TODO)", self._camera_id)
        return False

    def disconnect(self) -> None:
        self._connected = False

    def lock_exposure_gain(self) -> None:
        # TODO: Set exposure/gain via SDK and verify stability
        logger.warning("[%s] lock_exposure_gain: not implemented (TODO)", self._camera_id)
        self._exposure_locked = True

    def set_focus_capture_mode(self) -> None:
        # TODO: Configure trigger mode, ROI, line rate for focus
        logger.warning("[%s] set_focus_capture_mode: not implemented (TODO)", self._camera_id)
        self._focus_mode = True

    def capture_by_rows(self, row_count: int) -> np.ndarray:
        # TODO: Capture N lines from camera
        logger.warning("[%s] capture_by_rows: not implemented (TODO)", self._camera_id)
        return np.zeros((self._config.get("fallback_height", 512), self._config.get("fallback_width", 2048)), dtype=np.uint8)

    def capture_by_encoder_length(self, length_mm: float) -> np.ndarray:
        # TODO: Capture using encoder trigger
        logger.warning("[%s] capture_by_encoder_length: not implemented (TODO)", self._camera_id)
        return np.zeros((512, 2048), dtype=np.uint8)

    def capture_focus_sample(self, length_mm: float, speed_mode: str) -> np.ndarray:
        # TODO: Full focus capture with encoder sync
        logger.warning("[%s] capture_focus_sample: not implemented (TODO)", self._camera_id)
        return np.zeros((512, 2048), dtype=np.uint8)

    def get_status(self) -> dict[str, Any]:
        return {
            "camera_id": self._camera_id,
            "connected": self._connected,
            "exposure_locked": self._exposure_locked,
            "focus_mode": self._focus_mode,
        }
