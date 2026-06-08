"""Hybrid fusion engine — deterministic rule-based fusion of YOLO + anomaly results."""

from __future__ import annotations

from dataclasses import dataclass

# NOTE: These imports from src/ represent a legitimate dependency:
# core/ evaluation modules use src/ fusion types as the canonical domain model.
# See docs/architecture.md for rationale.
from src.fusion.decision_types import (
    AnomalyResult,
    BBoxPrediction,
    DefectCandidate,
    FinalDecision,
    FusionDecision,
    FusionStrategy,
    ModelSource,
    ReasonCode,
)


@dataclass
class FusionConfig:
    strategy: FusionStrategy = FusionStrategy.EXPLORATION_FIRST
    yolo_conf_threshold: float = 0.5
    anomaly_score_threshold: float = 0.65
    anomaly_high_threshold: float = 0.85


def _bbox_to_candidate(bbox: BBoxPrediction, idx: int = 0) -> DefectCandidate:
    """Convert a BBoxPrediction to a lightweight DefectCandidate for evidence."""
    x1, y1, x2, y2 = bbox.bbox_xyxy if len(bbox.bbox_xyxy) == 4 else [0, 0, 0, 0]
    return DefectCandidate(
        candidate_id=idx,
        source_model=ModelSource.YOLO,
        class_name=bbox.class_name,
        confidence=bbox.confidence,
        bbox_xyxy=list(bbox.bbox_xyxy),
        area_px=max(0.0, (x2 - x1) * (y2 - y1)),
        bbox_width=max(0.0, x2 - x1),
        bbox_height=max(0.0, y2 - y1),
        center_x=(x1 + x2) / 2.0,
        center_y=(y1 + y2) / 2.0,
    )


def _build_base_extra(
    anomaly_score: float,
    yolo_detections: list[BBoxPrediction],
    has_yolo_high: bool,
    has_yolo_low: bool,
) -> dict[str, object]:
    """Build the extra dict with evidence for downstream review queue."""
    return {
        "anomaly_score": anomaly_score,
        "yolo_detection_count": len(yolo_detections),
        "has_yolo_high_conf": has_yolo_high,
        "has_yolo_low_conf": has_yolo_low,
    }


def _high_conf_detections(
    detections: list[BBoxPrediction], threshold: float
) -> list[BBoxPrediction]:
    return [d for d in detections if d.confidence >= threshold]


class HybridFusionEngine:
    """Deterministic rule-based fusion engine for YOLO + anomaly detection results.

    Supports 4 strategy modes from the field exploration spec:
    - EXPLORATION_FIRST: anomaly primary, YOLO optional (but YOLO results used if available)
    - FEW_SHOT: YOLO handles known classes, anomaly catches unknowns
    - PRODUCTION_RETEST: parallel YOLO + anomaly → OK/NG/Suspect/Unknown
    - STABLE_PRODUCTION: YOLO primary, anomaly as drift monitor
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()

    # ── public API ──────────────────────────────────────────────────

    def fuse(
        self,
        yolo_detections: list[BBoxPrediction] | None,
        anomaly_result: AnomalyResult | None,
        image_path: str = "",
    ) -> FusionDecision:
        """Dispatch to the appropriate strategy method based on config."""
        strategy = self.config.strategy
        if strategy == FusionStrategy.EXPLORATION_FIRST:
            return self._exploration_first_fuse(yolo_detections, anomaly_result, image_path)
        elif strategy == FusionStrategy.FEW_SHOT:
            return self._few_shot_fuse(yolo_detections, anomaly_result, image_path)
        elif strategy == FusionStrategy.PRODUCTION_RETEST:
            return self._production_retest_fuse(yolo_detections, anomaly_result, image_path)
        elif strategy == FusionStrategy.STABLE_PRODUCTION:
            return self._stable_production_fuse(yolo_detections, anomaly_result, image_path)
        else:
            # Fallback to production_retest for legacy strategies
            return self._production_retest_fuse(yolo_detections, anomaly_result, image_path)

    # ── strategy implementations ────────────────────────────────────

    def _exploration_first_fuse(
        self,
        yolo_detections: list[BBoxPrediction] | None,
        anomaly_result: AnomalyResult | None,
        image_path: str = "",
    ) -> FusionDecision:
        """Anomaly-primary mode. YOLO results used if an existing model is available.

        If YOLO detects known defects with high confidence, they are reported as NG
        even in exploration mode. Otherwise anomaly score drives the decision:
        - high → UNKNOWN (strong anomaly candidate)
        - medium → NEEDS_REVIEW
        - low → OK
        """
        yolo_detections = yolo_detections or []
        anomaly_score = anomaly_result.image_score if anomaly_result else 0.0

        # Check YOLO first: if we have a model and it sees known defects, report them
        high_conf = _high_conf_detections(yolo_detections, self.config.yolo_conf_threshold)
        if high_conf:
            candidates = [_bbox_to_candidate(b, i) for i, b in enumerate(high_conf)]
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.EXPLORATION_FIRST,
                final_decision=FinalDecision.NG,
                reason=ReasonCode.YOLO_KNOWN_DEFECT.value,
                candidates=candidates,
                extra=_build_base_extra(
                    anomaly_score, yolo_detections, has_yolo_high=True, has_yolo_low=False,
                ),
                runtime_ms=0.0,
            )

        # Anomaly-driven exploration path
        if anomaly_score >= self.config.anomaly_high_threshold:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.EXPLORATION_FIRST,
                final_decision=FinalDecision.UNKNOWN,
                reason=ReasonCode.ANOMALY_UNKNOWN.value,
                extra=_build_base_extra(
                    anomaly_score, yolo_detections, has_yolo_high=False, has_yolo_low=False,
                ),
                runtime_ms=0.0,
            )
        elif anomaly_score >= self.config.anomaly_score_threshold:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.EXPLORATION_FIRST,
                final_decision=FinalDecision.NEEDS_REVIEW,
                reason=ReasonCode.NEEDS_MANUAL_REVIEW.value,
                extra=_build_base_extra(
                    anomaly_score, yolo_detections, has_yolo_high=False, has_yolo_low=False,
                ),
                runtime_ms=0.0,
            )
        else:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.EXPLORATION_FIRST,
                final_decision=FinalDecision.OK,
                reason=ReasonCode.CLEAN_BY_BOTH.value,
                extra=_build_base_extra(
                    anomaly_score, yolo_detections, has_yolo_high=False, has_yolo_low=False,
                ),
                runtime_ms=0.0,
            )

    def _few_shot_fuse(
        self,
        yolo_detections: list[BBoxPrediction] | None,
        anomaly_result: AnomalyResult | None,
        image_path: str = "",
    ) -> FusionDecision:
        """YOLO handles known classes; anomaly catches unknowns."""
        yolo_detections = yolo_detections or []
        anomaly_score = anomaly_result.image_score if anomaly_result else 0.0

        has_yolo_high = any(
            d.confidence >= self.config.yolo_conf_threshold for d in yolo_detections
        )
        anomaly_high = anomaly_score >= self.config.anomaly_high_threshold
        anomaly_med = anomaly_score >= self.config.anomaly_score_threshold

        extra = _build_base_extra(anomaly_score, yolo_detections, has_yolo_high, False)

        if has_yolo_high:
            high_conf = _high_conf_detections(yolo_detections, self.config.yolo_conf_threshold)
            candidates = [_bbox_to_candidate(b, i) for i, b in enumerate(high_conf)]
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.FEW_SHOT,
                final_decision=FinalDecision.NG,
                reason=ReasonCode.YOLO_KNOWN_DEFECT.value,
                candidates=candidates,
                extra=extra,
                runtime_ms=0.0,
            )
        elif anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.FEW_SHOT,
                final_decision=FinalDecision.UNKNOWN,
                reason=ReasonCode.ANOMALY_UNKNOWN.value,
                extra=extra,
                runtime_ms=0.0,
            )
        elif anomaly_med:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.FEW_SHOT,
                final_decision=FinalDecision.NEEDS_REVIEW,
                reason=ReasonCode.NEEDS_MANUAL_REVIEW.value,
                extra=extra,
                runtime_ms=0.0,
            )
        else:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.FEW_SHOT,
                final_decision=FinalDecision.OK,
                reason=ReasonCode.CLEAN_BY_BOTH.value,
                extra=extra,
                runtime_ms=0.0,
            )

    def _production_retest_fuse(
        self,
        yolo_detections: list[BBoxPrediction] | None,
        anomaly_result: AnomalyResult | None,
        image_path: str = "",
    ) -> FusionDecision:
        """Full fusion: OK / NG / Suspect / Unknown / Needs Review."""
        yolo_detections = yolo_detections or []
        anomaly_score = anomaly_result.image_score if anomaly_result else 0.0

        has_yolo_high = any(
            d.confidence >= self.config.yolo_conf_threshold for d in yolo_detections
        )
        has_yolo_low = any(
            0 < d.confidence < self.config.yolo_conf_threshold for d in yolo_detections
        )
        has_any_yolo = has_yolo_high or has_yolo_low
        anomaly_high = anomaly_score >= self.config.anomaly_high_threshold
        anomaly_medium = (
            self.config.anomaly_score_threshold <= anomaly_score < self.config.anomaly_high_threshold
        )
        anomaly_normal = anomaly_score < self.config.anomaly_score_threshold

        extra = _build_base_extra(anomaly_score, yolo_detections, has_yolo_high, has_yolo_low)

        # Rule 1: YOLO high confidence + anomaly normal → NG known defect
        if has_yolo_high and anomaly_normal:
            high_conf = _high_conf_detections(yolo_detections, self.config.yolo_conf_threshold)
            candidates = [_bbox_to_candidate(b, i) for i, b in enumerate(high_conf)]
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.NG,
                reason=ReasonCode.YOLO_KNOWN_DEFECT.value,
                candidates=candidates,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 2: YOLO none + anomaly normal → OK
        if not has_any_yolo and anomaly_normal:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.OK,
                reason=ReasonCode.CLEAN_BY_BOTH.value,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 3: YOLO none + anomaly high → Unknown
        if not has_any_yolo and anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.UNKNOWN,
                reason=ReasonCode.ANOMALY_UNKNOWN.value,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 3b: YOLO none + anomaly medium → Needs Review (not false positive)
        if not has_any_yolo and anomaly_medium:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.NEEDS_REVIEW,
                reason=ReasonCode.NEEDS_MANUAL_REVIEW.value,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 4: YOLO low confidence + anomaly high → Suspect
        if has_yolo_low and anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.SUSPECT,
                reason=ReasonCode.YOLO_UNCERTAIN_ANOMALY_CONFIRMED.value,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 5: YOLO high confidence + anomaly high → NG (anomaly supports)
        if has_yolo_high and anomaly_high:
            high_conf = _high_conf_detections(yolo_detections, self.config.yolo_conf_threshold)
            candidates = [_bbox_to_candidate(b, i) for i, b in enumerate(high_conf)]
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.PRODUCTION_RETEST,
                final_decision=FinalDecision.NG,
                reason=ReasonCode.YOLO_KNOWN_DEFECT.value,
                candidates=candidates,
                extra=extra,
                runtime_ms=0.0,
            )

        # Rule 6: YOLO low confidence + anomaly normal → possible YOLO false positive / review
        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.PRODUCTION_RETEST,
            final_decision=FinalDecision.NEEDS_REVIEW,
            reason=ReasonCode.POSSIBLE_FALSE_POSITIVE.value,
            extra=extra,
            runtime_ms=0.0,
        )

    def _stable_production_fuse(
        self,
        yolo_detections: list[BBoxPrediction] | None,
        anomaly_result: AnomalyResult | None,
        image_path: str = "",
    ) -> FusionDecision:
        """YOLO primary; anomaly only as drift/unknown monitor."""
        yolo_detections = yolo_detections or []
        anomaly_score = anomaly_result.image_score if anomaly_result else 0.0

        has_yolo_high = any(
            d.confidence >= self.config.yolo_conf_threshold for d in yolo_detections
        )
        anomaly_high = anomaly_score >= self.config.anomaly_high_threshold

        extra = _build_base_extra(anomaly_score, yolo_detections, has_yolo_high, False)

        if has_yolo_high:
            high_conf = _high_conf_detections(yolo_detections, self.config.yolo_conf_threshold)
            candidates = [_bbox_to_candidate(b, i) for i, b in enumerate(high_conf)]
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.STABLE_PRODUCTION,
                final_decision=FinalDecision.NG,
                reason=ReasonCode.YOLO_KNOWN_DEFECT.value,
                candidates=candidates,
                extra=extra,
                runtime_ms=0.0,
            )

        if anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.STABLE_PRODUCTION,
                final_decision=FinalDecision.UNKNOWN,
                reason=ReasonCode.ANOMALY_UNKNOWN.value,
                extra=extra,
                runtime_ms=0.0,
            )

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.STABLE_PRODUCTION,
            final_decision=FinalDecision.OK,
            reason=ReasonCode.CLEAN_BY_BOTH.value,
            extra=extra,
            runtime_ms=0.0,
        )
