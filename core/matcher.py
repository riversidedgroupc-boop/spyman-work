"""IoU computation and detection matching.

Consumes ``DetectionBox`` from ``core.schema`` and produces structured match
results consumed by the metrics and confusion modules.
"""

from __future__ import annotations

from core.schema import DetectionBox


def compute_iou(box_a: list[float], box_b: list[float]) -> float:
    """Intersection-over-Union between two [x1, y1, x2, y2] boxes."""
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    inter_area = (x_right - x_left) * (y_bottom - y_top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter_area

    return inter_area / union if union > 0 else 0.0


def match_detections(
    ground_truths: list[DetectionBox],
    predictions: list[DetectionBox],
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> dict:
    """Match predictions to ground truths via greedy IoU matching.

    Predictions are sorted by confidence descending.  Each ground truth and
    each prediction can be matched at most once.

    Returns
    -------
    dict
        ``matches`` (list of {gt, pred, iou, correct_class}),
        ``false_positives`` (list[DetectionBox]),
        ``false_negatives`` (list[DetectionBox]).
    """
    # Sort predictions by confidence descending
    sorted_preds = sorted(predictions, key=lambda p: p.confidence, reverse=True)

    matched_gts: set[int] = set()
    matched_preds: set[int] = set()
    matches: list[dict] = []
    false_positives: list[DetectionBox] = []
    false_negatives: list[DetectionBox] = []

    for pred_idx, pred in enumerate(sorted_preds):
        best_iou = 0.0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(ground_truths):
            if gt_idx in matched_gts:
                continue

            if class_aware and gt.class_id != pred.class_id:
                continue

            iou = compute_iou(gt.bbox, pred.bbox)
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_gt_idx >= 0:
            matches.append({
                "gt": ground_truths[best_gt_idx],
                "pred": pred,
                "iou": best_iou,
                "correct_class": ground_truths[best_gt_idx].class_id == pred.class_id,
            })
            matched_gts.add(best_gt_idx)
            matched_preds.add(pred_idx)
        else:
            false_positives.append(pred)

    # Remaining unmatched ground truths become false negatives
    for gt_idx, gt in enumerate(ground_truths):
        if gt_idx not in matched_gts:
            false_negatives.append(gt)

    return {
        "matches": matches,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
