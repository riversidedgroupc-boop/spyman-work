"""Autofocus event types for generator-based progress reporting.

Events are yielded by the autofocus orchestrator and consumed by the UI layer.
All events are immutable dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AFEvent:
    """Base event for autofocus progress reporting."""
    camera_id: str = ""


@dataclass(frozen=True)
class StageMoved(AFEvent):
    """Stage has moved to a new Z position."""
    z_mm: float = 0.0


@dataclass(frozen=True)
class ImageCaptured(AFEvent):
    """A focus sample image has been captured."""
    z_mm: float = 0.0
    image_path: str = ""


@dataclass(frozen=True)
class ScoreComputed(AFEvent):
    """Sharpness score computed for a Z position."""
    z_mm: float = 0.0
    score: float = 0.0


@dataclass(frozen=True)
class SearchPhaseDone(AFEvent):
    """A search phase (coarse/fine) has completed."""
    phase: str = ""  # "coarse" or "fine"
    best_z: float = 0.0
    best_score: float = 0.0
    sample_count: int = 0


@dataclass(frozen=True)
class CameraAFComplete(AFEvent):
    """Single-camera autofocus has completed."""
    best_z_mm: float = 0.0
    center_score: float = 0.0
    left_score: float = 0.0
    right_score: float = 0.0
    dof_check: str = ""  # PASS, WARNING, FAIL
    verify_score: float = 0.0
    status: str = "SUCCESS"


@dataclass(frozen=True)
class CameraAFFailed(AFEvent):
    """Single-camera autofocus has failed."""
    reason: str = ""
    error_type: str = ""


@dataclass(frozen=True)
class EmergencyStopped(AFEvent):
    """Emergency stop has been triggered."""
    reason: str = ""


@dataclass(frozen=True)
class AllComplete(AFEvent):
    """All cameras have completed autofocus."""
    run_id: str = ""
    success: bool = False
    camera_count: int = 0


@dataclass(frozen=True)
class ProgressUpdate(AFEvent):
    """General progress update."""
    message: str = ""
    current_step: int = 0
    total_steps: int = 0
