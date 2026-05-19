"""Shared adapters for Phase 3 UI modules.

These helpers keep app.py thin and normalize predictions from both Phase 1
ImageRecord objects and Phase 2 external ImagePrediction results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.schema import DetectionBox, ImagePrediction
from src.dataset.label_schema import class_name_to_id


def _class_id_from_name(class_name: str) -> int:
    cid = class_name_to_id(class_name)
    return cid if cid >= 0 else 0


def _confidence(pred: Any) -> float:
    score = getattr(pred, "score", None)
    if score is not None:
        return float(score)
    return float(getattr(pred, "confidence", 0.0))


def phase1_records_to_predictions(records: list[Any] | None) -> dict[str, list[DetectionBox]]:
    """Convert Phase 1 ImageRecord YOLO results to DetectionBox dict."""
    out: dict[str, list[DetectionBox]] = {}
    for rec in records or []:
        image_name = Path(getattr(rec, "image_path", "")).name
        if not image_name:
            continue
        detections: list[DetectionBox] = []
        yolo_result = getattr(rec, "yolo_result", None)
        for pred in getattr(yolo_result, "predictions", []) or []:
            class_name = str(getattr(pred, "class_name", "defect") or "defect")
            bbox = list(getattr(pred, "bbox_xyxy", [0, 0, 0, 0]))
            detections.append(
                DetectionBox(
                    image_name=image_name,
                    class_id=_class_id_from_name(class_name),
                    class_name=class_name,
                    confidence=_confidence(pred),
                    bbox=bbox,
                )
            )
        out[image_name] = detections
    return out


def phase1_records_to_ground_truths(records: list[Any] | None) -> dict[str, list[DetectionBox]]:
    """Convert Phase 1 ImageRecord annotations to DetectionBox dict."""
    out: dict[str, list[DetectionBox]] = {}
    for rec in records or []:
        if not getattr(rec, "has_annotation", False):
            continue
        image_name = Path(getattr(rec, "image_path", "")).name
        if not image_name:
            continue
        boxes: list[DetectionBox] = []
        for ann in getattr(rec, "annotations", []) or []:
            class_name = str(getattr(ann, "class_name", "defect") or "defect")
            boxes.append(
                DetectionBox(
                    image_name=image_name,
                    class_id=_class_id_from_name(class_name),
                    class_name=class_name,
                    confidence=1.0,
                    bbox=list(getattr(ann, "bbox_xyxy", [0, 0, 0, 0])),
                )
            )
        out[image_name] = boxes
    return out


def external_predictions_to_dict(
    predictions: list[ImagePrediction] | None,
) -> dict[str, list[DetectionBox]]:
    """Convert external ImagePrediction list to dict keyed by image name."""
    out: dict[str, list[DetectionBox]] = {}
    for pred in predictions or []:
        image_name = getattr(pred, "image_name", "")
        if image_name:
            out[image_name] = list(getattr(pred, "detections", []) or [])
    return out


def collect_phase3_predictions(
    records: list[Any] | None = None,
    external_predictions: list[ImagePrediction] | None = None,
) -> dict[str, list[DetectionBox]] | None:
    """Return the best available predictions for Phase 3 modules.

    External model predictions take precedence because they represent the latest
    explicit model inference run. Falls back to Phase 1 YOLO results.
    """
    external = external_predictions_to_dict(external_predictions)
    if external:
        return external

    phase1 = phase1_records_to_predictions(records)
    if phase1:
        return phase1
    return None


def detections_to_records(
    predictions_by_image: dict[str, list[DetectionBox]] | None,
) -> list[dict]:
    """Flatten detections into retrieval/report-friendly dict records."""
    records: list[dict] = []
    for image_name, detections in (predictions_by_image or {}).items():
        for det in detections:
            records.append(
                {
                    "image_name": image_name,
                    "class_id": det.class_id,
                    "class_name": det.class_name,
                    "confidence": det.confidence,
                    "bbox": list(det.bbox),
                }
            )
    return records
