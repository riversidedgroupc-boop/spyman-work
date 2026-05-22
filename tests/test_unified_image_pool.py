"""Tests for UnifiedImagePool."""
import numpy as np
from runtime.unified_image_pool import UnifiedImagePool, TileEntry, PoolStats


def make_tile(camera_id: str = "Camera_01", block_id: str = "BLK_001") -> TileEntry:
    return TileEntry(
        tile_id=f"{block_id}_T_000_000",
        run_id="run_test",
        customer_id="test_cust",
        product_id="test_prod",
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


def test_push_and_pop_batch():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(5):
        pool.push(make_tile(camera_id=f"Cam_{i%3}"))
    batch = pool.pop_batch(3)
    assert len(batch) == 3
    assert pool.size() == 2


def test_pop_batch_returns_available_when_short():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    pool.push(make_tile())
    pool.push(make_tile())
    batch = pool.pop_batch(4)
    assert len(batch) == 2


def test_pool_size_limit():
    pool = UnifiedImagePool(max_pool_size=10, memory_budget_mb=256, drop_policy="oldest")
    for i in range(20):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    assert pool.size() <= 10
    stats = pool.stats()
    assert stats.total_dropped > 0


def test_memory_budget():
    # ~300KB per tile, 1MB budget → ~3 max
    pool = UnifiedImagePool(max_pool_size=1000, memory_budget_mb=1, drop_policy="oldest")
    for i in range(20):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    assert pool.size() <= 4


def test_stats():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(8):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    for _ in range(3):
        pool.pop_batch(2)
    stats = pool.stats()
    assert stats.total_pushes == 8
    assert stats.total_pops >= 3
    assert stats.total_dropped == 0


def test_camera_distribution():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(9):
        pool.push(make_tile(camera_id=f"Camera_{i%3 + 1:02d}"))
    dist = pool.camera_distribution()
    assert dist["Camera_01"] == 3
    assert dist["Camera_02"] == 3
    assert dist["Camera_03"] == 3
