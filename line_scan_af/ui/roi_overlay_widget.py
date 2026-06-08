"""ROI overlay widget — displays line-scan image with ROI rectangles."""

from __future__ import annotations

import cv2
import numpy as np


def draw_roi_overlay(
    image: np.ndarray,
    center_roi: tuple[int, int, int, int] | None = None,
    left_roi: tuple[int, int, int, int] | None = None,
    right_roi: tuple[int, int, int, int] | None = None,
) -> np.ndarray:
    """Draw ROI rectangles on an image for visualization.

    Colors:
    - Center ROI: green
    - Left ROI: blue
    - Right ROI: red

    Args:
        image: 2D grayscale image.
        center_roi: (x, y, w, h) center ROI.
        left_roi: (x, y, w, h) left edge ROI.
        right_roi: (x, y, w, h) right edge ROI.

    Returns:
        BGR image (3-channel) with ROI overlays.
    """
    # Convert to BGR for colored overlays
    if len(image.shape) == 2:
        display = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        display = image.copy()

    def draw_rect(img, roi, color, label):
        if roi is None:
            return
        x, y, w, h = roi
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            img, label, (x + 4, y + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )

    draw_rect(display, center_roi, (0, 255, 0), "Center")
    draw_rect(display, left_roi, (255, 0, 0), "Left")
    draw_rect(display, right_roi, (0, 0, 255), "Right")

    return display


def render_roi_image(image: np.ndarray, rois: dict[str, tuple] | None = None) -> None:
    """Render an image with ROI overlays in Streamlit.

    Args:
        image: 2D or 3D numpy image array.
        rois: Optional dict of ROI name -> (x, y, w, h).
    """
    import streamlit as st

    roi_data = rois or {}
    overlay = draw_roi_overlay(
        image,
        center_roi=roi_data.get("center"),
        left_roi=roi_data.get("left"),
        right_roi=roi_data.get("right"),
    )
    st.image(overlay, channels="BGR", use_container_width=True)
