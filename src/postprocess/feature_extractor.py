"""Feature extraction for DefectCandidate objects.

Computes geometric features in both pixel and real-world (mm) units,
classifies defect morphology (scratch-like, point-like, dense region),
and optionally computes gray-level contrast.
"""

from __future__ import annotations

from src.fusion.decision_types import DefectCandidate
from src.postprocess.unit_converter import PixelSize, area_px_to_mm2, pixels_to_mm


class FeatureExtractor:
    """Extracts and computes geometric and morphological features for
    DefectCandidate objects.
    """

    SCRATCH_ASPECT_RATIO_THRESHOLD: float = 5.0
    POINT_MAX_AREA_PX: float = 30.0
    POINT_MAX_ASPECT_RATIO: float = 3.0
    DENSE_REGION_DENSITY_THRESHOLD: float = 50.0  # per meter

    def __init__(
        self,
        scratch_aspect_threshold: float = 5.0,
        point_max_area_px: float = 30.0,
        point_max_aspect: float = 3.0,
        dense_density_threshold: float = 50.0,
    ):
        self.SCRATCH_ASPECT_RATIO_THRESHOLD = scratch_aspect_threshold
        self.POINT_MAX_AREA_PX = point_max_area_px
        self.POINT_MAX_ASPECT_RATIO = point_max_aspect
        self.DENSE_REGION_DENSITY_THRESHOLD = dense_density_threshold

    def extract_features(
        self,
        candidate: DefectCandidate,
        pixel_size_mm: tuple[float, float] = (0.01, 0.01),
    ) -> DefectCandidate:
        """Compute geometric features for a single DefectCandidate.

        Populates: area_mm2, length_px, length_mm, width_px, width_mm,
        is_long_scratch_like, is_point_like, is_dense_region, and optionally
        gray_contrast.

        Args:
            candidate: The defect candidate to compute features for.
            pixel_size_mm: (x_mm_per_pixel, y_mm_per_pixel) conversion factors.

        Returns:
            The same DefectCandidate with features populated (mutated in place).
        """
        ps = PixelSize(x=pixel_size_mm[0], y=pixel_size_mm[1])

        # Compute bbox dimensions from bbox_xyxy if not already set
        x1, y1, x2, y2 = candidate.bbox_xyxy
        if candidate.bbox_width <= 0:
            candidate.bbox_width = x2 - x1
        if candidate.bbox_height <= 0:
            candidate.bbox_height = y2 - y1

        # Compute area from bbox if not already set
        area_px = candidate.area_px
        if area_px <= 0:
            area_px = candidate.bbox_width * candidate.bbox_height
            candidate.area_px = area_px
        candidate.area_mm2 = area_px_to_mm2(area_px, ps)

        # Length (longest axis) and width (shortest axis)
        w, h = candidate.bbox_width, candidate.bbox_height
        if w >= h:
            length_px = w
            width_px = h
        else:
            length_px = h
            width_px = w

        candidate.length_px = length_px
        candidate.width_px = width_px
        candidate.length_mm = pixels_to_mm(length_px, ps.x)
        candidate.width_mm = pixels_to_mm(width_px, ps.y)

        # Aspect ratio
        candidate.aspect_ratio = length_px / (width_px + 1e-8)

        # Morphology classification
        candidate.is_long_scratch_like = (
            candidate.aspect_ratio >= self.SCRATCH_ASPECT_RATIO_THRESHOLD
        )
        candidate.is_point_like = (
            area_px < self.POINT_MAX_AREA_PX
            and candidate.aspect_ratio < self.POINT_MAX_ASPECT_RATIO
        )
        candidate.is_dense_region = (
            candidate.defect_density_per_meter is not None
            and candidate.defect_density_per_meter >= self.DENSE_REGION_DENSITY_THRESHOLD
        )

        # Gray-level contrast (optional — requires image)
        if hasattr(candidate, "_image") and candidate._image is not None:
            candidate.gray_contrast = self._compute_gray_contrast(candidate)

        return candidate

    def extract_all(
        self,
        candidates: list[DefectCandidate],
        pixel_size_mm: tuple[float, float] = (0.01, 0.01),
    ) -> list[DefectCandidate]:
        """Compute features for all candidates in a list.

        Args:
            candidates: List of DefectCandidate objects.
            pixel_size_mm: (x_mm_per_pixel, y_mm_per_pixel) conversion factors.

        Returns:
            The same list with features populated (mutated in place).
        """
        for c in candidates:
            self.extract_features(c, pixel_size_mm)
        return candidates

    @staticmethod
    def _compute_gray_contrast(candidate: DefectCandidate) -> float:
        """Compute gray-level contrast between a defect region and its
        surrounding background.

        Requires the candidate to have a temporary `_image` attribute set
        to a numpy array (grayscale).

        Args:
            candidate: DefectCandidate with _image attached.

        Returns:
            Contrast value (0.0 if image not available or region invalid).
        """
        import numpy as np

        image = getattr(candidate, "_image", None)
        if image is None or not isinstance(image, np.ndarray):
            return 0.0

        x1, y1, x2, y2 = candidate.bbox_xyxy
        h_img, w_img = image.shape[:2]

        # Clamp to image bounds
        x1_i = max(0, int(x1))
        y1_i = max(0, int(y1))
        x2_i = min(w_img, int(x2))
        y2_i = min(h_img, int(y2))

        if x1_i >= x2_i or y1_i >= y2_i:
            return 0.0

        # Foreground mean
        fg_patch = image[y1_i:y2_i, x1_i:x2_i]
        fg_mean = float(np.mean(fg_patch))

        # Background: expand the bbox by 50% outward, excluding the bbox itself
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        bw = (x2 - x1) * 1.5
        bh = (y2 - y1) * 1.5

        bx1 = max(0, int(cx - bw / 2.0))
        by1 = max(0, int(cy - bh / 2.0))
        bx2 = min(w_img, int(cx + bw / 2.0))
        by2 = min(h_img, int(cy + bh / 2.0))

        bg_mask = np.ones((by2 - by1, bx2 - bx1), dtype=np.uint8)
        # Carve out the actual defect region from the background mask
        local_x1 = x1_i - bx1
        local_y1 = y1_i - by1
        local_x2 = x2_i - bx1
        local_y2 = y2_i - by1

        local_x1_c = max(0, local_x1)
        local_y1_c = max(0, local_y1)
        local_x2_c = min(bg_mask.shape[1], local_x2)
        local_y2_c = min(bg_mask.shape[0], local_y2)

        if local_x1_c < local_x2_c and local_y1_c < local_y2_c:
            bg_mask[local_y1_c:local_y2_c, local_x1_c:local_x2_c] = 0

        bg_patch = image[by1:by2, bx1:bx2]
        bg_values = bg_patch[bg_mask == 1]

        if len(bg_values) == 0:
            return 0.0

        bg_mean = float(np.mean(bg_values))
        return abs(fg_mean - bg_mean)
