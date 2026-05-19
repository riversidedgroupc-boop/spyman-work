"""Encoder reader abstraction for real-time position tracking.

Supports: simulated (internal clock), RS422 (serial port stub for V7).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from threading import Lock


class BaseEncoderReader(ABC):
    """Abstract encoder that returns current meter position."""

    @abstractmethod
    def connect(self, config: dict) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def read_position_meter(self) -> float:
        """Return current position in meters."""
        ...

    @abstractmethod
    def read_speed_mpm(self) -> float:
        """Return current line speed in meters per minute."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset position counter to zero."""
        ...

    @abstractmethod
    def get_status(self) -> dict:
        ...


class SimulatedEncoderReader(BaseEncoderReader):
    """Simulated encoder driven by internal clock and configurable speed."""

    def __init__(self):
        self._speed_mpm: float = 80.0
        self._pulses_per_meter: float = 1000.0
        self._position: float = 0.0
        self._start_time: float = 0.0
        self._connected: bool = False
        self._lock = Lock()

    def connect(self, config: dict) -> bool:
        self._speed_mpm = float(config.get("line_speed_mpm", 80.0))
        self._pulses_per_meter = float(config.get("pulses_per_meter", 1000.0))
        self._position = 0.0
        self._start_time = time.time()
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def read_position_meter(self) -> float:
        with self._lock:
            if not self._connected:
                return self._position
            elapsed_sec = time.time() - self._start_time
            self._position = (self._speed_mpm / 60.0) * elapsed_sec
            return self._position

    def read_speed_mpm(self) -> float:
        return self._speed_mpm

    def reset(self) -> None:
        with self._lock:
            self._position = 0.0
            self._start_time = time.time()

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "position_meter": round(self.read_position_meter(), 3),
            "speed_mpm": self._speed_mpm,
            "pulses_per_meter": self._pulses_per_meter,
            "type": "simulated",
        }


class RS422EncoderReader(BaseEncoderReader):
    """RS422 encoder reader (placeholder — V7 implementation)."""

    def __init__(self):
        self._connected = False
        self._position = 0.0

    def connect(self, config: dict) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def read_position_meter(self) -> float:
        return self._position

    def read_speed_mpm(self) -> float:
        return 0.0

    def reset(self) -> None:
        self._position = 0.0

    def get_status(self) -> dict:
        return {"connected": self._connected, "position_meter": self._position, "type": "rs422"}
