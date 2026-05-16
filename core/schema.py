"""Unified prediction schema for model-agnostic evaluation.

Defines ``DetectionBox``, ``ImagePrediction``, and ``ImageGroundTruth`` as the
canonical data objects consumed by the matcher, metrics, and confusion modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DetectionBox:
    """A single detection bounding box with class and confidence."""

    image_name: str
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]

    def __post_init__(self) -> None:
        if len(self.bbox) != 4:
            raise ValueError(f"bbox must have 4 numbers, got {len(self.bbox)}")
        if self.bbox[2] < self.bbox[0]:
            raise ValueError(
                f"x2 ({self.bbox[2]}) must be >= x1 ({self.bbox[0]})"
            )
        if self.bbox[3] < self.bbox[1]:
            raise ValueError(
                f"y2 ({self.bbox[3]}) must be >= y1 ({self.bbox[1]})"
            )
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(
                f"confidence must be in [0, 1], got {self.confidence}"
            )

    def area(self) -> float:
        """Return bounding box area in pixels."""
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])

    def to_dict(self) -> dict:
        return {
            "image_name": self.image_name,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": self.bbox,
        }


@dataclass
class ImagePrediction:
    """Predictions for a single image."""

    image_name: str
    detections: list[DetectionBox] = field(default_factory=list)

    def to_dataframe_rows(self) -> list[dict]:
        return [d.to_dict() for d in self.detections]


@dataclass
class ImageGroundTruth:
    """Ground truth boxes for a single image."""

    image_name: str
    boxes: list[DetectionBox] = field(default_factory=list)
