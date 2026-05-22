"""Tests for core.hybrid_strategy — Fusion decision matrix (6 spec test cases + strategy modes)."""
from __future__ import annotations

import pytest

from core.hybrid_strategy import HybridFusionEngine, FusionConfig
from src.fusion.decision_types import (
    AnomalyResult,
    BBoxPrediction,
    FinalDecision,
    FusionStrategy,
    ModelSource,
    ReasonCode,
)


# ── Helpers ────────────────────────────────────────────────────────

def _yolo_high(class_name: str = "scratch") -> list[BBoxPrediction]:
    return [
        BBoxPrediction(class_name=class_name, confidence=0.95),
    ]


def _yolo_low(class_name: str = "scratch") -> list[BBoxPrediction]:
    return [
        BBoxPrediction(class_name=class_name, confidence=0.35),
    ]


def _yolo_none() -> list[BBoxPrediction]:
    return []


def _anomaly_high() -> AnomalyResult:
    return AnomalyResult(image_score=0.92)


def _anomaly_medium() -> AnomalyResult:
    return AnomalyResult(image_score=0.70)


def _anomaly_normal() -> AnomalyResult:
    return AnomalyResult(image_score=0.10)


def _anomaly_none() -> AnomalyResult | None:
    return None


# ── Spec Section 11 Test Cases (production_retest) ─────────────────

@pytest.fixture
def engine():
    return HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))


class TestProductionRetestMatrix:
    """6 fusion test cases from Section 11 of the spec."""

    def test_yolo_high_anomaly_normal_ng(self, engine):
        """YOLO high confidence + anomaly normal -> NG known defect."""
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.final_decision == FinalDecision.NG
        assert decision.reason == ReasonCode.YOLO_KNOWN_DEFECT.value

    def test_yolo_none_anomaly_normal_ok(self, engine):
        """YOLO none + anomaly normal -> OK."""
        decision = engine.fuse(_yolo_none(), _anomaly_normal())
        assert decision.final_decision == FinalDecision.OK
        assert decision.reason == ReasonCode.CLEAN_BY_BOTH.value

    def test_yolo_none_anomaly_high_unknown(self, engine):
        """YOLO none + anomaly high -> Unknown / Needs Review."""
        decision = engine.fuse(_yolo_none(), _anomaly_high())
        assert decision.final_decision == FinalDecision.UNKNOWN
        assert decision.reason == ReasonCode.ANOMALY_UNKNOWN.value

    def test_yolo_low_anomaly_high_suspect(self, engine):
        """YOLO low confidence + anomaly high -> Suspect."""
        decision = engine.fuse(_yolo_low(), _anomaly_high())
        assert decision.final_decision == FinalDecision.SUSPECT
        assert decision.reason == ReasonCode.YOLO_UNCERTAIN_ANOMALY_CONFIRMED.value

    def test_yolo_high_anomaly_high_ng(self, engine):
        """YOLO high confidence + anomaly high -> NG (anomaly supports)."""
        decision = engine.fuse(_yolo_high(), _anomaly_high())
        assert decision.final_decision == FinalDecision.NG
        assert decision.reason == ReasonCode.YOLO_KNOWN_DEFECT.value

    def test_yolo_low_anomaly_normal_needs_review(self, engine):
        """YOLO low confidence + anomaly normal -> possible false positive / review."""
        decision = engine.fuse(_yolo_low(), _anomaly_normal())
        assert decision.final_decision == FinalDecision.NEEDS_REVIEW
        assert decision.reason == ReasonCode.POSSIBLE_FALSE_POSITIVE.value


# ── Strategy mode dispatch ─────────────────────────────────────────

class TestStrategyModes:
    """Each strategy mode produces the expected FusionStrategy in result."""

    def test_exploration_first_mode(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.EXPLORATION_FIRST))
        decision = engine.fuse(None, _anomaly_normal())
        assert decision.strategy == FusionStrategy.EXPLORATION_FIRST

    def test_exploration_first_high_anomaly_unknown(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.EXPLORATION_FIRST))
        decision = engine.fuse(None, _anomaly_high())
        assert decision.final_decision == FinalDecision.UNKNOWN

    def test_exploration_first_medium_anomaly_needs_review(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.EXPLORATION_FIRST))
        decision = engine.fuse(None, _anomaly_medium())
        assert decision.final_decision == FinalDecision.NEEDS_REVIEW

    def test_few_shot_mode(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.FEW_SHOT))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.strategy == FusionStrategy.FEW_SHOT
        assert decision.final_decision == FinalDecision.NG

    def test_few_shot_no_yolo_high_anomaly_unknown(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.FEW_SHOT))
        decision = engine.fuse(_yolo_none(), _anomaly_high())
        assert decision.final_decision == FinalDecision.UNKNOWN

    def test_production_retest_mode(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.strategy == FusionStrategy.PRODUCTION_RETEST

    def test_stable_production_mode(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.STABLE_PRODUCTION))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.strategy == FusionStrategy.STABLE_PRODUCTION
        assert decision.final_decision == FinalDecision.NG

    def test_stable_production_no_yolo_anomaly_high_unknown(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.STABLE_PRODUCTION))
        decision = engine.fuse(_yolo_none(), _anomaly_high())
        assert decision.final_decision == FinalDecision.UNKNOWN

    def test_stable_production_no_yolo_anomaly_normal_ok(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.STABLE_PRODUCTION))
        decision = engine.fuse(_yolo_none(), _anomaly_normal())
        assert decision.final_decision == FinalDecision.OK


# ── Edge cases ─────────────────────────────────────────────────────

class TestEdgeCases:

    def test_both_none(self):
        engine = HybridFusionEngine()
        decision = engine.fuse(None, None)
        assert decision.final_decision == FinalDecision.OK
        assert decision.reason == ReasonCode.CLEAN_BY_BOTH.value

    def test_empty_yolo_list_same_as_none(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))
        decision = engine.fuse([], _anomaly_high())
        assert decision.final_decision == FinalDecision.UNKNOWN

    def test_custom_thresholds(self):
        config = FusionConfig(
            strategy=FusionStrategy.PRODUCTION_RETEST,
            yolo_conf_threshold=0.8,
            anomaly_high_threshold=0.95,
        )
        engine = HybridFusionEngine(config)
        # With yolo_conf_threshold=0.8, confidence=0.75 is "low"
        yolo_mid = [BBoxPrediction(class_name="dent", confidence=0.75)]
        decision = engine.fuse(yolo_mid, _anomaly_high())  # anomaly 0.92 < 0.95 → not "high"
        # yolo low + anomaly not "high" → falls through to NEEDS_REVIEW (Rule 6)
        assert decision.final_decision == FinalDecision.NEEDS_REVIEW

    def test_image_path_preserved(self):
        engine = HybridFusionEngine()
        decision = engine.fuse(_yolo_high(), _anomaly_normal(), image_path="/data/test.png")
        assert decision.image_path == "/data/test.png"

    def test_default_config_is_exploration_first(self):
        engine = HybridFusionEngine()
        assert engine.config.strategy == FusionStrategy.EXPLORATION_FIRST

    def test_legacy_strategy_falls_back_to_production_retest(self):
        """Non-exploration strategies (YOLO_ONLY etc.) fall back to production_retest."""
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.YOLO_ONLY))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.strategy == FusionStrategy.PRODUCTION_RETEST

    # ── P1.1 fix: exploration_first honors YOLO high-conf ─────────

    def test_exploration_first_yolo_high_conf_ng(self):
        """If YOLO model exists and detects known defects, report as NG."""
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.EXPLORATION_FIRST))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert decision.final_decision == FinalDecision.NG
        assert decision.reason == ReasonCode.YOLO_KNOWN_DEFECT.value
        assert len(decision.candidates) == 1
        assert decision.candidates[0].class_name == "scratch"

    # ── P2.1 fix: medium anomaly without YOLO → NEEDS_REVIEW ──────

    def test_production_retest_no_yolo_medium_anomaly_needs_review(self):
        """No YOLO + medium anomaly → Needs Review, NOT false_positive."""
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))
        decision = engine.fuse(_yolo_none(), _anomaly_medium())
        assert decision.final_decision == FinalDecision.NEEDS_REVIEW
        assert decision.reason == ReasonCode.NEEDS_MANUAL_REVIEW.value

    # ── P2.2 fix: evidence in FusionDecision ──────────────────────

    def test_fusion_decision_has_extra_evidence(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert "anomaly_score" in decision.extra
        assert "yolo_detection_count" in decision.extra
        assert decision.extra["has_yolo_high_conf"] is True

    def test_fusion_decision_candidates_for_ng(self):
        engine = HybridFusionEngine(FusionConfig(strategy=FusionStrategy.PRODUCTION_RETEST))
        decision = engine.fuse(_yolo_high(), _anomaly_normal())
        assert len(decision.candidates) >= 1
        c = decision.candidates[0]
        assert c.source_model == ModelSource.YOLO
        assert c.class_name == "scratch"
        assert c.confidence == 0.95
