"""Image quality validation for focus samples.

Detects overexposure, underexposure, empty images, and dimension mismatches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ImageQualityResult:
    """Result of an image quality check."""

    is_acceptable: bool = True
    is_overexposed: bool = False
    is_underexposed: bool = False
    is_empty: bool = False
    overexpose_ratio: float = 0.0
    underexpose_ratio: float = 0.0
    mean_intensity: float = 0.0
    issues: list[str] = field(default_factory=list)
    expected_shape: tuple[int, int] | None = None
    actual_shape: tuple[int, int] | None = None
    size_mismatch: bool = False


class ImageQualityChecker:
    """Validates focus sample image quality."""

    def __init__(
        self,
        overexpose_threshold: int = 250,
        overexpose_ratio_limit: float = 0.05,
        underexpose_threshold: int = 10,
        expected_shape: tuple[int, int] | None = None,
    ) -> None:
        self._over_thresh = overexpose_threshold
        self._over_ratio = overexpose_ratio_limit
        self._under_thresh = underexpose_threshold
        self._expected_shape = expected_shape

    def check(self, image: np.ndarray) -> ImageQualityResult:
        """Run all quality checks on an image.

        Args:
            image: 2D grayscale image array.

        Returns:
            ImageQualityResult with findings.
        """
        result = ImageQualityResult()

        if image is None or image.size == 0:
            result.is_acceptable = False
            result.is_empty = True
            result.issues.append("Empty image (None or zero size)")
            return result

        result.actual_shape = image.shape
        result.mean_intensity = float(np.mean(image))

        # Overexposure check
        over_pixels = np.sum(image >= self._over_thresh)
        result.overexpose_ratio = over_pixels / image.size
        if result.overexpose_ratio > self._over_ratio:
            result.is_overexposed = True
            result.is_acceptable = False
            result.issues.append(
                f"Overexposed: {result.overexpose_ratio:.2%} pixels >= {self._over_thresh}"
            )

        # Underexposure check
        under_pixels = np.sum(image <= self._under_thresh)
        result.underexpose_ratio = under_pixels / image.size
        if result.underexpose_ratio > self._over_ratio:
            result.is_underexposed = True
            result.is_acceptable = False
            result.issues.append(
                f"Underexposed: {result.underexpose_ratio:.2%} pixels <= {self._under_thresh}"
            )

        # Size mismatch check
        if self._expected_shape is not None and image.shape != self._expected_shape:
            result.size_mismatch = True
            result.is_acceptable = False
            result.issues.append(
                f"Size mismatch: expected {self._expected_shape}, got {image.shape}"
            )

        if result.issues:
            logger.warning("Image quality issues: %s", "; ".join(result.issues))
        else:
            logger.debug("Image quality OK (mean=%.1f)", result.mean_intensity)

        return result

    def set_expected_shape(self, shape: tuple[int, int]) -> None:
        """Set the expected image dimensions for subsequent checks."""
        self._expected_shape = shape
