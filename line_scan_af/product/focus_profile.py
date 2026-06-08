"""Focus result data models using Pydantic."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FocusResult(BaseModel):
    """Single-camera autofocus result."""

    camera_id: str
    stage_id: str = ""
    best_z_mm: float = 0.0
    center_score: float = 0.0
    left_score: float = 0.0
    right_score: float = 0.0
    edge_score_ratio_left: float = 0.0
    edge_score_ratio_right: float = 0.0
    dof_check: str = ""  # PASS, WARNING, FAIL
    verify_score: float = 0.0
    roi_profile: str = ""
    curve_file: str = ""
    sample_image: str = ""
    status: str = "SUCCESS"  # SUCCESS, FAILED, CANCELLED
    error: str | None = None
    updated_time: datetime = Field(default_factory=datetime.now)

    @property
    def is_successful(self) -> bool:
        return self.status == "SUCCESS"


class ProductFocusData(BaseModel):
    """Per-product focus data stored in recipe."""
    product_name: str = ""
    diameter_mm: float = 0.0
    material: str = ""
    line_scan_focus: dict[str, dict[str, Any]] = Field(default_factory=dict)


class MultiFocusResult(BaseModel):
    """Multi-camera autofocus summary."""
    run_id: str
    product_name: str = ""
    diameter_mm: float = 0.0
    success: bool = False
    results: dict[str, FocusResult] = Field(default_factory=dict)
    total_elapsed_s: float = 0.0
