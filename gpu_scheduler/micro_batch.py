"""Micro-batch accumulator — gathers tiles into inference batches."""
from __future__ import annotations

import time
from runtime.unified_image_pool import TileEntry


class MicroBatchAccumulator:
    """Accumulates tiles into batches based on size or timeout.

    Rules (either triggers inference):
    - Batch size reaches `batch_size` → emit immediately
    - Time since first tile reaches `max_wait_ms` → emit immediately
    """

    def __init__(self, batch_size: int = 4, max_wait_ms: float = 10.0):
        self._batch_size = batch_size
        self._max_wait_ms = max_wait_ms
        self._buffer: list[TileEntry] = []
        self._first_tile_time: float | None = None

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def max_wait_ms(self) -> float:
        return self._max_wait_ms

    def accumulate(self, tile: TileEntry) -> list[TileEntry] | None:
        """Add a tile. Returns a batch if ready, or None if accumulating."""
        now = time.time()
        if self._first_tile_time is None:
            self._first_tile_time = now
        self._buffer.append(tile)

        # Condition 1: batch full
        if len(self._buffer) >= self._batch_size:
            return self._flush()
        # Condition 2: timeout
        elapsed = (now - self._first_tile_time) * 1000
        if elapsed >= self._max_wait_ms:
            return self._flush()
        return None

    def flush(self) -> list[TileEntry] | None:
        """Force-flush current buffer. Returns None if empty."""
        if not self._buffer:
            return None
        return self._flush()

    def should_flush_timeout(self) -> bool:
        """Return True when buffered tiles have waited longer than max_wait_ms."""
        if not self._buffer or self._first_tile_time is None:
            return False
        elapsed = (time.time() - self._first_tile_time) * 1000
        return elapsed >= self._max_wait_ms

    def _flush(self) -> list[TileEntry] | None:
        batch = self._buffer
        self._buffer = []
        self._first_tile_time = None
        return batch if batch else None

    def current_size(self) -> int:
        return len(self._buffer)
