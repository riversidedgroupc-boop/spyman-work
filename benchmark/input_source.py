"""Benchmark input sources — 4 types for feeding tiles into the pipeline."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

import numpy as np

from runtime.unified_image_pool import TileEntry


class InputSource(ABC):
    @abstractmethod
    def next_batch(self, batch_size: int) -> list[TileEntry]: ...

    @abstractmethod
    def reset(self) -> None: ...


class SimulatedTileSource(InputSource):
    """Generates synthetic tiles at a configurable rate."""

    def __init__(
        self,
        camera_count: int = 3,
        width: int = 2048,
        line_speed_mpm: float = 80.0,
        defect_rate: float = 0.05,
    ):
        self._camera_count = camera_count
        self._width = width
        self._line_speed_mpm = line_speed_mpm
        self._defect_rate = defect_rate
        self._tile_idx = 0
        self._meter = 0.0
        self._cam_idx = 0

    def next_batch(self, batch_size: int) -> list[TileEntry]:
        tiles = []
        for _ in range(batch_size):
            self._cam_idx = (self._cam_idx % self._camera_count) + 1
            self._meter += 0.1
            self._tile_idx += 1

            is_defect = np.random.random() < self._defect_rate
            if is_defect:
                img = np.random.randint(0, 120, (3, 320, 320), dtype=np.uint8)
                img[:, 100:220, 100:220] = np.random.randint(180, 255, (3, 120, 120), dtype=np.uint8)
            else:
                img = np.random.randint(40, 80, (3, 320, 320), dtype=np.uint8)

            tiles.append(TileEntry(
                tile_id=f"sim_tile_{self._tile_idx:06d}",
                run_id="bench_run",
                customer_id="bench",
                product_id="bench",
                camera_id=f"Camera_{self._cam_idx:02d}",
                block_id=f"sim_block_{self._tile_idx // 20:06d}",
                tile_index=self._tile_idx % 20,
                tile_x=0,
                tile_y=0,
                meter_start=round(self._meter, 3),
                meter_end=round(self._meter + 0.1, 3),
                encoder_count_start=self._tile_idx * 100,
                encoder_count_end=(self._tile_idx + 1) * 100,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                image=img,
            ))
        return tiles

    def reset(self) -> None:
        self._tile_idx = 0
        self._meter = 0.0
        self._cam_idx = 0


class SpeedMultiplierSource(InputSource):
    """Wraps any InputSource and multiplies the tile rate (0.5x to 8x)."""

    def __init__(self, inner: InputSource, multiplier: float = 1.0):
        self._inner = inner
        self._multiplier = multiplier
        self._buffer: list[TileEntry] = []

    def next_batch(self, batch_size: int) -> list[TileEntry]:
        actual_batch = max(1, int(batch_size * self._multiplier))
        return self._inner.next_batch(actual_batch)

    def reset(self) -> None:
        self._inner.reset()
