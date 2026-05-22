"""Tests for MicroBatchAccumulator."""
import time
import numpy as np
from gpu_scheduler.micro_batch import MicroBatchAccumulator
from runtime.unified_image_pool import TileEntry


def make_tile(block_id: str = "BLK_001") -> TileEntry:
    return TileEntry(
        tile_id=f"{block_id}_T_000_000",
        run_id="run_test",
        customer_id="test",
        product_id="test",
        camera_id="Cam_01",
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


def test_batch_size_trigger():
    acc = MicroBatchAccumulator(batch_size=3, max_wait_ms=1000)
    assert acc.accumulate(make_tile("A")) is None
    assert acc.accumulate(make_tile("B")) is None
    batch = acc.accumulate(make_tile("C"))
    assert batch is not None
    assert len(batch) == 3


def test_max_wait_trigger():
    acc = MicroBatchAccumulator(batch_size=10, max_wait_ms=50)
    assert acc.accumulate(make_tile("A")) is None
    time.sleep(0.06)
    batch = acc.accumulate(make_tile("B"))
    assert batch is not None
    assert len(batch) == 2


def test_flush_returns_none_when_empty():
    acc = MicroBatchAccumulator(batch_size=4, max_wait_ms=100)
    assert acc.flush() is None


def test_flush_clears_buffer():
    acc = MicroBatchAccumulator(batch_size=4, max_wait_ms=100)
    acc.accumulate(make_tile("A"))
    acc.accumulate(make_tile("B"))
    batch = acc.flush()
    assert batch is not None
    assert len(batch) == 2
    assert acc.current_size() == 0


def test_current_size():
    acc = MicroBatchAccumulator(batch_size=4, max_wait_ms=100)
    assert acc.current_size() == 0
    acc.accumulate(make_tile("A"))
    assert acc.current_size() == 1
    acc.accumulate(make_tile("B"))
    assert acc.current_size() == 2
