"""Benchmark report exporter — Markdown and JSON formats."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime

from benchmark.benchmark_runner import BenchmarkReport


def export_markdown(report: BenchmarkReport) -> str:
    cfg = report.config
    context_lines = ""
    if cfg.project_id:
        context_lines += f"- **Project**: {cfg.project_id}\n"
    if cfg.dataset_version_id:
        context_lines += f"- **Dataset Version**: {cfg.dataset_version_id}\n"
    if cfg.model_version_id:
        context_lines += f"- **Model Version**: {cfg.model_version_id}\n"

    return f"""# Benchmark Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Context
{context_lines or '(no project context)'}

## Configuration
| Parameter | Value |
|-----------|-------|
| Source | {cfg.source_type} |
| Backend | {cfg.backend} |
| Cameras | {cfg.camera_count} |
| Line Speed | {cfg.line_speed_mpm} m/min |
| Models | {cfg.model_combo} |
| Save Mode | {cfg.save_mode} |
| Batch Size | {cfg.batch_size} |
| Duration | {report.duration_sec:.0f}s |
| Speed Multiplier | {cfg.speed_multiplier}x |

## Throughput
- **Avg Tile/s**: {report.avg_tiles_per_sec:.1f}
- **Max Tile/s**: {report.max_tiles_per_sec:.1f}
- **Total Tiles**: {report.total_tiles}
- **Total Dropped**: {report.total_dropped}
- **Total Saved**: {report.total_saved}

## Latency
- **Avg**: {report.avg_latency_ms:.2f} ms
- **P95**: {report.p95_latency_ms:.2f} ms
- **P99**: {report.p99_latency_ms:.2f} ms

## System Load
| Resource | Avg | Peak |
|----------|-----|------|
| CPU | {report.avg_cpu_pct:.1f}% | {report.peak_cpu_pct:.1f}% |
| GPU | {report.avg_gpu_pct:.1f}% | {report.peak_gpu_pct:.1f}% |
| VRAM | {report.avg_vram_mb:.0f} MB | {report.peak_vram_mb:.0f} MB |
| RAM | {report.avg_ram_gb:.1f} GB | {report.peak_ram_gb:.1f} GB |

## System Pressure Index
- **Avg SPI**: {report.avg_spi:.1f}
- **Peak SPI**: {report.peak_spi:.1f}

## Hardware Recommendation
- **Recommended Tier**: {report.hardware_advice.get('recommended_tier', 'N/A')}
- **Notes**: {report.hardware_advice.get('notes', 'N/A')}
"""


def export_json(report: BenchmarkReport) -> str:
    return json.dumps(dataclasses.asdict(report), indent=2, default=str)
