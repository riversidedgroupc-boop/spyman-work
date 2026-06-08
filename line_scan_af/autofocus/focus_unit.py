"""FocusUnit — aggregates one camera, one stage, and its ROI configuration.

A FocusUnit is the atomic unit of autofocus: one camera + its Z stage + ROI model.
"""

from __future__ import annotations

from dataclasses import dataclass

from line_scan_af.controllers.camera_controller_base import CameraControllerBase
from line_scan_af.controllers.stage_controller_base import StageControllerBase
from line_scan_af.autofocus.roi_manager import ROIManager


@dataclass
class FocusUnit:
    """Binds a camera, stage, and ROI manager for autofocus."""

    camera_id: str
    stage_id: str
    light_id: str = ""
    enabled: bool = True

    # These are set after creation via the builder/manager
    stage_controller: StageControllerBase | None = None
    camera_controller: CameraControllerBase | None = None
    roi_manager: ROIManager | None = None

    @property
    def is_ready(self) -> bool:
        """Check if all components are connected and ready."""
        if not self.enabled:
            return False
        if self.stage_controller is None or self.camera_controller is None:
            return False
        stage_status = self.stage_controller.get_status()
        camera_status = self.camera_controller.get_status()
        return (
            stage_status.get("connected", False)
            and camera_status.get("connected", False)
        )
