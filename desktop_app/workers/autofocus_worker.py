# ruff: noqa: E402
"""Autofocus worker — QThread for background autofocus execution.

Inherits desktop_app BaseWorker pattern.
"""

from __future__ import annotations

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Signal

from desktop_app.workers.base_worker import BaseWorker
from line_scan_af.autofocus.focus_unit import FocusUnit
from line_scan_af.autofocus.multi_camera_autofocus_manager import MultiCameraAutoFocusManager
from line_scan_af.autofocus.events import (
    CameraAFComplete,
    CameraAFFailed,
    EmergencyStopped,
    ImageCaptured,
    ProgressUpdate,
    ScoreComputed,
    SearchPhaseDone,
    StageMoved,
)
from line_scan_af.config.config_loader import (
    CameraStageBinding,
    StageDriverConfig,
)


class AutofocusWorker(BaseWorker):
    """Runs multi-camera autofocus in a background thread.

    Signals (inherited from BaseWorker):
        started()
        progress(int, int)      — current_camera_index, total_cameras
        message(str)            — log message
        error(str)              — error message
        finished()              — all done or cancelled

    Additional signals:
        score_computed(str, float, float)  — (camera_id, z_mm, score)
        camera_done(str, object)           — (camera_id, result dict)
        all_done(object)                   — MultiFocusResult dict
        curve_updated(list, list)          — (z_positions, scores) per camera
        image_ready(str, object, object)   — (camera_id, image_ndarray, roi_dict)
    """

    score_computed = Signal(str, float, float)
    camera_done = Signal(str, object)
    all_done = Signal(object)
    curve_updated = Signal(list, list)
    image_ready = Signal(str, object, object)

    def __init__(
        self,
        focus_units: list,
        config: dict,
        binding: CameraStageBinding,
        driver_cfg: StageDriverConfig,
        parent=None,
        product_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._units = focus_units
        self._config = config
        self._binding = binding
        self._driver_cfg = driver_cfg
        self._product_name = product_name
        self._manager: MultiCameraAutoFocusManager | None = None

    def _run_impl(self) -> None:
        """Main autofocus execution — runs synchronously in the QThread."""
        from line_scan_af.autofocus.multi_camera_autofocus_manager import (
            MultiCameraAutoFocusManager,
        )

        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        run_dir = Path("focus_runs") / run_id

        self._manager = MultiCameraAutoFocusManager(
            focus_units=self._units,
            config=self._config,
            binding=self._binding,
            driver_cfg=self._driver_cfg,
            run_dir=run_dir,
            product_name=getattr(self, '_product_name', None),
        )

        total = len([u for u in self._units if u.enabled])
        camera_results: dict[str, dict] = {}
        current_camera_idx = 0
        curve_z: list[float] = []
        curve_scores: list[float] = []

        for event in self._manager.run_sequential():
            if self._cancelled:
                self._manager.emergency_stop()
                self.message.emit("Autofocus cancelled by user")
                break

            if isinstance(event, ProgressUpdate):
                self.message.emit(f"[{event.camera_id}] {event.message}")

            elif isinstance(event, StageMoved):
                self.message.emit(f"[{event.camera_id}] Stage → Z={event.z_mm:.3f}")

            elif isinstance(event, ImageCaptured):
                self.message.emit(f"[{event.camera_id}] Image captured @ Z={event.z_mm:.3f}")

            elif isinstance(event, ScoreComputed):
                curve_z.append(event.z_mm)
                curve_scores.append(event.score)
                self.score_computed.emit(event.camera_id, event.z_mm, event.score)

                if event.camera_id != (getattr(self, "_last_cam", "")):
                    setattr(self, "_last_cam", event.camera_id)
                    curve_z.clear()
                    curve_scores.clear()
                    curve_z.append(event.z_mm)
                    curve_scores.append(event.score)

            elif isinstance(event, SearchPhaseDone):
                self.curve_updated.emit(list(curve_z), list(curve_scores))
                self.message.emit(
                    f"[{event.camera_id}] {event.phase} search done: "
                    f"best Z={event.best_z:.3f}, score={event.best_score:.1f}"
                )

            elif isinstance(event, CameraAFComplete):
                result = {
                    "camera_id": event.camera_id,
                    "best_z_mm": event.best_z_mm,
                    "center_score": event.center_score,
                    "left_score": event.left_score,
                    "right_score": event.right_score,
                    "dof_check": event.dof_check,
                    "verify_score": event.verify_score,
                    "status": event.status,
                }
                camera_results[event.camera_id] = result
                self.camera_done.emit(event.camera_id, result)
                current_camera_idx += 1
                self.progress.emit(current_camera_idx, total)

            elif isinstance(event, CameraAFFailed):
                result = {
                    "camera_id": event.camera_id,
                    "status": "FAILED",
                    "error": event.reason,
                }
                camera_results[event.camera_id] = result
                self.camera_done.emit(event.camera_id, result)
                self.message.emit(f"[{event.camera_id}] AF FAILED: {event.reason}")

            elif isinstance(event, EmergencyStopped):
                self.message.emit("EMERGENCY STOP triggered!")
                break

        # Collect final result
        all_success = (
            len(camera_results) > 0
            and all(r.get("status") == "SUCCESS" for r in camera_results.values())
        )
        final_result = {
            "run_id": run_id,
            "success": all_success,
            "results": camera_results,
        }
        self.all_done.emit(final_result)

    def cancel(self) -> None:
        """Request cancellation — sets flag, worker checks on next event."""
        super().cancel()
        if self._manager:
            self._manager.cancel()
