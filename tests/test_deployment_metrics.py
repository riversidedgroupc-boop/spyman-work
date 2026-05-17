"""Tests for core/deployment_metrics.py."""

from __future__ import annotations

from core.deployment_metrics import (
    compute_detection_counts,
    compute_miss_rate,
    compute_false_alarm_rate,
    compute_false_alarms_per_meter,
    compute_review_load,
    compute_average_inference_time,
    compute_deployment_summary,
)
from core.schema import DetectionBox


def _box(img="img_001.jpg", cid=0, cname="defect", conf=0.9, bbox=None):
    if bbox is None:
        bbox = [0, 0, 100, 100]
    return DetectionBox(img, cid, cname, conf, bbox)


class TestComputeDetectionCounts:
    def test_empty(self):
        counts = compute_detection_counts({}, {})
        assert counts["num_images"] == 0
        assert counts["num_gt"] == 0
        assert counts["num_predictions"] == 0
        assert counts["true_positives"] == 0
        assert counts["false_positives"] == 0
        assert counts["false_negatives"] == 0

    def test_perfect_match(self):
        gt = {"img.jpg": [_box()]}
        pred = {"img.jpg": [_box(bbox=[5, 5, 95, 95])]}
        counts = compute_detection_counts(gt, pred)
        assert counts["true_positives"] == 1
        assert counts["false_positives"] == 0
        assert counts["false_negatives"] == 0

    def test_no_match(self):
        gt = {"img.jpg": [_box(bbox=[0, 0, 10, 10])]}
        pred = {"img.jpg": [_box(bbox=[90, 90, 100, 100])]}
        counts = compute_detection_counts(gt, pred)
        assert counts["true_positives"] == 0
        assert counts["false_positives"] == 1
        assert counts["false_negatives"] == 1

    def test_multi_image(self):
        gt = {
            "img1.jpg": [_box(img="img1.jpg"), _box(img="img1.jpg", bbox=[50, 50, 150, 150])],
            "img2.jpg": [_box(img="img2.jpg")],
        }
        pred = {
            "img1.jpg": [_box(img="img1.jpg", bbox=[10, 10, 90, 90])],
            "img2.jpg": [],
        }
        counts = compute_detection_counts(gt, pred)
        assert counts["num_images"] == 2
        assert counts["num_gt"] == 3
        assert counts["true_positives"] >= 1


class TestComputeMissRate:
    def test_no_misses(self):
        gt = {"img.jpg": [_box()]}
        pred = {"img.jpg": [_box(bbox=[5, 5, 95, 95])]}
        assert compute_miss_rate(gt, pred) == 0.0

    def test_all_missed(self):
        gt = {"img.jpg": [_box()]}
        pred = {"img.jpg": []}
        assert compute_miss_rate(gt, pred) == 1.0

    def test_no_gt(self):
        mr = compute_miss_rate({}, {"img.jpg": [_box()]})
        assert mr == 0.0


class TestComputeFalseAlarmRate:
    def test_no_false_alarms(self):
        gt = {"img.jpg": [_box()]}
        pred = {"img.jpg": [_box(bbox=[5, 5, 95, 95])]}
        assert compute_false_alarm_rate(gt, pred) == 0.0

    def test_all_false_alarms(self):
        gt = {"img.jpg": []}
        pred = {"img.jpg": [_box()]}
        assert compute_false_alarm_rate(gt, pred) == 1.0


class TestComputeFalseAlarmsPerMeter:
    def test_no_meter_data(self):
        result = compute_false_alarms_per_meter({}, {})
        assert result is None

    def test_with_meter_data(self):
        gt = {"img.jpg": []}
        pred = {"img.jpg": [_box()]}
        result = compute_false_alarms_per_meter(
            gt, pred, image_meter_length_map={"img.jpg": 10.0}
        )
        assert result == 0.1  # 1 FP / 10 meters

    def test_empty_meter_data(self):
        result = compute_false_alarms_per_meter({}, {}, image_meter_length_map={})
        assert result is None


class TestComputeReviewLoad:
    def test_no_review_needed(self):
        rl = compute_review_load({"img.jpg": [_box()]}, {"img.jpg": []})
        assert rl["review_load_images"] == 0
        assert rl["review_load_ratio"] == 0.0

    def test_all_review_needed(self):
        rl = compute_review_load({"img.jpg": []}, {"img.jpg": [_box()]})
        assert rl["review_load_images"] == 1
        assert rl["review_load_ratio"] == 1.0


class TestComputeAverageInferenceTime:
    def test_empty(self):
        result = compute_average_inference_time()
        assert result["avg_inference_ms"] == 0.0
        assert result["max_inference_ms"] == 0.0

    def test_list(self):
        result = compute_average_inference_time(timing_list=[10.0, 20.0, 30.0])
        assert result["avg_inference_ms"] == 20.0
        assert result["max_inference_ms"] == 30.0


class TestComputeDeploymentSummary:
    def test_full_summary(self):
        gt = {"img.jpg": [_box()]}
        pred = {"img.jpg": [_box(bbox=[5, 5, 95, 95])]}
        summary = compute_deployment_summary(
            gt, pred,
            image_meter_length_map={"img.jpg": 2.0},
            timing_list=[15.0, 25.0],
        )
        assert summary["miss_rate"] == 0.0
        assert summary["false_alarm_rate"] == 0.0
        assert summary["false_alarms_per_meter"] == 0.0
        assert summary["avg_inference_ms"] == 20.0
        assert summary["max_inference_ms"] == 25.0

    def test_wrong_class_overlap_is_not_true_positive_by_default(self):
        gt = {"img.jpg": [_box(cid=3, cname="NG_scratch")]}
        pred = {"img.jpg": [_box(cid=5, cname="NG_dent")]}
        counts = compute_detection_counts(gt, pred)
        assert counts["true_positives"] == 0
        assert counts["false_positives"] == 1
        assert counts["false_negatives"] == 1

    def test_wrong_class_overlap_can_be_class_agnostic_when_requested(self):
        gt = {"img.jpg": [_box(cid=3, cname="NG_scratch")]}
        pred = {"img.jpg": [_box(cid=5, cname="NG_dent")]}
        counts = compute_detection_counts(gt, pred, class_aware=False)
        assert counts["true_positives"] == 1
        assert counts["false_positives"] == 0
        assert counts["false_negatives"] == 0
