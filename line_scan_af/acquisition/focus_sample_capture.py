"""High-level focus sample capture with quality validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from line_scan_af.acquisition.line_scan_focus_capture import LineScanFocusCapture
from line_scan_af.utils.image_quality_checker import ImageQualityChecker, ImageQualityResult

logger = logging.getLogger(__name__)


@dataclass
class FocusSample:
    """A single focus sample captured at a specific Z position."""

    z_mm: float
    image: np.ndarray
    image_path: str | None = None
    quality: ImageQualityResult | None = None

    @property
    def is_valid(self) -> bool:
        return self.quality is not None and self.quality.is_acceptable


class FocusSampleCapture:
    """Captures focus samples at each Z position with quality validation."""

    def __init__(
        self,
        capture: LineScanFocusCapture,
        quality_checker: ImageQualityChecker,
        length_mm: float = 50.0,
        speed_mode: str = "low_speed",
        use_encoder: bool = True,
        fallback_row_count: int = 4096,
    ) -> None:
        self._capture = capture
        self._quality_checker = quality_checker
        self._length_mm = length_mm
        self._speed_mode = speed_mode
        self._use_encoder = use_encoder
        self._fallback_row_count = fallback_row_count

    def capture_at(self, z_mm: float) -> FocusSample:
        """Capture and validate a focus sample at the given Z position.

        Args:
            z_mm: Current Z position in mm.

        Returns:
            FocusSample with image and quality check result.
        """
        logger.info("Capturing focus sample at Z=%.3f mm", z_mm)

        # Notify camera of current Z so it can simulate defocus (mock) or track state
        self._capture.set_z_position(z_mm)

        image = self._capture.capture(
            length_mm=self._length_mm,
            speed_mode=self._speed_mode,
            use_encoder=self._use_encoder,
            fallback_row_count=self._fallback_row_count,
        )

        quality = self._quality_checker.check(image)

        return FocusSample(
            z_mm=z_mm,
            image=image,
            quality=quality,
        )
