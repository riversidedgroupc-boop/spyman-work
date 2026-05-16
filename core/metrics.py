"""Detection evaluation metrics: PR curve, AP, mAP.

All functions consume ``DetectionBox`` from ``core.schema`` via the matcher.
"""

from __future__ import annotations

import numpy as np

from core.schema import DetectionBox
from core.matcher import match_detections


def build_pr_curve(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    class_id: int,
    iou_threshold: float = 0.5,
) -> dict:
    """Build precision-recall data for a single class.

    Returns
    -------
    dict
        Keys: ``precision`` (list[float]), ``recall`` (list[float]),
        ``thresholds`` (list[float]), ``ap`` (float).
    """
    # Collect all predictions for this class across images
    all_preds: list[tuple[DetectionBox, str]] = []
    for img_name, preds in predictions_by_image.items():
        for p in preds:
            if p.class_id == class_id:
                all_preds.append((p, img_name))

    # Sort by confidence descending
    all_preds.sort(key=lambda x: x[0].confidence, reverse=True)

    # Count total ground truths for this class
    total_gt = 0
    for img_name, gts in ground_truths_by_image.items():
        for gt in gts:
            if gt.class_id == class_id:
                total_gt += 1

    if total_gt == 0:
        return {
            "precision": [],
            "recall": [],
            "thresholds": [],
            "ap": 0.0,
        }

    tp = np.zeros(len(all_preds), dtype=np.float64)
    fp = np.zeros(len(all_preds), dtype=np.float64)
    matched_gts_per_image: dict[str, set[int]] = {}

    for i, (pred, img_name) in enumerate(all_preds):
        if img_name not in matched_gts_per_image:
            matched_gts_per_image[img_name] = set()

        gts = ground_truths_by_image.get(img_name, [])
        best_iou = 0.0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(gts):
            if gt_idx in matched_gts_per_image[img_name]:
                continue
            if gt.class_id != class_id:
                continue
            from core.matcher import compute_iou

            iou = compute_iou(gt.bbox, pred.bbox)
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_gt_idx >= 0:
            tp[i] = 1
            matched_gts_per_image[img_name].add(best_gt_idx)
        else:
            fp[i] = 1

    # Cumulative sums
    tp_cum = np.cumsum(tp)
    fp_cum = np.cumsum(fp)

    # Precision and recall at each threshold
    precisions = tp_cum / (tp_cum + fp_cum + 1e-10)
    recalls = tp_cum / total_gt

    # Interpolated all-point AP (COCO-style)
    # Make precision monotonically decreasing from right
    prec_interp = precisions.copy()
    for i in range(len(prec_interp) - 2, -1, -1):
        prec_interp[i] = max(prec_interp[i], prec_interp[i + 1])

    # AP: area under interpolated PR curve using recall deltas
    ap = 0.0
    prev_recall = 0.0
    for i in range(len(recalls)):
        if recalls[i] != prev_recall:
            ap += prec_interp[i] * (recalls[i] - prev_recall)
            prev_recall = recalls[i]

    return {
        "precision": prec_interp.tolist(),
        "recall": recalls.tolist(),
        "thresholds": [p.confidence for p, _ in all_preds],
        "ap": float(ap),
    }


def compute_ap(recall: list[float], precision: list[float]) -> float:
    """Compute Average Precision from recall and precision arrays.

    Uses the all-point interpolated method.  Precision should already be
    monotonically decreasing (interpolated) if calling directly.
    """
    if not recall or not precision:
        return 0.0

    # Ensure precision is interpolated
    p = np.array(precision, dtype=np.float64)
    for i in range(len(p) - 2, -1, -1):
        p[i] = max(p[i], p[i + 1])

    r = np.array(recall, dtype=np.float64)
    ap = 0.0
    prev_r = 0.0
    for i in range(len(r)):
        if r[i] != prev_r:
            ap += p[i] * (r[i] - prev_r)
            prev_r = r[i]
    return float(ap)


def compute_map(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    class_ids: list[int],
    iou_thresholds: list[float] | None = None,
) -> dict:
    """Compute mAP across classes and IoU thresholds.

    Parameters
    ----------
    iou_thresholds:
        List of IoU thresholds.  Defaults to ``[0.5]`` for mAP@0.5.
        Use ``[0.50, 0.55, ..., 0.95]`` for mAP@0.5:0.95.

    Returns
    -------
    dict
        ``map``, ``map_50``, ``per_class``, ``thresholds``.
    """
    if iou_thresholds is None:
        iou_thresholds = [0.5]

    per_class: dict[int, dict] = {}
    threshold_results: dict[float, float] = {}

    for iou_thr in iou_thresholds:
        class_aps = []
        for cid in class_ids:
            pr_data = build_pr_curve(
                ground_truths_by_image,
                predictions_by_image,
                class_id=cid,
                iou_threshold=iou_thr,
            )
            ap_val = pr_data["ap"]
            class_aps.append(ap_val)

            if iou_thr == 0.5:
                # Collect extra per-class details at IoU 0.5
                num_gt = 0
                num_pred = 0
                for gts in ground_truths_by_image.values():
                    num_gt += sum(1 for b in gts if b.class_id == cid)
                for preds in predictions_by_image.values():
                    num_pred += sum(1 for b in preds if b.class_id == cid)
                per_class[cid] = {
                    "ap": ap_val,
                    "ap50": ap_val,
                    "num_gt": num_gt,
                    "num_predictions": num_pred,
                }

        mAP_at_thr = float(np.mean(class_aps)) if class_aps else 0.0
        threshold_results[round(iou_thr, 2)] = mAP_at_thr

    map_50 = threshold_results.get(0.5, 0.0)

    # Overall mAP (average across thresholds)
    all_aps_flat = list(threshold_results.values())
    overall_map = float(np.mean(all_aps_flat)) if all_aps_flat else 0.0

    # Also compute per-class AP at each threshold for full mAP per class
    for cid in class_ids:
        aps = []
        for iou_thr in iou_thresholds:
            pr_data = build_pr_curve(
                ground_truths_by_image,
                predictions_by_image,
                class_id=cid,
                iou_threshold=iou_thr,
            )
            aps.append(pr_data["ap"])
        if cid in per_class:
            per_class[cid]["ap"] = float(np.mean(aps)) if aps else 0.0

    return {
        "map": overall_map,
        "map_50": map_50,
        "per_class": per_class,
        "thresholds": threshold_results,
    }
