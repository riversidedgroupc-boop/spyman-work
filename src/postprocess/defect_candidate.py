"""Extraction of DefectCandidate objects from various model outputs."""

from __future__ import annotations

import cv2
import numpy as np

from src.fusion.decision_types import (
    BBoxPrediction,
    DefectCandidate,
    ModelSource,
    UnifiedPrediction,
)
from src.postprocess.connected_components import find_connected_components


def candidates_from_yolo(
    pred: UnifiedPrediction,
) -> list[DefectCandidate]:
    """Extract defect candidates from YOLO model predictions.

    Each BBoxPrediction in the YOLO output becomes one DefectCandidate.
    The bbox_xyxy coordinates are expected to be in pixel space.

    Args:
        pred: UnifiedPrediction from a YOLO model.

    Returns:
        List of DefectCandidate objects.
    """
    candidates: list[DefectCandidate] = []
    candidate_id = 0

    for bbox in pred.predictions:
        x1, y1, x2, y2 = bbox.bbox_xyxy
        w = x2 - x1
        h = y2 - y1
        area = w * h
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        aspect = max(w, h) / (min(w, h) + 1e-8)

        candidate = DefectCandidate(
            image_path=pred.image_path,
            candidate_id=candidate_id,
            source_model=ModelSource.YOLO,
            class_name=bbox.class_name,
            confidence=bbox.confidence,
            bbox_xyxy=list(bbox.bbox_xyxy),
            area_px=area,
            bbox_width=w,
            bbox_height=h,
            center_x=center_x,
            center_y=center_y,
            aspect_ratio=aspect,
            yolo_confidence=bbox.confidence,
        )
        candidates.append(candidate)
        candidate_id += 1

    return candidates


def candidates_from_anomaly(
    pred: UnifiedPrediction,
    model_source: ModelSource,
    image_width: int = 640,
    image_height: int = 640,
) -> list[DefectCandidate]:
    """Extract defect candidates from anomaly detection results.

    Uses connected components on the binary mask to isolate individual
    defect regions. If no binary mask is available, falls back to a
    single candidate covering the whole image when the anomaly score
    exceeds the threshold.

    Args:
        pred: UnifiedPrediction from an anomaly detection model.
        model_source: Which anomaly model produced the prediction.
        image_width: Image width in pixels (for mask scaling if needed).
        image_height: Image height in pixels (for mask scaling if needed).

    Returns:
        List of DefectCandidate objects.
    """
    binary_mask = pred.anomaly.binary_mask
    if binary_mask is None or (isinstance(binary_mask, np.ndarray) and binary_mask.size == 0):
        # No mask available — fall back to single candidate if score indicates anomaly
        if pred.anomaly.image_score >= pred.anomaly.threshold:
            candidate = DefectCandidate(
                image_path=pred.image_path,
                candidate_id=0,
                source_model=model_source,
                class_name="NG_unknown",
                confidence=pred.anomaly.image_score,
                bbox_xyxy=[0.0, 0.0, float(image_width), float(image_height)],
                area_px=float(image_width * image_height),
                bbox_width=float(image_width),
                bbox_height=float(image_height),
                center_x=image_width / 2.0,
                center_y=image_height / 2.0,
                aspect_ratio=float(image_width) / float(image_height),
                max_anomaly_score=pred.anomaly.image_score,
                mean_anomaly_score=pred.anomaly.image_score,
            )
            return [candidate]
        return []

    # Convert mask to numpy if it is a list
    if isinstance(binary_mask, list):
        mask_np = np.array(binary_mask, dtype=np.uint8)
    else:
        mask_np = binary_mask

    if mask_np.ndim != 2:
        return []

    # Ensure uint8
    if mask_np.dtype != np.uint8:
        mask_np = mask_np.astype(np.uint8)

    if np.count_nonzero(mask_np) == 0:
        return []

    components = find_connected_components(mask_np, min_area=4)
    candidates: list[DefectCandidate] = []

    for idx, comp in enumerate(components):
        x1, y1, x2, y2 = comp["bbox_xyxy"]
        w = x2 - x1
        h = y2 - y1
        cx, cy = comp["centroid"]
        area = comp["area_px"]
        aspect = max(w, h) / (min(w, h) + 1e-8)

        candidate = DefectCandidate(
            image_path=pred.image_path,
            candidate_id=idx,
            source_model=model_source,
            class_name="NG_unknown",
            confidence=float(pred.anomaly.image_score),
            bbox_xyxy=[float(x1), float(y1), float(x2), float(y2)],
            area_px=float(area),
            bbox_width=float(w),
            bbox_height=float(h),
            center_x=float(cx),
            center_y=float(cy),
            aspect_ratio=aspect,
            max_anomaly_score=float(pred.anomaly.image_score),
            mean_anomaly_score=float(pred.anomaly.image_score),
        )
        candidates.append(candidate)

    return candidates


def candidates_from_opencv(
    pred: UnifiedPrediction,
) -> list[DefectCandidate]:
    """Extract defect candidates from OpenCV-based model predictions.

    Similar to YOLO extraction but uses ModelSource.OPENCV.

    Args:
        pred: UnifiedPrediction from OpenCV runner.

    Returns:
        List of DefectCandidate objects.
    """
    candidates: list[DefectCandidate] = []
    candidate_id = 0

    for bbox in pred.predictions:
        x1, y1, x2, y2 = bbox.bbox_xyxy
        w = x2 - x1
        h = y2 - y1
        area = w * h
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        aspect = max(w, h) / (min(w, h) + 1e-8)

        candidate = DefectCandidate(
            image_path=pred.image_path,
            candidate_id=candidate_id,
            source_model=ModelSource.OPENCV,
            class_name=bbox.class_name,
            confidence=bbox.confidence,
            bbox_xyxy=list(bbox.bbox_xyxy),
            area_px=area,
            bbox_width=w,
            bbox_height=h,
            center_x=center_x,
            center_y=center_y,
            aspect_ratio=aspect,
        )
        candidates.append(candidate)
        candidate_id += 1

    return candidates
