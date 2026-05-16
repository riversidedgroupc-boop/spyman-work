"""Misclassification analysis for finding error patterns."""

from __future__ import annotations

from src.dataset.label_schema import (
    ACCEPTABLE_MICRO_CLASSES,
    BORDERLINE_CLASS,
    NG_CLASSES,
    OK_CLASSES,
)
from src.fusion.decision_types import FinalDecision, ImageRecord


def analyze_misclassifications(records: list[ImageRecord]) -> list[ImageRecord]:
    """Tag each record with its error type and return only misclassified records.

    Error types:
        - OK_false_positive: true OK classified as NG or SUSPECT
        - NG_miss: true NG classified as OK or ACCEPTABLE_MICRO_DEFECT
        - acceptable_micro_fp: true OK_micro classified as NG
        - borderline: any Borderline sample (always flagged)
        - unknown_miss: true NG_unknown NOT classified as SUSPECT or NG
    """
    misclassified: list[ImageRecord] = []

    for rec in records:
        if rec.fusion_decision is None:
            continue

        true_label = rec.true_label
        pred_decision = rec.fusion_decision.final_decision.value

        # Reset misclassification flags for fresh analysis
        rec.is_misclassified = False
        rec.error_type = ""

        if true_label in OK_CLASSES and pred_decision in (
            FinalDecision.NG.value,
            FinalDecision.SUSPECT.value,
        ):
            rec.is_misclassified = True
            rec.error_type = "OK_false_positive"
            misclassified.append(rec)

        elif true_label in NG_CLASSES and pred_decision in (
            FinalDecision.OK.value,
            FinalDecision.ACCEPTABLE_MICRO_DEFECT.value,
        ):
            rec.is_misclassified = True
            rec.error_type = "NG_miss"
            misclassified.append(rec)

        elif true_label in ACCEPTABLE_MICRO_CLASSES and pred_decision == FinalDecision.NG.value:
            rec.is_misclassified = True
            rec.error_type = "acceptable_micro_fp"
            misclassified.append(rec)

        elif true_label == BORDERLINE_CLASS:
            rec.is_misclassified = True
            rec.error_type = "borderline"
            misclassified.append(rec)

        elif true_label == "NG_unknown" and pred_decision not in (
            FinalDecision.SUSPECT.value,
            FinalDecision.NG.value,
        ):
            rec.is_misclassified = True
            rec.error_type = "unknown_miss"
            misclassified.append(rec)

    return misclassified


def group_by_error_type(records: list[ImageRecord]) -> dict[str, list[ImageRecord]]:
    """Group records by error type, including model-disagreement sub-groups.

    Returns a dict with keys for each error type plus:
        - "yolo_miss_anomaly_high": YOLO missed but anomaly score is high
        - "yolo_hit_anomaly_low": YOLO detected but anomaly score is low
    """
    groups: dict[str, list[ImageRecord]] = {
        "OK_false_positive": [],
        "NG_miss": [],
        "acceptable_micro_fp": [],
        "borderline": [],
        "unknown_miss": [],
        "yolo_miss_anomaly_high": [],
        "yolo_hit_anomaly_low": [],
    }

    for rec in records:
        error_type = rec.error_type
        if error_type and error_type in groups:
            groups[error_type].append(rec)

        # Additional model-disagreement analysis
        yolo_has_detection = (
            rec.yolo_result is not None and len(rec.yolo_result.predictions) > 0
        )
        patchcore_score = (
            rec.patchcore_result.anomaly.image_score
            if rec.patchcore_result is not None and rec.patchcore_result.anomaly is not None
            else 0.0
        )
        # Also check efficientad and fastflow scores if patchcore is not available
        efficientad_score = (
            rec.efficientad_result.anomaly.image_score
            if rec.efficientad_result is not None and rec.efficientad_result.anomaly is not None
            else 0.0
        )
        fastflow_score = (
            rec.fastflow_result.anomaly.image_score
            if rec.fastflow_result is not None and rec.fastflow_result.anomaly is not None
            else 0.0
        )
        max_anomaly = max(patchcore_score, efficientad_score, fastflow_score)

        anomaly_high = max_anomaly >= 0.65

        if not yolo_has_detection and anomaly_high:
            groups["yolo_miss_anomaly_high"].append(rec)
        if yolo_has_detection and not anomaly_high:
            groups["yolo_hit_anomaly_low"].append(rec)

    return groups


def summarize_error_distribution(
    records: list[ImageRecord],
) -> dict[str, int]:
    """Return a flat count of records per error type."""
    distribution: dict[str, int] = {}
    for rec in records:
        err = rec.error_type or "correct"
        distribution[err] = distribution.get(err, 0) + 1
    return distribution
