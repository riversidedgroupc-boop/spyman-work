"""Anomaly heatmap and binary mask overlay utilities."""

from __future__ import annotations

import cv2
import numpy as np


def create_heatmap_overlay(
    image: np.ndarray,
    anomaly_map: np.ndarray | None,
    alpha: float = 0.5,
    colormap: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """Overlay an anomaly score heatmap on an image.

    Args:
        image: Input BGR image (H, W, 3).
        anomaly_map: Single-channel anomaly score map (H_amap, W_amap), values
            can be any range — they will be normalized to [0, 255].
        alpha: Blend weight for the heatmap (0 = only image, 1 = only heatmap).
        colormap: OpenCV colormap constant.

    Returns:
        BGR image with heatmap overlay.
    """
    if anomaly_map is None:
        return image

    h, w = image.shape[:2]

    # Resize anomaly map to match image dimensions if needed
    if anomaly_map.shape[:2] != (h, w):
        anomaly_map = cv2.resize(anomaly_map.astype(np.float32), (w, h))

    # Normalize to [0, 255]
    amin = float(anomaly_map.min())
    amax = float(anomaly_map.max())
    denom = max(amax - amin, 1e-8)
    anomaly_norm = ((anomaly_map - amin) / denom * 255).astype(np.uint8)

    heatmap = cv2.applyColorMap(anomaly_norm, colormap)

    return cv2.addWeighted(image, 1.0 - alpha, heatmap, alpha, 0)


def draw_binary_mask(
    image: np.ndarray,
    mask: np.ndarray | None,
    color: tuple[int, int, int] = (0, 0, 255),
    alpha: float = 0.4,
) -> np.ndarray:
    """Overlay a binary mask on an image with a solid color.

    Args:
        image: Input BGR image (H, W, 3).
        mask: Binary mask (H_mask, W_mask), where > 0 indicates foreground.
        color: BGR color for the mask overlay.
        alpha: Blend weight for the mask (0 = only image, 1 = solid color).

    Returns:
        BGR image with mask overlay.
    """
    if mask is None:
        return image

    h, w = image.shape[:2]

    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask.astype(np.float32), (w, h))

    mask_binary = (mask > 0).astype(np.uint8)

    overlay = image.copy()
    overlay[mask_binary > 0] = color

    return cv2.addWeighted(overlay, alpha, image, 1.0 - alpha, 0)


def create_heatmap_comparison(
    image: np.ndarray,
    anomaly_maps: dict[str, np.ndarray | None],
    alpha: float = 0.5,
) -> dict[str, np.ndarray]:
    """Create heatmap overlays for multiple anomaly models.

    Args:
        image: Input BGR image.
        anomaly_maps: Dict mapping model name to its anomaly score map.
        alpha: Blend weight for all heatmaps.

    Returns:
        Dict mapping model name to the BGR image with its heatmap overlay.
    """
    results: dict[str, np.ndarray] = {}
    for name, anomaly_map in anomaly_maps.items():
        if anomaly_map is not None:
            results[name] = create_heatmap_overlay(image, anomaly_map, alpha)
        else:
            results[name] = image.copy()
    return results
