"""Depth-of-field verification for cylindrical tube inspection.

Checks that the edge ROIs (left/right, farther from camera) still have
acceptable sharpness relative to the center ROI. For a cylindrical surface,
the edges are at a different working distance and may be out of focus even
when the center is sharp.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DOFResult:
    """Result of a depth-of-field check."""

    status: str  # "PASS", "WARNING", "FAIL"
    center_score: float
    left_score: float
    right_score: float
    edge_ratio_left: float
    edge_ratio_right: float
    threshold: float
    suggestions: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return self.status in ("PASS", "WARNING")


class DepthOfFieldChecker:
    """Validates that edge regions are sufficiently sharp relative to center."""

    _DOF_SUGGESTIONS: list[str] = [
        "Aperture too wide, insufficient depth of field",
        "Single camera coverage angle too large",
        "ROIs too close to image edge",
        "Light reflection at edges too strong",
        "Tube diameter changed — re-focus recommended",
        "Consider reducing effective detection area",
        "Consider increasing adjacent camera overlap",
        "Consider adjusting aperture or enhancing lighting",
    ]

    @staticmethod
    def check(
        center_score: float,
        left_score: float,
        right_score: float,
        edge_ratio_threshold: float = 0.7,
    ) -> str:
        """Check depth of field based on edge-to-center sharpness ratios.

        Args:
            center_score: Sharpness score of center ROI (primary focus).
            left_score: Sharpness score of left edge ROI.
            right_score: Sharpness score of right edge ROI.
            edge_ratio_threshold: Minimum acceptable edge/center ratio.

        Returns:
            "PASS" if both ratios >= threshold.
            "WARNING" if one ratio < threshold.
            "FAIL" if both ratios < threshold.
        """
        if center_score <= 0:
            return "FAIL"

        ratio_left = left_score / center_score
        ratio_right = right_score / center_score

        left_ok = ratio_left >= edge_ratio_threshold
        right_ok = ratio_right >= edge_ratio_threshold

        if left_ok and right_ok:
            logger.info("DOF check PASS: left=%.2f, right=%.2f (threshold=%.2f)",
                        ratio_left, ratio_right, edge_ratio_threshold)
            return "PASS"
        elif left_ok or right_ok:
            logger.warning("DOF check WARNING: left=%.2f, right=%.2f (threshold=%.2f)",
                           ratio_left, ratio_right, edge_ratio_threshold)
            return "WARNING"
        else:
            logger.error("DOF check FAIL: left=%.2f, right=%.2f (threshold=%.2f)",
                         ratio_left, ratio_right, edge_ratio_threshold)
            return "FAIL"

    @staticmethod
    def analyze(
        center_score: float,
        left_score: float,
        right_score: float,
        edge_ratio_threshold: float = 0.7,
    ) -> DOFResult:
        """Full DOF analysis with suggestions.

        Returns a DOFResult with status, ratios, and improvement suggestions.
        """
        if center_score <= 0:
            return DOFResult(
                status="FAIL",
                center_score=center_score,
                left_score=left_score,
                right_score=right_score,
                edge_ratio_left=0.0,
                edge_ratio_right=0.0,
                threshold=edge_ratio_threshold,
                suggestions=["Center score is zero or negative — check image quality"],
            )

        ratio_left = left_score / center_score
        ratio_right = right_score / center_score

        status = DepthOfFieldChecker.check(
            center_score, left_score, right_score, edge_ratio_threshold
        )

        suggestions = []
        if status != "PASS":
            if ratio_left < edge_ratio_threshold:
                suggestions.append(f"Left edge ratio {ratio_left:.2f} < {edge_ratio_threshold}")
            if ratio_right < edge_ratio_threshold:
                suggestions.append(f"Right edge ratio {ratio_right:.2f} < {edge_ratio_threshold}")
            suggestions.extend(DepthOfFieldChecker._DOF_SUGGESTIONS[:3])

        return DOFResult(
            status=status,
            center_score=center_score,
            left_score=left_score,
            right_score=right_score,
            edge_ratio_left=round(ratio_left, 3),
            edge_ratio_right=round(ratio_right, 3),
            threshold=edge_ratio_threshold,
            suggestions=suggestions,
        )
