"""Line scan camera abstract interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket


class LineScanDevice(ABC):
    """Unified interface for line scan cameras (Hikrobot, Basler, virtual, etc.)."""

    @staticmethod
    @abstractmethod
    def enumerate_devices() -> list[DeviceInfo]:
        """Discover available devices. Returns list of DeviceInfo."""
        ...

    @abstractmethod
    def open(self, serial_number: str) -> bool:
        """Connect to device by serial number. Return True on success."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Disconnect and release resources."""
        ...

    @abstractmethod
    def start_grabbing(self) -> bool:
        """Start line data acquisition. Return True on success."""
        ...

    @abstractmethod
    def stop_grabbing(self) -> None:
        """Stop line data acquisition."""
        ...

    @abstractmethod
    def get_status(self) -> CameraStatus:
        """Return current camera status."""
        ...

    @abstractmethod
    def set_param(self, name: str, value: object) -> None:
        """Set a camera parameter by name (e.g. 'ExposureTime', 'LineRate')."""
        ...

    @abstractmethod
    def get_param(self, name: str) -> object:
        """Get a camera parameter value."""
        ...

    @abstractmethod
    def register_line_callback(
        self, callback: Callable[[FramePacket], None]
    ) -> None:
        """Register a callback invoked for each line (or block of lines) received."""
        ...

    @abstractmethod
    def unregister_line_callback(self) -> None:
        """Remove the current line callback."""
        ...
