"""Tests for core/defect_rules.py."""

from __future__ import annotations

from tests import make_detection_box

from core.defect_rules import (
    DefectRuleConfig,
    estimate_defect_size_mm,
    classify_defect_level,
    apply_defect_rules,
    summarize_defect_levels,
    LEVEL_A,
    LEVEL_B,
    LEVEL_C,
    LEVEL_UNKNOWN,
    LEVEL_LOW_CONF,
)


class TestEstimateDefectSizeMm:
    def test_basic(self):
        box = make_detection_box(bbox=[0, 0, 100, 200])
        size = estimate_defect_size_mm(box, pixel_size_mm=0.01)
        expected = ((100**2 + 200**2) ** 0.5) * 0.01
        assert abs(size - expected) < 0.001

    def test_none_pixel_size(self):
        assert estimate_defect_size_mm(make_detection_box(), None) is None

    def test_zero_pixel_size(self):
        assert estimate_defect_size_mm(make_detection_box(), 0.0) is None

    def test_square(self):
        box = make_detection_box(bbox=[0, 0, 50, 50])
        size = estimate_defect_size_mm(box, pixel_size_mm=0.02)
        expected = (50**2 + 50**2) ** 0.5 * 0.02
        assert size > 1.4


class TestClassifyDefectLevel:
    def test_unknown_class(self):
        config = DefectRuleConfig(unknown_class_names=["anomaly"])
        box = make_detection_box(cname="anomaly", conf=0.9)
        assert classify_defect_level(box, config) == LEVEL_UNKNOWN

    def test_low_confidence(self):
        config = DefectRuleConfig(min_alarm_confidence=0.5)
        box = make_detection_box(conf=0.3)
        assert classify_defect_level(box, config) == LEVEL_LOW_CONF

    def test_severe_class(self):
        config = DefectRuleConfig(severe_class_names=["scratch_deep"])
        box = make_detection_box(cname="scratch_deep", conf=0.9)
        assert classify_defect_level(box, config) == LEVEL_A

    def test_acceptable_small(self):
        config = DefectRuleConfig(
            acceptable_class_names=["scratch_light"],
            min_alarm_size_mm=0.07,
        )
        box = make_detection_box(cname="scratch_light", conf=0.9, bbox=[0, 0, 3, 3])
        level = classify_defect_level(box, config, pixel_size_mm=0.01)
        assert level == LEVEL_C  # size < min_alarm_size_mm

    def test_acceptable_large(self):
        config = DefectRuleConfig(
            acceptable_class_names=["scratch_light"],
            severe_size_mm=0.15,
        )
        box = make_detection_box(cname="scratch_light", conf=0.9, bbox=[0, 0, 200, 300])
        level = classify_defect_level(box, config, pixel_size_mm=0.01)
        assert level == LEVEL_A  # size >= severe_size_mm

    def test_default_classify(self):
        config = DefectRuleConfig()
        box = make_detection_box(cname="dent", conf=0.8)
        level = classify_defect_level(box, config)
        assert level == LEVEL_B


class TestApplyDefectRules:
    def test_basic(self):
        config = DefectRuleConfig(
            severe_class_names=["scratch_deep"],
            acceptable_class_names=["scratch_light"],
        )
        preds = {
            "img1.jpg": [
                make_detection_box(cname="scratch_deep", conf=0.9),
                make_detection_box(cname="scratch_light", conf=0.8, bbox=[0, 0, 3, 3]),
                make_detection_box(cname="anomaly", conf=0.7),
            ],
        }
        results = apply_defect_rules(preds, config, pixel_size_mm=0.01)
        img_results = results["img1.jpg"]
        assert len(img_results) == 3
        levels = [r["level"] for r in img_results]
        assert LEVEL_A in levels
        assert LEVEL_C in levels
        assert LEVEL_UNKNOWN in levels

    def test_empty(self):
        results = apply_defect_rules({}, DefectRuleConfig())
        assert results == {}


class TestSummarizeDefectLevels:
    def test_basic(self):
        config = DefectRuleConfig(severe_class_names=["scratch_deep"])
        preds = {
            "img.jpg": [
                make_detection_box(cname="scratch_deep", conf=0.9),
                make_detection_box(conf=0.1),  # low confidence
            ],
        }
        results = apply_defect_rules(preds, config)
        summary = summarize_defect_levels(results)
        assert summary["total"] == 2
        assert summary["by_level"][LEVEL_A] >= 1
        assert summary["by_level"][LEVEL_LOW_CONF] >= 1

    def test_empty(self):
        summary = summarize_defect_levels({})
        assert summary["total"] == 0
