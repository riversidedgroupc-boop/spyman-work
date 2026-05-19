"""Camera configuration data model and CRUD operations.

Each product spec can have 1-6 camera configs. One config per camera index.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.storage import insert, fetch_one, fetch_all, update, delete


@dataclass
class CameraConfig:
    config_id: str
    spec_id: str
    camera_index: int = 1
    camera_id: str = ""
    camera_name: str = ""
    camera_type: str = ""
    brand: str = ""
    serial_number: str = ""
    ip_address: str = ""
    adapter_type: str = "folder_watcher"
    connection_params: str = "{}"
    enabled: bool = True
    trigger_mode: str = "continuous"
    exposure_us: float | None = None
    gain_db: float | None = None
    resolution_width: int | None = None
    resolution_height: int | None = None
    pixel_size_um: float | None = None
    position_desc: str = ""
    save_ng_image: bool = True
    roi: str = "{}"
    model_binding: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not (1 <= self.camera_index <= 6):
            raise ValueError(f"camera_index must be 1-6, got {self.camera_index}")
        if not self.camera_id:
            self.camera_id = f"CAM_{self.camera_index:02d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "spec_id": self.spec_id,
            "camera_index": self.camera_index,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "camera_type": self.camera_type,
            "brand": self.brand,
            "serial_number": self.serial_number,
            "ip_address": self.ip_address,
            "adapter_type": self.adapter_type,
            "connection_params": self.connection_params,
            "enabled": 1 if self.enabled else 0,
            "trigger_mode": self.trigger_mode,
            "exposure_us": self.exposure_us,
            "gain_db": self.gain_db,
            "resolution_width": self.resolution_width,
            "resolution_height": self.resolution_height,
            "pixel_size_um": self.pixel_size_um,
            "position_desc": self.position_desc,
            "save_ng_image": 1 if self.save_ng_image else 0,
            "roi": self.roi,
            "model_binding": self.model_binding,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "CameraConfig":
        return cls(
            config_id=row["config_id"],
            spec_id=row["spec_id"],
            camera_index=int(row.get("camera_index", 1)),
            camera_id=row.get("camera_id", "") or f"CAM_{int(row.get('camera_index', 1)):02d}",
            camera_name=row.get("camera_name", ""),
            camera_type=row.get("camera_type", ""),
            brand=row.get("brand", ""),
            serial_number=row.get("serial_number", ""),
            ip_address=row.get("ip_address", ""),
            adapter_type=row.get("adapter_type", "folder_watcher"),
            connection_params=row.get("connection_params", "{}"),
            enabled=bool(row.get("enabled", 1)),
            trigger_mode=row.get("trigger_mode", "continuous"),
            exposure_us=row.get("exposure_us"),
            gain_db=row.get("gain_db"),
            resolution_width=row.get("resolution_width"),
            resolution_height=row.get("resolution_height"),
            pixel_size_um=row.get("pixel_size_um"),
            position_desc=row.get("position_desc", ""),
            save_ng_image=bool(row.get("save_ng_image", 1)),
            roi=row.get("roi", "{}"),
            model_binding=row.get("model_binding", ""),
            notes=row.get("notes", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )


def create_camera_config(spec_id: str, camera_index: int = 1, **kwargs) -> CameraConfig:
    now = datetime.now()
    config_id = now.strftime("CAMCONF_%Y%m%d_%H%M%S_%f")
    cfg = CameraConfig(
        config_id=config_id, spec_id=spec_id, camera_index=camera_index, **kwargs
    )
    insert("camera_configs", cfg.to_dict())
    return cfg


def get_camera_config(config_id: str) -> CameraConfig | None:
    row = fetch_one("camera_configs", config_id, id_column="config_id")
    return CameraConfig.from_dict(row) if row else None


def list_camera_configs(spec_id: str) -> list[CameraConfig]:
    rows = fetch_all(
        "camera_configs",
        where="spec_id = ? ORDER BY camera_index",
        params=(spec_id,),
    )
    return [CameraConfig.from_dict(r) for r in rows]


def update_camera_config(config_id: str, **fields) -> None:
    cfg = get_camera_config(config_id)
    if cfg is None:
        raise ValueError(f"CameraConfig not found: {config_id}")
    data: dict[str, Any] = {}
    for k, v in fields.items():
        if hasattr(cfg, k):
            data[k] = v
    if data:
        update("camera_configs", config_id, data, id_column="config_id")


def delete_camera_config(config_id: str) -> None:
    delete("camera_configs", config_id, id_column="config_id")


def delete_camera_configs_for_spec(spec_id: str) -> None:
    for cfg in list_camera_configs(spec_id):
        delete_camera_config(cfg.config_id)
