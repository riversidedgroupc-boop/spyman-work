"""Line scan block builder — accumulates lines into fixed-height 2D image blocks."""
from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from src.device.camera.line_scan.types import FramePacket, LineScanImageBlock


class LineScanBlockBuilder:
    """Accumulates line scan data and emits fixed-height LineScanImageBlock objects."""

    def __init__(self, camera_id: str, block_height: int = 1024) -> None:
        if block_height < 1:
            raise ValueError(f"block_height must be >= 1, got {block_height}")
        self._camera_id = camera_id
        self._block_height = block_height
        self._on_block: Callable[[LineScanImageBlock], None] | None = None
        self._buffer: np.ndarray | None = None
        self._row = 0
        self._start_frame_id = 0
        self._end_frame_id = 0
        self._start_encoder_count = 0
        self._end_encoder_count = 0
        self._block_id = 0
        self._width = 0

    @property
    def camera_id(self) -> str:
        return self._camera_id

    @property
    def block_height(self) -> int:
        return self._block_height

    @property
    def current_row(self) -> int:
        return self._row

    def set_on_block(self, callback: Callable[[LineScanImageBlock], None]) -> None:
        self._on_block = callback

    def push_line(self, packet: FramePacket) -> None:
        """Push one line of data. May trigger a block emission."""
        if packet.line_data is None:
            return
        data = packet.line_data
        h, w = data.shape
        if self._buffer is None or self._width != w:
            self._buffer = np.zeros((self._block_height, w), dtype=np.uint8)
            self._width = w
            self._row = 0
        if self._row == 0:
            self._start_frame_id = packet.frame_id
            self._start_encoder_count = packet.encoder_count
        remaining = self._block_height - self._row
        lines_to_copy = min(h, remaining)
        self._buffer[self._row : self._row + lines_to_copy, :] = data[:lines_to_copy, :]
        self._row += lines_to_copy
        if self._row >= self._block_height:
            self._emit_block(packet)

    def _emit_block(self, last_packet: FramePacket) -> None:
        if self._buffer is None:
            return
        self._end_frame_id = last_packet.frame_id
        self._end_encoder_count = last_packet.encoder_count
        block = LineScanImageBlock(
            block_id=f"{self._camera_id}_BLK_{self._block_id:06d}",
            camera_id=self._camera_id,
            start_frame_id=self._start_frame_id,
            end_frame_id=self._end_frame_id,
            start_encoder_count=self._start_encoder_count,
            end_encoder_count=self._end_encoder_count,
            start_meter=0.0,
            end_meter=0.0,
            width=self._width,
            height=self._block_height,
            image=self._buffer.copy(),
            timestamp_start=time.time(),
            timestamp_end=time.time(),
        )
        self._block_id += 1
        self._row = 0
        if self._on_block is not None:
            try:
                self._on_block(block)
            except Exception:
                pass

    def flush(self) -> LineScanImageBlock | None:
        """Emit any partial block. Returns None if buffer is empty."""
        if self._buffer is None or self._row == 0:
            return None
        partial = self._buffer[: self._row, :].copy()
        block = LineScanImageBlock(
            block_id=f"{self._camera_id}_BLK_{self._block_id:06d}_partial",
            camera_id=self._camera_id,
            start_frame_id=self._start_frame_id,
            end_frame_id=self._end_frame_id,
            start_encoder_count=self._start_encoder_count,
            end_encoder_count=self._end_encoder_count,
            start_meter=0.0,
            end_meter=0.0,
            width=self._width,
            height=self._row,
            image=partial,
            timestamp_start=time.time(),
            timestamp_end=time.time(),
        )
        self._row = 0
        return block

    def reset(self) -> None:
        """Reset buffer to empty state."""
        self._row = 0
        self._buffer = None
