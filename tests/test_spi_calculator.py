"""Tests for SpiCalculator and HardwareAdvisor."""
import pytest
from benchmark.metrics_collector import MetricSnapshot
from benchmark.spi_calculator import SpiCalculator
from benchmark.hardware_advisor import HardwareAdvisor, HardwareTier


def make_snapshot(cpu=30.0, gpu=40.0, vram_used=2000, vram_total=8000, pool_ratio=0.3, disk_mbps=50.0):
    return MetricSnapshot(
        cpu_percent=cpu,
        gpu_percent=gpu,
        gpu_vram_used_mb=vram_used,
        gpu_vram_total_mb=vram_total,
        pool_usage_ratio=pool_ratio,
        disk_write_mbps=disk_mbps,
    )


def test_spi_compute_low_load():
    calc = SpiCalculator()
    snap = make_snapshot(cpu=20, gpu=20, pool_ratio=0.1, disk_mbps=10)
    spi = calc.compute(snap)
    assert spi < 40


def test_spi_compute_high_load():
    calc = SpiCalculator()
    snap = make_snapshot(cpu=90, gpu=95, vram_used=7800, pool_ratio=0.9, disk_mbps=180)
    spi = calc.compute(snap)
    assert spi > 70


def test_pressure_level_low():
    calc = SpiCalculator()
    assert calc.pressure_level(30) == "low"


def test_pressure_level_critical():
    calc = SpiCalculator()
    assert calc.pressure_level(90) == "critical"


def test_compute_from_history():
    calc = SpiCalculator()
    history = [
        make_snapshot(cpu=20), make_snapshot(cpu=40), make_snapshot(cpu=60)
    ]
    result = calc.compute_from_history(history)
    assert result["avg_spi"] > 0
    assert result["peak_spi"] >= result["avg_spi"]
    assert result["pressure_level"] in ("low", "medium", "high", "critical")


def test_hardware_advisor_l1():
    advisor = HardwareAdvisor()
    advice = advisor.recommend(
        avg_spi=30, peak_spi=45, avg_tiles_per_sec=100,
        avg_inference_ms=5.0, total_dropped=0, gpu_vram_mb=500,
    )
    assert advice["recommended_tier"] == "L1"


def test_hardware_advisor_l4():
    advisor = HardwareAdvisor()
    advice = advisor.recommend(
        avg_spi=90, peak_spi=98, avg_tiles_per_sec=2000,
        avg_inference_ms=25.0, total_dropped=50, gpu_vram_mb=8000,
    )
    assert advice["recommended_tier"] == "L4"
