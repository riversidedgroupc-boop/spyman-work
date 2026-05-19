"""Base camera adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCameraAdapter(ABC):
    adapter_name: str = "base"

    @abstractmethod
    def list_devices(self) -> list[dict]:
        """Return list of available devices: [{"id": ..., "name": ...}]."""
        ...

    @abstractmethod
    def connect(self, config: dict) -> bool:
        """Connect to camera with config dict. Return True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def start_acquisition(self) -> None:
        """Start continuous frame acquisition (aliased as start_grabbing)."""
        ...

    @abstractmethod
    def stop_acquisition(self) -> None:
        """Stop continuous frame acquisition (aliased as stop_grabbing)."""
        ...

    @abstractmethod
    def get_frame(self):
        """Return next frame as numpy array (H,W,C BGR), or None if no frame."""
        ...

    @abstractmethod
    def get_status(self) -> dict:
        """Return {"connected": bool, "acquiring": bool, "fps": float, ...}."""
        ...

    def start_grabbing(self) -> None:
        """Alias for start_acquisition (V6 naming convention)."""
        self.start_acquisition()

    def stop_grabbing(self) -> None:
        """Alias for stop_acquisition (V6 naming convention)."""
        self.stop_acquisition()

    def set_exposure(self, exposure_us: float) -> None:
        """Set exposure time in microseconds. Default no-op."""

    def set_gain(self, gain_db: float) -> None:
        """Set gain in dB. Default no-op."""

    def set_trigger_mode(self, mode: str) -> None:
        """Set trigger mode (continuous, external, software). Default no-op."""

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        """Set region of interest. Default no-op."""
