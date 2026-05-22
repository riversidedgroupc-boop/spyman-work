"""History replay input source — reads saved images for benchmark replay."""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from benchmark.input_source import InputSource
from runtime.unified_image_pool import TileEntry


@dataclass
class ReplayConfig:
    camera_count: int = 3
    speed_multiplier: float = 1.0    # 0.5x, 1x, 2x, 4x, 8x
    tile_interval_ms: float = 50.0   # base interval between tile batches (at 1x)


class HistoryReplaySource(InputSource):
    """Replays tiles from a directory of saved images or image_index.db records.

    Reads image files, wraps them as TileEntry objects, and emits them at
    configurable speed for benchmark testing.
    """

    def __init__(
        self,
        image_paths: list[str],
        config: ReplayConfig | None = None,
    ):
        self._paths = image_paths
        self._config = config or ReplayConfig()
        self._index = 0
        self._start_time = 0.0
        self._tiles_emitted = 0

    def reset(self) -> None:
        self._index = 0
        self._start_time = 0.0
        self._tiles_emitted = 0

    def next_batch(self, batch_size: int) -> list[TileEntry]:
        if self._start_time == 0.0:
            self._start_time = time.time()

        if self._index >= len(self._paths):
            return []

        # Simulate real-time pacing: compute how many tiles should have been
        # emitted by now based on elapsed wall-clock time and speed multiplier.
        elapsed = time.time() - self._start_time
        scaled_interval = self._config.tile_interval_ms / self._config.speed_multiplier / 1000.0

        target_total = int(elapsed / scaled_interval) if scaled_interval > 0 else len(self._paths)
        target_total = min(target_total, len(self._paths))

        if self._tiles_emitted >= target_total:
            return []

        count = min(batch_size, target_total - self._tiles_emitted, len(self._paths) - self._index)

        tiles: list[TileEntry] = []
        for _ in range(count):
            path = self._paths[self._index]
            tile = self._load_tile(path)
            if tile is not None:
                tiles.append(tile)
            self._index += 1
            self._tiles_emitted += 1

        return tiles

    def _load_tile(self, path: str) -> TileEntry | None:
        try:
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            if img is None:
                return None
            img = cv2.resize(img, (320, 320))
            img = img.transpose(2, 0, 1)  # HWC → CHW
        except Exception:
            return None

        return TileEntry(
            tile_id=f"replay_{self._tiles_emitted:06d}",
            run_id="history_replay",
            customer_id="",
            product_id="",
            camera_id=f"cam_{(self._tiles_emitted % self._config.camera_count) + 1:02d}",
            block_id="",
            tile_index=self._tiles_emitted,
            tile_x=0,
            tile_y=0,
            meter_start=self._tiles_emitted * 0.32,
            meter_end=(self._tiles_emitted + 1) * 0.32,
            encoder_count_start=self._tiles_emitted * 100,
            encoder_count_end=(self._tiles_emitted + 1) * 100,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            image=img.astype(np.uint8),
        )

    @property
    def total_tiles(self) -> int:
        return len(self._paths)

    @property
    def tiles_emitted(self) -> int:
        return self._tiles_emitted

    @property
    def is_exhausted(self) -> bool:
        return self._index >= len(self._paths)
