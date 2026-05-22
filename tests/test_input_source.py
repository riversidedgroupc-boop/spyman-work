"""Tests for benchmark/input_source.py — SimulatedTileSource and SpeedMultiplierSource."""
from __future__ import annotations

import numpy as np

from benchmark.input_source import SimulatedTileSource, SpeedMultiplierSource
from runtime.unified_image_pool import TileEntry


class TestSimulatedTileSource:
    def test_next_batch_generates_correct_count(self):
        source = SimulatedTileSource(camera_count=3)
        batch = source.next_batch(5)
        assert len(batch) == 5

    def test_tiles_have_tile_entry_type(self):
        source = SimulatedTileSource(camera_count=1)
        batch = source.next_batch(1)
        assert isinstance(batch[0], TileEntry)

    def test_tiles_have_image_data(self):
        source = SimulatedTileSource(camera_count=1)
        batch = source.next_batch(1)
        tile = batch[0]
        assert isinstance(tile.image, np.ndarray)
        assert tile.image.shape == (3, 320, 320)
        assert tile.image.dtype == np.uint8

    def test_camera_rotation(self):
        source = SimulatedTileSource(camera_count=3)
        batch = source.next_batch(6)
        cameras = [t.camera_id for t in batch]
        # Should cycle through Camera_01, Camera_02, Camera_03
        assert "Camera_01" in cameras
        assert "Camera_02" in cameras
        assert "Camera_03" in cameras

    def test_tile_ids_are_unique(self):
        source = SimulatedTileSource(camera_count=2)
        batch1 = source.next_batch(3)
        batch2 = source.next_batch(3)
        ids1 = {t.tile_id for t in batch1}
        ids2 = {t.tile_id for t in batch2}
        assert ids1.isdisjoint(ids2)

    def test_meter_increments(self):
        source = SimulatedTileSource(camera_count=1)
        batch = source.next_batch(3)
        assert batch[0].meter_start < batch[1].meter_start < batch[2].meter_start

    def test_reset_restarts_counters(self):
        source = SimulatedTileSource(camera_count=1)
        batch1 = source.next_batch(10)
        source.reset()
        batch2 = source.next_batch(10)
        # After reset, tile_ids should restart from same pattern
        assert batch1[0].tile_id == batch2[0].tile_id
        assert batch1[0].meter_start == batch2[0].meter_start

    def test_metadata_fields_present(self):
        source = SimulatedTileSource(camera_count=2)
        batch = source.next_batch(1)
        t = batch[0]
        assert t.run_id == "bench_run"
        assert t.customer_id == "bench"
        assert t.product_id == "bench"
        assert t.tile_width == 320
        assert t.tile_height == 320
        assert isinstance(t.timestamp, str)
        assert len(t.timestamp) > 0

    def test_defect_rate_zero_produces_consistent_pattern(self):
        """With defect_rate=0, all tiles should have mean pixel value ~60."""
        source = SimulatedTileSource(camera_count=1, defect_rate=0.0)
        batch = source.next_batch(5)
        for t in batch:
            mean_val = float(np.mean(t.image))
            # Normal tiles have random 40-80 values, mean ~60
            assert 35 < mean_val < 85


class TestSpeedMultiplierSource:
    def test_1x_multiplier_passes_through(self):
        inner = SimulatedTileSource(camera_count=1)
        wrapper = SpeedMultiplierSource(inner, multiplier=1.0)
        batch = wrapper.next_batch(5)
        assert len(batch) == 5

    def test_2x_multiplier_doubles_batch_size(self):
        inner = SimulatedTileSource(camera_count=1)
        wrapper = SpeedMultiplierSource(inner, multiplier=2.0)
        batch = wrapper.next_batch(5)
        # With 2x, actual_batch = max(1, int(5 * 2.0)) = 10
        assert len(batch) == 10

    def test_0_5x_multiplier_halves_batch_size(self):
        inner = SimulatedTileSource(camera_count=1)
        wrapper = SpeedMultiplierSource(inner, multiplier=0.5)
        batch = wrapper.next_batch(5)
        # int(5 * 0.5) = 2
        assert len(batch) == 2

    def test_reset_delegates_to_inner(self):
        inner = SimulatedTileSource(camera_count=1)
        wrapper = SpeedMultiplierSource(inner, multiplier=2.0)
        before = wrapper.next_batch(3)
        wrapper.reset()
        after = wrapper.next_batch(3)
        # After reset, tile IDs should restart
        assert before[0].tile_id == after[0].tile_id

    def test_multiplier_below_1_still_produces_at_least_1(self):
        inner = SimulatedTileSource(camera_count=1)
        wrapper = SpeedMultiplierSource(inner, multiplier=0.001)
        batch = wrapper.next_batch(1)
        assert len(batch) == 1
