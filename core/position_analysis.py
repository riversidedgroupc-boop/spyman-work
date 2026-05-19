"""Meter-position defect analysis for copper tube inspection.

Answers: where along the tube do defects concentrate?
Supports CSV import and image-index-based position calibration.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from core.schema import DetectionBox


def load_image_position_map(csv_path: str) -> dict[str, dict]:
    """Load image-to-meter-position mapping from CSV.

    Expected columns: image_name, meter_start, meter_end
    """
    mapping: dict[str, dict] = {}
    p = Path(csv_path)
    if not p.exists():
        return mapping
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_name = row.get("image_name", "").strip()
            if not img_name:
                continue
            try:
                meter_start = float(row.get("meter_start", 0))
                meter_end = float(row.get("meter_end", 0))
            except (ValueError, TypeError):
                meter_start = 0.0
                meter_end = 0.0
            mapping[img_name] = {
                "meter_start": meter_start,
                "meter_end": meter_end,
                "meter_mid": (meter_start + meter_end) / 2,
            }
    return mapping


def assign_detection_positions(
    predictions_by_image: dict[str, list[DetectionBox]],
    image_position_map: dict[str, dict],
) -> list[dict]:
    """Assign meter positions to every detection.

    Returns a list of positioned detection dicts.
    """
    positioned: list[dict] = []

    for img_name, preds in predictions_by_image.items():
        pos = image_position_map.get(img_name)
        meter = pos["meter_mid"] if pos else None

        for box in preds:
            positioned.append({
                "image_name": img_name,
                "meter": meter,
                "meter_start": pos["meter_start"] if pos else None,
                "meter_end": pos["meter_end"] if pos else None,
                "class_name": box.class_name,
                "class_id": box.class_id,
                "confidence": box.confidence,
                "bbox": box.bbox,
            })

    return positioned


def bin_defects_by_meter(
    positioned_detections: list[dict],
    bin_size_m: float = 1.0,
) -> pd.DataFrame:
    """Bin defects into meter intervals and return counts per bin.

    Detections with no meter position are excluded.
    """
    valid = [d for d in positioned_detections if d["meter"] is not None]
    if not valid:
        return pd.DataFrame(columns=["meter_bin", "count"])

    min_meter = min(d["meter"] for d in valid)
    max_meter = max(d["meter"] for d in valid)

    bins: dict[int, int] = {}
    for d in valid:
        bin_idx = int((d["meter"] - min_meter) / bin_size_m)
        bins[bin_idx] = bins.get(bin_idx, 0) + 1

    rows = []
    for bin_idx in sorted(bins.keys()):
        bin_start = min_meter + bin_idx * bin_size_m
        rows.append({
            "meter_bin": f"{bin_start:.1f}-{bin_start + bin_size_m:.1f}",
            "meter_start": round(bin_start, 2),
            "meter_end": round(bin_start + bin_size_m, 2),
            "count": bins[bin_idx],
        })

    return pd.DataFrame(rows)


def detect_continuous_defect_segments(
    positioned_detections: list[dict],
    max_gap_m: float = 0.5,
) -> list[dict]:
    """Group positioned detections into continuous defect segments.

    Detections within max_gap_m of each other are merged into a single segment.
    """
    valid = sorted(
        [d for d in positioned_detections if d["meter"] is not None],
        key=lambda d: d["meter"],
    )
    if not valid:
        return []

    segments: list[dict] = []
    current = {
        "start_meter": valid[0]["meter"],
        "end_meter": valid[0]["meter"],
        "defect_count": 1,
        "class_names": {valid[0]["class_name"]},
        "image_names": [valid[0]["image_name"]],
    }

    for d in valid[1:]:
        if d["meter"] - current["end_meter"] <= max_gap_m:
            current["end_meter"] = d["meter"]
            current["defect_count"] += 1
            current["class_names"].add(d["class_name"])
            current["image_names"].append(d["image_name"])
        else:
            segments.append(current)
            current = {
                "start_meter": d["meter"],
                "end_meter": d["meter"],
                "defect_count": 1,
                "class_names": {d["class_name"]},
                "image_names": [d["image_name"]],
            }

    segments.append(current)
    return segments


def summarize_position_statistics(positioned_detections: list[dict]) -> dict:
    """Compute summary statistics for positioned detections."""
    valid = [d for d in positioned_detections if d["meter"] is not None]
    total = len(positioned_detections)

    if not valid:
        return {
            "total_detections": total,
            "positioned_count": 0,
            "unpositioned_count": total,
            "meter_range": None,
            "mean_meter": None,
            "max_count_per_meter": 0,
        }

    meters = [d["meter"] for d in valid]
    class_counts: dict[str, int] = {}
    for d in valid:
        c = d["class_name"]
        class_counts[c] = class_counts.get(c, 0) + 1

    binned = bin_defects_by_meter(valid)
    max_count = int(binned["count"].max()) if not binned.empty else 0

    return {
        "total_detections": total,
        "positioned_count": len(valid),
        "unpositioned_count": total - len(valid),
        "meter_range": (min(meters), max(meters)),
        "mean_meter": sum(meters) / len(meters),
        "max_count_per_meter": max_count,
        "class_distribution": class_counts,
    }
