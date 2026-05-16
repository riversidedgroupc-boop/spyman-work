"""General classification and detection metrics."""

from __future__ import annotations


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    """Compute overall accuracy."""
    if len(y_true) == 0:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def precision_recall_f1(y_true: list[str], y_pred: list[str], positive_class: str) -> dict[str, float]:
    """Compute precision, recall, and F1 for a given positive class."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive_class and p == positive_class)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != positive_class and p == positive_class)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == positive_class and p != positive_class)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def confusion_matrix_data(
    y_true: list[str], y_pred: list[str], labels: list[str]
) -> dict[str, dict[str, int]]:
    """Build a nested confusion matrix: {true_label: {pred_label: count}}."""
    matrix: dict[str, dict[str, int]] = {label: {lbl: 0 for lbl in labels} for label in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix
