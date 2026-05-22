"""Tests for ModelEnginePool."""
import numpy as np
import pytest
from gpu_scheduler.model_pool import ModelEnginePool, ModelEngine


class FakeYOLOEngine(ModelEngine):
    def __init__(self):
        self._loaded = False
        self.load_count = 0
        self.unload_count = 0
        self.infer_count = 0

    @property
    def model_type(self) -> str:
        return "yolo"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self.load_count += 1
        self._loaded = True
        return True

    def unload(self) -> None:
        self.unload_count += 1
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        self.infer_count += 1
        return [{"result_type": "OK", "confidence": 0.95, "bbox": None} for _ in images]

    @property
    def vram_mb(self) -> float:
        return 500.0


def test_load_and_unload():
    pool = ModelEnginePool(device_id=0)
    engine = FakeYOLOEngine()
    pool.register("yolo", engine)
    assert pool.load("yolo", "models/yolo/best.pt")
    assert pool.is_loaded("yolo")
    pool.unload("yolo")
    assert not pool.is_loaded("yolo")
    assert engine.load_count == 1
    assert engine.unload_count >= 1


def test_load_unknown_type_raises():
    pool = ModelEnginePool(device_id=0)
    with pytest.raises(ValueError, match="not registered"):
        pool.load("unknown", "some/path")


def test_infer_batch():
    pool = ModelEnginePool(device_id=0)
    engine = FakeYOLOEngine()
    pool.register("yolo", engine)
    pool.load("yolo", "models/yolo/best.pt")
    images = [np.ones((3, 320, 320), dtype=np.uint8) for _ in range(3)]
    results = pool.infer("yolo", images)
    assert len(results) == 3
    assert engine.infer_count == 1


def test_register_replaces_existing():
    pool = ModelEnginePool(device_id=0)
    e1 = FakeYOLOEngine()
    e2 = FakeYOLOEngine()
    pool.register("yolo", e1)
    pool.register("yolo", e2)
    assert pool._engines["yolo"] is e2


def test_list_loaded():
    pool = ModelEnginePool(device_id=0)
    pool.register("yolo", FakeYOLOEngine())
    pool.register("patchcore", FakeYOLOEngine())
    pool.load("yolo", "models/yolo/best.pt")
    loaded = pool.list_loaded()
    assert "yolo" in loaded
    assert "patchcore" not in loaded
