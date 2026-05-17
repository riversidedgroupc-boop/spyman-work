"""Tests for core/report.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.report import (
    build_report_context,
    generate_markdown_report,
    generate_html_report,
)


class TestBuildReportContext:
    def test_basic(self):
        ctx = build_report_context(
            project_name="Test Project",
            dataset_name="test_ds",
            model_names=["YOLOv8", "PatchCore"],
        )
        assert ctx["project_name"] == "Test Project"
        assert ctx["dataset_name"] == "test_ds"
        assert len(ctx["model_names"]) == 2

    def test_empty(self):
        ctx = build_report_context()
        assert ctx["project_name"] == ""
        assert ctx["dataset_name"] == ""
        assert ctx["model_names"] == []

    def test_with_summaries(self):
        dep = {"miss_rate": 0.05, "num_images": 100}
        rule = {"by_level": {"A_severe": 10}}
        ctx = build_report_context(
            deployment_summary=dep,
            rule_summary=rule,
        )
        assert ctx["deployment_summary"]["miss_rate"] == 0.05
        assert ctx["rule_summary"]["by_level"]["A_severe"] == 10


class TestGenerateMarkdownReport:
    def test_generates_file(self):
        ctx = build_report_context(
            project_name="Test",
            dataset_name="test_ds",
            model_names=["ModelA"],
            deployment_summary={
                "num_images": 100,
                "num_gt": 50,
                "num_predictions": 55,
                "true_positives": 45,
                "false_positives": 10,
                "false_negatives": 5,
                "miss_rate": 0.10,
                "false_alarm_rate": 0.18,
                "false_alarms_per_meter": 0.5,
                "review_load_images": 8,
                "review_load_ratio": 0.08,
                "avg_inference_ms": 20.0,
                "max_inference_ms": 45.0,
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            content = generate_markdown_report(ctx, str(output_path))
            assert output_path.exists()
            assert "Test" in content
            assert "模型评估报告" in content
            assert "0.1000" in content  # miss_rate formatted

    def test_minimal_report(self):
        ctx = build_report_context()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report_min.md"
            content = generate_markdown_report(ctx, str(output_path))
            assert output_path.exists()
            assert "模型评估报告" in content


class TestGenerateHtmlReport:
    def test_generates_file(self):
        ctx = build_report_context(
            project_name="Test HTML",
            dataset_name="ds",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            content = generate_html_report(ctx, str(output_path))
            assert output_path.exists()
            assert "<!DOCTYPE html>" in content
            assert "Test HTML" in content
            assert "</html>" in content
