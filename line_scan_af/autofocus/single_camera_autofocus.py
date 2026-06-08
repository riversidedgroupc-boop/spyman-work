"""Single-camera autofocus orchestrator.

Implements the complete single-camera AF workflow:
  coarse search → fine search → curve fitting → verify → DOF check

Uses generator pattern (yield events) so the UI can track progress
without blocking.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Generator
from pathlib import Path

import numpy as np

from line_scan_af.acquisition.focus_sample_capture import FocusSampleCapture
from line_scan_af.autofocus.curve_analyzer import CurveAnalyzer, CurveAnalysisResult
from line_scan_af.autofocus.depth_of_field_checker import DepthOfFieldChecker
from line_scan_af.autofocus.events import (
    AFEvent,
    CameraAFComplete,
    CameraAFFailed,
    ImageCaptured,
    ProgressUpdate,
    ScoreComputed,
    SearchPhaseDone,
    StageMoved,
)
from line_scan_af.autofocus.focus_evaluator import FocusEvaluator
from line_scan_af.autofocus.roi_manager import ROIManager
from line_scan_af.autofocus.search_strategy import SearchStrategy
from line_scan_af.controllers.stage_controller_base import StageControllerBase
from line_scan_af.utils.exceptions import (
    CaptureQualityError,
    FocusFailedError,
    PeakAtBoundaryError,
    VerificationFailedError,
)
from line_scan_af.utils.focus_image_saver import FocusImageSaver

logger = logging.getLogger(__name__)


class SingleCameraAutofocus:
    """Orchestrates autofocus for a single camera+stage pair.

    The run() method is a generator that yields AFEvent objects at each step,
    allowing the caller (UI) to track progress in real time.
    """

    def __init__(
        self,
        camera_id: str,
        stage: StageControllerBase,
        sample_capture: FocusSampleCapture,
        roi_manager: ROIManager,
        image_saver: FocusImageSaver,
        config: dict | None = None,
        config_snapshot: dict | None = None,
    ) -> None:
        self._camera_id = camera_id
        self._stage = stage
        self._capture = sample_capture
        self._roi = roi_manager
        self._saver = image_saver
        self._cfg = config or {}
        self._config_snapshot = config_snapshot

        self._cancel_flag = threading.Event()
        self._emergency_flag = threading.Event()

    # ---- Public API ----

    def run(
        self, history_z: float | None = None
    ) -> Generator[AFEvent, None, dict]:
        """Execute the complete single-camera AF workflow.

        Args:
            history_z: Previous best Z for this camera/product (if available).

        Yields:
            AFEvent instances for progress reporting.

        Returns:
            Dict with focus result (best_z_mm, center_score, etc.).
        """
        try:
            # Save config snapshot for traceability
            if self._config_snapshot:
                self._saver.save_config_snapshot(self._config_snapshot)

            yield from self._check_preconditions()

            # Generate search points
            yield ProgressUpdate(
                camera_id=self._camera_id,
                message=f"Generating search plan (history_z={history_z})",
            )

            search_cfg = self._cfg.get("search", {})
            coarse_step = search_cfg.get("coarse_step_mm", 0.5)
            fine_step = search_cfg.get("fine_step_mm", 0.05)
            z_min = search_cfg.get("full_search_z_min_mm", 0.0)
            z_max = search_cfg.get("full_search_z_max_mm", 30.0)

            if history_z is not None:
                history_range = search_cfg.get("history_search_range_mm", 2.0)
                coarse_points = SearchStrategy.generate_history_local_grid(
                    history_z, history_range, coarse_step
                )
                coarse_points = SearchStrategy.clamp_points(coarse_points, z_min, z_max)
            else:
                coarse_points = SearchStrategy.generate_coarse_grid(z_min, z_max, coarse_step)

            # Coarse search
            yield ProgressUpdate(
                camera_id=self._camera_id,
                message=f"Coarse search: {len(coarse_points)} points",
                total_steps=len(coarse_points),
            )
            coarse_samples = yield from self._search_loop(coarse_points, phase="coarse")

            if not coarse_samples:
                yield CameraAFFailed(camera_id=self._camera_id, reason="No valid coarse samples")
                return self._error_result("No valid coarse samples")

            # Find best from coarse
            zs = [s["z"] for s in coarse_samples]
            sc = [s["score"] for s in coarse_samples]
            best_z, best_score, _ = CurveAnalyzer.find_best_by_max(zs, sc)
            yield SearchPhaseDone(
                camera_id=self._camera_id, phase="coarse",
                best_z=best_z, best_score=best_score, sample_count=len(coarse_samples),
            )

            # Fine search around coarse best
            fine_points = SearchStrategy.generate_fine_grid(best_z, fine_step, n_points=11)
            fine_points = SearchStrategy.clamp_points(fine_points, z_min, z_max)

            yield ProgressUpdate(
                camera_id=self._camera_id,
                message=f"Fine search: {len(fine_points)} points",
                total_steps=len(fine_points),
            )
            fine_samples = yield from self._search_loop(fine_points, phase="fine")

            # Combine all samples for curve analysis
            all_samples = coarse_samples + fine_samples
            all_zs = [s["z"] for s in all_samples]
            all_scores = [s["score"] for s in all_samples]

            curve_cfg = self._cfg.get("curve", {})
            analysis = CurveAnalyzer.analyze(all_zs, all_scores, curve_cfg)

            if not analysis.is_valid:
                issues = "; ".join(analysis.issues)
                yield CameraAFFailed(camera_id=self._camera_id, reason=f"Curve analysis: {issues}")
                return self._error_result(f"Curve analysis failed: {issues}")

            best_z_final = analysis.recommended_z_mm

            # Save curve CSV
            curve_path = self._saver.save_curve_csv(
                self._camera_id, all_zs, all_scores
            )

            # Move to best Z with backlash compensation
            yield ProgressUpdate(camera_id=self._camera_id, message=f"Moving to best Z={best_z_final:.3f}")
            backlash = self._cfg.get("default_motion", {}).get("backlash_mm", 0.2)
            if not self._stage.move_to_with_backlash_compensation(best_z_final, backlash):
                raise RuntimeError(f"Move to best Z failed: {best_z_final:.3f}")

            # Verify capture
            yield ProgressUpdate(camera_id=self._camera_id, message="Verification capture")
            sample = self._capture.capture_at(best_z_final)
            if not sample.is_valid:
                yield CameraAFFailed(camera_id=self._camera_id, reason="Verification capture quality failed")
                return self._error_result("Verification capture quality failed")

            center_roi = self._roi.get_center_roi()
            verify_score = FocusEvaluator.tenengrad(
                FocusEvaluator._crop_roi(sample.image, center_roi)
            )

            verify_ratio = curve_cfg.get("verify_ratio", 0.85)
            if verify_score < analysis.best_score * verify_ratio:
                yield CameraAFFailed(
                    camera_id=self._camera_id,
                    reason=f"Verification failed: {verify_score:.1f} < {analysis.best_score * verify_ratio:.1f}",
                )
                return self._error_result("Verification failed")

            # DOF check
            dof_check = "PASS"
            left_score = 0.0
            right_score = 0.0

            dof_cfg = self._cfg.get("depth_of_field", {})
            if dof_cfg.get("enable", True):
                left_roi = self._roi.get_left_roi()
                right_roi = self._roi.get_right_roi()
                left_score = FocusEvaluator.tenengrad(
                    FocusEvaluator._crop_roi(sample.image, left_roi)
                )
                right_score = FocusEvaluator.tenengrad(
                    FocusEvaluator._crop_roi(sample.image, right_roi)
                )
                threshold = dof_cfg.get("edge_score_ratio_threshold", 0.7)
                dof_check = DepthOfFieldChecker.check(
                    verify_score, left_score, right_score, threshold
                )

            # Save best image
            best_image_path = self._saver.save_best_image(
                self._camera_id, sample.image
            )

            result = {
                "camera_id": self._camera_id,
                "best_z_mm": best_z_final,
                "center_score": verify_score,
                "left_score": left_score,
                "right_score": right_score,
                "dof_check": dof_check,
                "verify_score": verify_score,
                "curve_file": curve_path,
                "sample_image": best_image_path,
                "status": "SUCCESS",
            }

            yield CameraAFComplete(
                camera_id=self._camera_id,
                best_z_mm=best_z_final,
                center_score=verify_score,
                left_score=left_score,
                right_score=right_score,
                dof_check=dof_check,
                verify_score=verify_score,
                status="SUCCESS",
            )

            return result

        except Exception as e:
            logger.exception("[%s] Autofocus failed: %s", self._camera_id, e)
            yield CameraAFFailed(camera_id=self._camera_id, reason=str(e))
            return self._error_result(str(e))

    # ---- Internal ----

    def _check_preconditions(self) -> Generator[AFEvent, None, None]:
        """Verify stage is ready before starting."""
        yield ProgressUpdate(camera_id=self._camera_id, message="Checking preconditions")

        status = self._stage.get_status()
        if not status.get("connected"):
            raise RuntimeError(f"Stage {self._camera_id} not connected")
        if not status.get("homed"):
            yield ProgressUpdate(camera_id=self._camera_id, message="Homing stage...")
            if not self._stage.home():
                raise RuntimeError(f"Stage {self._camera_id} homing failed")

    def _search_loop(
        self, z_positions: list[float], phase: str
    ) -> Generator[AFEvent, None, list[dict]]:
        """Execute a search sweep over the given Z positions."""
        samples: list[dict] = []
        total = len(z_positions)

        for i, z in enumerate(z_positions):
            if self._cancel_flag.is_set():
                logger.info("[%s] Search cancelled at Z=%.3f", self._camera_id, z)
                break
            if self._emergency_flag.is_set():
                self._stage.emergency_stop()
                raise RuntimeError("Emergency stop triggered")

            # Move to Z
            if not self._stage.move_to(z):
                raise RuntimeError(f"Move command rejected at Z={z:.3f}")
            if not self._stage.wait_until_done(timeout_s=5.0):
                logger.warning("[%s] Move timeout at Z=%.3f, skipping", self._camera_id, z)
                continue

            yield StageMoved(camera_id=self._camera_id, z_mm=z)

            # Capture
            sample = self._capture.capture_at(z)
            if not sample.is_valid:
                logger.warning("[%s] Quality issue at Z=%.3f: %s", self._camera_id, z,
                               sample.quality.issues if sample.quality else "unknown")
                continue

            yield ImageCaptured(camera_id=self._camera_id, z_mm=z)

            # Compute score using center ROI
            center_roi = self._roi.get_center_roi()
            crop = FocusEvaluator._crop_roi(sample.image, center_roi)
            score = FocusEvaluator.tenengrad(crop)

            yield ScoreComputed(camera_id=self._camera_id, z_mm=z, score=score)

            sample_path = self._saver.save_sample(self._camera_id, z, sample.image)
            samples.append({"z": z, "score": score, "image": sample.image})
            samples[-1]["sample_image"] = sample_path
            yield ProgressUpdate(
                camera_id=self._camera_id,
                message=f"{phase}: Z={z:.3f} score={score:.1f}",
                current_step=i + 1,
                total_steps=total,
            )

        return samples

    def cancel(self) -> None:
        """Request cancellation at the next safe point."""
        self._cancel_flag.set()

    def emergency_stop(self) -> None:
        """Immediately stop stage and cancel."""
        self._emergency_flag.set()
        self._cancel_flag.set()
        self._stage.emergency_stop()

    @staticmethod
    def _error_result(reason: str) -> dict:
        return {"camera_id": "", "status": "FAILED", "error": reason}
