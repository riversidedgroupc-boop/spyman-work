"""Encoder-to-meter position mapper."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class EncoderConfig:
    """Encoder configuration for line scan positioning."""
    enabled: bool = True
    pulses_per_revolution: int = 1000
    roller_diameter_mm: float = 100.0
    direction: int = 1
    meter_offset: float = 0.0
    zero_count: int = 0

    @property
    def pulses_per_mm(self) -> float:
        circumference_mm = math.pi * self.roller_diameter_mm
        return self.pulses_per_revolution / circumference_mm

    @property
    def mm_per_pulse(self) -> float:
        return 1.0 / max(self.pulses_per_mm, 1e-9)


class EncoderMapper:
    """Converts encoder pulse counts to meter positions."""

    def __init__(self, config: EncoderConfig | None = None) -> None:
        self._config = config or EncoderConfig()
        self._zero_count = self._config.zero_count

    def reset_zero(self, current_count: int = 0) -> None:
        self._zero_count = current_count
        self._config.zero_count = current_count

    def set_meter_offset(self, offset: float) -> None:
        self._config.meter_offset = offset

    def count_to_meter(self, encoder_count: int) -> float:
        delta = (encoder_count - self._zero_count) * self._config.direction
        return delta / max(self._config.pulses_per_mm, 1e-9) / 1000.0 + self._config.meter_offset

    def meter_to_count(self, meter: float) -> int:
        delta_m = max(meter - self._config.meter_offset, 0.0)
        return self._zero_count + int(delta_m * 1000.0 * self._config.pulses_per_mm) * self._config.direction

    def calibrate(self, known_length_mm: float, measured_pulses: int) -> float:
        ppm = measured_pulses / known_length_mm
        self._config.roller_diameter_mm = self._config.pulses_per_revolution / (ppm * math.pi)
        return ppm

    def meters_per_pixel(self, block_height: int) -> float:
        return block_height / max(self._config.pulses_per_mm, 1e-9) / 1000.0

    @property
    def config(self) -> EncoderConfig:
        return self._config
