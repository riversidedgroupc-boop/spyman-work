"""Tests for benchmark/metrics_collector.py — MetricsCollector and MetricSnapshot."""
from __future__ import annotations

from tests import wait_for_condition

from benchmark.metrics_collector import MetricsCollector, MetricSnapshot


class TestMetricSnapshot:
    def test_default_values(self):
        snap = MetricSnapshot()
        assert snap.timestamp == 0.0
        assert snap.cpu_percent == 0.0
        assert snap.gpu_percent == 0.0
        assert snap.gpu_vram_used_mb == 0.0
        assert snap.gpu_vram_total_mb == 0.0
        assert snap.ram_used_gb == 0.0
        assert snap.ram_total_gb == 0.0
        assert snap.pool_usage_ratio == 0.0
        assert snap.disk_write_mbps == 0.0
        assert snap.disk_queue_len == 0
        assert snap.tiles_per_sec == 0.0
        assert snap.avg_inference_ms == 0.0
        assert snap.dropped_tiles == 0

    def test_custom_values(self):
        snap = MetricSnapshot(
            timestamp=100.5,
            cpu_percent=45.2,
            gpu_percent=80.0,
            tiles_per_sec=120.5,
            dropped_tiles=3,
        )
        assert snap.cpu_percent == 45.2
        assert snap.gpu_percent == 80.0
        assert snap.tiles_per_sec == 120.5
        assert snap.dropped_tiles == 3


class TestMetricsCollector:
    def test_initial_state(self):
        collector = MetricsCollector(sample_interval_sec=10.0)
        assert collector.history() == []
        snap = collector.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert snap.timestamp == 0.0  # default when empty

    def test_start_and_stop(self):
        collector = MetricsCollector(sample_interval_sec=0.05)
        collector.start()
        assert collector._running is True
        assert collector._thread is not None
        collector.stop()

    def test_collects_history_while_running(self):
        collector = MetricsCollector(sample_interval_sec=0.05)
        collector.start()
        wait_for_condition(lambda: len(collector.history()) >= 2, timeout=2.0)
        collector.stop()
        history = collector.history()
        assert len(history) >= 2

    def test_snapshot_returns_last_entry(self):
        collector = MetricsCollector(sample_interval_sec=0.05)
        collector.start()
        wait_for_condition(lambda: collector.snapshot().timestamp > 0, timeout=2.0)
        snap = collector.snapshot()
        collector.stop()
        # After running, snapshot should have a real timestamp > 0
        assert snap.timestamp > 0

    def test_clear_empties_history(self):
        collector = MetricsCollector(sample_interval_sec=0.05)
        collector.start()
        wait_for_condition(lambda: len(collector.history()) > 0, timeout=2.0)
        collector.stop()
        assert len(collector.history()) > 0
        collector.clear()
        assert collector.history() == []

    def test_stop_before_start_does_not_crash(self):
        collector = MetricsCollector()
        collector.stop()  # should not raise

    def test_set_sources_does_not_crash_with_none(self):
        collector = MetricsCollector()
        collector.set_sources(None, None, None)
        # Sampling loop should start even with None sources
        collector.start()
        wait_for_condition(lambda: len(collector.history()) >= 1, timeout=2.0)
        collector.stop()
        # History should still accumulate (CPU/memory data)
        assert len(collector.history()) >= 1
