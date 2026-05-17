"""Tests for Phase 3 data adapters."""

from __future__ import annotations

from core.schema import DetectionBox, ImagePrediction
from src.fusion.decision_types import BBoxPrediction, ImageRecord, UnifiedPrediction
from ui.phase3_data import (
    collect_phase3_predictions,
    detections_to_records,
    phase1_records_to_ground_truths,
    phase1_records_to_predictions,
)


def test_phase1_predictions_use_image_path_name_not_missing_image_name():
    rec = ImageRecord(
        image_path="data/images/sample_001.jpg",
        yolo_result=UnifiedPrediction(
            predictions=[
                BBoxPrediction(
                    class_name="NG_scratch",
                    confidence=0.7,
                    score=0.8,
                    bbox_xyxy=[1, 2, 30, 40],
                )
            ]
        ),
    )

    preds = phase1_records_to_predictions([rec])

    assert list(preds.keys()) == ["sample_001.jpg"]
    assert preds["sample_001.jpg"][0].image_name == "sample_001.jpg"
    assert preds["sample_001.jpg"][0].class_name == "NG_scratch"
    assert preds["sample_001.jpg"][0].confidence == 0.8


def test_external_predictions_take_precedence_over_phase1_records():
    phase1 = ImageRecord(
        image_path="data/images/a.jpg",
        yolo_result=UnifiedPrediction(
            predictions=[BBoxPrediction(class_name="NG_pit", confidence=0.4, bbox_xyxy=[0, 0, 5, 5])]
        ),
    )
    external_box = DetectionBox("b.jpg", 3, "NG_scratch", 0.9, [0, 0, 10, 10])
    external = [ImagePrediction("b.jpg", [external_box])]

    preds = collect_phase3_predictions([phase1], external)

    assert preds == {"b.jpg": [external_box]}


def test_phase1_ground_truths_and_retrieval_records():
    rec = ImageRecord(
        image_path="data/images/a.jpg",
        has_annotation=True,
        annotations=[BBoxPrediction(class_name="NG_dent", confidence=1.0, bbox_xyxy=[1, 2, 3, 4])],
    )

    gt = phase1_records_to_ground_truths([rec])
    records = detections_to_records(gt)

    assert gt["a.jpg"][0].class_name == "NG_dent"
    assert records == [
        {
            "image_name": "a.jpg",
            "class_id": gt["a.jpg"][0].class_id,
            "class_name": "NG_dent",
            "confidence": 1.0,
            "bbox": [1, 2, 3, 4],
        }
    ]
