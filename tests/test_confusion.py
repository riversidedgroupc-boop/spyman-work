"""Tests for core/confusion.py."""

from __future__ import annotations

import pytest

from tests import make_detection_box

from core.confusion import (
    build_detection_confusion_matrix,
    MISSED_LABEL,
    BACKGROUND_LABEL,
)


class TestDetectionConfusionMatrix:
    def test_correct_prediction(self):
        gt = {"img.jpg": [make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100])]}
        pred = {"img.jpg": [make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100], conf=0.9)]}
        df = build_detection_confusion_matrix(gt, pred, {0: "scratch"})
        assert df.loc["scratch", "scratch"] == 1
        assert df.loc["scratch", MISSED_LABEL] == 0

    def test_misclassification(self):
        gt = {"img.jpg": [make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100])]}
        pred = {"img.jpg": [make_detection_box(cls_id=1, cls_name="dent", bbox=[10, 10, 90, 90], conf=0.9)]}
        df = build_detection_confusion_matrix(gt, pred, {0: "scratch", 1: "dent"})
        # Misclassified: GT scratch, pred dent
        assert df.loc["scratch", "dent"] == 1

    def test_missed_detection(self):
        gt = {"img.jpg": [make_detection_box(cls_id=0, cls_name="scratch", bbox=[0, 0, 100, 100])]}
        pred = {"img.jpg": []}
        df = build_detection_confusion_matrix(gt, pred, {0: "scratch"})
        assert df.loc["scratch", MISSED_LABEL] == 1

    def test_false_positive(self):
        gt = {"img.jpg": []}
        pred = {"img.jpg": [make_detection_box(cls_id=1, cls_name="dent", bbox=[10, 10, 90, 90], conf=0.9)]}
        df = build_detection_confusion_matrix(gt, pred, {1: "dent"})
        assert df.loc[BACKGROUND_LABEL, "dent"] == 1

    def test_empty(self):
        df = build_detection_confusion_matrix({}, {}, {0: "scratch"})
        assert df.shape[0] > 0
        assert df.shape[1] > 0
        assert df.values.sum() == 0
