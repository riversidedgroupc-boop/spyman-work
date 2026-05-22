"""Regression tests for V8 realtime scheduling integration."""
from __future__ import annotations

import tempfile
import time

import numpy as np

from benchmark.metrics_collector import MetricsCollector
from gpu_scheduler.model_pool import ModelEngine, ModelEnginePool
from gpu_scheduler.scheduler import GPUInferenceScheduler
from runtime.unified_image_pool import TileEntry, UnifiedImagePool
from storage_v8.async_writer import AsyncDiskWriter
from storage_v8.save_policy import SaveMode, SavePolicyManager


class NgEngine(ModelEngine):
    def __init__(self) -> None:
        self._loaded = False

    @property
    def model_type(self) -> str:
        return "yolo"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def vram_mb(self) -> float:
        return 128.0

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        return [
            {
                "result_type": "NG",
                "confidence": 0.95,
                "model_version": "v_test",
                "defect_type": "scratch",
            }
            for _ in images
        ]


def make_tile(tile_id: str = "tile_001") -> TileEntry:
    return TileEntry(
        tile_id=tile_id,
        run_id="run_test",
        customer_id="cust_01",
        product_id="prod_01",
        camera_id="Cam_01",
        block_id="BLK_001",
        tile_index=1,
        tile_x=320,
        tile_y=0,
        meter_start=10.0,
        meter_end=10.5,
        encoder_count_start=100,
        encoder_count_end=105,
        timestamp="2026-05-20T20:30:00",
        image=np.ones((3, 320, 320), dtype=np.uint8) * 127,
    )


def test_scheduler_result_callback_can_drive_async_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        pool = UnifiedImagePool(max_pool_size=10, memory_budget_mb=64)
        model_pool = ModelEnginePool(device_id=0)
        model_pool.register("yolo", NgEngine())
        model_pool.load("yolo", "unused")
        scheduler = GPUInferenceScheduler(pool, model_pool, batch_size=2, max_wait_ms=50)

        writer = AsyncDiskWriter(
            base_dir=tmpdir,
            policy=SavePolicyManager(SaveMode.SAVE_NG_ONLY),
        )
        scheduler.set_on_result(writer.write)

        writer.start()
        scheduler.start()
        pool.push(make_tile())
        time.sleep(0.2)
        scheduler.stop()
        writer.stop()

        assert writer.get_stats()["written"] == 1


def test_metrics_collector_uses_tile_pop_count_not_batch_count():
    pool = UnifiedImagePool(max_pool_size=10, memory_budget_mb=64)
    for i in range(4):
        pool.push(make_tile(f"tile_{i}"))

    collector = MetricsCollector(sample_interval_sec=0.05)
    collector.set_sources(pool, None, None)
    collector.start()
    time.sleep(0.02)
    pool.pop_batch(4)
    time.sleep(0.08)
    collector.stop()

    assert max(s.tiles_per_sec for s in collector.history()) > 20
