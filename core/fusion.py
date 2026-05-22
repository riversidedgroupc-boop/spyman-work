"""Model fusion strategy evaluation.

Evaluates how different model combination strategies perform.
Fusion modes: union, intersection, primary_plus_review, score_weighted_merge.
"""

from __future__ import annotations

from core.schema import DetectionBox
from core.matcher import compute_iou


def _merge_overlapping_boxes(
    boxes_a: list[DetectionBox],
    boxes_b: list[DetectionBox],
    iou_threshold: float = 0.5,
) -> tuple[list[DetectionBox], list[DetectionBox]]:
    """Identify unique boxes from B that don't overlap with A.

    Returns (all_boxes_from_a, non_overlapping_boxes_from_b).
    """
    non_overlap: list[DetectionBox] = []
    for bb in boxes_b:
        has_overlap = False
        for ba in boxes_a:
            if compute_iou(ba.bbox, bb.bbox) >= iou_threshold:
                has_overlap = True
                break
        if not has_overlap:
            non_overlap.append(bb)
    return boxes_a, non_overlap


def fuse_predictions_union(
    predictions_a: dict[str, list[DetectionBox]],
    predictions_b: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
) -> dict[str, list[DetectionBox]]:
    """Union: keep all detections from both models, deduplicate by IoU."""
    all_images = set(predictions_a.keys()) | set(predictions_b.keys())
    result: dict[str, list[DetectionBox]] = {}

    for img_name in all_images:
        boxes_a = predictions_a.get(img_name, [])
        boxes_b = predictions_b.get(img_name, [])
        final = list(boxes_a)
        for bb in boxes_b:
            has_overlap = any(
                compute_iou(ba.bbox, bb.bbox) >= iou_threshold for ba in boxes_a
            )
            if not has_overlap:
                final.append(bb)
        result[img_name] = final

    return result


def fuse_predictions_intersection(
    predictions_a: dict[str, list[DetectionBox]],
    predictions_b: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
) -> dict[str, list[DetectionBox]]:
    """Intersection: only keep detections confirmed by both models."""
    all_images = set(predictions_a.keys()) | set(predictions_b.keys())
    result: dict[str, list[DetectionBox]] = {}

    for img_name in all_images:
        boxes_a = predictions_a.get(img_name, [])
        boxes_b = predictions_b.get(img_name, [])
        confirmed: list[DetectionBox] = []

        for ba in boxes_a:
            for bb in boxes_b:
                if compute_iou(ba.bbox, bb.bbox) >= iou_threshold:
                    # Keep the higher-confidence box
                    confirmed.append(ba if ba.confidence >= bb.confidence else bb)
                    break

        result[img_name] = confirmed

    return result


def mark_review_candidates(
    primary_predictions: dict[str, list[DetectionBox]],
    secondary_predictions: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
) -> dict[str, list[DetectionBox]]:
    """Primary-first with secondary review: keep primary predictions,
    add secondary-only detections as review candidates (marked with
    confidence=0.0 to indicate review-needed).
    """
    all_images = set(primary_predictions.keys()) | set(secondary_predictions.keys())
    result: dict[str, list[DetectionBox]] = {}

    for img_name in all_images:
        primary = primary_predictions.get(img_name, [])
        secondary = secondary_predictions.get(img_name, [])

        final = list(primary)
        for sb in secondary:
            has_overlap = any(
                compute_iou(pb.bbox, sb.bbox) >= iou_threshold for pb in primary
            )
            if not has_overlap:
                # Mark as review candidate with zero confidence
                review_box = DetectionBox(
                    image_name=sb.image_name,
                    class_id=sb.class_id,
                    class_name=sb.class_name,
                    confidence=0.0,
                    bbox=sb.bbox,
                )
                final.append(review_box)

        result[img_name] = final

    return result


def fuse_weighted_merge(
    predictions_list: list[dict[str, list[DetectionBox]]],
    weights: list[float] | None = None,
    iou_threshold: float = 0.5,
) -> dict[str, list[DetectionBox]]:
    """Weighted score merge: average confidence scores for overlapping detections.

    If weights is None, equal weights are used.
    """
    if not predictions_list:
        return {}

    if weights is None:
        weights = [1.0] * len(predictions_list)

    total_weight = sum(weights)
    all_images: set[str] = set()
    for preds in predictions_list:
        all_images |= set(preds.keys())

    result: dict[str, list[DetectionBox]] = {}

    for img_name in all_images:
        # Collect all boxes for this image
        img_boxes: list[tuple[DetectionBox, int]] = []
        for model_idx, preds in enumerate(predictions_list):
            for box in preds.get(img_name, []):
                img_boxes.append((box, model_idx))

        # Group overlapping boxes
        merged: list[DetectionBox] = []
        used: set[int] = set()

        for i, (box_i, mi) in enumerate(img_boxes):
            if i in used:
                continue
            weighted_conf = box_i.confidence * weights[mi]
            weight_sum = weights[mi]
            group = [i]

            for j, (box_j, mj) in enumerate(img_boxes):
                if j <= i or j in used:
                    continue
                if compute_iou(box_i.bbox, box_j.bbox) >= iou_threshold:
                    weighted_conf += box_j.confidence * weights[mj]
                    weight_sum += weights[mj]
                    group.append(j)

            avg_conf = weighted_conf / weight_sum if weight_sum > 0 else 0.0
            merged.append(DetectionBox(
                image_name=img_name,
                class_id=box_i.class_id,
                class_name=box_i.class_name,
                confidence=min(avg_conf, 1.0),
                bbox=box_i.bbox,
            ))
            used.update(group)

        result[img_name] = merged

    return result


def evaluate_fusion_strategy(
    strategy_name: str,
    predictions_list: list[dict[str, list[DetectionBox]]],
    ground_truths_by_image: dict[str, list[DetectionBox]],
    config: dict | None = None,
) -> dict:
    """Evaluate a fusion strategy and return metrics.

    Returns a dict with strategy_name, fused_predictions, and metrics summary.
    """
    config = config or {}
    iou_threshold = config.get("iou_threshold", 0.5)

    if strategy_name == "union":
        if len(predictions_list) < 2:
            raise ValueError("union requires at least 2 prediction sets")
        fused = fuse_predictions_union(
            predictions_list[0], predictions_list[1], iou_threshold
        )
        # Merge remaining
        for i in range(2, len(predictions_list)):
            fused = fuse_predictions_union(fused, predictions_list[i], iou_threshold)
    elif strategy_name == "intersection":
        if len(predictions_list) < 2:
            raise ValueError("intersection requires at least 2 prediction sets")
        fused = fuse_predictions_intersection(
            predictions_list[0], predictions_list[1], iou_threshold
        )
    elif strategy_name == "primary_plus_review":
        if len(predictions_list) < 2:
            raise ValueError("primary_plus_review requires at least 2 prediction sets")
        fused = mark_review_candidates(
            predictions_list[0], predictions_list[1], iou_threshold
        )
    elif strategy_name == "score_weighted_merge":
        weights = config.get("weights", None)
        fused = fuse_weighted_merge(predictions_list, weights, iou_threshold)
    else:
        raise ValueError(f"Unknown fusion strategy: {strategy_name}")

    return {
        "strategy_name": strategy_name,
        "fused_predictions": fused,
        "num_images": len(fused),
    }
