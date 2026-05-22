"""Tests for benchmark/benchmark_runner.py — BenchmarkRunner and BenchmarkReport."""
from __future__ import annotations

import time

from benchmark.benchmark_runner import BenchmarkConfig, BenchmarkReport, BenchmarkRunner
from benchmark.input_source import SimulatedTileSource
from benchmark.metrics_collector import MetricSnapshot, MetricsCollector
from gpu_scheduler.scheduler import GPUInferenceScheduler
from runtime.unified_image_pool import UnifiedImagePool


class TestBenchmarkConfig:
    def test_default_values(self):
        cfg = BenchmarkConfig()
        assert cfg.camera_count == 3
        assert cfg.line_speed_mpm == 80.0
        assert cfg.model_combo == "yolo+patchcore"
        assert cfg.save_mode == "save_ng_only"
        assert cfg.batch_size == 4
        assert cfg.max_wait_ms == 10.0
        assert cfg.duration_sec == 1800
        assert cfg.source_type == "simulated"
        assert cfg.speed_multiplier == 1.0

    def test_custom_values(self):
        cfg = BenchmarkConfig(
            camera_count=6,
            line_speed_mpm=120.0,
            duration_sec=60,
            speed_multiplier=2.0,
        )
        assert cfg.camera_count == 6
        assert cfg.duration_sec == 60


class TestBenchmarkReport:
    def test_minimal_report(self):
        report = BenchmarkReport(config=BenchmarkConfig())
        assert report.config.camera_count == 3
        assert report.duration_sec == 0.0
        assert report.total_tiles == 0

    def test_full_report(self):
        report = BenchmarkReport(
            config=BenchmarkConfig(),
            duration_sec=30.0,
            avg_tiles_per_sec=100.0,
            avg_spi=45.0,
            hardware_advice={"recommended_tier": "L2"},
        )
        assert report.duration_sec == 30.0
        assert report.avg_tiles_per_sec == 100.0
        assert report.avg_spi == 45.0
        assert report.hardware_advice == {"recommended_tier": "L2"}


class _FakeAsyncWriter:
    """Minimal fake for AsyncDiskWriter used in runner tests."""

    def __init__(self):
        self._stats = {"written": 0, "queue_size": 0}

    def write(self, tile, result) -> bool:
        self._stats["written"] += 1
        return True

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_stats(self) -> dict:
        return dict(self._stats)


class _FakeModelEnginePool:
    def is_loaded(self, model_type: str) -> bool:
        return True

    def infer(self, model_type: str, images: list) -> list[dict]:
        import numpy as np
        results = []
        for img in images:
            mean_val = float(np.mean(img))
            is_ng = mean_val > 100
            results.append({
                "result_type": "NG" if is_ng else "OK",
                "confidence": 0.92 if is_ng else 0.85,
                "model_version": "test_v1",
                "defect_type": "scratch" if is_ng else "",
                "bbox": None,
            })
        return results


class TestBenchmarkRunnerConstruction:
    def test_runner_creates_with_minimal_deps(self):
        pool = UnifiedImagePool(max_pool_size=100)
        source = SimulatedTileSource(camera_count=1)
        writer = _FakeAsyncWriter()

        from gpu_scheduler.priority_router import RoutingStrategy
        scheduler = GPUInferenceScheduler(
            pool=pool,
            model_pool=_FakeModelEnginePool(),
            strategy=RoutingStrategy.HYBRID_YOLO_FIRST,
        )

        runner = BenchmarkRunner(
            source=source,
            pool=pool,
            scheduler=scheduler,
            writer=writer,
        )
        assert runner is not None
        assert runner._running is False

    def test_stop_when_not_running_does_not_crash(self):
        pool = UnifiedImagePool(max_pool_size=100)
        source = SimulatedTileSource(camera_count=1)
        writer = _FakeAsyncWriter()

        from gpu_scheduler.priority_router import RoutingStrategy
        scheduler = GPUInferenceScheduler(
            pool=pool,
            model_pool=_FakeModelEnginePool(),
            strategy=RoutingStrategy.HYBRID_YOLO_FIRST,
        )

        runner = BenchmarkRunner(
            source=source,
            pool=pool,
            scheduler=scheduler,
            writer=writer,
        )
        runner.stop()  # should not raise


class TestBenchmarkRunnerBuildReport:
    def test_build_report_with_no_history(self):
        pool = UnifiedImagePool(max_pool_size=100)
        source = SimulatedTileSource(camera_count=1)
        writer = _FakeAsyncWriter()
        collector = MetricsCollector(sample_interval_sec=10.0)

        from gpu_scheduler.priority_router import RoutingStrategy
        scheduler = GPUInferenceScheduler(
            pool=pool,
            model_pool=_FakeModelEnginePool(),
            strategy=RoutingStrategy.HYBRID_YOLO_FIRST,
        )

        runner = BenchmarkRunner(
            source=source,
            pool=pool,
            scheduler=scheduler,
            writer=writer,
            collector=collector,
        )

        cfg = BenchmarkConfig(duration_sec=0.001)
        report = runner._build_report(cfg, 0.001)
        assert report.config == cfg
        assert report.duration_sec == 0.001
        # No history → defaults
        assert report.total_tiles == 0

    def test_build_report_with_history(self):
        pool = UnifiedImagePool(max_pool_size=100)
        source = SimulatedTileSource(camera_count=1)
        writer = _FakeAsyncWriter()
        collector = MetricsCollector(sample_interval_sec=10.0)

        # Inject some history
        snap = MetricSnapshot(
            timestamp=time.time(),
            cpu_percent=40.0,
            gpu_percent=70.0,
            gpu_vram_used_mb=1024.0,
            gpu_vram_total_mb=4096.0,
            ram_used_gb=3.0,
            ram_total_gb=16.0,
            pool_usage_ratio=0.5,
            tiles_per_sec=200.0,
            avg_inference_ms=15.0,
            p95_inference_ms=30.0,
            p99_inference_ms=50.0,
            dropped_tiles=0,
        )
        collector._history.append(snap)

        from gpu_scheduler.priority_router import RoutingStrategy
        scheduler = GPUInferenceScheduler(
            pool=pool,
            model_pool=_FakeModelEnginePool(),
            strategy=RoutingStrategy.HYBRID_YOLO_FIRST,
        )
        # Give scheduler some stats
        scheduler._stats.total_tiles_processed = 100
        scheduler._stats.avg_inference_ms = 15.0

        runner = BenchmarkRunner(
            source=source,
            pool=pool,
            scheduler=scheduler,
            writer=writer,
            collector=collector,
        )

        cfg = BenchmarkConfig(duration_sec=1.0)
        report = runner._build_report(cfg, 1.0)
        assert report.avg_cpu_pct == 40.0
        assert report.avg_gpu_pct == 70.0
        assert report.avg_vram_mb == 1024.0
        assert report.total_tiles == 100
        assert report.hardware_advice is not None
        assert "recommended_tier" in report.hardware_advice
