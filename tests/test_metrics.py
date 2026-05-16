"""Tests for industrial metrics."""

from __future__ import annotations

from src.metrics.industrial_metrics import (
    compute_industrial_metrics,
    compute_strategy_comparison,
    IndustrialMetrics,
)
from src.metrics.detection_metrics import accuracy, precision_recall_f1


class TestIndustrialMetrics:
    def test_all_correct_ok(self):
        true_labels = ["OK_clean"] * 10
        pred_decisions = ["OK"] * 10

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.ok_false_positive_rate == 0.0
        assert metrics.total_images == 10

    def test_all_correct_ng(self):
        true_labels = ["NG_scratch"] * 5
        pred_decisions = ["NG"] * 5

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.ng_miss_rate == 0.0

    def test_ok_false_positive(self):
        true_labels = ["OK_clean"] * 10
        pred_decisions = ["OK"] * 5 + ["NG"] * 5

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.ok_false_positive_rate == 0.5

    def test_ng_miss(self):
        true_labels = ["NG_scratch"] * 10
        pred_decisions = ["NG"] * 5 + ["OK"] * 5

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.ng_miss_rate == 0.5

    def test_unknown_defect_recall(self):
        true_labels = ["NG_unknown"] * 10
        pred_decisions = ["SUSPECT"] * 7 + ["OK"] * 3

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.unknown_defect_recall == 0.7

    def test_borderline_detection(self):
        true_labels = ["Borderline"] * 10
        pred_decisions = ["SUSPECT"] * 6 + ["NG"] * 2 + ["OK"] * 2

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.borderline_detection_rate == 0.8

    def test_acceptable_micro_fp(self):
        true_labels = ["OK_micro_defect"] * 10
        pred_decisions = ["ACCEPTABLE_MICRO_DEFECT"] * 7 + ["NG"] * 3

        metrics = compute_industrial_metrics(true_labels, pred_decisions)

        assert metrics.acceptable_micro_fp_rate == 0.3

    def test_empty_input(self):
        metrics = compute_industrial_metrics([], [])
        assert metrics.total_images == 0
        assert metrics.ok_false_positive_rate == 0.0


class TestDetectionMetrics:
    def test_accuracy(self):
        assert accuracy(["a", "b", "a"], ["a", "b", "a"]) == 1.0
        assert accuracy(["a", "a"], ["a", "b"]) == 0.5
        assert accuracy([], []) == 0.0

    def test_precision_recall_f1(self):
        result = precision_recall_f1(
            ["positive", "negative", "positive", "positive"],
            ["positive", "positive", "negative", "positive"],
            "positive",
        )
        assert result["tp"] == 2
        assert result["fp"] == 1
        assert result["fn"] == 1
        assert result["precision"] == 2 / 3
        assert result["recall"] == 2 / 3


class TestStrategyComparison:
    def test_compute_comparison(self):
        results = {
            "YOLO Only": (
                ["OK_clean", "NG_scratch", "OK_micro_defect"],
                ["OK", "NG", "ACCEPTABLE_MICRO_DEFECT"],
                [10.0, 12.0, 11.0],
            ),
            "Rule Based": (
                ["OK_clean", "NG_scratch", "OK_micro_defect"],
                ["OK", "NG", "OK"],
                [15.0, 18.0, 16.0],
            ),
        }

        comparison = compute_strategy_comparison(results)
        assert len(comparison) == 2
        assert comparison[0]["strategy"] in ("YOLO Only", "Rule Based")
        for c in comparison:
            assert "ok_fpr" in c
            assert "ng_miss_rate" in c
            assert "unknown_recall" in c
