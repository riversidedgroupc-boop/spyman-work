"""Benchmark runner — orchestrates stress tests with configurable scenarios."""
from __future__ import annotations

import time
from dataclasses import dataclass

from benchmark.input_source import InputSource
from benchmark.metrics_collector import MetricsCollector
from benchmark.spi_calculator import SpiCalculator
from benchmark.hardware_advisor import HardwareAdvisor
from gpu_scheduler.scheduler import GPUInferenceScheduler
from runtime.unified_image_pool import UnifiedImagePool
from storage_v8.async_writer import AsyncDiskWriter


@dataclass
class BenchmarkConfig:
    camera_count: int = 3
    line_speed_mpm: float = 80.0
    model_combo: str = "yolo+patchcore"  # yolo, patchcore, yolo+patchcore
    save_mode: str = "save_ng_only"
    batch_size: int = 4
    max_wait_ms: float = 10.0
    duration_sec: float = 1800  # 30 minutes
    source_type: str = "simulated"  # simulated, real_camera, history_replay
    speed_multiplier: float = 1.0  # 0.5x, 1x, 2x, 4x, 8x


@dataclass
class BenchmarkReport:
    config: BenchmarkConfig
    duration_sec: float = 0.0
    avg_tiles_per_sec: float = 0.0
    max_tiles_per_sec: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_cpu_pct: float = 0.0
    peak_cpu_pct: float = 0.0
    avg_gpu_pct: float = 0.0
    peak_gpu_pct: float = 0.0
    avg_vram_mb: float = 0.0
    peak_vram_mb: float = 0.0
    avg_ram_gb: float = 0.0
    peak_ram_gb: float = 0.0
    avg_spi: float = 0.0
    peak_spi: float = 0.0
    total_tiles: int = 0
    total_dropped: int = 0
    total_saved: int = 0
    hardware_advice: dict | None = None


class BenchmarkRunner:
    def __init__(
        self,
        source: InputSource,
        pool: UnifiedImagePool,
        scheduler: GPUInferenceScheduler,
        writer: AsyncDiskWriter,
        collector: MetricsCollector | None = None,
    ):
        self._source = source
        self._pool = pool
        self._scheduler = scheduler
        self._writer = writer
        self._collector = collector or MetricsCollector()
        self._collector.set_sources(pool, scheduler, writer)
        self._spi = SpiCalculator()
        self._advisor = HardwareAdvisor()
        self._running = False

    def run(self, config: BenchmarkConfig, progress_callback=None) -> BenchmarkReport:
        self._pool.clear()
        self._collector.clear()
        self._source.reset()

        self._running = True
        self._scheduler.set_on_result(self._writer.write)
        self._scheduler.start()
        self._writer.start()
        self._collector.start()

        start_time = time.time()
        end_time = start_time + config.duration_sec

        while time.time() < end_time and self._running:
            tiles = self._source.next_batch(config.batch_size)
            for t in tiles:
                self._pool.push(t)

            if progress_callback:
                elapsed = time.time() - start_time
                progress_callback(elapsed / config.duration_sec, self._collector.snapshot())

            time.sleep(0.01)

        self._scheduler.stop()
        self._writer.stop()
        self._collector.stop()

        return self._build_report(config, time.time() - start_time)

    def stop(self) -> None:
        self._running = False

    def _build_report(self, config: BenchmarkConfig, elapsed: float) -> BenchmarkReport:
        history = self._collector.history()
        if not history:
            return BenchmarkReport(config=config, duration_sec=elapsed)

        tiles_per_sec = [s.tiles_per_sec for s in history]
        spi_data = self._spi.compute_from_history(history)
        sched_stats = self._scheduler.get_stats()

        advice = self._advisor.recommend(
            avg_spi=spi_data["avg_spi"],
            peak_spi=spi_data["peak_spi"],
            avg_tiles_per_sec=sum(tiles_per_sec) / len(tiles_per_sec),
            avg_inference_ms=sched_stats.avg_inference_ms,
            total_dropped=sum(s.dropped_tiles for s in history),
            gpu_vram_mb=max((s.gpu_vram_used_mb for s in history), default=0),
        )

        return BenchmarkReport(
            config=config,
            duration_sec=elapsed,
            avg_tiles_per_sec=sum(tiles_per_sec) / len(tiles_per_sec),
            max_tiles_per_sec=max(tiles_per_sec),
            avg_latency_ms=sched_stats.avg_inference_ms,
            p95_latency_ms=sched_stats.p95_inference_ms,
            p99_latency_ms=sched_stats.p99_inference_ms,
            avg_cpu_pct=sum(s.cpu_percent for s in history) / len(history),
            peak_cpu_pct=max(s.cpu_percent for s in history),
            avg_gpu_pct=sum(s.gpu_percent for s in history) / len(history),
            peak_gpu_pct=max(s.gpu_percent for s in history),
            avg_vram_mb=sum(s.gpu_vram_used_mb for s in history) / len(history),
            peak_vram_mb=max(s.gpu_vram_used_mb for s in history),
            avg_ram_gb=sum(s.ram_used_gb for s in history) / len(history),
            peak_ram_gb=max(s.ram_used_gb for s in history),
            avg_spi=spi_data["avg_spi"],
            peak_spi=spi_data["peak_spi"],
            total_tiles=sched_stats.total_tiles_processed,
            total_dropped=sum(s.dropped_tiles for s in history),
            total_saved=self._writer.get_stats().get("written", 0),
            hardware_advice=advice,
        )
