"""Sharpness evaluation algorithms for autofocus.

All methods are static — pure functions with no side effects, independently testable.
Primary algorithm: Tenengrad (Sobel gradient magnitude).
Auxiliary: Laplacian variance, gray-level variance.
"""

from __future__ import annotations

import cv2
import numpy as np


class FocusEvaluator:
    """Collection of focus sharpness metrics."""

    @staticmethod
    def tenengrad(image: np.ndarray, ksize: int = 3) -> float:
        """Tenengrad sharpness using Sobel gradient magnitude.

        This is the PRIMARY algorithm for focus evaluation.
        Computes mean squared gradient magnitude in X and Y directions.

        Args:
            image: 2D grayscale image.
            ksize: Sobel kernel size (must be 1, 3, 5, or 7).

        Returns:
            Sharpness score (higher = sharper).
        """
        if image is None or image.size == 0:
            return 0.0
        gx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=ksize)
        gy = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=ksize)
        magnitude = gx * gx + gy * gy
        return float(np.mean(magnitude))

    @staticmethod
    def laplacian_variance(image: np.ndarray) -> float:
        """Sharpness via variance of Laplacian.

        Good at detecting fine texture differences.
        Higher variance = more high-frequency content = sharper.

        Args:
            image: 2D grayscale image.

        Returns:
            Variance of Laplacian response.
        """
        if image is None or image.size == 0:
            return 0.0
        lap = cv2.Laplacian(image, cv2.CV_64F)
        return float(np.var(lap))

    @staticmethod
    def gray_variance(image: np.ndarray) -> float:
        """Simple gray-level variance — useful for low-texture scenes.

        Args:
            image: 2D grayscale image.

        Returns:
            Pixel intensity variance.
        """
        if image is None or image.size == 0:
            return 0.0
        return float(np.var(image))

    @staticmethod
    def detect_overexposure(image: np.ndarray, threshold: int = 250, max_ratio: float = 0.05) -> bool:
        """Check if image has excessive saturated pixels."""
        if image is None or image.size == 0:
            return False
        ratio = np.sum(image >= threshold) / image.size
        return ratio > max_ratio

    @staticmethod
    def detect_underexposure(image: np.ndarray, threshold: int = 10, max_ratio: float = 0.05) -> bool:
        """Check if image has excessive dark pixels."""
        if image is None or image.size == 0:
            return False
        ratio = np.sum(image <= threshold) / image.size
        return ratio > max_ratio

    @staticmethod
    def multi_roi_median_score(
        image: np.ndarray,
        rois: list[tuple[int, int, int, int]],
        algorithm: str = "tenengrad",
    ) -> float:
        """Compute median sharpness score across multiple ROIs.

        This is more robust than a single ROI — it reduces the impact of
        localized glare, scratches, or contamination.

        Args:
            image: 2D grayscale image.
            rois: List of (x, y, w, h) ROI rectangles.
            algorithm: "tenengrad", "laplacian", or "gray_variance".

        Returns:
            Median score across all ROIs.
        """
        if not rois:
            return 0.0

        algo = {
            "tenengrad": FocusEvaluator.tenengrad,
            "laplacian": FocusEvaluator.laplacian_variance,
            "gray_variance": FocusEvaluator.gray_variance,
        }.get(algorithm, FocusEvaluator.tenengrad)

        scores = []
        for x, y, w, h in rois:
            h_img, w_img = image.shape[:2]
            x = max(0, min(x, w_img - 1))
            y = max(0, min(y, h_img - 1))
            w = max(1, min(w, w_img - x))
            h = max(1, min(h, h_img - y))
            roi = image[y:y + h, x:x + w]
            scores.append(algo(roi))

        return float(np.median(scores)) if scores else 0.0

    @staticmethod
    def _crop_roi(
        image: np.ndarray, roi: tuple[int, int, int, int]
    ) -> np.ndarray:
        """Crop a region of interest from an image.

        Args:
            image: 2D grayscale image.
            roi: (x, y, w, h) rectangle.

        Returns:
            Cropped sub-image.
        """
        x, y, w, h = roi
        x = max(0, min(x, image.shape[1] - 1))
        y = max(0, min(y, image.shape[0] - 1))
        w = max(1, min(w, image.shape[1] - x))
        h = max(1, min(h, image.shape[0] - y))
        return image[y:y + h, x:x + w]
