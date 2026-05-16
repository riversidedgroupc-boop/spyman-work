"""Unit conversion utilities for pixel-to-mm calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PixelSize:
    x: float = 0.01
    y: float = 0.01


def pixels_to_mm(px: float, pixel_size_mm: float) -> float:
    """Convert a pixel dimension to millimeters using a single-axis scale."""
    return px * pixel_size_mm


def pixels_to_mm_xy(px: float, pixel_size: PixelSize) -> tuple[float, float]:
    """Convert a pixel value to mm using separate x/y pixel sizes.

    Returns (length_in_mm_x, length_in_mm_y).
    """
    return px * pixel_size.x, px * pixel_size.y


def area_px_to_mm2(area_px: float, pixel_size: PixelSize) -> float:
    """Convert area in square pixels to square millimeters."""
    return area_px * pixel_size.x * pixel_size.y
