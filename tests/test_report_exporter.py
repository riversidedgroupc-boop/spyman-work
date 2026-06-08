"""Tests for benchmark/report_exporter.py — Markdown and JSON export."""
from __future__ import annotations

import json

from benchmark.benchmark_runner import BenchmarkConfig, BenchmarkReport
from benchmark.report_exporter import export_markdown, export_json


def _make_report() -> BenchmarkReport:
    return BenchmarkReport(
        config=BenchmarkConfig(
            camera_count=3,
            line_speed_mpm=80.0,
            model_combo="yolo+patchcore",
            save_mode="save_ng_only",
            batch_size=4,
            duration_sec=60.0,
            source_type="simulated",
            speed_multiplier=1.0,
        ),
        duration_sec=58.3,
        avg_tiles_per_sec=245.6,
        max_tiles_per_sec=310.2,
        avg_latency_ms=12.5,
        p95_latency_ms=28.3,
        p99_latency_ms=45.1,
        avg_cpu_pct=35.2,
        peak_cpu_pct=68.7,
        avg_gpu_pct=72.1,
        peak_gpu_pct=95.3,
        avg_vram_mb=1024.0,
        peak_vram_mb=1536.0,
        avg_ram_gb=4.2,
        peak_ram_gb=6.8,
        avg_spi=52.3,
        peak_spi=78.9,
        total_tiles=14200,
        total_dropped=5,
        total_saved=120,
        hardware_advice={
            "recommended_tier": "L2",
            "spi_avg": 52.3,
            "spi_peak": 78.9,
            "tiles_per_sec": 245.6,
            "avg_inference_ms": 12.5,
            "total_dropped": 5,
            "notes": "入门独显平台适用",
        },
    )


def _make_report_with_context() -> BenchmarkReport:
    return BenchmarkReport(
        config=BenchmarkConfig(
            camera_count=3,
            line_speed_mpm=80.0,
            model_combo="yolo+patchcore",
            save_mode="save_ng_only",
            batch_size=4,
            duration_sec=60.0,
            source_type="simulated",
            speed_multiplier=1.0,
            backend="onnx",
            project_id="PROJ_test",
            dataset_version_id="DSVER_001",
            model_version_id="MODEL_abc",
        ),
        duration_sec=58.3,
        avg_tiles_per_sec=245.6,
        max_tiles_per_sec=310.2,
        avg_latency_ms=12.5,
        p95_latency_ms=28.3,
        p99_latency_ms=45.1,
        avg_cpu_pct=35.2,
        peak_cpu_pct=68.7,
        avg_gpu_pct=72.1,
        peak_gpu_pct=95.3,
        avg_vram_mb=1024.0,
        peak_vram_mb=1536.0,
        avg_ram_gb=4.2,
        peak_ram_gb=6.8,
        avg_spi=52.3,
        peak_spi=78.9,
        total_tiles=14200,
        total_dropped=5,
        total_saved=120,
        hardware_advice={
            "recommended_tier": "L2",
            "notes": "入门独显平台适用",
        },
    )


class TestExportMarkdown:
    def test_contains_config_section(self):
        md = export_markdown(_make_report())
        assert "# Benchmark Report" in md
        assert "## Configuration" in md

    def test_contains_throughput_section(self):
        md = export_markdown(_make_report())
        assert "## Throughput" in md
        assert "245.6" in md

    def test_contains_latency_section(self):
        md = export_markdown(_make_report())
        assert "## Latency" in md
        assert "12.50" in md

    def test_contains_system_load_section(self):
        md = export_markdown(_make_report())
        assert "## System Load" in md
        assert "35.2%" in md

    def test_contains_spi_section(self):
        md = export_markdown(_make_report())
        assert "## System Pressure Index" in md
        assert "52.3" in md

    def test_contains_hardware_recommendation(self):
        md = export_markdown(_make_report())
        assert "## Hardware Recommendation" in md
        assert "L2" in md

    def test_contains_backend_in_config(self):
        md = export_markdown(_make_report_with_context())
        assert "onnx" in md

    def test_context_section_shows_project_info(self):
        md = export_markdown(_make_report_with_context())
        assert "## Context" in md
        assert "PROJ_test" in md
        assert "DSVER_001" in md
        assert "MODEL_abc" in md

    def test_context_section_omitted_when_no_project(self):
        md = export_markdown(_make_report())
        assert "(no project context)" in md


class TestExportJson:
    def test_contains_all_fields(self):
        js = export_json(_make_report())
        data = json.loads(js)
        assert "config" in data
        assert "duration_sec" in data
        assert "avg_tiles_per_sec" in data
        assert "avg_latency_ms" in data
        assert "avg_spi" in data
        assert "hardware_advice" in data

    def test_values_are_correct(self):
        js = export_json(_make_report())
        data = json.loads(js)
        assert data["avg_tiles_per_sec"] == 245.6
        assert data["total_tiles"] == 14200
        assert data["avg_spi"] == 52.3

    def test_config_is_serialized(self):
        js = export_json(_make_report())
        data = json.loads(js)
        cfg = data["config"]
        assert cfg["camera_count"] == 3
        assert cfg["model_combo"] == "yolo+patchcore"
