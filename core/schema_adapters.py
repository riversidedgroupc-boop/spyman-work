"""Bidirectional adapters between DetectionBox and BBoxPrediction.

These converters bridge the two parallel detection box representations:
- ``core.schema.DetectionBox``  — canonical evaluation type (``bbox`` field).
- ``src.fusion.decision_types.BBoxPrediction`` — fusion pipeline type (``bbox_xyxy`` field).

All adapters are pure functions with zero side effects.  They do not mutate
their inputs and always return new objects.
"""

from __future__ import annotations

from core.schema import DetectionBox
from src.fusion.decision_types import BBoxPrediction


def bbox_prediction_to_detection_box(
    pred: BBoxPrediction,
    image_name: str = "",
    class_id: int = 0,
) -> DetectionBox:
    """Convert a BBoxPrediction (fusion type) to a DetectionBox (core type).

    Parameters
    ----------
    pred : BBoxPrediction
        Source prediction from the fusion / decision pipeline.
        Uses ``pred.bbox_xyxy`` for the bounding box.
    image_name : str
        Image name to set on the target DetectionBox (not present on BBoxPrediction).
    class_id : int
        Numeric class id to set on the target DetectionBox.

    Returns
    -------
    DetectionBox
        New DetectionBox with fields mapped from the source prediction.
    """
    return DetectionBox(
        image_name=image_name,
        class_id=class_id,
        class_name=pred.class_name,
        confidence=pred.confidence,
        bbox=list(pred.bbox_xyxy),
    )


def detection_box_to_bbox_prediction(
    box: DetectionBox,
) -> BBoxPrediction:
    """Convert a DetectionBox (core type) to a BBoxPrediction (fusion type).

    Parameters
    ----------
    box : DetectionBox
        Source detection box from the core evaluation domain.
        Uses ``box.bbox`` for the bounding box.

    Returns
    -------
    BBoxPrediction
        New BBoxPrediction with fields mapped from the source box.
        The ``type`` field is set to "bbox", ``mask`` and ``score`` are None.
    """
    return BBoxPrediction(
        type="bbox",
        class_name=box.class_name,
        confidence=box.confidence,
        bbox_xyxy=list(box.bbox),
        mask=None,
        score=None,
    )
