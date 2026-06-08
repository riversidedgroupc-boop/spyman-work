"""Tests for core/metrics.py."""

from __future__ import annotations

import pytest

from tests import make_detection_box

from core.metrics import build_pr_curve, compute_ap, compute_map


class TestBuildPRCurve:
    def test_one_perfect_prediction(self):
        gt_by_img = {"img.jpg": [make_detection_box(bbox=[0, 0, 100, 100])]}
        pred_by_img = {"img.jpg": [make_detection_box(bbox=[0, 0, 100, 100], conf=0.9)]}
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0, iou_threshold=0.5)
        assert result["ap"] == pytest.approx(1.0)

    def test_no_predictions(self):
        gt_by_img = {"img.jpg": [make_detection_box()]}
        pred_by_img: dict[str, list] = {}
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0)
        assert result["ap"] == 0.0

    def test_no_ground_truths(self):
        gt_by_img: dict[str, list] = {}
        pred_by_img = {"img.jpg": [make_detection_box()]}
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0)
        assert result["ap"] == 0.0

    def test_all_wrong(self):
        gt_by_img = {"img.jpg": [make_detection_box(bbox=[0, 0, 10, 10])]}
        pred_by_img = {"img.jpg": [make_detection_box(bbox=[90, 90, 100, 100], conf=0.9)]}
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0)
        assert result["ap"] == 0.0

    def test_mixed_tp_fp(self):
        gt_by_img = {"img.jpg": [make_detection_box(bbox=[0, 0, 100, 100])]}
        pred_by_img = {
            "img.jpg": [
                make_detection_box(bbox=[0, 0, 100, 100], conf=0.9),  # TP
                make_detection_box(bbox=[200, 200, 300, 300], conf=0.8),  # FP
            ]
        }
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0)
        assert len(result["precision"]) == 2
        assert len(result["recall"]) == 2
        assert result["ap"] > 0.0
        assert result["ap"] < 1.0

    def test_pr_curve_non_increasing_precision(self):
        gt_by_img = {"img.jpg": [make_detection_box(bbox=[0, 0, 100, 100])]}
        pred_by_img = {
            "img.jpg": [
                make_detection_box(bbox=[0, 0, 100, 100], conf=0.9),
                make_detection_box(bbox=[200, 200, 300, 300], conf=0.8),
            ]
        }
        result = build_pr_curve(gt_by_img, pred_by_img, class_id=0)
        # Interpolated precision should be non-increasing
        for i in range(len(result["precision"]) - 1):
            assert result["precision"][i] >= result["precision"][i + 1] - 1e-10


class TestComputeAP:
    def test_perfect(self):
        ap = compute_ap([0.0, 0.5, 1.0], [1.0, 1.0, 1.0])
        assert ap == 1.0

    def test_zero(self):
        ap = compute_ap([], [])
        assert ap == 0.0


class TestComputeMAP:
    def test_single_class_perfect(self):
        gt_by_img = {"img.jpg": [make_detection_box(cls_id=0, bbox=[0, 0, 100, 100])]}
        pred_by_img = {"img.jpg": [make_detection_box(cls_id=0, bbox=[0, 0, 100, 100], conf=0.9)]}
        result = compute_map(gt_by_img, pred_by_img, class_ids=[0])
        assert result["map_50"] == pytest.approx(1.0)

    def test_multiple_classes(self):
        gt_by_img = {
            "img.jpg": [
                make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100]),
                make_detection_box(cls_id=1, cls_name="dent", bbox=[50, 50, 150, 150]),
            ]
        }
        pred_by_img = {
            "img.jpg": [
                make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100], conf=0.9),
                make_detection_box(cls_id=1, cls_name="dent", bbox=[50, 50, 150, 150], conf=0.8),
            ]
        }
        result = compute_map(gt_by_img, pred_by_img, class_ids=[0, 1])
        assert result["map_50"] == pytest.approx(1.0)
        assert 0 in result["per_class"]
        assert 1 in result["per_class"]

    def test_multi_threshold(self):
        thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
        gt_by_img = {"img.jpg": [make_detection_box(cls_id=0, bbox=[0, 0, 100, 100])]}
        pred_by_img = {"img.jpg": [make_detection_box(cls_id=0, bbox=[0, 0, 100, 100], conf=0.9)]}
        result = compute_map(gt_by_img, pred_by_img, class_ids=[0], iou_thresholds=thresholds)
        assert result["map_50"] == pytest.approx(1.0)
        assert len(result["thresholds"]) == len(thresholds)

    def test_empty(self):
        result = compute_map({}, {}, class_ids=[0])
        assert result["map"] == 0.0
        assert result["map_50"] == 0.0
