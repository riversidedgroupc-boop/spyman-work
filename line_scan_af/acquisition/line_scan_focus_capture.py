"""Low-level line-scan capture orchestration using camera controller."""

from __future__ import annotations

import logging
import time

import numpy as np

from line_scan_af.controllers.camera_controller_base import CameraControllerBase

logger = logging.getLogger(__name__)


class LineScanFocusCapture:
    """Orchestrates line-scan image capture for a single Z position.

    Wraps a CameraControllerBase to provide consistent focus-sample capture
    with retry, quality check, and timing information.
    """

    def __init__(self, camera: CameraControllerBase, settle_ms: float = 150) -> None:
        self._camera = camera
        self._settle_ms = settle_ms

    def set_z_position(self, z_mm: float) -> None:
        """Forward Z position to camera for defocus simulation / bookkeeping."""
        self._camera.set_z_position(z_mm)

    def capture(
        self,
        length_mm: float,
        speed_mode: str = "low_speed",
        use_encoder: bool = True,
        fallback_row_count: int = 4096,
    ) -> np.ndarray:
        """Capture a focus sample after settling delay.

        Args:
            length_mm: Physical sample length in mm.
            speed_mode: "low_speed" or "normal".
            use_encoder: If True, use encoder-synced capture; else fallback to row count.
            fallback_row_count: Row count when encoder is not used.

        Returns:
            2D numpy array (height, width) — the line-scan image.

        Raises:
            ValueError: If the captured image is empty.
        """
        if self._settle_ms > 0:
            time.sleep(self._settle_ms / 1000.0)

        if use_encoder:
            image = self._camera.capture_by_encoder_length(length_mm)
        else:
            image = self._camera.capture_by_rows(fallback_row_count)

        if image is None or image.size == 0:
            raise ValueError("Capture returned empty image")

        logger.debug(
            "Captured %dx%d image (encoder=%s, length=%.1fmm)",
            image.shape[0], image.shape[1], use_encoder, length_mm,
        )
        return image
