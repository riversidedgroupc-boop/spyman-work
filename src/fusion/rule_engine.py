"""Fusion rule engine for combining multi-model results into final decisions."""

from __future__ import annotations

import time
from typing import Optional

from src.fusion.decision_types import (
    BBoxPrediction,
    DefectCandidate,
    FinalDecision,
    FusionDecision,
    FusionStrategy,
    UnifiedPrediction,
)


class RuleEngine:
    """Applies fusion rules to combine YOLO, anomaly detection, and OpenCV results."""

    def __init__(self, fusion_config: dict) -> None:
        self.config = fusion_config
        self.yolo_conf = fusion_config.get("yolo", {}).get("conf_threshold", 0.6)
        self.major_defect_classes = fusion_config.get("yolo", {}).get("major_defect_classes", [])
        self.direct_ng_conf = fusion_config.get("yolo", {}).get("direct_ng_conf_threshold", 0.75)

        anomaly_cfg = fusion_config.get("anomaly", {})
        self.patchcore_threshold = anomaly_cfg.get("patchcore_score_threshold", 0.65)
        self.efficientad_threshold = anomaly_cfg.get("efficientad_score_threshold", 0.65)
        self.fastflow_threshold = anomaly_cfg.get("fastflow_score_threshold", 0.65)
        self.unknown_ng_threshold = anomaly_cfg.get("unknown_ng_score_threshold", 0.85)

        geo = fusion_config.get("geometry", {})
        self.min_area_px = geo.get("min_defect_area_px", 8)
        self.acceptable_micro_area = geo.get("acceptable_micro_area_px", 30)
        self.ng_area_px = geo.get("ng_area_px", 200)
        self.acceptable_scratch_len = geo.get("acceptable_scratch_length_mm", 0.5)
        self.ng_scratch_len = geo.get("ng_scratch_length_mm", 2.0)
        self.long_scratch_ar = geo.get("long_scratch_aspect_ratio", 5.0)

        density = fusion_config.get("density", {})
        self.enable_density = density.get("enable_density_rule", True)
        self.max_micro_count = density.get("max_micro_defect_count_per_meter", 50)
        self.max_micro_area = density.get("max_micro_defect_area_per_meter", 500)

        fusion = fusion_config.get("fusion", {})
        self.double_confirm = fusion.get("require_double_confirm_for_ng", False)

    def decide(
        self,
        image_path: str,
        strategy: FusionStrategy = FusionStrategy.RULE_BASED,
        yolo_result: UnifiedPrediction | None = None,
        patchcore_result: UnifiedPrediction | None = None,
        efficientad_result: UnifiedPrediction | None = None,
        fastflow_result: UnifiedPrediction | None = None,
        opencv_result: UnifiedPrediction | None = None,
        candidates: list[DefectCandidate] | None = None,
    ) -> FusionDecision:
        """Apply fusion strategy and return final decision."""

        if strategy == FusionStrategy.YOLO_ONLY:
            return self._decide_yolo_only(image_path, yolo_result, candidates)
        elif strategy == FusionStrategy.ANOMALY_ONLY:
            return self._decide_anomaly_only(image_path, patchcore_result, efficientad_result, fastflow_result)
        elif strategy == FusionStrategy.YOLO_PRIORITY:
            return self._decide_yolo_priority(
                image_path, yolo_result, patchcore_result, efficientad_result, fastflow_result, candidates
            )
        elif strategy == FusionStrategy.ANOMALY_PRIORITY:
            return self._decide_anomaly_priority(
                image_path, yolo_result, patchcore_result, efficientad_result, fastflow_result, candidates
            )
        elif strategy == FusionStrategy.DOUBLE_CONFIRM:
            return self._decide_double_confirm(
                image_path, yolo_result, patchcore_result, efficientad_result, fastflow_result, candidates
            )
        else:
            return self._decide_rule_based(
                image_path, yolo_result, patchcore_result, efficientad_result, fastflow_result, opencv_result, candidates
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_max_anomaly_score(
        self,
        patchcore_result: UnifiedPrediction | None = None,
        efficientad_result: UnifiedPrediction | None = None,
        fastflow_result: UnifiedPrediction | None = None,
    ) -> float:
        scores: list[float] = []
        for r in (patchcore_result, efficientad_result, fastflow_result):
            if r is not None and r.anomaly is not None:
                scores.append(r.anomaly.image_score)
        return max(scores) if scores else 0.0

    def _has_yolo_major_defect(
        self, yolo_result: UnifiedPrediction | None
    ) -> tuple[bool, Optional[BBoxPrediction]]:
        if yolo_result is None:
            return False, None
        for pred in yolo_result.predictions:
            if pred.class_name in self.major_defect_classes and pred.confidence >= self.direct_ng_conf:
                return True, pred
        return False, None

    def _has_any_yolo_defect(self, yolo_result: UnifiedPrediction | None) -> bool:
        if yolo_result is None:
            return False
        return any(p.confidence >= self.yolo_conf for p in yolo_result.predictions)

    def _yolo_confident_predictions(
        self, yolo_result: UnifiedPrediction | None
    ) -> list[BBoxPrediction]:
        if yolo_result is None:
            return []
        return [p for p in yolo_result.predictions if p.confidence >= self.yolo_conf]

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _decide_yolo_only(
        self,
        image_path: str,
        yolo_result: UnifiedPrediction | None,
        candidates: list[DefectCandidate] | None,
    ) -> FusionDecision:
        t0 = time.perf_counter()

        if yolo_result is None or len(yolo_result.predictions) == 0:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_ONLY,
                final_decision=FinalDecision.OK,
                reason="No YOLO detections",
                yolo_result=yolo_result,
                candidates=candidates or [],
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        has_major, major_pred = self._has_yolo_major_defect(yolo_result)
        if has_major and major_pred is not None:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_ONLY,
                final_decision=FinalDecision.NG,
                reason=f"YOLO known major defect: {major_pred.class_name} (conf={major_pred.confidence:.2f})",
                yolo_result=yolo_result,
                candidates=candidates or [],
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        if self._has_any_yolo_defect(yolo_result):
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_ONLY,
                final_decision=FinalDecision.SUSPECT,
                reason="YOLO detected defects below NG threshold",
                yolo_result=yolo_result,
                candidates=candidates or [],
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.YOLO_ONLY,
            final_decision=FinalDecision.OK,
            reason="No YOLO defect above threshold",
            yolo_result=yolo_result,
            candidates=candidates or [],
            runtime_ms=(time.perf_counter() - t0) * 1000,
        )

    def _decide_anomaly_only(
        self,
        image_path: str,
        patchcore: UnifiedPrediction | None,
        efficientad: UnifiedPrediction | None,
        fastflow: UnifiedPrediction | None,
    ) -> FusionDecision:
        t0 = time.perf_counter()
        max_score = self._get_max_anomaly_score(patchcore, efficientad, fastflow)

        if max_score >= self.unknown_ng_threshold:
            decision = FinalDecision.SUSPECT
            reason = f"High anomaly score ({max_score:.3f}) >= {self.unknown_ng_threshold}"
        elif max_score >= self.patchcore_threshold:
            decision = FinalDecision.SUSPECT
            reason = f"Elevated anomaly score ({max_score:.3f})"
        else:
            decision = FinalDecision.OK
            reason = f"Low anomaly score ({max_score:.3f})"

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.ANOMALY_ONLY,
            final_decision=decision,
            reason=reason,
            patchcore_result=patchcore,
            efficientad_result=efficientad,
            fastflow_result=fastflow,
            runtime_ms=(time.perf_counter() - t0) * 1000,
        )

    def _decide_yolo_priority(
        self,
        image_path: str,
        yolo: UnifiedPrediction | None,
        patchcore: UnifiedPrediction | None,
        efficientad: UnifiedPrediction | None,
        fastflow: UnifiedPrediction | None,
        candidates: list[DefectCandidate] | None,
    ) -> FusionDecision:
        has_major, major_pred = self._has_yolo_major_defect(yolo)
        if has_major and major_pred is not None:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_PRIORITY,
                final_decision=FinalDecision.NG,
                reason=f"YOLO known major defect: {major_pred.class_name} (conf={major_pred.confidence:.2f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        max_anomaly = self._get_max_anomaly_score(patchcore, efficientad, fastflow)

        if self._has_any_yolo_defect(yolo):
            if max_anomaly >= self.patchcore_threshold:
                return FusionDecision(
                    image_path=image_path,
                    strategy=FusionStrategy.YOLO_PRIORITY,
                    final_decision=FinalDecision.NG,
                    reason="YOLO defect + anomaly confirmed",
                    yolo_result=yolo,
                    patchcore_result=patchcore,
                    candidates=candidates or [],
                )
            else:
                return FusionDecision(
                    image_path=image_path,
                    strategy=FusionStrategy.YOLO_PRIORITY,
                    final_decision=FinalDecision.SUSPECT,
                    reason="YOLO defect but anomaly not confirmed",
                    yolo_result=yolo,
                    patchcore_result=patchcore,
                    candidates=candidates or [],
                )

        if max_anomaly >= self.unknown_ng_threshold:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_PRIORITY,
                final_decision=FinalDecision.SUSPECT,
                reason=f"Unknown anomaly (score={max_anomaly:.3f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        if max_anomaly >= self.patchcore_threshold:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.YOLO_PRIORITY,
                final_decision=FinalDecision.ACCEPTABLE_MICRO_DEFECT,
                reason=f"Minor anomaly, YOLO clean (score={max_anomaly:.3f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.YOLO_PRIORITY,
            final_decision=FinalDecision.OK,
            reason="YOLO clean and low anomaly",
            yolo_result=yolo,
            patchcore_result=patchcore,
            candidates=candidates or [],
        )

    def _decide_anomaly_priority(
        self,
        image_path: str,
        yolo: UnifiedPrediction | None,
        patchcore: UnifiedPrediction | None,
        efficientad: UnifiedPrediction | None,
        fastflow: UnifiedPrediction | None,
        candidates: list[DefectCandidate] | None,
    ) -> FusionDecision:
        max_score = self._get_max_anomaly_score(patchcore, efficientad, fastflow)

        if max_score >= self.unknown_ng_threshold:
            if self._has_any_yolo_defect(yolo):
                return FusionDecision(
                    image_path=image_path,
                    strategy=FusionStrategy.ANOMALY_PRIORITY,
                    final_decision=FinalDecision.NG,
                    reason=f"High anomaly confirmed by YOLO (score={max_score:.3f})",
                    yolo_result=yolo,
                    patchcore_result=patchcore,
                    candidates=candidates or [],
                )
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.ANOMALY_PRIORITY,
                final_decision=FinalDecision.SUSPECT,
                reason=f"High anomaly, YOLO unknown (score={max_score:.3f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        if max_score >= self.patchcore_threshold:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.ANOMALY_PRIORITY,
                final_decision=FinalDecision.SUSPECT,
                reason=f"Elevated anomaly score ({max_score:.3f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        if self._has_any_yolo_defect(yolo):
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.ANOMALY_PRIORITY,
                final_decision=FinalDecision.SUSPECT,
                reason="YOLO defect but anomaly low",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.ANOMALY_PRIORITY,
            final_decision=FinalDecision.OK,
            reason="Clean",
            yolo_result=yolo,
            patchcore_result=patchcore,
            candidates=candidates or [],
        )

    def _decide_double_confirm(
        self,
        image_path: str,
        yolo: UnifiedPrediction | None,
        patchcore: UnifiedPrediction | None,
        efficientad: UnifiedPrediction | None,
        fastflow: UnifiedPrediction | None,
        candidates: list[DefectCandidate] | None,
    ) -> FusionDecision:
        has_yolo_ng = self._has_any_yolo_defect(yolo)
        max_anomaly = self._get_max_anomaly_score(patchcore, efficientad, fastflow)
        anomaly_high = max_anomaly >= self.patchcore_threshold

        if has_yolo_ng and anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.DOUBLE_CONFIRM,
                final_decision=FinalDecision.NG,
                reason="Both YOLO and anomaly confirm NG",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )
        elif has_yolo_ng or anomaly_high:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.DOUBLE_CONFIRM,
                final_decision=FinalDecision.SUSPECT,
                reason=f"Only one model flagged (YOLO={has_yolo_ng}, Anomaly={anomaly_high})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                candidates=candidates or [],
            )

        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.DOUBLE_CONFIRM,
            final_decision=FinalDecision.OK,
            reason="Both clean",
            yolo_result=yolo,
            patchcore_result=patchcore,
            candidates=candidates or [],
        )

    def _decide_rule_based(
        self,
        image_path: str,
        yolo: UnifiedPrediction | None,
        patchcore: UnifiedPrediction | None,
        efficientad: UnifiedPrediction | None,
        fastflow: UnifiedPrediction | None,
        opencv: UnifiedPrediction | None,
        candidates: list[DefectCandidate] | None,
    ) -> FusionDecision:
        """Full rule-based fusion with geometry and density checks."""
        t0 = time.perf_counter()
        _candidates = candidates or []

        # Rule 1: YOLO high-confidence major defect -> NG
        has_major, major_pred = self._has_yolo_major_defect(yolo)
        if has_major and major_pred is not None:
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.RULE_BASED,
                final_decision=FinalDecision.NG,
                reason=f"YOLO known major defect: {major_pred.class_name} (conf={major_pred.confidence:.2f})",
                yolo_result=yolo,
                patchcore_result=patchcore,
                efficientad_result=efficientad,
                fastflow_result=fastflow,
                opencv_result=opencv,
                candidates=_candidates,
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        max_anomaly = self._get_max_anomaly_score(patchcore, efficientad, fastflow)

        # Check candidates for geometry-based rules
        if _candidates:
            for c in _candidates:
                # Rule 2: Long scratch-like defect + anomaly -> NG
                if (
                    c.is_long_scratch_like
                    and c.length_mm is not None
                    and c.length_mm >= self.ng_scratch_len
                ):
                    if max_anomaly >= self.patchcore_threshold:
                        return FusionDecision(
                            image_path=image_path,
                            strategy=FusionStrategy.RULE_BASED,
                            final_decision=FinalDecision.NG,
                            reason="Long continuous scratch with anomaly",
                            yolo_result=yolo,
                            patchcore_result=patchcore,
                            efficientad_result=efficientad,
                            fastflow_result=fastflow,
                            opencv_result=opencv,
                            candidates=_candidates,
                            runtime_ms=(time.perf_counter() - t0) * 1000,
                        )

                # Rule 3: Large unknown anomaly -> SUSPECT
                if c.area_px >= self.ng_area_px and max_anomaly >= self.patchcore_threshold:
                    if not self._has_any_yolo_defect(yolo):
                        return FusionDecision(
                            image_path=image_path,
                            strategy=FusionStrategy.RULE_BASED,
                            final_decision=FinalDecision.SUSPECT,
                            reason="Unknown anomaly - large area, YOLO no detection",
                            yolo_result=yolo,
                            patchcore_result=patchcore,
                            efficientad_result=efficientad,
                            fastflow_result=fastflow,
                            opencv_result=opencv,
                            candidates=_candidates,
                            runtime_ms=(time.perf_counter() - t0) * 1000,
                        )

        # Rule 4: Small defects -> ACCEPTABLE or OK
        if max_anomaly >= self.patchcore_threshold:
            if _candidates:
                all_small = all(c.area_px <= self.acceptable_micro_area for c in _candidates)
                if all_small:
                    return FusionDecision(
                        image_path=image_path,
                        strategy=FusionStrategy.RULE_BASED,
                        final_decision=FinalDecision.ACCEPTABLE_MICRO_DEFECT,
                        reason="Acceptable micro defect",
                        yolo_result=yolo,
                        patchcore_result=patchcore,
                        efficientad_result=efficientad,
                        fastflow_result=fastflow,
                        opencv_result=opencv,
                        candidates=_candidates,
                        runtime_ms=(time.perf_counter() - t0) * 1000,
                    )

            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.RULE_BASED,
                final_decision=FinalDecision.SUSPECT,
                reason=f"Anomaly detected ({max_anomaly:.3f}), review needed",
                yolo_result=yolo,
                patchcore_result=patchcore,
                efficientad_result=efficientad,
                fastflow_result=fastflow,
                opencv_result=opencv,
                candidates=_candidates,
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        # Rule 5: Dense micro defects check
        if self.enable_density and _candidates:
            total_area = sum(c.area_px for c in _candidates)
            if len(_candidates) >= self.max_micro_count or total_area >= self.max_micro_area:
                return FusionDecision(
                    image_path=image_path,
                    strategy=FusionStrategy.RULE_BASED,
                    final_decision=FinalDecision.SUSPECT,
                    reason=f"Dense micro defects (count={len(_candidates)}, area={total_area:.0f})",
                    yolo_result=yolo,
                    patchcore_result=patchcore,
                    efficientad_result=efficientad,
                    fastflow_result=fastflow,
                    opencv_result=opencv,
                    candidates=_candidates,
                    runtime_ms=(time.perf_counter() - t0) * 1000,
                )

        # Rule 6: Low anomaly but YOLO sees something -> SUSPECT
        if self._has_any_yolo_defect(yolo):
            return FusionDecision(
                image_path=image_path,
                strategy=FusionStrategy.RULE_BASED,
                final_decision=FinalDecision.SUSPECT,
                reason="YOLO defect, anomaly low, review needed",
                yolo_result=yolo,
                patchcore_result=patchcore,
                efficientad_result=efficientad,
                fastflow_result=fastflow,
                opencv_result=opencv,
                candidates=_candidates,
                runtime_ms=(time.perf_counter() - t0) * 1000,
            )

        # Rule 7: All clean
        return FusionDecision(
            image_path=image_path,
            strategy=FusionStrategy.RULE_BASED,
            final_decision=FinalDecision.OK,
            reason="Low anomaly and no defect",
            yolo_result=yolo,
            patchcore_result=patchcore,
            efficientad_result=efficientad,
            fastflow_result=fastflow,
            opencv_result=opencv,
            candidates=_candidates,
            runtime_ms=(time.perf_counter() - t0) * 1000,
        )
