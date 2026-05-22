"""Hardware advisor — recommends hardware tier based on benchmark results."""
from __future__ import annotations

from enum import Enum


class HardwareTier(str, Enum):
    L1_LIGHT = "L1"         # RK3588 / ARM
    L2_ENTRY = "L2"         # GTX 1650 / RTX 3050
    L3_STANDARD = "L3"      # RTX 4060 / 4060 Ti / 4070
    L4_HIGH = "L4"          # RTX 4080 / 4090 / RTX 5000 Ada


class HardwareAdvisor:
    def recommend(
        self,
        avg_spi: float,
        peak_spi: float,
        avg_tiles_per_sec: float,
        avg_inference_ms: float,
        total_dropped: int,
        gpu_vram_mb: float,
    ) -> dict:
        if avg_spi < 40 and total_dropped == 0:
            tier = HardwareTier.L1_LIGHT
        elif avg_spi < 70 and total_dropped < 10:
            tier = HardwareTier.L2_ENTRY
        elif avg_spi < 85:
            tier = HardwareTier.L3_STANDARD
        else:
            tier = HardwareTier.L4_HIGH

        return {
            "recommended_tier": tier.value,
            "spi_avg": avg_spi,
            "spi_peak": peak_spi,
            "tiles_per_sec": avg_tiles_per_sec,
            "avg_inference_ms": avg_inference_ms,
            "total_dropped": total_dropped,
            "notes": self._tier_notes(tier),
        }

    def _tier_notes(self, tier: HardwareTier) -> str:
        notes = {
            HardwareTier.L1_LIGHT: "轻量平台适用。1相机+低线速+Save NG Only。不适合多模型并行。",
            HardwareTier.L2_ENTRY: "入门独显平台适用。1-3相机+中等线速。建议主模型单独运行。",
            HardwareTier.L3_STANDARD: "标准工业检测平台。3相机+60-100 m/min+YOLO+PatchCore。推荐配置。",
            HardwareTier.L4_HIGH: "高性能平台。3-6相机+高线速+多模型并行+离线回放。",
        }
        return notes[tier]
