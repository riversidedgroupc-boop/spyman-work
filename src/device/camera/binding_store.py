"""Camera binding persistence — SN/MAC-based camera slot assignment survives restart."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SLOT_IDS = [f"camera_{i:02d}" for i in range(1, 7)]  # camera_01 ~ camera_06


@dataclass
class CameraBinding:
    """Binding between a physical camera (identified by SN) and a logical slot."""

    camera_slot: str  # "camera_01" ~ "camera_06"
    enabled: bool = True
    role: str = "spare"  # "top", "left", "right", "spare"
    serial_number: str = ""  # Primary key for binding
    mac_address: str = ""  # Fallback key
    ip_address: str = ""  # Informational
    model: str = ""  # Informational
    param_profile: str = ""  # Path to param template file

    def __post_init__(self) -> None:
        if self.camera_slot not in SLOT_IDS:
            raise ValueError(f"Invalid camera_slot: {self.camera_slot}, must be one of {SLOT_IDS}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CameraBinding:
        return cls(
            camera_slot=data.get("camera_slot", ""),
            enabled=data.get("enabled", True),
            role=data.get("role", "spare"),
            serial_number=data.get("serial_number", ""),
            mac_address=data.get("mac_address", ""),
            ip_address=data.get("ip_address", ""),
            model=data.get("model", ""),
            param_profile=data.get("param_profile", ""),
        )


class BindingStore:
    """Persistent storage for camera slot ↔ physical device bindings.

    Stores bindings in a JSON file so camera assignments survive app restart.
    Bindings are keyed primarily by serial number (stable across power cycles),
    with MAC address as a fallback identifier.
    """

    DEFAULT_FILENAME = "camera_binding.json"

    def __init__(self, config_dir: str | None = None) -> None:
        if config_dir is None:
            config_dir = os.path.join(os.getcwd(), "config")
        self._config_dir = Path(config_dir)
        self._file_path = self._config_dir / self.DEFAULT_FILENAME
        self._bindings: dict[str, CameraBinding] = {}  # slot → binding

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def load_all(self) -> list[CameraBinding]:
        """Load all bindings from disk. Returns empty list if file doesn't exist."""
        self._bindings.clear()
        if not self._file_path.exists():
            logger.info("No binding file at %s, starting fresh", self._file_path)
            return []

        try:
            data = json.loads(self._file_path.read_text(encoding="utf-8"))
            cameras = data.get("cameras", [])
            for entry in cameras:
                binding = CameraBinding.from_dict(entry)
                self._bindings[binding.camera_slot] = binding
            logger.info("Loaded %d camera bindings from %s", len(self._bindings), self._file_path)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse binding file: %s", e)
            return []

        return list(self._bindings.values())

    def save_all(self, bindings: list[CameraBinding] | None = None) -> None:
        """Save bindings to disk. If bindings arg is None, saves current in-memory state."""
        if bindings is not None:
            for b in bindings:
                self._bindings[b.camera_slot] = b

        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": "1.0",
            "cameras": [b.to_dict() for b in self._bindings.values()],
        }
        tmp_path = self._file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(self._file_path)
        logger.info("Saved %d camera bindings to %s", len(self._bindings), self._file_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_binding(self, slot: str) -> CameraBinding | None:
        """Get binding for a specific slot, or None."""
        return self._bindings.get(slot)

    def set_binding(self, binding: CameraBinding) -> None:
        """Set or update a binding for the given slot."""
        self._bindings[binding.camera_slot] = binding

    def remove_binding(self, slot: str) -> None:
        """Remove binding for a slot."""
        self._bindings.pop(slot, None)

    def get_serial_map(self) -> dict[str, str]:
        """Return {slot: serial_number} for all enabled bindings with a serial."""
        return {
            slot: b.serial_number
            for slot, b in self._bindings.items()
            if b.enabled and b.serial_number
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def find_by_serial(self, serial_number: str) -> CameraBinding | None:
        """Find the binding (if any) that matches a given serial number."""
        for b in self._bindings.values():
            if b.serial_number == serial_number:
                return b
        return None

    def find_by_mac(self, mac_address: str) -> CameraBinding | None:
        """Find the binding (if any) that matches a given MAC address."""
        for b in self._bindings.values():
            if b.mac_address.upper() == mac_address.upper():
                return b
        return None

    @property
    def bindings(self) -> dict[str, CameraBinding]:
        """Return the current in-memory bindings dict."""
        return dict(self._bindings)
