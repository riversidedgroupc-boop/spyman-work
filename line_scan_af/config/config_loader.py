"""Configuration loading and validation using Pydantic v2.

All autofocus parameters must be loaded through these models — no hardcoded
values are permitted in algorithm or orchestration code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# ---- Capture config ----

class CaptureConfig(BaseModel):
    speed_mode: Literal["low_speed", "normal"] = "low_speed"
    sample_length_mm: float = Field(default=50.0, gt=0)
    fallback_row_count: int = Field(default=4096, gt=0)
    use_encoder_length: bool = True


# ---- Search config ----

class SearchConfig(BaseModel):
    use_history_first: bool = True
    history_search_range_mm: float = Field(default=2.0, gt=0)
    coarse_step_mm: float = Field(default=0.5, gt=0)
    fine_step_mm: float = Field(default=0.05, gt=0)
    full_search_z_min_mm: float = 0.0
    full_search_z_max_mm: float = 30.0


# ---- Evaluation config ----

class EvaluationConfig(BaseModel):
    main_algorithm: Literal["tenengrad", "laplacian"] = "tenengrad"
    enable_laplacian: bool = True
    enable_gray_variance: bool = False
    overexpose_threshold: int = Field(default=250, ge=0, le=255)
    overexpose_ratio_limit: float = Field(default=0.05, ge=0, le=1)
    underexpose_threshold: int = Field(default=10, ge=0, le=255)
    use_multi_roi_median: bool = True


# ---- Curve config ----

class CurveConfig(BaseModel):
    enable_quadratic_fit: bool = True
    min_focus_score: float = Field(default=100.0, gt=0)
    peak_ratio: float = Field(default=1.2, gt=1)
    verify_ratio: float = Field(default=0.85, ge=0, le=1)
    reject_peak_at_boundary: bool = True


# ---- Depth of field config ----

class DepthOfFieldConfig(BaseModel):
    enable: bool = True
    edge_score_ratio_threshold: float = Field(default=0.7, ge=0, le=1)


# ---- Top-level config ----

class AutofocusConfig(BaseModel):
    focus_mode: str = "changeover"
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    curve: CurveConfig = Field(default_factory=CurveConfig)
    depth_of_field: DepthOfFieldConfig = Field(default_factory=DepthOfFieldConfig)

    @classmethod
    def from_json(cls, path: str | Path) -> AutofocusConfig:
        """Load and validate autofocus config from a JSON file."""
        path = Path(path)
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


# ---- Camera-stage binding ----

class FocusUnitBinding(BaseModel):
    camera_id: str
    stage_id: str
    light_id: str = ""
    enabled: bool = True


class CameraStageBinding(BaseModel):
    focus_units: list[FocusUnitBinding]

    @classmethod
    def from_json(cls, path: str | Path) -> CameraStageBinding:
        path = Path(path)
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


# ---- Stage driver config ----

class StageDriverConfig(BaseModel):
    stage_driver_type: str = "mock"
    available_driver_types: list[str] = Field(default_factory=lambda: ["mock", "serial", "plc", "motion_card"])
    serial: dict = Field(default_factory=dict)
    default_motion: dict = Field(default_factory=dict)

    @classmethod
    def from_json(cls, path: str | Path) -> StageDriverConfig:
        path = Path(path)
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


# ---- Config directory helpers ----

_config_dir_candidate = Path(__file__).resolve().parent.parent.parent / "config" / "autofocus"
if _config_dir_candidate.exists():
    _CONFIG_DIR = _config_dir_candidate
else:
    _CONFIG_DIR = Path(__file__).resolve().parent  # standalone


def load_autofocus_config() -> AutofocusConfig:
    return AutofocusConfig.from_json(_CONFIG_DIR / "autofocus_config.json")


def load_camera_stage_binding() -> CameraStageBinding:
    return CameraStageBinding.from_json(_CONFIG_DIR / "camera_stage_binding.json")


def load_stage_driver_config() -> StageDriverConfig:
    return StageDriverConfig.from_json(_CONFIG_DIR / "stage_driver_config.json")
