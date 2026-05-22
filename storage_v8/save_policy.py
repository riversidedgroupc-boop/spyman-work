"""Save policy manager — controls which tiles get saved to disk."""
from __future__ import annotations

import time
from enum import Enum

from gpu_scheduler.stats import TileResult


class SaveMode(str, Enum):
    SAVE_ALL = "save_all"
    SAVE_NG_ONLY = "save_ng_only"
    SAVE_NG_OK_SAMPLING = "save_ng_ok_sampling"
    RESULT_ONLY = "result_only"


class OkSampler:
    """Sampling controller for OK tiles."""

    def __init__(
        self,
        every_n_tiles: int = 100,
        every_n_meters: float = 10.0,
        every_n_seconds: int = 30,
    ):
        self._every_n_tiles = every_n_tiles
        self._every_n_meters = every_n_meters
        self._every_n_seconds = every_n_seconds

        self._tile_count = 0
        self._last_meter: float | None = None
        self._last_sample_time: float = 0.0

    def should_keep(self, result: TileResult) -> bool:
        self._tile_count += 1

        if self._tile_count % self._every_n_tiles == 0:
            return True

        if self._last_meter is not None:
            if abs(result.meter_start - self._last_meter) >= self._every_n_meters:
                self._last_meter = result.meter_start
                return True
        else:
            self._last_meter = result.meter_start

        now = time.time()
        if now - self._last_sample_time >= self._every_n_seconds:
            self._last_sample_time = now
            return True

        return False


class SavePolicyManager:
    """Determines whether a tile result should be saved to disk.

    NG and UNKNOWN results are always saved (unless RESULT_ONLY mode).
    OK results are handled per the current SaveMode.
    """

    def __init__(self, mode: SaveMode = SaveMode.SAVE_NG_ONLY):
        self._mode = mode
        self._ok_sampler = OkSampler()
        self._stats = {"total_saved": 0, "total_skipped": 0}

    @property
    def mode(self) -> SaveMode:
        return self._mode

    def switch_mode(self, new_mode: SaveMode) -> None:
        self._mode = new_mode

    def should_save_image(self, result: TileResult) -> bool:
        """Decide whether to save the image file. Result JSON is always saved."""
        if self._mode == SaveMode.RESULT_ONLY:
            self._stats["total_skipped"] += 1
            return False

        if result.result_type in ("NG", "UNKNOWN"):
            self._stats["total_saved"] += 1
            return True

        if self._mode == SaveMode.SAVE_ALL:
            self._stats["total_saved"] += 1
            return True

        if self._mode == SaveMode.SAVE_NG_OK_SAMPLING:
            if self._ok_sampler.should_keep(result):
                self._stats["total_saved"] += 1
                return True
            self._stats["total_skipped"] += 1
            return False

        # SAVE_NG_ONLY: OK tiles are NOT saved
        self._stats["total_skipped"] += 1
        return False

    def should_save_result(self, result: TileResult) -> bool:
        """Decide whether to persist result metadata without saving an image."""
        return self._mode == SaveMode.RESULT_ONLY

    def get_stats(self) -> dict:
        return dict(self._stats)
