"""Tests for core/schema.py."""

from __future__ import annotations

import pytest

from core.schema import DetectionBox, ImagePrediction, ImageGroundTruth


class TestDetectionBox:
    def test_valid_box(self):
        box = DetectionBox(
            image_name="img_001.jpg",
            class_id=0,
            class_name="scratch",
            confidence=0.9,
            bbox=[10, 20, 100, 200],
        )
        assert box.area() == (90 * 180)
        d = box.to_dict()
        assert d["image_name"] == "img_001.jpg"
        assert d["class_id"] == 0
        assert d["confidence"] == 0.9

    def test_invalid_bbox_length(self):
        with pytest.raises(ValueError, match="must have 4 numbers"):
            DetectionBox(
                image_name="x.jpg",
                class_id=0,
                class_name="x",
                confidence=0.5,
                bbox=[1, 2, 3],
            )

    def test_invalid_bbox_order(self):
        with pytest.raises(ValueError, match="x2"):
            DetectionBox(
                image_name="x.jpg",
                class_id=0,
                class_name="x",
                confidence=0.5,
                bbox=[100, 0, 10, 10],
            )
        with pytest.raises(ValueError, match="y2"):
            DetectionBox(
                image_name="x.jpg",
                class_id=0,
                class_name="x",
                confidence=0.5,
                bbox=[0, 100, 10, 10],
            )

    def test_invalid_confidence(self):
        with pytest.raises(ValueError, match="confidence"):
            DetectionBox(
                image_name="x.jpg",
                class_id=0,
                class_name="x",
                confidence=1.5,
                bbox=[0, 0, 10, 10],
            )
        with pytest.raises(ValueError, match="confidence"):
            DetectionBox(
                image_name="x.jpg",
                class_id=0,
                class_name="x",
                confidence=-0.1,
                bbox=[0, 0, 10, 10],
            )

    def test_area_zero(self):
        box = DetectionBox("x.jpg", 0, "x", 0.5, [5, 5, 5, 5])
        assert box.area() == 0.0

    def test_area_positive(self):
        box = DetectionBox("x.jpg", 0, "x", 0.5, [0, 0, 10, 20])
        assert box.area() == 200.0


class TestImagePrediction:
    def test_empty(self):
        pred = ImagePrediction(image_name="img.jpg")
        assert pred.detections == []
        assert pred.to_dataframe_rows() == []

    def test_with_detections(self):
        box = DetectionBox("img.jpg", 0, "scratch", 0.9, [10, 20, 100, 200])
        pred = ImagePrediction(image_name="img.jpg", detections=[box])
        rows = pred.to_dataframe_rows()
        assert len(rows) == 1
        assert rows[0]["class_name"] == "scratch"


class TestImageGroundTruth:
    def test_empty(self):
        gt = ImageGroundTruth(image_name="img.jpg")
        assert gt.boxes == []

    def test_with_boxes(self):
        box = DetectionBox("img.jpg", 0, "scratch", 1.0, [0, 0, 10, 10])
        gt = ImageGroundTruth(image_name="img.jpg", boxes=[box])
        assert len(gt.boxes) == 1
