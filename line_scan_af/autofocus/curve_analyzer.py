"""Focus score curve analysis and peak finding.

Analyzes the (Z, score) data from an autofocus sweep to find the best focus
position, validate curve quality, and detect anomalies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)


@dataclass
class CurveAnalysisResult:
    """Result of focus curve analysis."""

    best_z_mm: float
    best_score: float
    fitted_peak_z_mm: float | None = None
    fitted_peak_score: float | None = None
    is_valid: bool = True
    peak_at_boundary: bool = False
    is_flat: bool = False
    is_noisy: bool = False
    multi_peak: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def recommended_z_mm(self) -> float:
        """Best Z position — prefer fitted peak if available, else raw max."""
        if self.fitted_peak_z_mm is not None:
            return round(self.fitted_peak_z_mm, 3)
        return round(self.best_z_mm, 3)


class CurveAnalyzer:
    """Analyzes Z-vs-sharpness data to find the optimal focus position."""

    @staticmethod
    def find_best_by_max(
        z_positions: list[float], scores: list[float]
    ) -> tuple[float, float, int]:
        """Find the Z with the highest score.

        Returns:
            (best_z, best_score, index)
        """
        if not scores:
            raise ValueError("Empty score list")
        idx = int(np.argmax(scores))
        return z_positions[idx], scores[idx], idx

    @staticmethod
    def quadratic_fit(
        z_positions: list[float], scores: list[float]
    ) -> tuple[float, float] | None:
        """Fit a quadratic curve to find the interpolated peak.

        Model: score = a*z^2 + b*z + c
        Peak at z = -b/(2a)

        Args:
            z_positions: Z positions in mm.
            scores: Sharpness scores.

        Returns:
            (peak_z, peak_score) or None if fit fails.
        """
        if len(scores) < 3:
            logger.warning("Need at least 3 points for quadratic fit, got %d", len(scores))
            return None

        z_arr = np.array(z_positions, dtype=np.float64)
        s_arr = np.array(scores, dtype=np.float64)

        def quadratic(z, a, b, c):
            return a * z * z + b * z + c

        try:
            # Initial guess: a negative (downward parabola)
            p0 = [-0.01, 0.5, np.median(s_arr)]
            popt, _ = curve_fit(quadratic, z_arr, s_arr, p0=p0, maxfev=5000)
            a, b, c = popt

            if a >= 0:
                # Upward parabola — no peak
                logger.warning("Quadratic fit: upward parabola (a=%.6f), no peak", a)
                return None

            peak_z = -b / (2 * a)
            peak_score = quadratic(peak_z, a, b, c)

            # Sanity check: peak should be within or near the search range
            z_span = z_arr.max() - z_arr.min()
            if peak_z < z_arr.min() - z_span or peak_z > z_arr.max() + z_span:
                logger.warning("Fitted peak %.3f is far outside search range", peak_z)
                return None

            return round(float(peak_z), 3), round(float(peak_score), 1)

        except (RuntimeError, ValueError) as e:
            logger.warning("Quadratic fit failed: %s", e)
            return None

    @staticmethod
    def is_peak_at_boundary(
        best_z: float, z_positions: list[float], margin_ratio: float = 0.1
    ) -> bool:
        """Check if the best Z is at the edge of the search range."""
        if not z_positions:
            return False
        z_arr = np.array(z_positions)
        z_span = z_arr.max() - z_arr.min()
        margin = z_span * margin_ratio
        return best_z <= z_arr.min() + margin or best_z >= z_arr.max() - margin

    @staticmethod
    def check_flatness(scores: list[float], threshold_ratio: float = 1.2) -> bool:
        """Check if the score curve is too flat (no clear peak).

        A curve is "flat" if max/median < threshold_ratio.
        """
        if not scores:
            return True
        s_arr = np.array(scores)
        median = np.median(s_arr)
        if median < 1e-6:
            return True
        return (s_arr.max() / median) < threshold_ratio

    @staticmethod
    def check_multi_peak(scores: list[float], threshold_ratio: float = 0.8) -> bool:
        """Check for multiple significant peaks using simple local maxima."""
        if len(scores) < 5:
            return False

        s_arr = np.array(scores)
        peaks = []
        for i in range(1, len(s_arr) - 1):
            if s_arr[i] > s_arr[i - 1] and s_arr[i] > s_arr[i + 1]:
                peaks.append(s_arr[i])

        if len(peaks) <= 1:
            return False

        max_peak = max(peaks)
        # Check if there's another peak > threshold_ratio * max_peak
        secondary_peaks = [p for p in peaks if p != max_peak]
        if not secondary_peaks:
            return False
        return max(secondary_peaks) / max_peak > threshold_ratio

    @staticmethod
    def check_noisy(scores: list[float]) -> bool:
        """Check if the score curve is excessively noisy.

        Uses the coefficient of variation of first differences.
        """
        if len(scores) < 4:
            return False
        diffs = np.abs(np.diff(scores))
        if np.mean(diffs) < 1e-6:
            return False
        return float(np.std(diffs) / np.mean(diffs)) > 2.0

    @staticmethod
    def analyze(
        z_positions: list[float],
        scores: list[float],
        config: dict | None = None,
    ) -> CurveAnalysisResult:
        """Full curve analysis — find best Z and validate curve quality.

        Args:
            z_positions: Z positions in mm (same length as scores).
            scores: Sharpness scores.
            config: Optional dict with keys:
                - min_focus_score (default 100.0)
                - peak_ratio (default 1.2)
                - verify_ratio (default 0.85)
                - reject_peak_at_boundary (default True)
                - enable_quadratic_fit (default True)

        Returns:
            CurveAnalysisResult with best Z and validation results.
        """
        cfg = config or {}
        min_score = cfg.get("min_focus_score", 100.0)
        peak_ratio = cfg.get("peak_ratio", 1.2)
        reject_boundary = cfg.get("reject_peak_at_boundary", True)
        enable_fit = cfg.get("enable_quadratic_fit", True)

        result = CurveAnalysisResult(best_z_mm=0.0, best_score=0.0)

        if not z_positions or not scores:
            result.is_valid = False
            result.issues.append("Empty data")
            return result
        if len(z_positions) != len(scores):
            result.is_valid = False
            result.issues.append("z_positions and scores length mismatch")
            return result

        # Find raw max
        best_z, best_score, _ = CurveAnalyzer.find_best_by_max(z_positions, scores)
        result.best_z_mm = best_z
        result.best_score = best_score

        # Score too low
        if best_score < min_score:
            result.is_valid = False
            result.issues.append(f"Best score ({best_score:.1f}) < min ({min_score:.1f})")

        # Flat curve
        if CurveAnalyzer.check_flatness(scores, peak_ratio):
            result.is_flat = True
            result.is_valid = False
            result.issues.append("Curve is too flat — no clear peak")

        # Multi-peak
        if CurveAnalyzer.check_multi_peak(scores):
            result.multi_peak = True
            # Not necessarily invalid, but worth flagging
            result.issues.append("Multiple significant peaks detected")

        # Noisy
        if CurveAnalyzer.check_noisy(scores):
            result.is_noisy = True
            result.issues.append("Curve is excessively noisy")

        # Peak at boundary
        if CurveAnalyzer.is_peak_at_boundary(best_z, z_positions):
            result.peak_at_boundary = True
            if reject_boundary:
                result.is_valid = False
            result.issues.append(f"Best Z ({best_z:.3f}) is at search boundary")

        # Quadratic fit
        if enable_fit:
            fit = CurveAnalyzer.quadratic_fit(z_positions, scores)
            if fit is not None:
                result.fitted_peak_z_mm, result.fitted_peak_score = fit

        return result
