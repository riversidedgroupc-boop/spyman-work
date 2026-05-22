"""Inference statistics types for GPU scheduler."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InferenceTiming:
    """Per-inference timing record."""
    model_type: str = ""
    tile_count: int = 0
    elapsed_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0


@dataclass
class SchedulerStats:
    """Cumulative scheduler statistics."""
    total_tiles_processed: int = 0
    total_batches: int = 0
    total_inference_time_ms: float = 0.0
    avg_inference_ms: float = 0.0
    p95_inference_ms: float = 0.0
    p99_inference_ms: float = 0.0
    queue_depth: int = 0
    max_queue_depth: int = 0
    dropped_tiles: int = 0
    model_switches: int = 0
    gpu_utilization_pct: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0

    per_model: dict[str, ModelStats] = field(default_factory=dict)
    _recent_latencies: list[float] = field(default_factory=list)
    _max_recent: int = 1000

    def record_inference(self, timing: InferenceTiming) -> None:
        self.total_tiles_processed += timing.tile_count
        self.total_batches += 1
        self.total_inference_time_ms += timing.elapsed_ms

        self._recent_latencies.append(timing.inference_ms)
        if len(self._recent_latencies) > self._max_recent:
            self._recent_latencies = self._recent_latencies[-self._max_recent:]

        if self._recent_latencies:
            sorted_lat = sorted(self._recent_latencies)
            self.avg_inference_ms = sum(sorted_lat) / len(sorted_lat)
            self.p95_inference_ms = sorted_lat[int(len(sorted_lat) * 0.95)]
            self.p99_inference_ms = sorted_lat[int(len(sorted_lat) * 0.99)]

        if timing.model_type not in self.per_model:
            self.per_model[timing.model_type] = ModelStats(model_type=timing.model_type)
        self.per_model[timing.model_type].record(timing.inference_ms, timing.tile_count)


@dataclass
class ModelStats:
    """Per-model cumulative statistics."""
    model_type: str = ""
    inference_count: int = 0
    total_tiles: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    ng_count: int = 0
    _recent_latencies: list[float] = field(default_factory=list)
    _max_recent: int = 200

    def record(self, latency_ms: float, tile_count: int) -> None:
        self.inference_count += 1
        self.total_tiles += tile_count
        self._recent_latencies.append(latency_ms)
        if len(self._recent_latencies) > self._max_recent:
            self._recent_latencies = self._recent_latencies[-self._max_recent:]
        if self._recent_latencies:
            sorted_l = sorted(self._recent_latencies)
            self.avg_latency_ms = sum(sorted_l) / len(sorted_l)
            self.p95_latency_ms = sorted_l[int(len(sorted_l) * 0.95)]


@dataclass
class TileResult:
    """Inference result for a single tile — carries full traceability metadata."""
    tile_id: str
    camera_id: str
    run_id: str
    product_id: str
    model_type: str
    model_version: str
    result_type: str  # OK / NG / UNKNOWN
    defect_type: str = ""
    confidence: float = 0.0
    bbox: list[int] | None = None  # [x1, y1, x2, y2] in block coords
    inference_time_ms: float = 0.0
    gpu_device_id: int = 0
    meter_start: float = 0.0
    meter_end: float = 0.0
    created_time: str = ""
