"""Industrial inspection metrics for copper tube defect evaluation.

These metrics are specifically designed for surface-defect inspection where:
- False positives on OK parts waste production capacity.
- Missed NG defects are a quality escape risk.
- Acceptable micro defects should not be over-rejected.
- Unknown anomaly types still need a detection path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.dataset.label_schema import (
    ACCEPTABLE_MICRO_CLASSES,
    BORDERLINE_CLASS,
    NG_CLASSES,
    OK_CLASSES,
)
from src.fusion.decision_types import FinalDecision


@dataclass
class IndustrialMetrics:
    """Aggregated industrial inspection metrics."""

    ok_false_positive_rate: float = 0.0  # True OK predicted as NG or SUSPECT
    ng_miss_rate: float = 0.0  # True NG predicted as OK or ACCEPTABLE
    acceptable_micro_fp_rate: float = 0.0  # True OK_micro predicted as NG
    unknown_defect_recall: float = 0.0  # True NG_unknown predicted as SUSPECT or NG
    borderline_detection_rate: float = 0.0  # True Borderline predicted as SUSPECT or NG
    avg_inference_time_ms: float = 0.0
    total_images: int = 0
    per_meter_false_alarms: float = 0.0  # Reserved for per-meter stats
    detail: dict = field(default_factory=dict)


def compute_industrial_metrics(
    true_labels: list[str],
    predicted_decisions: list[str],
    inference_times_ms: list[float] | None = None,
) -> IndustrialMetrics:
    """Compute all industrial inspection metrics.

    Args:
        true_labels: Ground truth labels (e.g. "OK_clean", "NG_scratch", ...).
        predicted_decisions: Fusion decisions, one of "OK", "ACCEPTABLE_MICRO_DEFECT",
            "SUSPECT", "NG".
        inference_times_ms: Per-image inference times in milliseconds.

    Returns:
        IndustrialMetrics dataclass with computed rates and detail counts.
    """
    total = len(true_labels)
    if total == 0:
        return IndustrialMetrics()

    # --- category counts ---
    ok_true_count = sum(1 for t in true_labels if t in OK_CLASSES)
    ng_true_count = sum(1 for t in true_labels if t in NG_CLASSES)
    acceptable_micro_count = sum(1 for t in true_labels if t in ACCEPTABLE_MICRO_CLASSES)
    unknown_ng_count = sum(1 for t in true_labels if t == "NG_unknown")
    borderline_count = sum(1 for t in true_labels if t == BORDERLINE_CLASS)

    # --- metric 1: OK false positive rate ---
    ok_fp = sum(
        1
        for t, p in zip(true_labels, predicted_decisions)
        if t in OK_CLASSES and p in (FinalDecision.NG.value, FinalDecision.SUSPECT.value)
    )
    ok_fpr = ok_fp / max(ok_true_count, 1)

    # --- metric 2: NG miss rate ---
    ng_miss = sum(
        1
        for t, p in zip(true_labels, predicted_decisions)
        if t in NG_CLASSES
        and p in (FinalDecision.OK.value, FinalDecision.ACCEPTABLE_MICRO_DEFECT.value)
    )
    ng_miss_rate = ng_miss / max(ng_true_count, 1)

    # --- metric 3: acceptable micro false positive rate ---
    micro_fp = sum(
        1
        for t, p in zip(true_labels, predicted_decisions)
        if t in ACCEPTABLE_MICRO_CLASSES and p == FinalDecision.NG.value
    )
    micro_fpr = micro_fp / max(acceptable_micro_count, 1)

    # --- metric 4: unknown defect recall ---
    unknown_detected = sum(
        1
        for t, p in zip(true_labels, predicted_decisions)
        if t == "NG_unknown"
        and p in (FinalDecision.SUSPECT.value, FinalDecision.NG.value)
    )
    unknown_recall = unknown_detected / max(unknown_ng_count, 1)

    # --- metric 5: borderline detection rate ---
    borderline_detected = sum(
        1
        for t, p in zip(true_labels, predicted_decisions)
        if t == BORDERLINE_CLASS
        and p in (FinalDecision.SUSPECT.value, FinalDecision.NG.value)
    )
    borderline_rate = borderline_detected / max(borderline_count, 1)

    # --- metric 6: average inference time ---
    avg_time = float(np.mean(inference_times_ms)) if inference_times_ms else 0.0

    return IndustrialMetrics(
        ok_false_positive_rate=ok_fpr,
        ng_miss_rate=ng_miss_rate,
        acceptable_micro_fp_rate=micro_fpr,
        unknown_defect_recall=unknown_recall,
        borderline_detection_rate=borderline_rate,
        avg_inference_time_ms=avg_time,
        total_images=total,
        detail={
            "total": total,
            "ok_true_count": ok_true_count,
            "ng_true_count": ng_true_count,
            "acceptable_micro_count": acceptable_micro_count,
            "unknown_ng_count": unknown_ng_count,
            "borderline_count": borderline_count,
            "ok_fp_count": ok_fp,
            "ng_miss_count": ng_miss,
            "micro_fp_count": micro_fp,
            "unknown_detected_count": unknown_detected,
            "borderline_detected_count": borderline_detected,
        },
    )


def compute_strategy_comparison(
    all_strategy_results: dict[str, tuple[list[str], list[str], list[float]]],
) -> list[dict]:
    """Compare multiple fusion strategies side-by-side.

    Args:
        all_strategy_results: Mapping from strategy name to
            (true_labels, predicted_decisions, inference_times).

    Returns:
        List of dicts with strategy name and all computed metrics.
    """
    comparison: list[dict] = []
    for strategy_name, (true_labels, predictions, times) in all_strategy_results.items():
        metrics = compute_industrial_metrics(true_labels, predictions, times)
        comparison.append({
            "strategy": strategy_name,
            "ok_fpr": round(metrics.ok_false_positive_rate, 4),
            "ng_miss_rate": round(metrics.ng_miss_rate, 4),
            "micro_fpr": round(metrics.acceptable_micro_fp_rate, 4),
            "unknown_recall": round(metrics.unknown_defect_recall, 4),
            "borderline_rate": round(metrics.borderline_detection_rate, 4),
            "avg_time_ms": round(metrics.avg_inference_time_ms, 1),
            "total_images": metrics.total_images,
        })
    return comparison
