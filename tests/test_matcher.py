"""Tests for core/matcher.py."""

from __future__ import annotations

import pytest

from core.schema import DetectionBox
from core.matcher import compute_iou, match_detections


def _box(cls_id=0, cls_name="defect", conf=0.9, bbox=None):
    if bbox is None:
        bbox = [0, 0, 100, 100]
    return DetectionBox("img.jpg", cls_id, cls_name, conf, bbox)


class TestComputeIOU:
    def test_perfect_overlap(self):
        assert compute_iou([0, 0, 100, 100], [0, 0, 100, 100]) == 1.0

    def test_no_overlap(self):
        assert compute_iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0

    def test_partial_overlap(self):
        iou = compute_iou([0, 0, 100, 100], [50, 50, 150, 150])
        expected = 2500 / 17500  # inter=2500, union=10000+10000-2500=17500
        assert abs(iou - expected) < 1e-6

    def test_one_contains_another(self):
        iou = compute_iou([0, 0, 100, 100], [20, 20, 60, 60])
        # inter = 40*40=1600, union=10000
        assert abs(iou - 0.16) < 1e-6

    def test_zero_box(self):
        assert compute_iou([0, 0, 0, 0], [0, 0, 0, 0]) == 0.0


class TestMatchDetections:
    def test_one_match(self):
        gt = [_box(bbox=[0, 0, 100, 100])]
        pred = [_box(bbox=[10, 10, 90, 90])]
        result = match_detections(gt, pred, iou_threshold=0.5)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["iou"] > 0.5
        assert result["matches"][0]["correct_class"] is True
        assert len(result["false_positives"]) == 0
        assert len(result["false_negatives"]) == 0

    def test_duplicate_predictions(self):
        gt = [_box(bbox=[0, 0, 100, 100])]
        pred = [
            _box(bbox=[10, 10, 90, 90], conf=0.9),
            _box(bbox=[20, 20, 80, 80], conf=0.8),
        ]
        result = match_detections(gt, pred, iou_threshold=0.5)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["pred"].confidence == 0.9
        assert len(result["false_positives"]) == 1
        assert result["false_positives"][0].confidence == 0.8

    def test_class_mismatch_class_aware(self):
        gt = [_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100])]
        pred = [_box(cls_id=1, cls_name="dent", bbox=[10, 10, 90, 90])]
        result = match_detections(gt, pred, iou_threshold=0.5, class_aware=True)
        assert len(result["matches"]) == 0
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 1

    def test_class_mismatch_not_class_aware(self):
        gt = [_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100])]
        pred = [_box(cls_id=1, cls_name="dent", bbox=[10, 10, 90, 90])]
        result = match_detections(gt, pred, iou_threshold=0.5, class_aware=False)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["correct_class"] is False

    def test_low_iou_no_match(self):
        gt = [_box(bbox=[0, 0, 10, 10])]
        pred = [_box(bbox=[90, 90, 100, 100])]
        result = match_detections(gt, pred, iou_threshold=0.5)
        assert len(result["matches"]) == 0
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 1

    def test_empty_inputs(self):
        result = match_detections([], [])
        assert result["matches"] == []
        assert result["false_positives"] == []
        assert result["false_negatives"] == []

    def test_prediction_matches_best_gt(self):
        gt = [
            _box(bbox=[0, 0, 100, 100], cls_id=0),
            _box(bbox=[50, 50, 150, 150], cls_id=0),
        ]
        pred = [_box(bbox=[40, 40, 110, 110], cls_id=0)]
        result = match_detections(gt, pred, iou_threshold=0.1)
        assert len(result["matches"]) == 1
        # Should match the first GT (higher IoU)
        assert result["matches"][0]["gt"].bbox == [0, 0, 100, 100]
        assert len(result["false_negatives"]) == 1
