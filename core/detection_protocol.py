"""Shared protocol for detection box representations.

Defines ``DetectionBoxProtocol`` — a typing.Protocol that documents the common
interface shared between ``core.schema.DetectionBox`` and
``src.fusion.decision_types.BBoxPrediction``.  Both classes implement this
interface structurally (duck typing), so no explicit subclassing is required.

This protocol exists to:
1. Document the implicit contract between the two parallel box types.
2. Enable static type checking across modules that accept either type.
3. Support future consolidation toward a single canonical type in v1.0.
"""

from __future__ import annotations

from typing import Protocol


class DetectionBoxProtocol(Protocol):
    """Structural interface shared by DetectionBox and BBoxPrediction.

    Both ``core.schema.DetectionBox`` and ``src.fusion.decision_types.BBoxPrediction``
    satisfy this protocol without modification.

    Required attributes
    -------------------
    class_name : str
        Human-readable defect class label (e.g. "NG_scratch", "OK_clean").
    confidence : float
        Detection confidence in [0, 1].
    """

    class_name: str
    confidence: float

    def bbox_as_xyxy(self) -> list[float]:
        """Return the bounding box as [x1, y1, x2, y2]."""
        ...
