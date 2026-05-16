"""Detection-level confusion matrix.

Builds a class-level matrix where rows are ground-truth classes and columns are
predicted classes, with ``__missed__`` and ``__background__`` sentinels.
"""

from __future__ import annotations

import pandas as pd

from core.schema import DetectionBox
from core.matcher import match_detections

MISSED_LABEL = "__missed__"
BACKGROUND_LABEL = "__background__"


def build_detection_confusion_matrix(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    class_names: dict[int, str],
    iou_threshold: float = 0.5,
) -> pd.DataFrame:
    """Build a detection confusion matrix across all images.

    Rows = ground truth class,  Columns = predicted class.
    Includes ``__missed__`` column for false negatives and ``__background__``
    row for false positives.

    Parameters
    ----------
    ground_truths_by_image:
        Image name → list of ground-truth ``DetectionBox``.
    predictions_by_image:
        Image name → list of predicted ``DetectionBox``.
    class_names:
        Mapping from class_id to human-readable name.
    iou_threshold:
        IoU threshold for considering a match.

    Returns
    -------
    pd.DataFrame
        Confusion matrix with class names as row/column labels plus sentinels.
    """
    all_class_ids = set(class_names.keys())
    for gts in ground_truths_by_image.values():
        for b in gts:
            all_class_ids.add(b.class_id)
    for preds in predictions_by_image.values():
        for b in preds:
            all_class_ids.add(b.class_id)

    sorted_ids = sorted(all_class_ids)
    labels = [class_names.get(cid, f"class_{cid}") for cid in sorted_ids]

    row_labels = labels + [BACKGROUND_LABEL]
    col_labels = labels + [MISSED_LABEL]

    matrix: dict[str, dict[str, int]] = {
        rl: {cl: 0 for cl in col_labels} for rl in row_labels
    }

    all_images = set(ground_truths_by_image.keys()) | set(predictions_by_image.keys())

    for img_name in all_images:
        gts = ground_truths_by_image.get(img_name, [])
        preds = predictions_by_image.get(img_name, [])

        result = match_detections(
            gts, preds, iou_threshold=iou_threshold, class_aware=False
        )

        # Matched pairs: row = GT class, col = predicted class
        for m in result["matches"]:
            gt_label = class_names.get(m["gt"].class_id, f"class_{m['gt'].class_id}")
            pred_label = class_names.get(m["pred"].class_id, f"class_{m['pred'].class_id}")
            if gt_label in matrix and pred_label in matrix[gt_label]:
                matrix[gt_label][pred_label] += 1

        # False negatives: row = GT class, col = __missed__
        for fn in result["false_negatives"]:
            gt_label = class_names.get(fn.class_id, f"class_{fn.class_id}")
            if gt_label in matrix:
                matrix[gt_label][MISSED_LABEL] += 1

        # False positives: row = __background__, col = predicted class
        for fp in result["false_positives"]:
            pred_label = class_names.get(fp.class_id, f"class_{fp.class_id}")
            if BACKGROUND_LABEL in matrix and pred_label in matrix[BACKGROUND_LABEL]:
                matrix[BACKGROUND_LABEL][pred_label] += 1

    df = pd.DataFrame.from_dict(matrix, orient="index", dtype=int)
    return df
