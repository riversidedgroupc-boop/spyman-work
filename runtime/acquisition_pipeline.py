"""Acquisition pipeline — reads frames from camera adapters or line-scan devices."""
from __future__ import annotations

import time
from threading import Thread, Event
from typing import Any

from camera_adapters.base import BaseCameraAdapter
from runtime.frame_buffer import FrameBuffer

# Line-scan support (optional — degrades gracefully if not installed)
try:
    from src.device.camera.line_scan.interface import LineScanDevice
    from src.device.camera.line_scan.types import FramePacket, LineScanImageBlock
    from src.device.camera.line_scan.block_builder import LineScanBlockBuilder

    _LINE_SCAN_AVAILABLE = True
except ImportError:
    LineScanDevice = None  # type: ignore[assignment]
    FramePacket = None  # type: ignore[assignment]
    LineScanImageBlock = None  # type: ignore[assignment]
    LineScanBlockBuilder = None  # type: ignore[assignment]
    _LINE_SCAN_AVAILABLE = False


class AcquisitionPipeline:
    """Reads frames from area-scan adapters or line-scan devices into FrameBuffer.

    Supports mixed mode: area-scan cameras via BaseCameraAdapter and line-scan
    cameras via LineScanDevice with built-in block builder integration.
    """

    def __init__(self, buffer_size: int = 100):
        # Area-scan adapters (existing API)
        self._adapters: dict[str, BaseCameraAdapter] = {}
        # Line-scan devices (new)
        self._line_scan_cams: dict[str, LineScanDevice | object] = {}
        self._block_builders: dict[str, LineScanBlockBuilder | object] = {}

        self._buffer = FrameBuffer(max_size=buffer_size)
        self._running = Event()
        self._threads: list[Thread] = []
        self._interval = 0.05  # 20 FPS max for area-scan
        self._encoder: Any = None  # BaseEncoderReader | None
        self._sampling: Any = None  # SamplingController | None

    # ------------------------------------------------------------------
    # Area-scan adapter API (existing, unchanged)
    # ------------------------------------------------------------------

    def add_camera(self, camera_id: str, adapter: BaseCameraAdapter) -> None:
        self._adapters[camera_id] = adapter

    def remove_camera(self, camera_id: str) -> None:
        adapter = self._adapters.pop(camera_id, None)
        if adapter:
            adapter.stop_acquisition()

    # ------------------------------------------------------------------
    # Line-scan device API (new)
    # ------------------------------------------------------------------

    def add_line_scan_camera(
        self,
        camera_id: str,
        device: "LineScanDevice | object",
        block_height: int = 1024,
    ) -> None:
        """Register a line-scan camera with built-in block builder.

        Line data is accumulated into fixed-height blocks internally via
        LineScanBlockBuilder.  Completed blocks are pushed to FrameBuffer
        as individual frames, tagged with ``"block"`` metadata.

        Args:
            camera_id: Unique identifier for this camera slot.
            device: A ``LineScanDevice`` instance (real or virtual).
            block_height: Number of lines per image block (default 1024).

        Raises:
            RuntimeError: If line-scan support is not available (missing
                ``src.device.camera``).
        """
        if not _LINE_SCAN_AVAILABLE:
            raise RuntimeError(
                "Line-scan support not available (src.device.camera not found)"
            )

        self._line_scan_cams[camera_id] = device
        builder = LineScanBlockBuilder(camera_id=camera_id, block_height=block_height)
        self._block_builders[camera_id] = builder

        # When a block completes, push it to the FrameBuffer
        def _on_block(block: LineScanImageBlock) -> None:
            if block.image is not None:
                frame_data: dict[str, Any] = {
                    "camera_id": camera_id,
                    "image": block.image,
                    "timestamp": time.time(),
                    "position_meter": block.start_meter,
                    "block": block,  # attach full metadata for downstream tile slicing
                }
                self._buffer.put(frame_data)

        builder.set_on_block(_on_block)

        # Wire device line callback → block builder
        device.register_line_callback(lambda pkt: builder.push_line(pkt))  # type: ignore[union-attr]

    def remove_line_scan_camera(self, camera_id: str) -> None:
        device = self._line_scan_cams.pop(camera_id, None)
        if device is not None:
            device.unregister_line_callback()  # type: ignore[union-attr]
            device.stop_grabbing()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Encoder / sampling (shared)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running.set()

        # Start area-scan adapters (existing logic)
        for cam_id, adapter in self._adapters.items():
            adapter.start_acquisition()
            t = Thread(
                target=self._acquisition_loop, args=(cam_id, adapter), daemon=True
            )
            t.start()
            self._threads.append(t)

        # Start line-scan devices (new — device manages its own thread)
        for device in self._line_scan_cams.values():
            device.start_grabbing()  # type: ignore[union-attr]

    def stop(self) -> None:
        self._running.clear()

        for adapter in self._adapters.values():
            adapter.stop_acquisition()
        for device in self._line_scan_cams.values():
            device.stop_grabbing()  # type: ignore[union-attr]
        for t in self._threads:
            t.join(timeout=2)

    # ------------------------------------------------------------------
    # Area-scan acquisition thread
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_buffer(self) -> FrameBuffer:
        return self._buffer

    def get_encoder(self) -> Any:
        """Return the current encoder reader, or None."""
        return self._encoder

    def get_status(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []

        # Area-scan adapters
        for cid, adapter in self._adapters.items():
            s: dict[str, Any] = {"camera_id": cid, **adapter.get_status()}
            if self._encoder is not None:
                try:
                    s["encoder_position_m"] = round(
                        self._encoder.read_position_meter(), 3
                    )
                except Exception:
                    s["encoder_position_m"] = 0.0
            statuses.append(s)

        # Line-scan devices
        for cid, device in self._line_scan_cams.items():
            st = device.get_status()  # type: ignore[union-attr]
            s = {
                "camera_id": cid,
                "connected": st.connected,
                "acquiring": st.grabbing,
                "fps": st.line_rate,
                "frame_count": st.received_line_count,
                "type": "line_scan",
            }
            statuses.append(s)

        return statuses
