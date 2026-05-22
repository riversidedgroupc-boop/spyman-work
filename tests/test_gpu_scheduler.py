"""Tests for GPUInferenceScheduler."""
import time
import numpy as np
import pytest
from gpu_scheduler.scheduler import GPUInferenceScheduler
from gpu_scheduler.model_pool import ModelEnginePool, ModelEngine
from gpu_scheduler.priority_router import RoutingStrategy
from runtime.unified_image_pool import UnifiedImagePool, TileEntry


class FakeYOLOEngine(ModelEngine):
    def __init__(self):
        self._loaded = False
        self.infer_count = 0

    @property
    def model_type(self) -> str:
        return "yolo"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        self.infer_count += 1
        return [
            {"result_type": "OK", "confidence": 0.9, "model_version": "v1", "bbox": None}
            for _ in images
        ]

    @property
    def vram_mb(self) -> float:
        return 500.0


class FakePatchCoreEngine(ModelEngine):
    def __init__(self):
        self._loaded = False
        self.infer_count = 0

    @property
    def model_type(self) -> str:
        return "patchcore"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        self.infer_count += 1
        return [
            {"result_type": "OK", "confidence": 0.8, "model_version": "v1", "bbox": None}
            for _ in images
        ]

    @property
    def vram_mb(self) -> float:
        return 600.0


def make_tile(camera_id: str = "Cam_01", block_id: str = "BLK_001") -> TileEntry:
    return TileEntry(
        tile_id=f"{block_id}_T_000_000",
        run_id="run_test",
        customer_id="test",
        product_id="test",
        camera_id=camera_id,
        block_id=block_id,
        tile_index=0,
        tile_x=0,
        tile_y=0,
        meter_start=100.0,
        meter_end=100.5,
        encoder_count_start=1000,
        encoder_count_end=1005,
        timestamp="2026-05-20T20:30:00",
        image=np.ones((3, 320, 320), dtype=np.uint8) * 128,
    )


@pytest.fixture
def scheduler_fixture():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    model_pool = ModelEnginePool(device_id=0)
    model_pool.register("yolo", FakeYOLOEngine())
    model_pool.register("patchcore", FakePatchCoreEngine())
    model_pool.load("yolo", "models/yolo/best.pt")
    model_pool.load("patchcore", "models/patchcore/model.ckpt")

    scheduler = GPUInferenceScheduler(
        pool=pool,
        model_pool=model_pool,
        strategy=RoutingStrategy.HYBRID_YOLO_FIRST,
        batch_size=4,
        max_wait_ms=100,
    )
    return pool, model_pool, scheduler


def test_start_and_stop(scheduler_fixture):
    _, _, scheduler = scheduler_fixture
    scheduler.start()
    assert scheduler.is_running()
    scheduler.stop()
    assert not scheduler.is_running()


def test_processes_tiles(scheduler_fixture):
    pool, _, scheduler = scheduler_fixture
    pool.push(make_tile("Cam_01", "A"))
    pool.push(make_tile("Cam_02", "B"))

    scheduler.start()
    time.sleep(0.15)
    scheduler.stop()

    stats = scheduler.get_stats()
    assert stats.total_tiles_processed >= 2
    assert stats.total_batches >= 1


def test_cold_start_strategy(scheduler_fixture):
    pool, _, scheduler = scheduler_fixture
    scheduler.switch_strategy(RoutingStrategy.COLD_START)
    pool.push(make_tile("Cam_01", "A"))

    scheduler.start()
    time.sleep(0.15)
    scheduler.stop()

    patchcore = scheduler._model_pool._engines["patchcore"]
    assert patchcore.infer_count >= 1


def test_switch_strategy_runtime(scheduler_fixture):
    _, _, scheduler = scheduler_fixture
    scheduler.start()
    scheduler.switch_strategy(RoutingStrategy.PATCHCORE_FIRST)
    assert scheduler.get_stats() is not None
    scheduler.stop()


def test_get_stats_empty():
    pool = UnifiedImagePool(max_pool_size=10, memory_budget_mb=64)
    model_pool = ModelEnginePool(device_id=0)
    scheduler = GPUInferenceScheduler(
        pool=pool,
        model_pool=model_pool,
        batch_size=2,
        max_wait_ms=10,
    )
    stats = scheduler.get_stats()
    assert stats.total_tiles_processed == 0
    assert stats.total_batches == 0
