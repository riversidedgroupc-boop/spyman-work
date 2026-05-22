"""SPI (System Pressure Index) calculator."""
from __future__ import annotations

from benchmark.metrics_collector import MetricSnapshot


class SpiCalculator:
    DEFAULT_WEIGHTS = {
        "camera": 0.20,
        "cpu": 0.20,
        "gpu": 0.30,
        "memory": 0.15,
        "disk": 0.15,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)

    def compute(self, snapshot: MetricSnapshot) -> float:
        camera = min(snapshot.pool_usage_ratio * 100, 100)
        cpu = min(snapshot.cpu_percent, 100)
        vram_ratio = snapshot.gpu_vram_used_mb / max(snapshot.gpu_vram_total_mb, 1)
        gpu = max(snapshot.gpu_percent, vram_ratio * 100)
        memory = min(snapshot.pool_usage_ratio * 100, 100)
        disk = min(snapshot.disk_write_mbps / 200 * 100, 100)

        spi = (
            camera * self._weights["camera"]
            + cpu * self._weights["cpu"]
            + gpu * self._weights["gpu"]
            + memory * self._weights["memory"]
            + disk * self._weights["disk"]
        )
        return round(spi, 1)

    def pressure_level(self, spi: float) -> str:
        if spi < 40:
            return "low"
        elif spi < 70:
            return "medium"
        elif spi < 85:
            return "high"
        return "critical"

    def compute_from_history(self, history: list[MetricSnapshot]) -> dict:
        if not history:
            return {"avg_spi": 0, "peak_spi": 0, "pressure_level": "low"}
        spis = [self.compute(s) for s in history]
        avg = sum(spis) / len(spis)
        peak = max(spis)
        return {
            "avg_spi": round(avg, 1),
            "peak_spi": round(peak, 1),
            "pressure_level": self.pressure_level(avg),
        }
