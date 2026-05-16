"""Draw bounding boxes and decision stamps on images."""

from __future__ import annotations

import cv2
import numpy as np

# Color scheme for different model sources
MODEL_COLORS: dict[str, tuple[int, int, int]] = {
    "yolo": (0, 255, 0),  # Green
    "patchcore": (255, 0, 0),  # Blue
    "efficientad": (0, 0, 255),  # Red
    "fastflow": (255, 255, 0),  # Cyan
    "opencv": (255, 0, 255),  # Magenta
    "fusion": (0, 255, 255),  # Yellow
    "ground_truth": (0, 165, 255),  # Orange
}

DECISION_COLORS: dict[str, tuple[int, int, int]] = {
    "OK": (0, 255, 0),
    "ACCEPTABLE_MICRO_DEFECT": (255, 255, 0),
    "SUSPECT": (0, 165, 255),
    "NG": (0, 0, 255),
}


def draw_bboxes(
    image: np.ndarray,
    bboxes: list[tuple[float, float, float, float]],
    labels: list[str] | None = None,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    show_conf: bool = True,
) -> np.ndarray:
    """Draw bounding boxes with optional labels on an image (BGR).

    Args:
        image: Input BGR image.
        bboxes: List of (x1, y1, x2, y2) bounding boxes.
        labels: Optional label strings for each box.
        color: Box and label background color (BGR).
        thickness: Line thickness in pixels.
        show_conf: If True, labels are drawn with background fill.

    Returns:
        Annotated BGR image (copy, original unchanged).
    """
    img = image.copy()

    for i, bbox in enumerate(bboxes):
        x1, y1, x2, y2 = (int(round(v)) for v in bbox)

        # Clamp to image boundaries
        h, w = img.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        # Draw bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        # Draw label if provided
        if labels and i < len(labels) and show_conf:
            label = labels[i]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_thickness = 1

            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

            # Label background
            label_y = max(y1 - th - baseline - 4, 0)
            cv2.rectangle(img, (x1, label_y), (x1 + tw, y1), color, -1)

            # Label text (white)
            cv2.putText(
                img, label, (x1, y1 - baseline - 2), font, font_scale, (255, 255, 255), font_thickness
            )

    return img


def draw_decision_stamp(
    image: np.ndarray,
    decision: str,
    reason: str = "",
) -> np.ndarray:
    """Overlay a decision banner (OK/NG/SUSPECT/ACCEPTABLE) at the top of an image.

    Args:
        image: Input BGR image.
        decision: Decision string matching a key in DECISION_COLORS.
        reason: Optional explanation text (shown at bottom-left).

    Returns:
        Annotated BGR image (copy).
    """
    img = image.copy()
    h, w = img.shape[:2]
    color = DECISION_COLORS.get(decision, (128, 128, 128))

    # Semi-transparent banner at top
    overlay = img.copy()
    banner_height = 60
    cv2.rectangle(overlay, (0, 0), (w, banner_height), color, -1)
    img = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)

    # Decision text
    cv2.putText(
        img, decision, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2
    )

    # Reason text at bottom-left
    if reason:
        truncated = reason[:80]
        cv2.putText(
            img,
            truncated,
            (10, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

    return img
