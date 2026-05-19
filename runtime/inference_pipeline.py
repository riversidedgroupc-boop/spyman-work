"""Inference pipeline — reads frames from buffer, runs model inference."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Thread, Event
from typing import Any, Callable

from runtime.frame_buffer import FrameBuffer


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
    """

    def __init__(self, buffer: FrameBuffer):
        self._buffer = buffer
        self._runners: dict[str, Any] = {}     # camera_id -> runner
        self._default_runner: Any = None
        self._running = Event()
        self._thread: Thread | None = None
        self._stats: dict[str, CameraInferenceStats] = {}
        self._results: list[dict] = []
        self._on_ng_callback: Callable | None = None

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
            try:
                import cv2
                import tempfile
                import os

                runner = self._get_runner(camera_id)

                # Save frame to temp file for model runner
                img = frame_data["image"]
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                cv2.imwrite(tmp.name, img)
                tmp.close()

                prediction = runner.predict_image(tmp.name)
                os.unlink(tmp.name)

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
                continue

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
