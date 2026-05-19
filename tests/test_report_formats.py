"""Tests for multi-format report generation."""
import json
import os
import tempfile

import pytest

from desktop_app.workers.report_worker import ReportWorker


def _wait_worker(worker):
    """Block until worker finishes."""
    worker.start()
    worker.wait(3000)


def test_report_markdown_format(tmp_path):
    worker = ReportWorker(
        report_type="project",
        project_name="TestProject",
        output_dir=str(tmp_path),
        export_format="md",
        context={"customer": "ACME", "spec": "CopperTube", "version": "0.6.0"},
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    assert path.endswith(".md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "ACME" in content
    assert "CopperTube" in content


def test_report_html_format(tmp_path):
    worker = ReportWorker(
        report_type="project",
        project_name="TestProject",
        output_dir=str(tmp_path),
        export_format="html",
        context={"customer": "ACME", "version": "0.6.0"},
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    assert path.endswith(".html")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "<html" in content.lower()
    assert "ACME" in content


def test_report_json_format(tmp_path):
    worker = ReportWorker(
        report_type="system",
        project_name="TestSystem",
        output_dir=str(tmp_path),
        export_format="json",
        context={"health": {"uptime_seconds": 3600, "disk_percent": 45}},
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    assert path.endswith(".json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["report_type"] == "system"
    assert data["context"]["health"]["uptime_seconds"] == 3600


def test_report_csv_format(tmp_path):
    worker = ReportWorker(
        report_type="project",
        project_name="CSVProject",
        output_dir=str(tmp_path),
        export_format="csv",
        context={"customer": "CSVCorp", "spec": "AluBar", "camera_count": "3"},
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    assert path.endswith(".csv")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "CSVCorp" in content
    assert "AluBar" in content


def test_report_pdf_fallback(tmp_path):
    """PDF export falls back to HTML if fpdf2 is not installed."""
    worker = ReportWorker(
        report_type="project",
        project_name="PDFFallback",
        output_dir=str(tmp_path),
        export_format="pdf",
        context={"customer": "PDFCorp"},
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    # Most likely HTML fallback since fpdf2 may not be installed
    assert path.endswith(".html") or path.endswith(".pdf")


def test_report_batch_format(tmp_path):
    worker = ReportWorker(
        report_type="batch",
        project_name="BatchProject",
        output_dir=str(tmp_path),
        export_format="md",
        context={
            "batch_id": "BATCH_001",
            "total_inspected": 500,
            "ng_count": 12,
            "ng_rate": 0.024,
            "defect_distribution": [
                {"label": "scratch", "count": 8},
                {"label": "pit", "count": 4},
            ],
        },
    )
    _wait_worker(worker)
    path = worker.get_output_path()
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "BATCH_001" in content
    assert "500" in content
    assert "2.40%" in content
