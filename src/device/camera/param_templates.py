"""Camera parameter template management — save, load, export, import."""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMPLATE_EXT = ".json"


@dataclass
class CameraParams:
    """Full set of configurable camera parameters for a template."""

    camera_slot: str = ""
    pixel_format: str = "Mono8"
    exposure_time: float = 100.0
    gain: float = 1.0
    trigger_mode: str = "Off"
    trigger_source: str = "Line0"
    acquisition_mode: str = "Continuous"
    width: int = 2048
    block_height: int = 1024
    line_rate: int = 20000
    packet_size: int = 9000
    inter_packet_delay: int = 0
    buffer_count: int = 16
    reverse_x: bool = False
    reverse_y: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CameraParams:
        return cls(
            camera_slot=data.get("camera_slot", ""),
            pixel_format=data.get("pixel_format", "Mono8"),
            exposure_time=data.get("exposure_time", 100.0),
            gain=data.get("gain", 1.0),
            trigger_mode=data.get("trigger_mode", "Off"),
            trigger_source=data.get("trigger_source", "Line0"),
            acquisition_mode=data.get("acquisition_mode", "Continuous"),
            width=data.get("width", 2048),
            block_height=data.get("block_height", 1024),
            line_rate=data.get("line_rate", 20000),
            packet_size=data.get("packet_size", 9000),
            inter_packet_delay=data.get("inter_packet_delay", 0),
            buffer_count=data.get("buffer_count", 16),
            reverse_x=data.get("reverse_x", False),
            reverse_y=data.get("reverse_y", False),
        )

    @classmethod
    def defaults(cls, camera_slot: str = "") -> CameraParams:
        """Return factory-default parameters."""
        return cls(camera_slot=camera_slot)


class ParamTemplateManager:
    """Manages named parameter templates stored as JSON files.

    Templates are stored in a flat directory with one JSON file per template.
    Naming convention: ``<name>.json``.
    Recommended naming: ``CustomerA_Product01_Camera01_Params.json``.
    """

    DEFAULT_DIR = "camera_templates"

    def __init__(self, templates_dir: str | None = None) -> None:
        if templates_dir is None:
            templates_dir = os.path.join(os.getcwd(), "config", self.DEFAULT_DIR)
        self._dir = Path(templates_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, name: str, params: CameraParams) -> str:
        """Save a parameter set as a named template. Returns the file path."""
        filename = self._sanitize_name(name) + TEMPLATE_EXT
        path = self._dir / filename
        tmp = path.with_suffix(".tmp")
        payload = params.to_dict()
        payload["_template_name"] = name
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        logger.info("Saved param template: %s", path)
        return str(path)

    def load(self, name: str) -> CameraParams | None:
        """Load a parameter template by name. Returns None if not found."""
        filename = self._sanitize_name(name) + TEMPLATE_EXT
        path = self._dir / filename
        if not path.exists():
            logger.warning("Template not found: %s", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CameraParams.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("Failed to parse template %s: %s", path, e)
            return None

    def list_templates(self) -> list[str]:
        """List all template names (without extension)."""
        names: list[str] = []
        for f in sorted(self._dir.glob(f"*{TEMPLATE_EXT}")):
            names.append(f.stem)
        return names

    def delete(self, name: str) -> bool:
        """Delete a template by name. Returns True if deleted."""
        filename = self._sanitize_name(name) + TEMPLATE_EXT
        path = self._dir / filename
        if path.exists():
            path.unlink()
            logger.info("Deleted template: %s", path)
            return True
        return False

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_to(self, name: str, dst_path: str) -> None:
        """Export a template to an arbitrary file path."""
        filename = self._sanitize_name(name) + TEMPLATE_EXT
        src = self._dir / filename
        if not src.exists():
            raise FileNotFoundError(f"Template not found: {src}")
        shutil.copy2(src, dst_path)
        logger.info("Exported template %s to %s", name, dst_path)

    def import_from(self, src_path: str) -> str:
        """Import a template from an external file. Returns the template name."""
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        data = json.loads(src.read_text(encoding="utf-8"))
        # Validate it parses as CameraParams
        CameraParams.from_dict(data)
        name = data.get("_template_name", src.stem)
        filename = self._sanitize_name(name) + TEMPLATE_EXT
        dst = self._dir / filename
        shutil.copy2(src, dst)
        logger.info("Imported template %s from %s", name, src_path)
        return name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_defaults(camera_slot: str = "") -> CameraParams:
        """Return factory-default parameters."""
        return CameraParams.defaults(camera_slot)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Replace characters unsafe for filenames."""
        return name.replace("\\", "_").replace("/", "_").replace(":", "_")
