"""Benchmark module — compares PyTorch, ONNX, and TensorRT backends on the same
image set, measuring speed, consistency, and correctness.

Phase E deliverable.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.schema import DetectionBox, ImagePrediction


@dataclass
class BenchmarkResult:
    """Aggregate benchmark metrics for a candidate export vs its source model."""

    source_model_id: str
    candidate_export_id: str
    image_count: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    decision_match_rate: float
    mean_bbox_iou: float
    mean_confidence_delta: float
    recommended: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "source_model_id": self.source_model_id,
            "candidate_export_id": self.candidate_export_id,
            "image_count": self.image_count,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "decision_match_rate": self.decision_match_rate,
            "mean_bbox_iou": self.mean_bbox_iou,
            "mean_confidence_delta": self.mean_confidence_delta,
            "recommended": self.recommended,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> BenchmarkResult:
        return cls(
            source_model_id=str(d["source_model_id"]),
            candidate_export_id=str(d["candidate_export_id"]),
            image_count=int(d["image_count"]),
            avg_latency_ms=float(d["avg_latency_ms"]),
            p95_latency_ms=float(d["p95_latency_ms"]),
            p99_latency_ms=float(d["p99_latency_ms"]),
            decision_match_rate=float(d["decision_match_rate"]),
            mean_bbox_iou=float(d["mean_bbox_iou"]),
            mean_confidence_delta=float(d["mean_confidence_delta"]),
            recommended=bool(d["recommended"]),
        )


# ── Public API ──────────────────────────────────────────────────────────────────


def run_benchmark(
    source_model_id: str,
    candidate_export_id: str,
    image_dir: str,
    confidence: float = 0.5,
    iou: float = 0.45,
    image_size: int = 640,
) -> BenchmarkResult:
    """Run both the source model (PyTorch) and candidate export on all images.

    Parameters
    ----------
    source_model_id : str
        ``model_versions.model_id`` of the source ``.pt`` model.
    candidate_export_id : str
        ``model_export_artifacts.export_id`` of the candidate engine.
    image_dir : str
        Directory containing images to benchmark against (recursive glob).
    confidence : float
        Detection confidence threshold.
    iou : float
        NMS IoU threshold.
    image_size : int
        Input resize dimension in pixels.

    Returns
    -------
    BenchmarkResult
        Aggregated metrics comparing source and candidate backends.
    """
    from core.model_version import get_model_version
    from core.model_export import get_export_artifact
    from model_runners.backend_factory import create_runner_for_artifact
    from model_runners.yolo_runner import YoloModelRunner

    # ── 1. Look up source model ─────────────────────────────────────────────
    source_mv = get_model_version(source_model_id)
    if source_mv is None:
        raise ValueError(f"Source model version not found: {source_model_id}")
    if not source_mv.model_path:
        raise ValueError(f"Source model has no model_path: {source_model_id}")

    # ── 2. Look up candidate export ─────────────────────────────────────────
    candidate = get_export_artifact(candidate_export_id)
    if candidate is None:
        raise ValueError(f"Candidate export artifact not found: {candidate_export_id}")
    if candidate.status != "completed":
        raise ValueError(
            f"Candidate export is not completed (status={candidate.status}): "
            f"{candidate_export_id}"
        )

    # ── 3. Load images ──────────────────────────────────────────────────────
    image_paths = _load_images(image_dir)
    if not image_paths:
        raise ValueError(f"No images (.png/.jpg/.bmp) found in {image_dir}")

    # ── 4. Create source runner (always PyTorch) ────────────────────────────
    source_runner: Any = YoloModelRunner(
        model_path=source_mv.model_path,
        config={"confidence": confidence, "iou": iou, "image_size": image_size},
    )
    source_runner.load()

    # ── 5. Create candidate runner via factory ──────────────────────────────
    candidate_runner: Any = create_runner_for_artifact(
        candidate_export_id,
        confidence=confidence,
        iou=iou,
        image_size=image_size,
    )
    if candidate_runner is None:
        raise RuntimeError(
            f"Failed to create runner for candidate export: {candidate_export_id}"
        )

    # ── 6. Benchmark loop ───────────────────────────────────────────────────
    source_timings: list[float] = []
    candidate_timings: list[float] = []
    decision_matches: int = 0
    all_ious: list[float] = []
    all_conf_deltas: list[float] = []

    for img_path in image_paths:
        # Source (PyTorch)
        t0 = time.perf_counter()
        src_result = source_runner.predict_image(img_path)
        src_elapsed = (time.perf_counter() - t0) * 1000.0
        source_timings.append(src_elapsed)

        # Candidate (ONNX / TensorRT)
        t0 = time.perf_counter()
        cand_result = candidate_runner.predict_image(img_path)
        cand_elapsed = (time.perf_counter() - t0) * 1000.0
        candidate_timings.append(cand_elapsed)

        # Decision match
        if _compare_decisions(src_result, cand_result):
            decision_matches += 1

        # Detection-level matching
        pairs = _match_detections(src_result.detections, cand_result.detections)
        for det_s, det_c in pairs:
            all_ious.append(_compute_bbox_iou(det_s.bbox, det_c.bbox))
            all_conf_deltas.append(abs(det_s.confidence - det_c.confidence))

    # ── 7. Aggregate metrics ────────────────────────────────────────────────
    n = len(image_paths)
    src_avg, _src_p95, _src_p99 = _compute_latency_stats(source_timings)
    cand_avg, cand_p95, cand_p99 = _compute_latency_stats(candidate_timings)

    decision_match_rate = decision_matches / n if n > 0 else 0.0
    mean_bbox_iou = sum(all_ious) / len(all_ious) if all_ious else 0.0
    mean_confidence_delta = (
        sum(all_conf_deltas) / len(all_conf_deltas) if all_conf_deltas else 0.0
    )

    # ── 8. Recommendation ───────────────────────────────────────────────────
    recommended = (
        decision_match_rate >= 0.99
        and mean_bbox_iou >= 0.98
        and mean_confidence_delta <= 0.03
        and cand_avg < src_avg
    )

    result = BenchmarkResult(
        source_model_id=source_model_id,
        candidate_export_id=candidate_export_id,
        image_count=n,
        avg_latency_ms=round(cand_avg, 3),
        p95_latency_ms=round(cand_p95, 3),
        p99_latency_ms=round(cand_p99, 3),
        decision_match_rate=round(decision_match_rate, 6),
        mean_bbox_iou=round(mean_bbox_iou, 6),
        mean_confidence_delta=round(mean_confidence_delta, 6),
        recommended=recommended,
    )

    # ── 9. Save report ──────────────────────────────────────────────────────
    if candidate.artifact_path:
        report_dir = os.path.dirname(candidate.artifact_path)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
            report_path = os.path.join(report_dir, "benchmark_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    return result


# ── Internal helpers ────────────────────────────────────────────────────────────


def _load_images(image_dir: str) -> list[str]:
    """Recursively collect all .png / .jpg / .bmp image paths under *image_dir*.

    Returns an empty list when the directory exists but contains no matching files.
    Raises ``FileNotFoundError`` if the directory does not exist.
    """
    dir_path = Path(image_dir)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")

    extensions = {".png", ".jpg", ".jpeg", ".bmp"}
    paths = sorted(
        str(p) for p in dir_path.rglob("*") if p.suffix.lower() in extensions
    )
    return paths


def _compare_decisions(
    result_a: ImagePrediction,
    result_b: ImagePrediction,
) -> bool:
    """Return ``True`` if both results agree on OK/NG decision.

    An image is considered **NG** when it has at least one detection, **OK** otherwise.
    """
    is_ng_a = len(result_a.detections) > 0
    is_ng_b = len(result_b.detections) > 0
    return is_ng_a == is_ng_b


def _compute_bbox_iou(box_a: list[float], box_b: list[float]) -> float:
    """Compute Intersection-over-Union between two boxes ``[x1, y1, x2, y2]``."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])

    inter_w = max(0.0, xb - xa)
    inter_h = max(0.0, yb - ya)
    inter_area = inter_w * inter_h
    if inter_area == 0.0:
        return 0.0

    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0.0 else 0.0


def _match_detections(
    dets_a: list[DetectionBox],
    dets_b: list[DetectionBox],
    iou_threshold: float = 0.5,
) -> list[tuple[DetectionBox, DetectionBox]]:
    """Greedy IoU matching between two detection lists.

    For each detection in *dets_a*, find the best-matching detection in *dets_b*
    whose IoU meets or exceeds *iou_threshold*.  Each detection in *dets_b* is
    matched at most once.
    """
    if not dets_a or not dets_b:
        return []

    remaining_b: list[DetectionBox] = list(dets_b)
    pairs: list[tuple[DetectionBox, DetectionBox]] = []

    for det_a in dets_a:
        best_iou = 0.0
        best_idx = -1
        for idx, det_b in enumerate(remaining_b):
            cur_iou = _compute_bbox_iou(det_a.bbox, det_b.bbox)
            if cur_iou > best_iou:
                best_iou = cur_iou
                best_idx = idx

        if best_idx >= 0 and best_iou >= iou_threshold:
            pairs.append((det_a, remaining_b.pop(best_idx)))

    return pairs


def _compute_latency_stats(timings: list[float]) -> tuple[float, float, float]:
    """Return ``(avg, p95, p99)`` in milliseconds from a list of latency values."""
    if not timings:
        return (0.0, 0.0, 0.0)

    s = sorted(timings)
    n = len(s)
    avg = sum(s) / n
    p95_idx = max(0, math.ceil(n * 0.95) - 1)
    p99_idx = max(0, math.ceil(n * 0.99) - 1)
    return (avg, s[p95_idx], s[p99_idx])
