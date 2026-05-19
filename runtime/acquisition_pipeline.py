"""Acquisition pipeline — reads frames from camera adapters into FrameBuffer."""
from __future__ import annotations

import time
from threading import Thread, Event
from typing import Any

from camera_adapters.base import BaseCameraAdapter
from runtime.frame_buffer import FrameBuffer


class AcquisitionPipeline:
    """Continuously reads frames from multiple camera adapters into a shared buffer."""

    def __init__(self, buffer_size: int = 100):
        self._adapters: dict[str, BaseCameraAdapter] = {}
        self._buffer = FrameBuffer(max_size=buffer_size)
        self._running = Event()
        self._threads: list[Thread] = []
        self._interval = 0.05  # 20 FPS max
        self._encoder: Any = None  # BaseEncoderReader | None
        self._sampling: Any = None  # SamplingController | None

    def add_camera(self, camera_id: str, adapter: BaseCameraAdapter) -> None:
        self._adapters[camera_id] = adapter

    def remove_camera(self, camera_id: str) -> None:
        adapter = self._adapters.pop(camera_id, None)
        if adapter:
            adapter.stop_acquisition()

    def set_encoder(self, encoder: Any) -> None:
        """Attach an encoder reader for position tracking.

        encoder must implement: read_position_meter() -> float, get_status() -> dict
        """
        self._encoder = encoder

    def set_sampling_controller(self, controller: Any) -> None:
        """Attach a SamplingController to gate frame capture.

        controller must implement: should_capture(position_m, now) -> bool, state
        """
        self._sampling = controller

    def start(self) -> None:
        self._running.set()
        for cam_id, adapter in self._adapters.items():
            adapter.start_acquisition()
            t = Thread(target=self._acquisition_loop, args=(cam_id, adapter), daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._running.clear()
        for adapter in self._adapters.values():
            adapter.stop_acquisition()
        for t in self._threads:
            t.join(timeout=2)

    def _acquisition_loop(self, cam_id: str, adapter: BaseCameraAdapter) -> None:
        from datetime import datetime

        while self._running.is_set():
            frame = adapter.get_frame()
            if frame is not None:
                # Read encoder position if available
                pos_m = 0.0
                if self._encoder is not None:
                    try:
                        pos_m = self._encoder.read_position_meter()
                    except Exception:
                        pos_m = 0.0

                # Check sampling controller gate
                if self._sampling is not None:
                    if not self._sampling.should_capture(
                        position_m=pos_m, now=datetime.now()
                    ):
                        time.sleep(self._interval)
                        continue

                frame_data: dict[str, Any] = {
                    "camera_id": cam_id,
                    "image": frame,
                    "timestamp": time.time(),
                    "position_meter": pos_m,
                }
                self._buffer.put(frame_data)
            else:
                time.sleep(self._interval)

    def get_buffer(self) -> FrameBuffer:
        return self._buffer

    def get_encoder(self) -> Any:
        """Return the current encoder reader, or None."""
        return self._encoder

    def get_status(self) -> list[dict]:
        statuses = []
        for cid, adapter in self._adapters.items():
            s = {"camera_id": cid, **adapter.get_status()}
            if self._encoder is not None:
                try:
                    s["encoder_position_m"] = round(self._encoder.read_position_meter(), 3)
                except Exception:
                    s["encoder_position_m"] = 0.0
            statuses.append(s)
        return statuses
