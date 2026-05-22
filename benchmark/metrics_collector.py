"""Metrics collector — samples CPU, GPU, memory, disk, and pipeline stats."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class MetricSnapshot:
    timestamp: float = 0.0
    cpu_percent: float = 0.0
    gpu_percent: float = 0.0
    gpu_vram_used_mb: float = 0.0
    gpu_vram_total_mb: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    pool_usage_ratio: float = 0.0
    disk_write_mbps: float = 0.0
    disk_queue_len: int = 0
    tiles_per_sec: float = 0.0
    avg_inference_ms: float = 0.0
    p95_inference_ms: float = 0.0
    p99_inference_ms: float = 0.0
    acquire_queue_len: int = 0
    save_queue_len: int = 0
    dropped_tiles: int = 0


class MetricsCollector:
    """Samples system and pipeline metrics at configurable intervals.

    Uses psutil for CPU/RAM and nvidia-ml-py for GPU. Gracefully degrades
    if any library is unavailable.
    """

    def __init__(self, sample_interval_sec: float = 0.2):
        self._sample_interval_sec = sample_interval_sec
        self._history: list[MetricSnapshot] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # Try to init GPU monitoring
        self._nvml_available = False
        self._gpu_handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_available = True
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._nvml_available = False

        # External refs to be set by benchmark runner
        self._pool = None  # UnifiedImagePool
        self._scheduler = None  # GPUInferenceScheduler
        self._writer = None  # AsyncDiskWriter

    def set_sources(self, pool, scheduler, writer) -> None:
        self._pool = pool
        self._scheduler = scheduler
        self._writer = writer

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _sample_loop(self) -> None:
        last_tiles = 0
        last_time = time.time()
        while self._running:
            time.sleep(self._sample_interval_sec)

            snap = MetricSnapshot(timestamp=time.time())

            # CPU
            try:
                import psutil
                snap.cpu_percent = psutil.cpu_percent(interval=0)
                mem = psutil.virtual_memory()
                snap.ram_used_gb = mem.used / (1024**3)
                snap.ram_total_gb = mem.total / (1024**3)
            except Exception:
                pass

            # GPU
            if self._nvml_available and self._gpu_handle is not None:
                try:
                    import pynvml
                    util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                    snap.gpu_percent = util.gpu
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                    snap.gpu_vram_used_mb = mem_info.used / (1024**2)
                    snap.gpu_vram_total_mb = mem_info.total / (1024**2)
                except Exception:
                    pass

            # Pipeline
            if self._pool is not None:
                snap.pool_usage_ratio = self._pool.usage_ratio()
                snap.dropped_tiles = self._pool.stats().total_dropped
            if self._scheduler is not None:
                sched_stats = self._scheduler.get_stats()
                snap.avg_inference_ms = sched_stats.avg_inference_ms
                snap.p95_inference_ms = sched_stats.p95_inference_ms
                snap.p99_inference_ms = sched_stats.p99_inference_ms
            if self._writer is not None:
                ws = self._writer.get_stats()
                snap.save_queue_len = ws.get("queue_size", 0)
                snap.disk_queue_len = snap.save_queue_len

            # Throughput
            if self._pool is not None:
                current_tiles = self._pool.stats().total_tiles_popped
                dt = time.time() - last_time
                snap.tiles_per_sec = (current_tiles - last_tiles) / max(dt, 0.001)
                last_tiles = current_tiles
                last_time = time.time()

            with self._lock:
                self._history.append(snap)

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            if self._history:
                return self._history[-1]
            return MetricSnapshot()

    def history(self) -> list[MetricSnapshot]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
