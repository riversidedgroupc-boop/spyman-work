"""Connected component analysis for anomaly detection masks."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


def find_connected_components(
    binary_mask: np.ndarray,
    min_area: int = 8,
) -> list[dict]:
    """Find connected components in a binary mask.

    Uses cv2.connectedComponentsWithStats for efficient analysis.

    Args:
        binary_mask: Binary mask as a 2D uint8 or bool numpy array.
            Non-zero values are treated as foreground.
        min_area: Minimum area (in pixels) for a component to be included.

    Returns:
        List of dicts, each containing:
            - bbox_xyxy: [x1, y1, x2, y2] bounding box in pixel coordinates
            - area_px: area of the component in square pixels
            - centroid: (cx, cy) centroid of the component
            - contour: contour points as Nx1x2 numpy array of ints
    """
    if binary_mask is None or not isinstance(binary_mask, np.ndarray):
        return []

    # Ensure uint8 format
    if binary_mask.dtype != np.uint8:
        mask_u8 = binary_mask.astype(np.uint8)
    else:
        mask_u8 = binary_mask

    if np.count_nonzero(mask_u8) == 0:
        return []

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask_u8, connectivity=8
    )

    results: list[dict] = []
    # stats[0] is the background; start from label 1
    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue

        x = int(stats[label_idx, cv2.CC_STAT_LEFT])
        y = int(stats[label_idx, cv2.CC_STAT_TOP])
        w = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        h = int(stats[label_idx, cv2.CC_STAT_HEIGHT])

        cx, cy = centroids[label_idx]

        # Extract contour for this component
        component_mask = (labels == label_idx).astype(np.uint8)
        contours, _ = cv2.findContours(
            component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        contour = contours[0] if contours else np.array([], dtype=np.int32)

        results.append(
            {
                "bbox_xyxy": [float(x), float(y), float(x + w), float(y + h)],
                "area_px": area,
                "centroid": (float(cx), float(cy)),
                "contour": contour,
            }
        )

    return results


def largest_component(
    binary_mask: np.ndarray,
) -> Optional[dict]:
    """Find the largest (by area) connected component in a binary mask.

    Args:
        binary_mask: Binary mask as a 2D uint8 or bool numpy array.

    Returns:
        Dict with bbox_xyxy, area_px, centroid, contour for the largest
        component, or None if the mask is empty.
    """
    components = find_connected_components(binary_mask, min_area=1)
    if not components:
        return None

    return max(components, key=lambda c: c["area_px"])


def component_count(
    binary_mask: np.ndarray,
    min_area: int = 8,
) -> int:
    """Count the number of connected components above a minimum area.

    Args:
        binary_mask: Binary mask as a 2D uint8 or bool numpy array.
        min_area: Minimum area threshold.

    Returns:
        Number of components meeting the area threshold.
    """
    components = find_connected_components(binary_mask, min_area=min_area)
    return len(components)
