"""Defect acceptance rule engine for copper tube inspection.

Classifies detections into severity levels:
- A_severe: Must alarm
- B_general: Record and optionally alarm
- C_acceptable: Acceptable minor defect, no alarm by default
- UNKNOWN: Unknown anomaly, send to review
- LOW_CONFIDENCE: Below confidence threshold, review candidate
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.schema import DetectionBox


@dataclass
class DefectRuleConfig:
    min_alarm_size_mm: float = 0.07
    severe_size_mm: float = 0.15
    min_alarm_confidence: float = 0.25
    acceptable_class_names: list[str] = field(default_factory=list)
    severe_class_names: list[str] = field(default_factory=list)
    unknown_class_names: list[str] = field(default_factory=lambda: ["unknown", "anomaly"])
    density_window_m: float = 3.0
    density_alarm_count: int = 3


LEVEL_A = "A_severe"
LEVEL_B = "B_general"
LEVEL_C = "C_acceptable"
LEVEL_UNKNOWN = "UNKNOWN"
LEVEL_LOW_CONF = "LOW_CONFIDENCE"


def estimate_defect_size_mm(
    box: DetectionBox, pixel_size_mm: float | None = None
) -> float | None:
    """Estimate the maximum dimension of a defect in mm.

    Uses the diagonal of the bounding box as the defect size estimate.
    Returns None if pixel_size_mm is unavailable.
    """
    if pixel_size_mm is None or pixel_size_mm <= 0:
        return None
    w_px = box.bbox[2] - box.bbox[0]
    h_px = box.bbox[3] - box.bbox[1]
    diag_px = (w_px**2 + h_px**2) ** 0.5
    return diag_px * pixel_size_mm


def classify_defect_level(
    box: DetectionBox,
    config: DefectRuleConfig,
    pixel_size_mm: float | None = None,
) -> str:
    """Classify a single detection into a severity level."""
    class_lower = box.class_name.lower()

    if class_lower in [n.lower() for n in config.unknown_class_names]:
        return LEVEL_UNKNOWN

    if box.confidence < config.min_alarm_confidence:
        return LEVEL_LOW_CONF

    size_mm = estimate_defect_size_mm(box, pixel_size_mm)

    if class_lower in [n.lower() for n in config.severe_class_names]:
        return LEVEL_A

    if class_lower in [n.lower() for n in config.acceptable_class_names]:
        if size_mm is not None:
            if size_mm >= config.severe_size_mm:
                return LEVEL_A
            if size_mm < config.min_alarm_size_mm:
                return LEVEL_C
        return LEVEL_B

    # Default: use size-based classification
    if size_mm is not None:
        if size_mm >= config.severe_size_mm:
            return LEVEL_A
        if size_mm < config.min_alarm_size_mm:
            return LEVEL_C

    return LEVEL_B


def apply_defect_rules(
    predictions_by_image: dict[str, list[DetectionBox]],
    config: DefectRuleConfig,
    pixel_size_mm: float | None = None,
) -> dict:
    """Apply defect rules to all predictions across images.

    Returns a dict with image_name -> list of dicts with level classification.
    """
    results: dict[str, list[dict]] = {}

    for img_name, preds in predictions_by_image.items():
        classified: list[dict] = []
        for box in preds:
            level = classify_defect_level(box, config, pixel_size_mm)
            classified.append({
                "image_name": box.image_name,
                "class_id": box.class_id,
                "class_name": box.class_name,
                "confidence": box.confidence,
                "bbox": box.bbox,
                "level": level,
                "estimated_size_mm": estimate_defect_size_mm(box, pixel_size_mm),
            })
        results[img_name] = classified

    return results


def summarize_defect_levels(rule_results: dict) -> dict:
    """Count defects by level across all images."""
    summary: dict[str, int] = {
        LEVEL_A: 0,
        LEVEL_B: 0,
        LEVEL_C: 0,
        LEVEL_UNKNOWN: 0,
        LEVEL_LOW_CONF: 0,
    }
    total = 0
    for img_name, items in rule_results.items():
        for item in items:
            level = item["level"]
            if level in summary:
                summary[level] += 1
            total += 1

    return {"total": total, "by_level": summary}
