"""Tests for fusion rule engine."""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from src.fusion.decision_types import (
    FinalDecision, FusionStrategy, FusionDecision,
    UnifiedPrediction, BBoxPrediction, AnomalyResult,
)
from src.fusion.rule_engine import RuleEngine


FUSION_CONFIG = {
    "yolo": {
        "conf_threshold": 0.6,
        "major_defect_classes": ["NG_scratch", "NG_pit", "NG_dent", "NG_stain"],
        "direct_ng_conf_threshold": 0.75,
    },
    "anomaly": {
        "patchcore_score_threshold": 0.65,
        "efficientad_score_threshold": 0.65,
        "fastflow_score_threshold": 0.65,
        "unknown_ng_score_threshold": 0.85,
    },
    "geometry": {
        "min_defect_area_px": 8,
        "acceptable_micro_area_px": 30,
        "ng_area_px": 200,
        "acceptable_scratch_length_mm": 0.5,
        "ng_scratch_length_mm": 2.0,
        "long_scratch_aspect_ratio": 5.0,
    },
    "density": {
        "enable_density_rule": True,
        "max_micro_defect_count_per_meter": 50,
        "max_micro_defect_area_per_meter": 500,
    },
    "fusion": {
        "strategy": "rule_based",
        "yolo_priority": True,
        "anomaly_for_unknown": True,
        "require_double_confirm_for_ng": False,
    },
}


@pytest.fixture
def engine():
    return RuleEngine(FUSION_CONFIG)


def make_yolo_result(
    predictions: list[dict] | None = None,
) -> UnifiedPrediction:
    preds = []
    if predictions:
        for p in predictions:
            preds.append(BBoxPrediction(
                type="bbox",
                class_name=p.get("class_name", ""),
                confidence=p.get("confidence", 0.0),
                bbox_xyxy=p.get("bbox_xyxy", [0, 0, 0, 0]),
            ))
    return UnifiedPrediction(
        image_path="/test/img.jpg",
        model_name="yolo",
        predictions=preds,
    )


def make_anomaly_result(score: float) -> UnifiedPrediction:
    return UnifiedPrediction(
        image_path="/test/img.jpg",
        model_name="patchcore",
        anomaly=AnomalyResult(image_score=score, threshold=0.65),
    )


class TestYoloOnly:
    def test_no_detections_returns_ok(self, engine):
        yolo = make_yolo_result([])
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.YOLO_ONLY,
            yolo_result=yolo,
        )
        assert result.final_decision == FinalDecision.OK

    def test_major_defect_high_conf_returns_ng(self, engine):
        yolo = make_yolo_result([
            {"class_name": "NG_scratch", "confidence": 0.85},
        ])
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.YOLO_ONLY,
            yolo_result=yolo,
        )
        assert result.final_decision == FinalDecision.NG
        assert "NG_scratch" in result.reason

    def test_low_conf_returns_suspect(self, engine):
        yolo = make_yolo_result([
            {"class_name": "NG_scratch", "confidence": 0.65},
        ])
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.YOLO_ONLY,
            yolo_result=yolo,
        )
        assert result.final_decision == FinalDecision.SUSPECT


class TestAnomalyOnly:
    def test_low_score_returns_ok(self, engine):
        anomaly = make_anomaly_result(0.3)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.ANOMALY_ONLY,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.OK

    def test_high_score_returns_suspect(self, engine):
        anomaly = make_anomaly_result(0.9)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.ANOMALY_ONLY,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.SUSPECT


class TestDoubleConfirm:
    def test_both_agree_returns_ng(self, engine):
        yolo = make_yolo_result([
            {"class_name": "NG_pit", "confidence": 0.8},
        ])
        anomaly = make_anomaly_result(0.85)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.DOUBLE_CONFIRM,
            yolo_result=yolo,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.NG

    def test_only_one_returns_suspect(self, engine):
        yolo = make_yolo_result([
            {"class_name": "NG_pit", "confidence": 0.8},
        ])
        anomaly = make_anomaly_result(0.3)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.DOUBLE_CONFIRM,
            yolo_result=yolo,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.SUSPECT

    def test_both_clean_returns_ok(self, engine):
        yolo = make_yolo_result([])
        anomaly = make_anomaly_result(0.3)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.DOUBLE_CONFIRM,
            yolo_result=yolo,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.OK


class TestRuleBased:
    def test_major_defect_ng(self, engine):
        yolo = make_yolo_result([
            {"class_name": "NG_dent", "confidence": 0.9},
        ])
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.RULE_BASED,
            yolo_result=yolo,
        )
        assert result.final_decision == FinalDecision.NG

    def test_clean_image_ok(self, engine):
        yolo = make_yolo_result([])
        anomaly = make_anomaly_result(0.1)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.RULE_BASED,
            yolo_result=yolo,
            patchcore_result=anomaly,
        )
        assert result.final_decision == FinalDecision.OK

    def test_unknown_anomaly_suspect(self, engine):
        yolo = make_yolo_result([])
        anomaly = make_anomaly_result(0.75)
        result = engine.decide(
            "/test/img.jpg",
            strategy=FusionStrategy.RULE_BASED,
            yolo_result=yolo,
            patchcore_result=anomaly,
        )
        # Should be SUSPECT for elevated anomaly without YOLO
        assert result.final_decision == FinalDecision.SUSPECT
