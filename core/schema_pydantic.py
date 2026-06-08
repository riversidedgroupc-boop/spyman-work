"""Pydantic v2 models for detection box serialization boundaries.

These models coexist with the dataclass versions in ``core.schema``.  Use the
Pydantic models at I/O boundaries (API endpoints, JSON import/export, config
files) where runtime validation and serialization are needed.  Use dataclass
versions internally where allocation cost matters.

Typical usage::

    # Inbound (validate foreign data)
    box_v2 = DetectionBoxV2.model_validate(raw_dict)
    box = box_v2.to_dataclass()

    # Outbound (serialize to JSON-safe dict)
    payload = DetectionBoxV2.from_dataclass(box).model_dump()
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from core.schema import DetectionBox


class DetectionBoxV2(BaseModel):
    """Pydantic v2 model for a single detection bounding box.

    Coexists with ``core.schema.DetectionBox`` (dataclass).  This model adds
    runtime validation and JSON schema support for serialization boundaries.
    """

    image_name: str = ""
    class_id: int = 0
    class_name: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    model_config = {
        "extra": "forbid",
        "frozen": False,
    }

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: list[float]) -> list[float]:
        """Validate that bbox has 4 elements with x2 >= x1 and y2 >= y1."""
        if len(v) != 4:
            raise ValueError(f"bbox must have exactly 4 numbers, got {len(v)}")
        x1, y1, x2, y2 = v
        if x2 < x1:
            raise ValueError(f"bbox x2 ({x2}) must be >= x1 ({x1})")
        if y2 < y1:
            raise ValueError(f"bbox y2 ({y2}) must be >= y1 ({y1})")
        return v

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        """Clamp or validate confidence to [0, 1]."""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {v}")
        return v

    # ── conversion methods ──────────────────────────────────────────

    def to_dataclass(self) -> DetectionBox:
        """Convert this Pydantic model to the equivalent dataclass version."""
        return DetectionBox(
            image_name=self.image_name,
            class_id=self.class_id,
            class_name=self.class_name,
            confidence=self.confidence,
            bbox=list(self.bbox),
        )

    @classmethod
    def from_dataclass(cls, box: DetectionBox) -> DetectionBoxV2:
        """Construct a Pydantic model from the dataclass version."""
        return cls(
            image_name=box.image_name,
            class_id=box.class_id,
            class_name=box.class_name,
            confidence=box.confidence,
            bbox=list(box.bbox),
        )
