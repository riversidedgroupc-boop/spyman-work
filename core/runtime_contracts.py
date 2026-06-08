from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RuntimeBackend = Literal["python_runtime", "fake_cpp_runtime", "cpp_runtime", "cpp_runtime_stdio"]
CameraType = Literal["area_scan", "line_scan", "folder_watcher"]
RuntimeState = Literal["idle", "stopped", "starting", "running", "stopping", "error"]
CommandName = Literal["start", "stop", "status"]


class CameraRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: str = Field(min_length=1)
    camera_type: CameraType
    serial_number: str = ""
    ip_address: str = ""
    width: int = Field(gt=0)
    height: int = Field(default=0, ge=0)
    block_height: int = Field(default=1024, gt=0)
    pixel_format: str = "Mono8"
    exposure_us: float | None = Field(default=None, gt=0)
    gain_db: float | None = None
    line_rate: int | None = Field(default=None, gt=0)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    backend: RuntimeBackend = "python_runtime"
    cameras: list[CameraRuntimeConfig] = Field(default_factory=list)
    model_artifacts: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    iou: float = Field(default=0.45, ge=0.0, le=1.0)
    save_policy: str = "save_ng_only"
    output_dir: str = ""


class RuntimeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: CommandName
    config: RuntimeConfig | None = None


class RuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RuntimeState
    uptime_ms: int = Field(default=0, ge=0)
    fps_by_camera: dict[str, float] = Field(default_factory=dict)
    queue_size: int = Field(default=0, ge=0)
    dropped_frames: int = Field(default=0, ge=0)
    ng_count: int = Field(default=0, ge=0)
    error_code: str = ""
    error_message: str = ""


class DefectEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp_ms: int = Field(ge=0)
    meter_position: float
    defect_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_xyxy: list[float] = Field(min_length=4, max_length=4)
    image_path: str = ""
    model_version: str = ""
