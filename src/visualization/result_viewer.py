"""High-level result visualization combining all drawing functions."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.fusion.decision_types import FusionDecision, UnifiedPrediction
from src.utils.image_utils import bgr_to_rgb, load_image
from src.visualization.draw_boxes import MODEL_COLORS, draw_bboxes, draw_decision_stamp
from src.visualization.draw_heatmap import create_heatmap_overlay, draw_binary_mask


def create_result_visualization(
    image_path: str | Path,
    yolo_result: UnifiedPrediction | None = None,
    anomaly_result: UnifiedPrediction | None = None,
    opencv_result: UnifiedPrediction | None = None,
    fusion_decision: FusionDecision | None = None,
    ground_truth_boxes: list[tuple[float, float, float, float]] | None = None,
    show_heatmap: bool = True,
    show_bbox: bool = True,
    show_decision: bool = True,
) -> np.ndarray:
    """Create comprehensive visualization of all results on one image.

    Args:
        image_path: Path to the source image.
        yolo_result: YOLO detection result.
        anomaly_result: Anomaly detection result (can be any of patchcore/efficientad/fastflow).
        opencv_result: OpenCV-based detection result.
        fusion_decision: Final fusion decision.
        ground_truth_boxes: Optional ground truth bounding boxes.
        show_heatmap: If True, overlay anomaly heatmap.
        show_bbox: If True, draw detection bounding boxes.
        show_decision: If True, draw decision stamp.

    Returns:
        RGB image (H, W, 3) with all selected overlays.
    """
    img = load_image(image_path)  # BGR

    # --- heatmap / mask overlay (drawn first, underneath boxes) ---
    if show_heatmap and anomaly_result is not None and anomaly_result.anomaly is not None:
        anomaly = anomaly_result.anomaly
        if anomaly.pixel_score_map is not None:
            pixel_map = np.array(anomaly.pixel_score_map, dtype=np.float32)
            img = create_heatmap_overlay(img, pixel_map)
        if anomaly.binary_mask is not None:
            mask = np.array(anomaly.binary_mask, dtype=np.uint8)
            img = draw_binary_mask(img, mask)

    # --- ground truth boxes ---
    if ground_truth_boxes:
        gt_labels = ["GT"] * len(ground_truth_boxes)
        img = draw_bboxes(img, ground_truth_boxes, gt_labels, MODEL_COLORS["ground_truth"], thickness=2)

    # --- YOLO detections ---
    if show_bbox and yolo_result is not None:
        yolo_boxes = [tuple(p.bbox_xyxy) for p in yolo_result.predictions]
        yolo_labels = [f"{p.class_name} {p.confidence:.2f}" for p in yolo_result.predictions]
        img = draw_bboxes(img, yolo_boxes, yolo_labels, MODEL_COLORS["yolo"])

    # --- OpenCV detections ---
    if show_bbox and opencv_result is not None:
        cv_boxes = [tuple(p.bbox_xyxy) for p in opencv_result.predictions]
        cv_labels = [p.class_name for p in opencv_result.predictions]
        img = draw_bboxes(img, cv_boxes, cv_labels, MODEL_COLORS["opencv"])

    # --- decision stamp ---
    if show_decision and fusion_decision is not None:
        img = draw_decision_stamp(
            img,
            fusion_decision.final_decision.value,
            fusion_decision.reason,
        )

    return bgr_to_rgb(img)


def create_comparison_grid(
    image_path: str | Path,
    results: dict[str, UnifiedPrediction | None],
    fusion_decision: FusionDecision | None = None,
    max_cols: int = 3,
) -> np.ndarray:
    """Create a side-by-side comparison grid of different model outputs.

    The grid shows: original image, then one panel for each non-None result.
    YOLO panels show bounding boxes; anomaly panels show heatmap overlays.

    Args:
        image_path: Path to the source image.
        results: Dict mapping display name to UnifiedPrediction.
        fusion_decision: Optional fusion decision for a header panel.
        max_cols: Maximum columns in the grid.

    Returns:
        RGB image containing the tiled comparison grid.
    """
    original = load_image(image_path)  # BGR
    h, w = original.shape[:2]

    panels: list[np.ndarray] = [bgr_to_rgb(original)]  # panel 0 = original
    panel_names: list[str] = ["Original"]

    for name, result in results.items():
        if result is None:
            continue

        panel = original.copy()
        model_name = result.model_name

        # Draw prediction boxes if present
        if result.predictions:
            boxes = [tuple(p.bbox_xyxy) for p in result.predictions]
            labels = [p.class_name for p in result.predictions]
            color = MODEL_COLORS.get(model_name, MODEL_COLORS["yolo"])
            panel = draw_bboxes(panel, boxes, labels, color)

        # Draw anomaly heatmap if present
        if result.anomaly is not None and result.anomaly.pixel_score_map is not None:
            pixel_map = np.array(result.anomaly.pixel_score_map, dtype=np.float32)
            panel = create_heatmap_overlay(panel, pixel_map)

        # Add model name label
        cv2.putText(
            panel,
            name.upper(),
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            MODEL_COLORS.get(model_name, (255, 255, 255)),
            2,
        )

        panels.append(bgr_to_rgb(panel))
        panel_names.append(name)

    # Add fusion decision panel if provided
    if fusion_decision is not None:
        decision_panel = original.copy()
        decision_panel = draw_decision_stamp(
            decision_panel,
            fusion_decision.final_decision.value,
            fusion_decision.reason,
        )
        panels.append(bgr_to_rgb(decision_panel))
        panel_names.append("Fusion Decision")

    # --- layout in grid ---
    n = len(panels)
    cols = min(n, max_cols)
    rows = (n + cols - 1) // cols

    # Pad to fill grid
    while len(panels) < rows * cols:
        panels.append(np.zeros_like(panels[0]))

    grid_rows: list[np.ndarray] = []
    for r in range(rows):
        row_panels = panels[r * cols : (r + 1) * cols]

        # Resize all panels in this row to the same height
        target_h = min(p.shape[0] for p in row_panels)
        resized: list[np.ndarray] = []
        for p in row_panels:
            scale = target_h / max(p.shape[0], 1)
            new_w = int(p.shape[1] * scale)
            resized.append(cv2.resize(p, (new_w, target_h)))

        grid_rows.append(np.hstack(resized))

    return np.vstack(grid_rows)
