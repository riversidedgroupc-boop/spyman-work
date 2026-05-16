"""Tests for annotation parser."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.dataset.annotation_parser import (
    parse_yolo_annotation,
    parse_yolo_annotation_normalized,
    find_label_file,
    has_label,
)


def test_parse_yolo_annotation():
    """Parse a valid YOLO label file."""
    content = "0 0.5 0.5 0.1 0.2\n3 0.3 0.4 0.08 0.12\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        results = parse_yolo_annotation(tmp_path, 640, 480)
        assert len(results) == 2
        assert results[0]["class_id"] == 0
        assert results[0]["class_name"] == "OK_clean"
        assert results[1]["class_id"] == 3
        assert results[1]["class_name"] == "NG_scratch"

        # Check bbox conversion
        r0 = results[0]
        assert len(r0["bbox_xyxy"]) == 4
        # x_center=0.5, y_center=0.5, w=0.1, h=0.2 at 640x480
        # x1 = (0.5 - 0.1/2) * 640 = 0.45 * 640 = 288
        # y1 = (0.5 - 0.2/2) * 480 = 0.4 * 480 = 192
        # x2 = (0.5 + 0.1/2) * 640 = 0.55 * 640 = 352
        # y2 = (0.5 + 0.2/2) * 480 = 0.6 * 480 = 288
        assert r0["bbox_xyxy"][0] == 288.0
        assert r0["bbox_xyxy"][2] == 352.0
    finally:
        tmp_path.unlink(missing_ok=True)


def test_parse_empty_file():
    """Parse empty label file returns empty list."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        tmp_path = Path(f.name)

    try:
        results = parse_yolo_annotation(tmp_path, 640, 480)
        assert results == []
    finally:
        tmp_path.unlink(missing_ok=True)


def test_parse_missing_file():
    """Missing label file returns empty list."""
    results = parse_yolo_annotation(Path("/nonexistent/path.txt"), 640, 480)
    assert results == []


def test_parse_yolo_annotation_normalized():
    """Parse normalized coordinates."""
    content = "3 0.45 0.32 0.08 0.12\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        results = parse_yolo_annotation_normalized(tmp_path)
        assert len(results) == 1
        assert results[0]["x_center"] == 0.45
        assert results[0]["y_center"] == 0.32
        assert results[0]["width"] == 0.08
        assert results[0]["height"] == 0.12
    finally:
        tmp_path.unlink(missing_ok=True)


def test_find_label_file():
    """Find label file by image path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        label_dir = Path(tmpdir) / "labels"
        label_dir.mkdir()
        (label_dir / "img001.txt").write_text("0 0.5 0.5 0.1 0.1")

        result = find_label_file("data/images/img001.jpg", label_dir)
        assert result is not None
        assert result.name == "img001.txt"


def test_has_label():
    """Test has_label check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        label_dir = Path(tmpdir) / "labels"
        label_dir.mkdir()
        (label_dir / "img001.txt").write_text("0 0.5 0.5 0.1 0.1")

        assert has_label("data/images/img001.jpg", label_dir)
        assert not has_label("data/images/img999.jpg", label_dir)
