"""Mask drawing utilities — thin re-exports from draw_heatmap for backward compatibility.

The core mask drawing functionality lives in draw_heatmap.py (draw_binary_mask).
This module provides additional mask-level operations: contour drawing and mask
difference visualization for model comparison.
"""

from __future__ import annotations

import cv2
import numpy as np


def draw_contours_from_mask(
    image: np.ndarray,
    mask: np.ndarray | None,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Extract contours from a binary mask and draw them on the image.

    Args:
        image: Input BGR image.
        mask: Binary mask (non-zero = defect region).
        color: Contour color (BGR).
        thickness: Contour line thickness (-1 for filled).

    Returns:
        Image with contours drawn (copy).
    """
    if mask is None:
        return image

    img = image.copy()
    h, w = img.shape[:2]

    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask.astype(np.float32), (w, h))

    mask_uint8 = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(img, contours, -1, color, thickness)
    return img


def draw_mask_difference(
    image: np.ndarray,
    mask_a: np.ndarray | None,
    mask_b: np.ndarray | None,
    color_a: tuple[int, int, int] = (0, 255, 0),
    color_b: tuple[int, int, int] = (255, 0, 0),
    color_both: tuple[int, int, int] = (0, 255, 255),
    alpha: float = 0.5,
) -> np.ndarray:
    """Visualize the difference between two binary masks.

    - Green: regions only in mask_a.
    - Red: regions only in mask_b.
    - Yellow: regions in both masks.

    Args:
        image: Input BGR image.
        mask_a: First binary mask.
        mask_b: Second binary mask.
        color_a: Color for mask_a-only regions.
        color_b: Color for mask_b-only regions.
        color_both: Color for overlapping regions.
        alpha: Blend opacity.

    Returns:
        Image with mask difference overlay.
    """
    if mask_a is None and mask_b is None:
        return image

    h, w = image.shape[:2]

    def _prep(m: np.ndarray | None) -> np.ndarray:
        if m is None:
            return np.zeros((h, w), dtype=np.uint8)
        if m.shape[:2] != (h, w):
            m = cv2.resize(m.astype(np.float32), (w, h))
        return (m > 0).astype(np.uint8)

    a = _prep(mask_a)
    b = _prep(mask_b)

    overlay = image.copy()
    overlay[a > 0] = color_a
    overlay[b > 0] = color_b
    overlay[(a > 0) & (b > 0)] = color_both

    return cv2.addWeighted(overlay, alpha, image, 1.0 - alpha, 0)
