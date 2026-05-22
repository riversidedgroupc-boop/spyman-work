"""Inference pipeline — reads frames from buffer, runs model inference.

Supports both area-scan frames (whole image) and line-scan frames (block
containing pre-built image — optionally sliced into tiles for inference).
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from threading import Thread, Event
from typing import Any, Callable

import cv2

from runtime.frame_buffer import FrameBuffer
from core.log_manager import LogManager

# Optional line-scan tile support
try:
    from src.device.camera.line_scan.types import LineScanImageBlock
    from src.device.camera.line_scan.tile_generator import TileGenerator
    _TILE_SUPPORT = True
except ImportError:
    LineScanImageBlock = None  # type: ignore[assignment]
    TileGenerator = None  # type: ignore[assignment]
    _TILE_SUPPORT = False


@dataclass
class CameraInferenceStats:
    """Per-camera inference statistics."""
    inference_count: int = 0
    ng_count: int = 0
    error_count: int = 0
    last_error: str = ""
    model_name: str = "none"


class InferencePipeline:
    """Continuously processes frames from buffer through per-camera model runners.

    Each camera can have its own runner instance (different weights, thresholds).
    If a camera has no dedicated runner, the default runner is used.

    Line-scan frames (with ``"block"`` key) are sliced into tiles before
    inference; all-tile results are aggregated and the frame is marked NG
    if *any* tile contains detections.
    """

    _tile_gen: "TileGenerator | None" = None  # shared tile generator instance

    def __init__(self, buffer: FrameBuffer):
        self._buffer = buffer
        self._runners: dict[str, Any] = {}     # camera_id -> runner
        self._default_runner: Any = None
        self._running = Event()
        self._thread: Thread | None = None
        self._stats: dict[str, CameraInferenceStats] = {}
        self._results: list[dict] = []
        self._on_ng_callback: Callable | None = None

        if _TILE_SUPPORT:
            self._tile_gen = TileGenerator(tile_size=320)

    def set_runner(self, runner: Any, camera_id: str | None = None) -> None:
        """Set model runner for a specific camera (or default if camera_id is None).

        Each runner must have: runner_name (str), predict_image(path) -> ImagePrediction.
        """
        if camera_id:
            self._runners[camera_id] = runner
            if camera_id not in self._stats:
                self._stats[camera_id] = CameraInferenceStats()
            self._stats[camera_id].model_name = getattr(runner, "runner_name", "unknown")
        else:
            self._default_runner = runner

    def set_on_ng(self, callback: Callable) -> None:
        """Callback(ng_result: dict) called when defect detected."""
        self._on_ng_callback = callback

    def _get_runner(self, camera_id: str) -> Any:
        """Resolve runner for a camera: dedicated > default > error."""
        runner = self._runners.get(camera_id)
        if runner is not None:
            return runner
        if self._default_runner is not None:
            return self._default_runner
        raise RuntimeError(
            f"No runner configured for camera '{camera_id}' and no default runner set"
        )

    def start(self) -> None:
        if not self._runners and self._default_runner is None:
            raise RuntimeError("No runners configured — call set_runner() first")
        self._running.set()
        self._thread = Thread(target=self._inference_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)

    def _inference_loop(self) -> None:
        while self._running.is_set():
            frame_data = self._buffer.get()
            if frame_data is None:
                time.sleep(0.01)
                continue

            camera_id = frame_data.get("camera_id", "")

            # ── Line-scan path: block → tiles → per-tile inference ──
            if "block" in frame_data and _TILE_SUPPORT and self._tile_gen is not None:
                self._infer_tiles(frame_data, camera_id)
                continue

            # ── Area-scan path: whole image inference ──
            try:
                runner = self._get_runner(camera_id)

                img = frame_data["image"]
                tmp_path = ""
                try:
                    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    tmp_path = tmp.name
                    tmp.close()
                    if not cv2.imwrite(tmp_path, img):
                        raise RuntimeError(f"failed to write temporary inference image: {tmp_path}")
                    prediction = runner.predict_image(tmp_path)
                finally:
                    if tmp_path:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

                stats = self._stats.setdefault(camera_id, CameraInferenceStats())
                stats.inference_count += 1
                detections = getattr(prediction, 'detections', [])
                is_ng = len(detections) > 0
                if is_ng:
                    stats.ng_count += 1

                result = {
                    "camera_id": camera_id,
                    "timestamp": frame_data.get("timestamp", 0),
                    "position_meter": frame_data.get("position_meter"),
                    "image": img,
                    "prediction": prediction,
                    "is_ng": is_ng,
                }
                self._results.append(result)

                if is_ng and self._on_ng_callback:
                    self._on_ng_callback(result)

                # Keep only last 1000 results
                if len(self._results) > 1000:
                    self._results = self._results[-500:]

            except Exception as e:
                stats = self._stats.setdefault(camera_id, CameraInferenceStats())
                stats.error_count += 1
                stats.last_error = str(e)
                LogManager.instance().get_logger("inference").exception(
                    "Inference failed for camera=%s runner=%s",
                    camera_id,
                    getattr(self._runners.get(camera_id) or self._default_runner, "runner_name", "unknown"),
                )
                continue

    # ------------------------------------------------------------------
    # Tile-based inference (line-scan)
    # ------------------------------------------------------------------

    def _infer_tiles(self, frame_data: dict[str, Any], camera_id: str) -> None:
        """Slice a line-scan block into tiles and run inference on each.

        Aggregates all-tile detections into a single result.  The frame is
        marked NG if **any** tile contains a detection.
        """
        block: "LineScanImageBlock" = frame_data["block"]
        tiles = self._tile_gen.slice_block(block)  # type: ignore[union-attr]

        if not tiles:
            return

        camera_stats = self._stats.setdefault(camera_id, CameraInferenceStats())
        runner = self._get_runner(camera_id)

        all_detections: list[Any] = []
        tile_ng_count = 0
        last_prediction: Any = None

        for tile in tiles:
            camera_stats.inference_count += 1
            try:
                tmp_path = ""
                try:
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp_path = tmp.name
                    tmp.close()
                    if not cv2.imwrite(tmp_path, tile.image):
                        raise RuntimeError(f"failed to write temporary inference tile: {tmp_path}")
                    prediction = runner.predict_image(tmp_path)
                    last_prediction = prediction
                finally:
                    if tmp_path:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

                tile_dets = getattr(prediction, "detections", [])
                if tile_dets:
                    tile_ng_count += 1
                    # Remap tile-relative coordinates to block-relative
                    for det in tile_dets:
                        bx, by = self._tile_gen.tile_to_original_coords(  # type: ignore[union-attr]
                            tile, int(det.bbox[0]), int(det.bbox[1])
                        )
                        # Attach block-space coordinates for positioning
                        setattr(det, "block_x", bx)
                        setattr(det, "block_y", by)
                        setattr(det, "tile_id", tile.tile_id)
                        setattr(det, "meter_start", tile.meter_start)
                        setattr(det, "meter_end", tile.meter_end)
                        if block.end_meter != block.start_meter and block.height:
                            defect_meter = block.start_meter + (
                                by / block.height
                            ) * (block.end_meter - block.start_meter)
                            setattr(det, "meter_position", defect_meter)

                all_detections.extend(tile_dets)

            except Exception:
                camera_stats.error_count += 1
                camera_stats.last_error = "tile inference failed"
                LogManager.instance().get_logger("inference").exception(
                    "Tile inference failed for camera=%s block=%s tile=%s",
                    camera_id,
                    getattr(block, "block_id", ""),
                    getattr(tile, "tile_id", ""),
                )

        is_ng = len(all_detections) > 0
        if is_ng:
            camera_stats.ng_count += 1

        # Build merged prediction for downstream consumers
        from dataclasses import replace as _dc_replace
        try:
            merged_pred = _dc_replace(last_prediction, detections=all_detections)
        except Exception:
            if last_prediction is None:
                from core.schema import ImagePrediction

                merged_pred = ImagePrediction(image_name=block.block_id, detections=[])
            else:
                merged_pred = last_prediction
                merged_pred.detections = all_detections  # type: ignore[union-attr]

        position_meter = frame_data.get("position_meter")
        if position_meter is None and all_detections:
            position_meter = getattr(all_detections[0], "meter_position", None)
        if position_meter is None:
            position_meter = block.start_meter

        result = {
            "camera_id": camera_id,
            "timestamp": frame_data.get("timestamp", 0),
            "position_meter": position_meter,
            "image": block.image,
            "block": block,
            "tiles": tiles,
            "prediction": merged_pred,
            "is_ng": is_ng,
            "tile_ng_count": tile_ng_count,
        }
        self._results.append(result)

        if is_ng and self._on_ng_callback:
            self._on_ng_callback(result)

        if len(self._results) > 1000:
            self._results = self._results[-500:]

    def get_results(self) -> list[dict]:
        return list(self._results)

    def get_status(self) -> dict:
        """Get aggregated inference status (backward-compatible)."""
        return {
            "running": self._running.is_set(),
            "inference_count": self.total_inference_count,
            "ng_count": self.total_ng_count,
            "error_count": sum(s.error_count for s in self._stats.values()),
            "last_error": "; ".join(
                f"{cid}:{s.last_error}"
                for cid, s in self._stats.items()
                if s.last_error
            ) or "",
            "model": ", ".join(
                f"{cid}:{s.model_name}"
                for cid, s in sorted(self._stats.items())
            ) if self._stats else "none",
        }

    def get_camera_status(self, camera_id: str) -> dict | None:
        """Get per-camera inference status."""
        stats = self._stats.get(camera_id)
        if stats is None:
            return None
        return {
            "camera_id": camera_id,
            "running": self._running.is_set(),
            "inference_count": stats.inference_count,
            "ng_count": stats.ng_count,
            "error_count": stats.error_count,
            "last_error": stats.last_error,
            "model": stats.model_name,
        }

    def get_all_statuses(self) -> list[dict]:
        """Get per-camera status list for all cameras."""
        return [
            {
                "camera_id": cid,
                "running": self._running.is_set(),
                "inference_count": s.inference_count,
                "ng_count": s.ng_count,
                "error_count": s.error_count,
                "last_error": s.last_error,
                "model": s.model_name,
            }
            for cid, s in sorted(self._stats.items())
        ]

    @property
    def total_inference_count(self) -> int:
        return sum(s.inference_count for s in self._stats.values())

    @property
    def total_ng_count(self) -> int:
        return sum(s.ng_count for s in self._stats.values())
