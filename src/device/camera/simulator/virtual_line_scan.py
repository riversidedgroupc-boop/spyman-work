"""Virtual line scan camera — generates synthetic line data for development/testing.

Simulates a line scan camera producing 2048-pixel-wide lines with optional defects.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Thread

import numpy as np

from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import CameraStatus, DeviceInfo, FramePacket


class VirtualLineScanCamera(LineScanDevice):
    """Simulated line scan camera with configurable width, line rate, and defects."""

    def __init__(self, width: int = 2048, line_rate: float = 20000.0) -> None:
        self._width = width
        self._line_rate = line_rate
        self._connected = False
        self._grabbing = False
        self._serial = f"VIRTUAL_{id(self):08X}"
        self._line_count = 0
        self._callback: Callable[[FramePacket], None] | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()
        self._params: dict[str, object] = {
            "ExposureTime": 20.0,
            "Gain": 0.0,
            "LineRate": line_rate,
            "PixelFormat": "Mono8",
            "Width": width,
            "TriggerMode": "Off",
            "TriggerSource": "Line0",
        }

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]:
        return [
            DeviceInfo(
                vendor="Virtual",
                model="VirtualLineScan-2048",
                serial_number="VIRTUAL_00000001",
                ip_address="127.0.0.1",
                mac_address="00:00:00:00:00:01",
                transport_layer="Virtual",
                user_defined_name="Virtual Line Scan Camera",
            )
        ]

    def open(self, serial_number: str) -> bool:
        self._serial = serial_number
        self._connected = True
        self._line_count = 0
        return True

    def close(self) -> None:
        self.stop_grabbing()
        self._connected = False

    def start_grabbing(self) -> bool:
        if not self._connected:
            return False
        self._grabbing = True
        self._stop_event.clear()
        self._thread = Thread(target=self._acquisition_loop, daemon=True)
        self._thread.start()
        return True

    def stop_grabbing(self) -> None:
        self._grabbing = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id="Camera_Virtual",
            vendor="Virtual",
            model="VirtualLineScan-2048",
            serial_number=self._serial,
            ip_address="127.0.0.1",
            connected=self._connected,
            grabbing=self._grabbing,
            line_rate=self._line_rate,
            received_line_count=self._line_count,
        )

    def set_param(self, name: str, value: object) -> None:
        self._params[name] = value
        if name == "LineRate":
            self._line_rate = float(value)

    def get_param(self, name: str) -> object:
        return self._params.get(name)

    def register_line_callback(
        self, callback: Callable[[FramePacket], None]
    ) -> None:
        self._callback = callback

    def unregister_line_callback(self) -> None:
        self._callback = None

    def _acquisition_loop(self) -> None:
        """Generate synthetic line data at the configured line rate."""
        interval = 1.0 / max(self._line_rate, 1.0)
        line_data = np.zeros((1, self._width), dtype=np.uint8)

        while not self._stop_event.is_set():
            # Generate synthetic line with random noise
            line_data[0, :] = np.random.randint(0, 5, size=self._width, dtype=np.uint8)

            # Occasionally inject a synthetic "defect" pattern
            if self._line_count % 500 == 0 and self._line_count > 0:
                defect_start = self._width // 2 - 50
                defect_end = self._width // 2 + 50
                line_data[0, defect_start:defect_end] = np.clip(
                    np.random.normal(180, 30, defect_end - defect_start), 0, 255
                ).astype(np.uint8)

            self._line_count += 1

            if self._callback is not None:
                packet = FramePacket(
                    camera_id=self._serial,
                    frame_id=self._line_count,
                    timestamp_ns=time.time_ns(),
                    encoder_count=self._line_count,
                    width=self._width,
                    height=1,
                    pixel_format="Mono8",
                    line_data=line_data.copy(),
                )
                try:
                    self._callback(packet)
                except Exception:
                    pass

            time.sleep(interval)
