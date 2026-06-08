"""Hybrid retest service — run YOLO + anomaly fusion on image directories.

Phase D: batch-process images with PRODUCTION_RETEST strategy, route
UNKNOWN/NEEDS_REVIEW/SUSPECT results back to the anomaly review queue.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from core.anomaly_review import create_anomaly_review
from core.field_session import create_field_session, get_field_session
from core.hybrid_strategy import FusionConfig, HybridFusionEngine
from core.id_utils import generate_id
from core.model_version import get_model_version
from core.storage import fetch_all, insert
# NOTE: These imports from src/ represent a legitimate dependency:
# core/ evaluation modules use src/ fusion types as the canonical domain model.
# See docs/architecture.md for rationale.
from src.fusion.decision_types import (
    AnomalyResult,
    BBoxPrediction,
    FusionDecision,
    FusionStrategy,
)


# ── Image extensions ────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

# ── Config / Result dataclasses ─────────────────────────────────────

@dataclass
class HybridRetestConfig:
    project_id: str
    spec_id: str = ""
    field_session_id: str = ""
    yolo_model_id: str = ""
    anomaly_model_id: str = ""
    image_dir: str = ""
    yolo_conf_threshold: float = 0.5
    anomaly_score_threshold: float = 0.65
    anomaly_high_threshold: float = 0.85
    route_review_statuses: tuple[str, ...] = ("UNKNOWN", "NEEDS_REVIEW", "SUSPECT")


@dataclass
class HybridRetestItem:
    image_path: str
    final_decision: str
    reason: str = ""
    yolo_detection_count: int = 0
    anomaly_score: float = 0.0
    runtime_ms: float = 0.0
    review_id: str | None = None


@dataclass
class HybridRetestResult:
    run_id: str
    total_count: int = 0
    ok_count: int = 0
    ng_count: int = 0
    suspect_count: int = 0
    unknown_count: int = 0
    needs_review_count: int = 0
    items: list[HybridRetestItem] = field(default_factory=list)


# ── Runner protocol (duck-typed) ────────────────────────────────────

class FakeYoloRunner:
    """Fake YOLO runner for testing — returns empty or preset detections."""

    runner_name: str = "fake_yolo"

    def __init__(self, detections: list[BBoxPrediction] | None = None) -> None:
        self._detections = detections or []

    def predict_image(self, image_path: str) -> object:
        # Return an object with a 'detections' attribute
        class _Result:
            detections = self._detections
        return _Result()


class FakeAnomalyRunner:
    """Fake anomaly runner for testing — returns preset anomaly score."""

    runner_name: str = "fake_anomaly"

    def __init__(self, score: float = 0.0, heatmap_path: str = "") -> None:
        self._score = score
        self._heatmap_path = heatmap_path

    def predict_image(self, image_path: str) -> object:
        class _Result:
            image_score = self._score
            heatmap_path = self._heatmap_path
        return _Result()


# ── Helpers ─────────────────────────────────────────────────────────

def _scan_images(image_dir: str) -> list[str]:
    """Return sorted list of image paths in a directory."""
    if not os.path.isdir(image_dir):
        return []
    paths: list[str] = []
    for name in sorted(os.listdir(image_dir)):
        ext = os.path.splitext(name)[1].lower()
        if ext in _IMAGE_EXTS:
            paths.append(os.path.join(image_dir, name))
    return paths


def _run_yolo(
    runner: object, image_path: str
) -> tuple[list[BBoxPrediction], float]:
    """Run YOLO runner, returning (detections, runtime_ms)."""
    if runner is None:
        return [], 0.0
    t0 = time.perf_counter()
    result = runner.predict_image(image_path)
    dt = (time.perf_counter() - t0) * 1000.0
    detections: list[BBoxPrediction] = getattr(result, "detections", [])
    # Ensure each detection is a BBoxPrediction
    converted: list[BBoxPrediction] = []
    for d in detections:
        if isinstance(d, BBoxPrediction):
            converted.append(d)
        else:
            # DetectionBox uses .bbox; BBoxPrediction uses .bbox_xyxy — accept either
            bbox = list(getattr(d, "bbox_xyxy",
                       getattr(d, "bbox", [0.0, 0.0, 0.0, 0.0])))
            if len(bbox) == 0:
                bbox = [0.0, 0.0, 0.0, 0.0]
            converted.append(BBoxPrediction(
                class_name=getattr(d, "class_name", ""),
                confidence=getattr(d, "confidence", 0.0),
                bbox_xyxy=bbox,
            ))
    return converted, dt


def _run_anomaly(
    runner: object, image_path: str
) -> tuple[AnomalyResult, float]:
    """Run anomaly runner, returning (AnomalyResult, runtime_ms)."""
    if runner is None:
        return AnomalyResult(image_score=0.0), 0.0
    t0 = time.perf_counter()
    result = runner.predict_image(image_path)
    dt = (time.perf_counter() - t0) * 1000.0
    anomaly_result = AnomalyResult(
        image_score=getattr(result, "image_score", 0.0),
        heatmap_path=getattr(result, "heatmap_path", None),
    )
    return anomaly_result, dt


def _build_yolo_runner(model_id: str, confidence: float = 0.01) -> object | None:
    """Build a YOLO model runner from a model_version record.

    Returns a duck-typed runner with predict_image() → result with .detections.
    Empty model_id means "no YOLO runner". Any non-empty but invalid model_id
    is a configuration error and must fail loudly, otherwise the UI can appear
    to use YOLO while actually running anomaly-only.
    """
    if not model_id:
        return None
    mv = get_model_version(model_id)
    if not mv or not mv.model_path:
        raise ValueError(f"YOLO model version is missing or has no model_path: {model_id}")
    if not os.path.isfile(mv.model_path):
        raise FileNotFoundError(f"YOLO model file not found: {mv.model_path}")

    from model_runners.yolo_runner import YoloModelRunner

    runner = YoloModelRunner(
        model_path=mv.model_path,
        config={"confidence": max(0.001, min(float(confidence), 0.99))},
    )
    runner.load()
    return runner


def _build_anomaly_runner(model_id: str, score_threshold: float = 0.65) -> object | None:
    """Build an anomaly model runner from a model_version record."""
    if not model_id:
        return None
    mv = get_model_version(model_id)
    if not mv or not mv.model_path:
        raise ValueError(f"anomaly model version is missing or has no model_path: {model_id}")
    if mv.model_type != "patchcore":
        raise ValueError(f"unsupported anomaly model type: {mv.model_type}")
    if not os.path.isfile(mv.model_path):
        raise FileNotFoundError(f"anomaly model file not found: {mv.model_path}")

    from src.inference.patchcore_runner import PatchCoreRunner

    runner = PatchCoreRunner(
        {
            "mode": "statistical",
            "model_path": mv.model_path,
            "score_threshold": max(0.001, min(float(score_threshold), 0.99)),
        }
    )
    runner.load_model()
    return runner


def _ensure_field_session(config: HybridRetestConfig) -> str:
    """Return field_session_id, creating one if needed."""
    if config.field_session_id:
        fs = get_field_session(config.field_session_id)
        if fs:
            return config.field_session_id
    fs = create_field_session(
        project_id=config.project_id,
        spec_id=config.spec_id,
        session_type="production_retest",
    )
    return fs.field_session_id


def _decision_counts(items: list[HybridRetestItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        d = item.final_decision
        counts[d] = counts.get(d, 0) + 1
    return counts


# ── Main service ────────────────────────────────────────────────────

def run_hybrid_retest(
    config: HybridRetestConfig,
    yolo_runner: object | None = None,
    anomaly_runner: object | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> HybridRetestResult:
    """Run hybrid retest on all images in config.image_dir.

    Args:
        config: Retest configuration.
        yolo_runner: Object with predict_image() → result with .detections.
        anomaly_runner: Object with predict_image() → result with .image_score.
        progress_callback: Called with (current, total, image_path).

    Returns:
        HybridRetestResult with run_id, counts, and item list.
    """
    # ── Validate ──────────────────────────────────────────────────
    image_paths = _scan_images(config.image_dir)
    if not image_paths:
        raise ValueError(f"No images found in directory: {config.image_dir}")

    # ── Ensure field session ──────────────────────────────────────
    field_session_id = _ensure_field_session(config)

    # ── Build fusion engine ───────────────────────────────────────
    fusion_cfg = FusionConfig(
        strategy=FusionStrategy.PRODUCTION_RETEST,
        yolo_conf_threshold=config.yolo_conf_threshold,
        anomaly_score_threshold=config.anomaly_score_threshold,
        anomaly_high_threshold=config.anomaly_high_threshold,
    )
    engine = HybridFusionEngine(fusion_cfg)

    # ── Create run record ─────────────────────────────────────────
    run_id = generate_id("HRR")
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert("hybrid_retest_runs", {
        "run_id": run_id,
        "project_id": config.project_id,
        "spec_id": config.spec_id,
        "field_session_id": field_session_id,
        "yolo_model_id": config.yolo_model_id,
        "anomaly_model_id": config.anomaly_model_id,
        "image_dir": config.image_dir,
        "config_json": json.dumps({
            "yolo_conf_threshold": config.yolo_conf_threshold,
            "anomaly_score_threshold": config.anomaly_score_threshold,
            "anomaly_high_threshold": config.anomaly_high_threshold,
        }),
        "status": "running",
        "started_at": started_at,
    })

    items: list[HybridRetestItem] = []
    total = len(image_paths)

    try:
        for idx, image_path in enumerate(image_paths):
            if progress_callback:
                progress_callback(idx + 1, total, image_path)

            # Run both models
            yolo_dets, yolo_runtime = _run_yolo(yolo_runner, image_path)
            anomaly_result, anomaly_runtime = _run_anomaly(anomaly_runner, image_path)
            total_runtime = max(yolo_runtime, anomaly_runtime)

            # Fuse
            fusion: FusionDecision = engine.fuse(yolo_dets, anomaly_result, image_path)
            final_decision = fusion.final_decision.value  # "OK", "NG", etc.

            # Route to anomaly_reviews if applicable
            review_id: str | None = None
            if final_decision in set(config.route_review_statuses):
                notes = json.dumps({
                    "run_id": run_id,
                    "final_decision": final_decision,
                    "reason": fusion.reason,
                    "yolo_model_id": config.yolo_model_id,
                    "anomaly_model_id": config.anomaly_model_id,
                    "anomaly_score": anomaly_result.image_score,
                    "yolo_detection_count": len(yolo_dets),
                }, ensure_ascii=False)
                ar = create_anomaly_review(
                    field_session_id=field_session_id,
                    image_path=image_path,
                    anomaly_score=anomaly_result.image_score,
                    review_status="unknown_pending",
                    notes=notes,
                )
                review_id = ar.review_id

            # Record item
            item = HybridRetestItem(
                image_path=image_path,
                final_decision=final_decision,
                reason=fusion.reason,
                yolo_detection_count=len(yolo_dets),
                anomaly_score=anomaly_result.image_score,
                runtime_ms=total_runtime,
                review_id=review_id,
            )
            items.append(item)

            # Persist to DB
            insert("hybrid_retest_items", {
                "item_id": generate_id("HRI"),
                "run_id": run_id,
                "image_path": image_path,
                "final_decision": final_decision,
                "reason": fusion.reason,
                "yolo_detection_count": len(yolo_dets),
                "anomaly_score": anomaly_result.image_score,
                "runtime_ms": total_runtime,
                "review_id": review_id or "",
                "extra_json": json.dumps(fusion.extra, ensure_ascii=False),
            })

        # ── Build result ──────────────────────────────────────────
        counts = _decision_counts(items)
        ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_json = json.dumps(counts)

        result = HybridRetestResult(
            run_id=run_id,
            total_count=total,
            ok_count=counts.get("OK", 0),
            ng_count=counts.get("NG", 0),
            suspect_count=counts.get("SUSPECT", 0),
            unknown_count=counts.get("UNKNOWN", 0),
            needs_review_count=counts.get("NEEDS_REVIEW", 0),
            items=items,
        )

        # Update run record
        from core.storage import update
        update("hybrid_retest_runs", run_id, {
            "status": "completed",
            "ended_at": ended_at,
            "summary_json": summary_json,
            "updated_at": ended_at,
        }, id_column="run_id")

        return result

    except Exception:
        # Mark run as failed
        from core.storage import update
        ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            update("hybrid_retest_runs", run_id, {
                "status": "failed",
                "ended_at": ended_at,
                "updated_at": ended_at,
            }, id_column="run_id")
        except Exception as exc:
            logging.error("Failed to mark run %s as failed: %s", run_id, exc)
        raise


# ── CRUD helpers ────────────────────────────────────────────────────

def list_retest_runs(project_id: str) -> list[dict]:
    """List hybrid retest runs for a project, newest first."""
    rows = fetch_all(
        "hybrid_retest_runs",
        where="project_id = ? ORDER BY created_at DESC",
        params=(project_id,),
    )
    return rows


def list_retest_items(run_id: str) -> list[dict]:
    """List all items for a retest run."""
    rows = fetch_all(
        "hybrid_retest_items",
        where="run_id = ? ORDER BY created_at",
        params=(run_id,),
    )
    return rows
