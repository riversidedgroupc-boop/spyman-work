"""OpenCV traditional vision runner for surface defect detection.

Performs bright-spot, dark-spot, scratch-like, and local-contrast anomaly
detection using classical image-processing techniques (no deep learning required).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.fusion.decision_types import BBoxPrediction, UnifiedPrediction
from src.inference.base_runner import BaseRunner
from src.utils.image_utils import load_image
from src.utils.logger import get_logger

_log = get_logger()


def _contour_to_xyxy(cnt: np.ndarray) -> list[float]:
    """Convert an OpenCV contour to [x1, y1, x2, y2] format."""
    x, y, w, h = cv2.boundingRect(cnt)
    return [float(x), float(y), float(x + w), float(y + h)]


def _contour_area(cnt: np.ndarray) -> float:
    """Return contour area via cv2.contourArea."""
    return float(cv2.contourArea(cnt))


def _contour_aspect_ratio(cnt: np.ndarray) -> float:
    """Compute the aspect ratio of a contour's bounding rect (max/min)."""
    _, _, w, h = cv2.boundingRect(cnt)
    if w == 0 or h == 0:
        return 1.0
    return max(w / h, h / w)


def _score_from_area(area: float, max_area: float, offset: float = 0.2) -> float:
    """Map area to a confidence-like score in [offset, 1.0]."""
    if max_area <= 0:
        return offset
    ratio = min(area / max_area, 1.0)
    return round(offset + ratio * (1.0 - offset), 4)


def _score_from_contrast(contrast: float, max_contrast: float = 255.0) -> float:
    """Map contrast to a confidence-like score in [0.2, 1.0]."""
    ratio = min(contrast / max_contrast, 1.0)
    return round(0.2 + ratio * 0.8, 4)


class OpenCVRunner(BaseRunner):
    """Traditional computer-vision runner for surface-defect detection.

    Detects four categories of anomalies:

    * **opencv_bright**   – high-intensity spots (pits, scratches catching light).
    * **opencv_dark**     – low-intensity spots (dirt, stains, shadows).
    * **opencv_scratch**  – elongated features revealed by morphology gradient +
      directional filtering.
    * **opencv_anomaly**  – local-contrast deviations (Gaussian blur diff).

    Parameters
    ----------
    config : dict | None
        Keys: ``bright_threshold`` (220), ``dark_threshold`` (35),
        ``min_area_px`` (8), ``max_area_px`` (5000), ``scratch_aspect_ratio`` (5.0),
        ``local_contrast_threshold`` (30), ``morphology_kernel_size`` (3).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("opencv", config)
        self.bright_threshold: int = int(self.config.get("bright_threshold", 220))
        self.dark_threshold: int = int(self.config.get("dark_threshold", 35))
        self.min_area_px: int = int(self.config.get("min_area_px", 8))
        self.max_area_px: int = int(self.config.get("max_area_px", 5000))
        self.scratch_aspect_ratio: float = float(
            self.config.get("scratch_aspect_ratio", 5.0)
        )
        self.local_contrast_threshold: int = int(
            self.config.get("local_contrast_threshold", 30)
        )
        self.morph_kernel: int = int(
            self.config.get("morphology_kernel_size", 3)
        )
        # Directional kernel used for scratch enhancement
        self._scratch_kernel_size: int = int(
            self.config.get("scratch_kernel_size", 7)
        )

    # ------------------------------------------------------------------ load_model

    def load_model(self) -> None:
        """No model file needed — pure OpenCV pipeline."""
        self._is_loaded = True
        _log.info("OpenCV runner ready (no model loading required)")

    # ------------------------------------------------------------------ predict

    def predict(self, image_path: str | Path) -> UnifiedPrediction:
        """Run the full classical-vision defect detection pipeline."""
        t0 = time.perf_counter()

        gray = load_image(image_path, grayscale=True)
        predictions: list[BBoxPrediction] = []

        # 1. Bright spots --------------------------------------------------------
        predictions.extend(self._detect_bright_spots(gray))

        # 2. Dark spots ----------------------------------------------------------
        predictions.extend(self._detect_dark_spots(gray))

        # 3. Scratch-like features -----------------------------------------------
        predictions.extend(self._detect_scratches(gray))

        # 4. Local contrast anomalies --------------------------------------------
        predictions.extend(self._detect_local_contrast(gray))

        elapsed = (time.perf_counter() - t0) * 1000.0

        return UnifiedPrediction(
            image_path=str(image_path),
            model_name="opencv",
            predictions=predictions,
            runtime_ms=elapsed,
        )

    # ----------------------------------------------------------------- predict_batch

    def predict_batch(self, image_paths: list[str | Path]) -> list[UnifiedPrediction]:
        """Process batch sequentially."""
        return [self.predict(p) for p in image_paths]

    # --------------------------------------------------------- _detect_bright_spots

    def _detect_bright_spots(self, gray: np.ndarray) -> list[BBoxPrediction]:
        """Detect bright spots via simple thresholding."""
        _, thresh = cv2.threshold(gray, self.bright_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[BBoxPrediction] = []
        for cnt in contours:
            area = _contour_area(cnt)
            if area < self.min_area_px or area > self.max_area_px:
                continue

            bbox = _contour_to_xyxy(cnt)
            # Mean intensity inside contour as confidence proxy
            mask = np.zeros_like(gray)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_val = float(cv2.mean(gray, mask=mask)[0])
            score = _score_from_contrast(mean_val, 255.0)

            results.append(
                BBoxPrediction(
                    type="bbox",
                    class_name="opencv_bright",
                    confidence=score,
                    bbox_xyxy=bbox,
                    score=score,
                )
            )
        return results

    # ---------------------------------------------------------- _detect_dark_spots

    def _detect_dark_spots(self, gray: np.ndarray) -> list[BBoxPrediction]:
        """Detect dark spots via inverted thresholding."""
        _, thresh = cv2.threshold(
            gray, self.dark_threshold, 255, cv2.THRESH_BINARY_INV
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[BBoxPrediction] = []
        for cnt in contours:
            area = _contour_area(cnt)
            if area < self.min_area_px or area > self.max_area_px:
                continue

            bbox = _contour_to_xyxy(cnt)
            # Darker regions get higher anomaly scores
            mask = np.zeros_like(gray)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_val = float(cv2.mean(gray, mask=mask)[0])
            darkness = 255.0 - mean_val
            score = _score_from_contrast(darkness, 255.0)

            results.append(
                BBoxPrediction(
                    type="bbox",
                    class_name="opencv_dark",
                    confidence=score,
                    bbox_xyxy=bbox,
                    score=score,
                )
            )
        return results

    # ------------------------------------------------------------ _detect_scratches

    def _detect_scratches(self, gray: np.ndarray) -> list[BBoxPrediction]:
        """Detect scratch-like elongated features.

        Uses morphology gradient to enhance edges, then thresholds and filters
        contours by aspect ratio to isolate scratch-like shapes.
        """
        kernel_size = max(self.morph_kernel, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

        # Morphological gradient = dilation - erosion
        gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)

        # Adaptive threshold on the gradient image
        grad_thresh = cv2.adaptiveThreshold(
            gradient,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )

        # Morphological close to connect nearby edge fragments
        close_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self._scratch_kernel_size, self._scratch_kernel_size)
        )
        closed = cv2.morphologyEx(grad_thresh, cv2.MORPH_CLOSE, close_kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[BBoxPrediction] = []
        for cnt in contours:
            area = _contour_area(cnt)
            if area < self.min_area_px or area > self.max_area_px:
                continue

            aspect = _contour_aspect_ratio(cnt)
            if aspect < self.scratch_aspect_ratio:
                continue

            bbox = _contour_to_xyxy(cnt)
            score = _score_from_area(area, float(self.max_area_px))

            results.append(
                BBoxPrediction(
                    type="bbox",
                    class_name="opencv_scratch",
                    confidence=score,
                    bbox_xyxy=bbox,
                    score=score,
                )
            )
        return results

    # -------------------------------------------------------- _detect_local_contrast

    def _detect_local_contrast(self, gray: np.ndarray) -> list[BBoxPrediction]:
        """Detect anomalies via local contrast deviation (Gaussian blur diff).

        Subtract a heavily blurred version from the original, threshold the
        absolute difference, and find significant connected components.
        """
        # Blur radius should be significantly larger than typical defect size
        blur_radius = max(15, self.morph_kernel * 5)
        if blur_radius % 2 == 0:
            blur_radius += 1

        blurred = cv2.GaussianBlur(gray, (blur_radius, blur_radius), 0)
        diff = cv2.absdiff(gray, blurred)

        _, thresh = cv2.threshold(
            diff,
            self.local_contrast_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        # Small morphological open to remove salt-and-pepper noise
        clean_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, clean_kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[BBoxPrediction] = []
        for cnt in contours:
            area = _contour_area(cnt)
            if area < self.min_area_px or area > self.max_area_px:
                continue

            bbox = _contour_to_xyxy(cnt)
            # Compute mean contrast inside the contour
            mask = np.zeros_like(gray)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_contrast = float(cv2.mean(diff, mask=mask)[0])
            score = _score_from_contrast(mean_contrast, 255.0)

            results.append(
                BBoxPrediction(
                    type="bbox",
                    class_name="opencv_anomaly",
                    confidence=score,
                    bbox_xyxy=bbox,
                    score=score,
                )
            )
        return results

    # ------------------------------------------------------------ get_model_info

    def get_model_info(self) -> dict[str, Any]:
        """Return runner metadata including all thresholds."""
        info = super().get_model_info()
        info.update(
            {
                "bright_threshold": self.bright_threshold,
                "dark_threshold": self.dark_threshold,
                "min_area_px": self.min_area_px,
                "max_area_px": self.max_area_px,
                "scratch_aspect_ratio": self.scratch_aspect_ratio,
                "local_contrast_threshold": self.local_contrast_threshold,
                "morphology_kernel_size": self.morph_kernel,
            }
        )
        return info
