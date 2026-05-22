"""Tests for AsyncDiskWriter."""
import os
import tempfile
import time
import numpy as np
from gpu_scheduler.stats import TileResult
from runtime.unified_image_pool import TileEntry
from storage_v8.save_policy import SavePolicyManager, SaveMode
from storage_v8.async_writer import AsyncDiskWriter


def make_tile() -> TileEntry:
    return TileEntry(
        tile_id="T_001",
        run_id="run_test",
        customer_id="test",
        product_id="test",
        camera_id="Cam_01",
        block_id="BLK_001",
        tile_index=0,
        tile_x=0,
        tile_y=0,
        meter_start=100.0,
        meter_end=100.5,
        encoder_count_start=1000,
        encoder_count_end=1005,
        timestamp="2026-05-20T20:30:00",
        image=np.ones((320, 320), dtype=np.uint8) * 128,
    )


def make_result(result_type: str = "NG") -> TileResult:
    return TileResult(
        tile_id="T_001",
        camera_id="Cam_01",
        run_id="run_test",
        product_id="prod_01",
        model_type="yolo",
        model_version="v1",
        result_type=result_type,
        defect_type="scratch",
        confidence=0.95,
        bbox=None,
        inference_time_ms=5.0,
        gpu_device_id=0,
        meter_start=100.0,
        meter_end=100.5,
        created_time="2026-05-20T20:30:00",
    )


def test_write_ng_saves_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = SavePolicyManager(SaveMode.SAVE_NG_ONLY)
        writer = AsyncDiskWriter(base_dir=tmpdir, policy=policy, queue_size=10)
        writer.start()

        assert writer.write(make_tile(), make_result("NG"))

        writer.stop()
        stats = writer.get_stats()
        assert stats["written"] >= 1


def test_save_ng_only_skips_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = SavePolicyManager(SaveMode.SAVE_NG_ONLY)
        writer = AsyncDiskWriter(base_dir=tmpdir, policy=policy)
        writer.start()

        assert writer.write(make_tile(), make_result("OK"))

        writer.stop()
        stats = writer.get_stats()
        assert stats["skipped"] >= 1
        assert stats["written"] == 0


def test_result_only_persists_result_without_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = SavePolicyManager(SaveMode.RESULT_ONLY)
        writer = AsyncDiskWriter(base_dir=tmpdir, policy=policy)
        writer.start()

        assert writer.write(make_tile(), make_result("NG"))

        writer.stop()
        stats = writer.get_stats()
        assert stats["written"] == 0
        assert stats["results_written"] == 1
