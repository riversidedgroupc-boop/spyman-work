"""Chart generation using matplotlib (Agg backend, no GUI)."""

from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


def create_confusion_matrix_chart(
    matrix: dict[str, dict[str, int]],
    title: str = "Confusion Matrix",
) -> BytesIO:
    """Generate a confusion matrix heatmap as PNG bytes.

    Args:
        matrix: Nested dict {true_label: {pred_label: count}}.
        title: Chart title.

    Returns:
        BytesIO buffer containing PNG data, seeked to position 0.
    """
    labels = list(matrix.keys())
    n = len(labels)
    data = np.zeros((n, n), dtype=int)

    for i, true_label in enumerate(labels):
        row = matrix.get(true_label, {})
        for j, pred_label in enumerate(labels):
            data[i, j] = row.get(pred_label, 0)

    fig, ax = plt.subplots(figsize=(max(8, n * 1.2), max(6, n * 1.0)))
    im = ax.imshow(data, cmap="Blues")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)

    # Annotate each cell
    for i in range(n):
        for j in range(n):
            text_color = "white" if data[i, j] > data.max() * 0.6 else "black"
            ax.text(
                j,
                i,
                str(data[i, j]),
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold" if i == j else "normal",
                color=text_color,
            )

    plt.colorbar(im, ax=ax)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_metrics_bar_chart(
    metrics_dict: dict[str, float],
    title: str = "Metrics",
) -> BytesIO:
    """Create a horizontal bar chart for named metrics.

    Args:
        metrics_dict: {metric_name: value} where values are in [0, 1].
        title: Chart title.

    Returns:
        BytesIO buffer containing PNG data.
    """
    names = list(metrics_dict.keys())
    values = list(metrics_dict.values())

    fig, ax = plt.subplots(figsize=(10, max(3, len(names) * 0.5)))

    colors = [
        "#2ecc71" if v >= 0.8 else "#f39c12" if v >= 0.5 else "#e74c3c" for v in values
    ]
    bars = ax.barh(names, values, color=colors)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}",
            va="center",
            fontsize=9,
        )

    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Rate")
    ax.set_title(title)
    ax.invert_yaxis()  # first metric on top
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_strategy_comparison_chart(comparison: list[dict]) -> BytesIO:
    """Create a grouped bar chart comparing fusion strategies across metrics.

    Args:
        comparison: List of dicts from compute_strategy_comparison().

    Returns:
        BytesIO buffer containing PNG data.
    """
    if not comparison:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=12)
        ax.axis("off")
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    strategies = [c["strategy"] for c in comparison]
    metric_keys = [
        ("ok_fpr", "OK FPR"),
        ("ng_miss_rate", "NG Miss"),
        ("micro_fpr", "Micro FPR"),
        ("unknown_recall", "Unknown Recall"),
        ("borderline_rate", "Borderline"),
    ]

    x = np.arange(len(strategies))
    n_metrics = len(metric_keys)
    width = 0.15

    fig, ax = plt.subplots(figsize=(max(10, len(strategies) * 2), 6))
    colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db"]

    for i, ((key, label), color) in enumerate(zip(metric_keys, colors)):
        values = [c[key] for c in comparison]
        offset = (i - n_metrics / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=label, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(strategies, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Rate")
    ax.set_title("Strategy Comparison")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.set_ylim(0, 1.15)
    # Draw a horizontal line at 0.95 as visual reference for good performance
    ax.axhline(y=0.95, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_histogram(
    values: list[float],
    title: str = "Distribution",
    xlabel: str = "Value",
    bins: int = 30,
) -> BytesIO:
    """Create a histogram chart.

    Args:
        values: Numeric values to plot.
        title: Chart title.
        xlabel: X-axis label.
        bins: Number of histogram bins.

    Returns:
        BytesIO buffer containing PNG data.
    """
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(values, bins=bins, color="#4472C4", alpha=0.8, edgecolor="white")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_time_series_chart(
    times_ms: list[float],
    title: str = "Inference Time per Image",
) -> BytesIO:
    """Create a scatter/line chart of inference times.

    Args:
        times_ms: Per-image inference times in milliseconds.
        title: Chart title.

    Returns:
        BytesIO buffer containing PNG data.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(times_ms))
    ax.plot(x, times_ms, "o-", markersize=2, linewidth=0.8, color="#4472C4", alpha=0.7)
    ax.axhline(y=np.mean(times_ms), color="red", linestyle="--", linewidth=0.8,
               label=f"Mean: {np.mean(times_ms):.1f} ms")
    ax.set_xlabel("Image Index")
    ax.set_ylabel("Inference Time (ms)")
    ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
