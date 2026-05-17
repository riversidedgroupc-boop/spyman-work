"""Tests for core/position_analysis.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from core.position_analysis import (
    load_image_position_map,
    assign_detection_positions,
    bin_defects_by_meter,
    detect_continuous_defect_segments,
    summarize_position_statistics,
)
from core.schema import DetectionBox


def _box(img="img_001.jpg", cid=0, cname="scratch", conf=0.9, bbox=None):
    if bbox is None:
        bbox = [10, 20, 100, 200]
    return DetectionBox(img, cid, cname, conf, bbox)


class TestLoadImagePositionMap:
    def test_basic(self):
        csv_content = "image_name,meter_start,meter_end\nimg_001.jpg,0,1.5\nimg_002.jpg,1.5,3.0\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            f.flush()
            mapping = load_image_position_map(f.name)

        assert "img_001.jpg" in mapping
        assert mapping["img_001.jpg"]["meter_start"] == 0.0
        assert mapping["img_001.jpg"]["meter_end"] == 1.5
        assert mapping["img_001.jpg"]["meter_mid"] == 0.75

        Path(f.name).unlink(missing_ok=True)

    def test_missing_file(self):
        mapping = load_image_position_map("/nonexistent/path.csv")
        assert mapping == {}

    def test_ignore_empty_lines(self):
        csv_content = "image_name,meter_start,meter_end\n\nimg_001.jpg,0,1.0\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            f.flush()
            mapping = load_image_position_map(f.name)

        assert len(mapping) == 1
        Path(f.name).unlink(missing_ok=True)


class TestAssignDetectionPositions:
    def test_basic(self):
        preds = {
            "img_001.jpg": [_box(img="img_001.jpg")],
            "img_002.jpg": [_box(img="img_002.jpg", cname="dent")],
        }
        pos_map = {
            "img_001.jpg": {"meter_start": 0, "meter_end": 1, "meter_mid": 0.5},
            "img_002.jpg": {"meter_start": 1, "meter_end": 2, "meter_mid": 1.5},
        }
        result = assign_detection_positions(preds, pos_map)
        assert len(result) == 2
        assert result[0]["meter"] == 0.5
        assert result[1]["meter"] == 1.5

    def test_missing_position(self):
        preds = {"img_003.jpg": [_box(img="img_003.jpg")]}
        pos_map = {}
        result = assign_detection_positions(preds, pos_map)
        assert len(result) == 1
        assert result[0]["meter"] is None


class TestBinDefectsByMeter:
    def test_basic(self):
        positioned = [
            {"meter": 0.3, "class_name": "scratch"},
            {"meter": 0.7, "class_name": "dent"},
            {"meter": 2.5, "class_name": "scratch"},
        ]
        df = bin_defects_by_meter(positioned, bin_size_m=1.0)
        assert len(df) == 2
        assert df.iloc[0]["count"] == 2  # bin 0: 0.3, 0.7
        assert df.iloc[1]["count"] == 1  # bin 1: 2.5

    def test_empty(self):
        df = bin_defects_by_meter([{"meter": None, "class_name": "x"}])
        assert df.empty

    def test_single(self):
        positioned = [{"meter": 5.0, "class_name": "scratch"}]
        df = bin_defects_by_meter(positioned)
        assert len(df) == 1
        assert df["count"].values[0] == 1


class TestDetectContinuousDefectSegments:
    def test_single_segment(self):
        positioned = [
            {"meter": 1.0, "class_name": "scratch", "image_name": "a.jpg"},
            {"meter": 1.3, "class_name": "scratch", "image_name": "b.jpg"},
            {"meter": 1.6, "class_name": "dent", "image_name": "c.jpg"},
        ]
        segments = detect_continuous_defect_segments(positioned, max_gap_m=0.5)
        assert len(segments) == 1
        assert segments[0]["defect_count"] == 3

    def test_two_segments(self):
        positioned = [
            {"meter": 1.0, "class_name": "scratch", "image_name": "a.jpg"},
            {"meter": 5.0, "class_name": "dent", "image_name": "b.jpg"},
        ]
        segments = detect_continuous_defect_segments(positioned, max_gap_m=0.5)
        assert len(segments) == 2

    def test_empty(self):
        assert detect_continuous_defect_segments([]) == []
        assert detect_continuous_defect_segments([{"meter": None}]) == []


class TestSummarizePositionStatistics:
    def test_basic(self):
        positioned = [
            {"meter": 1.0, "class_name": "scratch"},
            {"meter": 2.0, "class_name": "scratch"},
            {"meter": 3.0, "class_name": "dent"},
        ]
        stats = summarize_position_statistics(positioned)
        assert stats["total_detections"] == 3
        assert stats["positioned_count"] == 3
        assert stats["meter_range"] == (1.0, 3.0)
        assert stats["mean_meter"] == 2.0

    def test_with_unpositioned(self):
        positioned = [
            {"meter": 1.0, "class_name": "x"},
            {"meter": None, "class_name": "y"},
        ]
        stats = summarize_position_statistics(positioned)
        assert stats["positioned_count"] == 1
        assert stats["unpositioned_count"] == 1
