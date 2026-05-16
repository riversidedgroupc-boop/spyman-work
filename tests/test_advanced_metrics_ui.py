"""Regression tests for advanced metrics data conversion."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.fusion.decision_types import BBoxPrediction, ImageRecord, UnifiedPrediction
from ui.advanced_metrics import (
    _build_gt_from_records,
    _build_pred_from_phase1,
)


def test_ground_truth_records_convert_normalized_boxes_to_pixels(tmp_path):
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (200, 100)).save(image_path)
    record = ImageRecord(
        image_path=str(image_path),
        true_label="NG_scratch",
        has_annotation=True,
        annotations=[
            BBoxPrediction(
                class_name="NG_scratch",
                confidence=1.0,
                bbox_xyxy=[0.25, 0.25, 0.75, 0.75],
            )
        ],
    )

    result = _build_gt_from_records([record])

    box = result["sample.jpg"][0]
    assert box.class_id == 3
    assert box.class_name == "NG_scratch"
    assert box.bbox == [50.0, 25.0, 150.0, 75.0]


def test_phase1_predictions_map_class_names_to_ids():
    record = ImageRecord(
        image_path="sample.jpg",
        yolo_result=UnifiedPrediction(
            image_path="sample.jpg",
            model_name="yolo",
            predictions=[
                BBoxPrediction(
                    class_name="NG_pit",
                    confidence=0.8,
                    bbox_xyxy=[10, 20, 30, 40],
                    score=0.9,
                )
            ],
        ),
    )

    result = _build_pred_from_phase1([record])

    box = result["sample.jpg"][0]
    assert box.class_id == 4
    assert box.class_name == "NG_pit"
    assert box.confidence == 0.9

