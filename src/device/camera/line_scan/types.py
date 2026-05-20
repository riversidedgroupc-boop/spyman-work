"""Shared types for line scan camera device layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DeviceInfo:
    """Information about a discovered camera device."""
    vendor: str = ""
    model: str = ""
    serial_number: str = ""
    ip_address: str = ""
    mac_address: str = ""
    transport_layer: str = ""  # "GigE", "USB", etc.
    user_defined_name: str = ""


@dataclass
class CameraStatus:
    """Real-time status of a connected camera."""
    camera_id: str = ""
    vendor: str = ""
    model: str = ""
    serial_number: str = ""
    ip_address: str = ""
    connected: bool = False
    grabbing: bool = False
    line_rate: float = 0.0
    received_line_count: int = 0
    dropped_line_count: int = 0
    timeout_count: int = 0
    block_count: int = 0
    last_error_code: int = 0
    last_error_message: str = ""
    fps_or_line_rate: float = 0.0
    last_frame_time: float = 0.0


@dataclass
class FramePacket:
    """A single line (or few lines) of data from a line scan camera."""
    camera_id: str = ""
    frame_id: int = 0
    timestamp_ns: int = 0
    encoder_count: int = 0
    width: int = 0
    height: int = 1  # usually 1 for line scan
    pixel_format: str = "Mono8"
    line_data: np.ndarray | None = None  # shape: (height, width)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineScanImageBlock:
    """A 2D image block stitched from consecutive line scan lines."""
    block_id: str = ""
    camera_id: str = ""
    start_frame_id: int = 0
    end_frame_id: int = 0
    start_encoder_count: int = 0
    end_encoder_count: int = 0
    start_meter: float = 0.0
    end_meter: float = 0.0
    width: int = 0
    height: int = 0
    image: np.ndarray | None = None  # shape: (height, width)
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageTile:
    """A fixed-size tile sliced from a LineScanImageBlock for model input."""
    tile_id: str = ""
    block_id: str = ""
    camera_id: str = ""
    x0: int = 0
    y0: int = 0
    width: int = 320
    height: int = 320
    image: np.ndarray | None = None  # shape: (320, 320, 3)
    meter_start: float = 0.0
    meter_end: float = 0.0
