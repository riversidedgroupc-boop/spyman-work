"""ROI manager — provides ROI rectangles for focus evaluation.

Wraps TubeROIModel and provides convenience methods for getting
center/left/right ROI coordinates.
"""

from __future__ import annotations

from line_scan_af.autofocus.tube_roi_model import TubeROIDefinition, TubeROIModel


class ROIManager:
    """Manages ROI definitions for a single camera during autofocus."""

    def __init__(self, roi_def: TubeROIDefinition) -> None:
        self._def = roi_def

    @property
    def definition(self) -> TubeROIDefinition:
        return self._def

    def get_center_roi(self) -> tuple[int, int, int, int]:
        """Get the center ROI (primary focus target)."""
        return self._def.center_roi

    def get_left_roi(self) -> tuple[int, int, int, int]:
        """Get the left ROI (for DOF edge verification)."""
        return self._def.left_roi

    def get_right_roi(self) -> tuple[int, int, int, int]:
        """Get the right ROI (for DOF edge verification)."""
        return self._def.right_roi

    def get_overlap_roi(self) -> tuple[int, int, int, int] | None:
        """Get the overlap ROI (for adjacent camera overlap check)."""
        return self._def.overlap_roi

    def get_all_rois(self) -> list[tuple[int, int, int, int]]:
        """Get all non-None ROIs as a list."""
        rois = [self._def.center_roi, self._def.left_roi, self._def.right_roi]
        if self._def.overlap_roi is not None:
            rois.append(self._def.overlap_roi)
        return rois

    @classmethod
    def from_model(cls, model: TubeROIModel, camera_id: str) -> ROIManager:
        """Create a ROIManager from a TubeROIModel and camera ID."""
        return cls(model.compute_for_camera(camera_id))
