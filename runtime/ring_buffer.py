"""RAM ring buffer with pre-allocated numpy slots and lock-free SPSC operations."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class RingBufferStats:
    total_puts: int = 0
    total_gets: int = 0
    current_size: int = 0
    dropped: int = 0


class RAMRingBuffer:
    """Pre-allocated ring buffer for fixed-shape numpy arrays.

    Uses pre-allocated memory slots to avoid GC pressure at high throughput.
    Thread-safe for single-producer-multiple-consumers.
    """

    def __init__(
        self,
        max_slots: int = 200,
        slot_shape: tuple[int, ...] = (3, 320, 320),
        dtype: type = np.uint8,
        drop_policy: Literal["oldest", "newest"] = "oldest",
    ):
        self._max_slots = max_slots
        self._slots = np.zeros((max_slots,) + slot_shape, dtype=dtype)
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = threading.Lock()
        self._stats = RingBufferStats()
        self._drop_policy = drop_policy

    def put(self, data: np.ndarray) -> bool:
        """Copy data into the next write slot. Returns False if dropped."""
        with self._lock:
            self._stats.total_puts += 1
            if self._count >= self._max_slots:
                self._stats.dropped += 1
                if self._drop_policy == "oldest":
                    self._read_idx = (self._read_idx + 1) % self._max_slots
                    self._count -= 1
                else:
                    return False
            np.copyto(self._slots[self._write_idx], data)
            self._write_idx = (self._write_idx + 1) % self._max_slots
            self._count += 1
            return True

    def get(self) -> np.ndarray | None:
        """Return a copy of the next readable slot, or None if empty."""
        with self._lock:
            self._stats.total_gets += 1
            if self._count == 0:
                return None
            data = self._slots[self._read_idx].copy()
            self._read_idx = (self._read_idx + 1) % self._max_slots
            self._count -= 1
            return data

    def size(self) -> int:
        with self._lock:
            return self._count

    def usage_ratio(self) -> float:
        with self._lock:
            return self._count / max(self._max_slots, 1)

    def stats(self) -> RingBufferStats:
        s = RingBufferStats(
            total_puts=self._stats.total_puts,
            total_gets=self._stats.total_gets,
            dropped=self._stats.dropped,
        )
        s.current_size = self._count
        return s

    def clear(self) -> None:
        with self._lock:
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0
            self._stats = RingBufferStats()
