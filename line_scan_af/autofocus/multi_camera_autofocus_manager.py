"""Multi-camera sequential autofocus manager.

Orchestrates autofocus for up to 6 cameras in sequence. v1 only supports
sequential execution — each camera must complete before the next starts.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from line_scan_af.acquisition.focus_sample_capture import FocusSampleCapture
from line_scan_af.acquisition.line_scan_focus_capture import LineScanFocusCapture
from line_scan_af.autofocus.events import (
    AFEvent,
    AllComplete,
    CameraAFComplete,
    CameraAFFailed,
    EmergencyStopped,
    ProgressUpdate,
)
from line_scan_af.autofocus.focus_unit import FocusUnit
from line_scan_af.autofocus.roi_manager import ROIManager
from line_scan_af.autofocus.single_camera_autofocus import SingleCameraAutofocus
from line_scan_af.autofocus.tube_roi_model import TubeROIModel
from line_scan_af.config.config_loader import CameraStageBinding, StageDriverConfig
from line_scan_af.controllers.stage_factory import create_stage
from line_scan_af.controllers.stage_controller_base import StageControllerBase
from line_scan_af.utils.image_quality_checker import ImageQualityChecker
from line_scan_af.utils.focus_image_saver import FocusImageSaver

logger = logging.getLogger(__name__)


class MultiCameraAutoFocusManager:
    """Manages sequential autofocus across multiple camera+stage pairs.

    Usage:
        manager = MultiCameraAutoFocusManager(...)
        for event in manager.run_sequential():
            # Update UI with event
            ...
        result = manager.last_result
    """

    def __init__(
        self,
        focus_units: list[FocusUnit],
        config: dict,
        binding: CameraStageBinding,
        driver_cfg: StageDriverConfig,
        run_dir: Path | None = None,
        product_name: str | None = None,
    ) -> None:
        self._units = focus_units
        self._config = config
        self._binding = binding
        self._driver_cfg = driver_cfg
        self._product_name = product_name

        self._cancel_flag = threading.Event()
        self._emergency_flag = threading.Event()

        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._run_id = run_id
        self._run_dir = run_dir or Path("focus_runs") / run_id

        self._image_saver = FocusImageSaver(self._run_dir)
        self._last_result: dict | None = None

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def last_result(self) -> dict | None:
        return self._last_result

    def run_sequential(self) -> Generator[AFEvent, None, dict]:
        """Execute sequential autofocus for all enabled focus units.

        Yields AFEvent at each significant step. The caller can consume
        these to update a UI progress display.

        Returns:
            MultiFocusResult as a dict.
        """
        enabled_units = [u for u in self._units if u.enabled]
        total = len(enabled_units)
        results: dict[str, dict] = {}
        start_time = time.monotonic()

        yield ProgressUpdate(
            camera_id="",
            message=f"Starting {total}-camera sequential autofocus",
            total_steps=total,
        )

        for i, unit in enumerate(enabled_units):
            if self._emergency_flag.is_set():
                yield EmergencyStopped(camera_id="", reason="Emergency stop before camera")
                break

            if self._cancel_flag.is_set():
                yield ProgressUpdate(message="Autofocus cancelled by user")
                break

            yield ProgressUpdate(
                camera_id=unit.camera_id,
                message=f"Camera {i+1}/{total}: {unit.camera_id} starting",
                current_step=i + 1,
                total_steps=total,
            )

            try:
                # Build single-camera AF for this unit
                af = self._build_single_af(unit)

                # Check for historical focus Z for this camera+product
                history_z = None
                try:
                    from line_scan_af.product.product_recipe_focus_extension import ProductRecipeFocusExtension
                    ext = ProductRecipeFocusExtension()
                    product_name = self._product_name or "CopperTube_8mm"
                    history_z = ext.get_history_z(
                        product_name, unit.camera_id
                    )
                    if history_z is not None:
                        logger.info("[%s] Using history Z=%.3f for local search", unit.camera_id, history_z)
                except Exception:
                    pass

                # Run it, forwarding all events
                result = None
                for event in af.run(history_z=history_z):
                    if self._emergency_flag.is_set():
                        af.emergency_stop()
                        yield EmergencyStopped(camera_id=unit.camera_id, reason="Emergency stop")
                        break
                    if self._cancel_flag.is_set():
                        af.cancel()
                        yield ProgressUpdate(camera_id=unit.camera_id, message="Cancelled")
                        break
                    yield event
                    if isinstance(event, CameraAFComplete):
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
                    elif isinstance(event, CameraAFFailed):
                        result = {
                            "camera_id": event.camera_id,
                            "status": "FAILED",
                            "error": event.reason,
                        }

                if result:
                    results[unit.camera_id] = result

                    if result.get("status") == "FAILED":
                        logger.error("[%s] AF failed, stopping remaining cameras", unit.camera_id)
                        yield ProgressUpdate(
                            camera_id=unit.camera_id,
                            message=f"Camera {unit.camera_id} failed — stopping sequence",
                        )
                        break

            except Exception as e:
                logger.exception("[%s] Unexpected error during AF", unit.camera_id)
                results[unit.camera_id] = {
                    "camera_id": unit.camera_id,
                    "status": "FAILED",
                    "error": str(e),
                }
                yield CameraAFFailed(camera_id=unit.camera_id, reason=str(e))

        elapsed = time.monotonic() - start_time
        all_success = (
            len(results) > 0
            and all(r.get("status") == "SUCCESS" for r in results.values())
        )

        self._last_result = {
            "run_id": self._run_id,
            "success": all_success,
            "results": results,
            "total_elapsed_s": round(elapsed, 1),
        }

        # Save summary
        self._image_saver.save_summary(self._last_result)

        yield AllComplete(
            camera_id="",
            run_id=self._run_id,
            success=all_success,
            camera_count=len(results),
        )

        return self._last_result

    def _build_single_af(self, unit: FocusUnit) -> SingleCameraAutofocus:
        """Build a SingleCameraAutofocus for a given FocusUnit."""
        capture = LineScanFocusCapture(
            camera=unit.camera_controller,
            settle_ms=self._config.get("default_motion", {}).get("settle_ms", 150),
        )

        capture_cfg = self._config.get("capture", {})
        quality_checker = ImageQualityChecker(
            overexpose_threshold=self._config.get("evaluation", {}).get("overexpose_threshold", 250),
            overexpose_ratio_limit=self._config.get("evaluation", {}).get("overexpose_ratio_limit", 0.05),
        )

        sample_capture = FocusSampleCapture(
            capture=capture,
            quality_checker=quality_checker,
            length_mm=capture_cfg.get("sample_length_mm", 50.0),
        )

        return SingleCameraAutofocus(
            camera_id=unit.camera_id,
            stage=unit.stage_controller,
            sample_capture=sample_capture,
            roi_manager=unit.roi_manager,
            image_saver=FocusImageSaver(self._run_dir / unit.camera_id.lower()),
            config=self._config,
            config_snapshot=dict(self._config),
        )

    def cancel(self) -> None:
        """Request graceful cancellation after current camera completes."""
        self._cancel_flag.set()

    def emergency_stop(self) -> None:
        """Immediately stop all motion and cancel all operations."""
        self._emergency_flag.set()
        self._cancel_flag.set()
        for unit in self._units:
            if unit.stage_controller:
                unit.stage_controller.emergency_stop()
