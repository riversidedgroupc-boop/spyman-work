"""Anomaly detection specific metrics."""

from __future__ import annotations

import numpy as np


def compute_auroc(scores: list[float], labels: list[int]) -> float:
    """Compute image-level AUROC using sklearn.

    Returns 0.0 when all labels are the same class (undefined AUROC).
    """
    from sklearn.metrics import roc_auc_score

    unique_labels = set(labels)
    if len(unique_labels) < 2:
        return 0.0
    return float(roc_auc_score(labels, scores))


def compute_auroc_manual(scores: list[float], labels: list[int]) -> float:
    """Compute AUROC without sklearn dependency (Wilcoxon-Mann-Whitney statistic).

    Uses the pairwise comparison approach: count how many positive-negative pairs
    are correctly ordered, with 0.5 credit for ties.
    """
    scores_arr = np.array(scores, dtype=np.float64)
    labels_arr = np.array(labels, dtype=np.int32)

    pos_scores = scores_arr[labels_arr == 1]
    neg_scores = scores_arr[labels_arr == 0]

    if len(pos_scores) == 0 or len(neg_scores) == 0:
        return 0.0

    # Vectorized pairwise comparison for better performance
    # pos_scores[:, None] > neg_scores[None, :] creates an MxN boolean matrix
    pos_mat = pos_scores[:, None]  # shape (M, 1)
    neg_mat = neg_scores[None, :]  # shape (1, N)

    correct = int(np.sum(pos_mat > neg_mat))
    ties = int(np.sum(pos_mat == neg_mat))
    total_pairs = len(pos_scores) * len(neg_scores)

    return (correct + 0.5 * ties) / max(total_pairs, 1)


def anomaly_detection_rate(
    scores: list[float], labels: list[int], threshold: float
) -> dict[str, float]:
    """Compute binary detection metrics at a given anomaly score threshold.

    Returns TPR, FPR, and raw counts.
    """
    preds = [1 if s >= threshold else 0 for s in scores]
    tp = sum(1 for p, lbl in zip(preds, labels) if p == 1 and lbl == 1)
    fp = sum(1 for p, lbl in zip(preds, labels) if p == 1 and lbl == 0)
    fn = sum(1 for p, lbl in zip(preds, labels) if p == 0 and lbl == 1)
    tn = sum(1 for p, lbl in zip(preds, labels) if p == 0 and lbl == 0)

    return {
        "tpr": tp / max(tp + fn, 1),
        "fpr": fp / max(fp + tn, 1),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "threshold": threshold,
    }


def compute_optimal_threshold(
    scores: list[float], labels: list[int], n_thresholds: int = 100
) -> dict[str, float]:
    """Find the threshold that maximizes Youden's index (TPR - FPR).

    Args:
        scores: anomaly scores.
        labels: binary labels (1 = anomaly, 0 = normal).
        n_thresholds: number of candidate thresholds to evaluate.

    Returns:
        dict with optimal threshold and corresponding TPR/FPR.
    """
    if len(set(labels)) < 2:
        return {"threshold": 0.5, "tpr": 0.0, "fpr": 0.0}

    candidates = np.linspace(min(scores), max(scores), n_thresholds)
    best_threshold = 0.5
    best_youden = -1.0
    best_tpr = 0.0
    best_fpr = 0.0

    for thresh in candidates:
        metrics = anomaly_detection_rate(scores, labels, float(thresh))
        youden = metrics["tpr"] - metrics["fpr"]
        if youden > best_youden:
            best_youden = youden
            best_threshold = float(thresh)
            best_tpr = metrics["tpr"]
            best_fpr = metrics["fpr"]

    return {"threshold": best_threshold, "tpr": best_tpr, "fpr": best_fpr}
