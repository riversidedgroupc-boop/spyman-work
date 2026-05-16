"""Morphological operations for binary mask post-processing."""

from __future__ import annotations

import cv2
import numpy as np


def _get_kernel(kernel_size: int) -> np.ndarray:
    """Create a rectangular structuring element."""
    k = int(kernel_size)
    if k < 1:
        k = 1
    return cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))


def apply_morphology(
    mask: np.ndarray,
    operation: str = "open",
    kernel_size: int = 3,
    iterations: int = 1,
) -> np.ndarray:
    """Apply a morphological operation to a binary mask.

    Args:
        mask: Binary mask (uint8 or bool).
        operation: One of 'open', 'close', 'dilate', 'erode'.
        kernel_size: Size of the rectangular structuring element.
        iterations: Number of times to apply the operation.

    Returns:
        Processed mask as uint8 numpy array.
    """
    if mask.dtype != np.uint8:
        mask_u8 = mask.astype(np.uint8)
    else:
        mask_u8 = mask

    kernel = _get_kernel(kernel_size)
    op = operation.lower()

    if op == "open":
        return cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel, iterations=iterations)
    elif op == "close":
        return cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=iterations)
    elif op == "dilate":
        return cv2.dilate(mask_u8, kernel, iterations=iterations)
    elif op == "erode":
        return cv2.erode(mask_u8, kernel, iterations=iterations)
    else:
        raise ValueError(
            f"Unknown operation '{operation}'. "
            f"Supported: 'open', 'close', 'dilate', 'erode'."
        )


def clean_mask(
    mask: np.ndarray,
    min_area: int = 8,
    open_kernel: int = 3,
) -> np.ndarray:
    """Clean a binary mask by opening and removing small connected components.

    Args:
        mask: Binary mask (uint8 or bool).
        min_area: Minimum area for connected components to retain.
        open_kernel: Kernel size for the morphological opening.

    Returns:
        Cleaned mask as uint8 numpy array.
    """
    if mask.dtype != np.uint8:
        mask_u8 = mask.astype(np.uint8)
    else:
        mask_u8 = mask.copy()

    # Step 1: morphological opening to remove noise
    if open_kernel > 0:
        mask_u8 = apply_morphology(mask_u8, operation="open", kernel_size=open_kernel)

    # Step 2: remove small connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask_u8, connectivity=8
    )

    cleaned = np.zeros_like(mask_u8)
    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area >= min_area:
            cleaned[labels == label_idx] = 255

    return cleaned


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill holes in a binary mask using contour-based flood fill.

    Args:
        mask: Binary mask (uint8 or bool).

    Returns:
        Mask with holes filled as uint8 numpy array.
    """
    if mask.dtype != np.uint8:
        mask_u8 = mask.astype(np.uint8)
    else:
        mask_u8 = mask.copy()

    # Invert so holes become foreground, then flood-fill from the border
    inverted = cv2.bitwise_not(mask_u8)

    h, w = mask_u8.shape[:2]
    filled_inverted = inverted.copy()
    mask_flood = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(filled_inverted, mask_flood, (0, 0), 0)

    # The parts of inverted that survived the flood fill are the holes
    holes = cv2.bitwise_and(inverted, filled_inverted)

    # Add holes back to the original mask (they become foreground)
    result = cv2.bitwise_or(mask_u8, holes)

    return result
