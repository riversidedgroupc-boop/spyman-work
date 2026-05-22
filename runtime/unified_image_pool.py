"""Unified image pool — single entry point for all camera tiles."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class TileEntry:
    """A tile with complete metadata for traceability."""

    tile_id: str
    run_id: str
    customer_id: str
    product_id: str
    camera_id: str
    block_id: str
    tile_index: int
    tile_x: int
    tile_y: int
    meter_start: float
    meter_end: float
    encoder_count_start: int
    encoder_count_end: int
    timestamp: str
    image: np.ndarray  # (3, 320, 320) uint8 or (320, 320) uint8 for Mono8
    tile_width: int = 320
    tile_height: int = 320
    image_format: str = "RGB8"
    source_buffer_id: str = ""
    model_version: str = ""

    @property
    def meter_center(self) -> float:
        return (self.meter_start + self.meter_end) / 2


@dataclass
class PoolStats:
    total_pushes: int = 0
    total_pops: int = 0
    total_tiles_popped: int = 0
    total_dropped: int = 0
    current_size: int = 0
    max_observed_size: int = 0
    pool_usage_ratio: float = 0.0


class UnifiedImagePool:
    """Thread-safe pool for all camera tiles with memory budget control.

    All camera workers push tiles; the GPU scheduler is the sole consumer.
    """

    TILE_BYTES = 3 * 320 * 320  # ~307,200 bytes per uint8 RGB tile

    def __init__(
        self,
        max_pool_size: int = 1000,
        memory_budget_mb: int = 512,
        drop_policy: Literal["oldest", "newest"] = "oldest",
    ):
        self._max_pool_size = max_pool_size
        self._memory_budget_mb = memory_budget_mb
        self._max_slots_by_memory = max(1, (memory_budget_mb * 1024 * 1024) // self.TILE_BYTES)
        self._effective_max = min(max_pool_size, self._max_slots_by_memory)
        self._drop_policy = drop_policy

        self._items: list[TileEntry] = []
        self._lock = threading.Lock()
        self._stats = PoolStats()
        self._camera_counts: dict[str, int] = {}

    def push(self, tile: TileEntry) -> bool:
        """Push a tile into the pool. Returns False if dropped."""
        with self._lock:
            self._stats.total_pushes += 1
            if len(self._items) >= self._effective_max:
                self._stats.total_dropped += 1
                if self._drop_policy == "oldest":
                    dropped = self._items.pop(0)
                    self._camera_counts[dropped.camera_id] = max(
                        0, self._camera_counts.get(dropped.camera_id, 0) - 1
                    )
                else:
                    return False
            self._items.append(tile)
            self._camera_counts[tile.camera_id] = self._camera_counts.get(tile.camera_id, 0) + 1
            self._stats.current_size = len(self._items)
            self._stats.max_observed_size = max(self._stats.max_observed_size, self._stats.current_size)
            self._stats.pool_usage_ratio = self._stats.current_size / max(self._effective_max, 1)
            return True

    def pop_batch(self, batch_size: int) -> list[TileEntry]:
        """Pop up to batch_size tiles. Returns empty list if pool is empty."""
        with self._lock:
            n = min(batch_size, len(self._items))
            if n == 0:
                return []
            self._stats.total_pops += 1
            self._stats.total_tiles_popped += n
            batch = self._items[:n]
            self._items = self._items[n:]
            for t in batch:
                self._camera_counts[t.camera_id] = max(
                    0, self._camera_counts.get(t.camera_id, 0) - 1
                )
            self._stats.current_size = len(self._items)
            self._stats.pool_usage_ratio = self._stats.current_size / max(self._effective_max, 1)
            return batch

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def usage_ratio(self) -> float:
        with self._lock:
            return len(self._items) / max(self._effective_max, 1)

    def camera_distribution(self) -> dict[str, int]:
        with self._lock:
            return dict(self._camera_counts)

    def stats(self) -> PoolStats:
        with self._lock:
            s = PoolStats(
                total_pushes=self._stats.total_pushes,
                total_pops=self._stats.total_pops,
                total_tiles_popped=self._stats.total_tiles_popped,
                total_dropped=self._stats.total_dropped,
                current_size=len(self._items),
                max_observed_size=self._stats.max_observed_size,
                pool_usage_ratio=len(self._items) / max(self._effective_max, 1),
            )
            return s

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._camera_counts.clear()
            self._stats = PoolStats()
