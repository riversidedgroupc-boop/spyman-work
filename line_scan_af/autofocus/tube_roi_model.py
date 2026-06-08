"""Tube ROI model — computes ROI positions for cylindrical tube inspection.

For a cylindrical tube surface, different regions along the arc have different
working distances from the camera. The center ROI (closest to camera) is used
for focus search; left/right ROIs are used for depth-of-field verification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TubeROIDefinition:
    """ROI coordinates for a tube camera view."""
    camera_id: str
    tube_diameter_mm: float
    image_width: int
    image_height: int
    center_roi: tuple[int, int, int, int]   # (x, y, w, h)
    left_roi: tuple[int, int, int, int]
    right_roi: tuple[int, int, int, int]
    overlap_roi: tuple[int, int, int, int] | None = None


class TubeROIModel:
    """Computes ROI positions based on tube diameter and image dimensions.

    The model assumes the camera views a 120° arc of the tube surface.
    Resolution is uniform horizontally (line-scan pixels map linearly to surface).
    """

    def __init__(
        self,
        tube_diameter_mm: float = 8.0,
        image_width: int = 2048,
        image_height: int = 512,
        camera_arc_deg: float = 120.0,
        center_roi_width_ratio: float = 0.30,
        side_roi_width_ratio: float = 0.20,
        side_roi_offset_ratio: float = 0.30,
        roi_height_ratio: float = 0.60,
    ) -> None:
        self._diameter = tube_diameter_mm
        self._width = image_width
        self._height = image_height
        self._arc = camera_arc_deg
        self._center_width_ratio = center_roi_width_ratio
        self._side_width_ratio = side_roi_width_ratio
        self._side_offset_ratio = side_roi_offset_ratio
        self._roi_height_ratio = roi_height_ratio

    def compute_for_camera(self, camera_id: str) -> TubeROIDefinition:
        """Compute all ROIs for a given camera.

        Layout (horizontal):
        | left_roi | ...gap... | center_roi | ...gap... | right_roi |

        Each ROI is centered vertically.
        """
        roi_h = int(self._height * self._roi_height_ratio)
        roi_y = (self._height - roi_h) // 2

        # Center ROI
        cw = int(self._width * self._center_width_ratio)
        cx = (self._width - cw) // 2
        center = (cx, roi_y, cw, roi_h)

        # Left ROI
        sw = int(self._width * self._side_width_ratio)
        lx = int(self._width * self._side_offset_ratio) - sw // 2
        lx = max(0, lx)
        left = (lx, roi_y, sw, roi_h)

        # Right ROI
        rx = self._width - int(self._width * self._side_offset_ratio) - sw // 2
        rx = min(self._width - sw, max(0, rx))
        right = (rx, roi_y, sw, roi_h)

        return TubeROIDefinition(
            camera_id=camera_id,
            tube_diameter_mm=self._diameter,
            image_width=self._width,
            image_height=self._height,
            center_roi=center,
            left_roi=left,
            right_roi=right,
        )

    def update_diameter(self, diameter_mm: float) -> None:
        """Update tube diameter and recalculate on next compute_for_camera()."""
        self._diameter = diameter_mm
