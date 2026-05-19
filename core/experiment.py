"""Experiment schema for multi-model comparison.

Provides ``ModelRunConfig``, ``ModelRunResult``, and ``Experiment`` dataclasses
plus helpers for ID generation and DataFrame conversion.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.schema import DetectionBox


@dataclass
class ModelRunConfig:
    model_name: str
    model_type: str
    model_path: str
    confidence: float
    iou: float
    image_size: int
    device: str
    extra_config: dict = field(default_factory=dict)


@dataclass
class ModelRunResult:
    run_id: str
    config: ModelRunConfig
    predictions_by_image: dict[str, list[DetectionBox]]
    metrics: dict
    timing: dict
    created_at: str


@dataclass
class Experiment:
    experiment_id: str
    name: str
    dataset_name: str
    ground_truths_by_image: dict[str, list[DetectionBox]]
    model_runs: list[ModelRunResult]
    created_at: str


def create_run_id(config: ModelRunConfig) -> str:
    """Generate a short unique run ID from model identity and parameters."""
    suffix = uuid.uuid4().hex[:8]
    safe_name = config.model_name.replace(" ", "_").replace("/", "_")[:32]
    return f"{safe_name}_{suffix}"


def create_experiment_id(name: str, dataset_name: str) -> str:
    """Generate a short unique experiment ID."""
    suffix = uuid.uuid4().hex[:8]
    safe_name = name.replace(" ", "_")[:24]
    safe_ds = dataset_name.replace(" ", "_")[:16]
    return f"{safe_name}_{safe_ds}_{suffix}"


def model_run_to_summary_row(run: ModelRunResult) -> dict:
    """Convert a single model run result to a flat summary dict."""
    m = run.metrics
    t = run.timing
    total_preds = sum(len(v) for v in run.predictions_by_image.values())
    return {
        "run_id": run.run_id,
        "model_name": run.config.model_name,
        "model_type": run.config.model_type,
        "confidence": run.config.confidence,
        "iou": run.config.iou,
        "num_images": len(run.predictions_by_image),
        "num_predictions": total_preds,
        "map_50": m.get("map_50"),
        "map": m.get("map"),
        "avg_inference_ms": t.get("avg_ms"),
        "total_inference_ms": t.get("total_ms"),
        "created_at": run.created_at,
    }


def experiment_to_dataframe_rows(experiment: Experiment) -> list[dict]:
    """Produce a list of flat dicts, one per model run in the experiment."""
    rows: list[dict] = []
    for run in experiment.model_runs:
        row = model_run_to_summary_row(run)
        row["experiment_id"] = experiment.experiment_id
        row["experiment_name"] = experiment.name
        row["dataset_name"] = experiment.dataset_name
        rows.append(row)
    return rows


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
