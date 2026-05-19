"""Manual review and sample feedback loop.

Stores review records as JSON Lines under ``outputs/reviews/``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REVIEW_LABELS = [
    "true_defect",
    "false_positive",
    "acceptable_minor_defect",
    "unknown_defect",
    "label_error",
    "retrain_candidate",
    "ignore",
]


@dataclass
class ReviewRecord:
    review_id: str
    image_name: str
    detection_id: str
    model_name: str | None
    class_name: str
    confidence: float
    bbox: list[float]
    review_label: str
    reviewer_note: str
    created_at: str


def create_review_record(
    image_name: str,
    detection_id: str,
    class_name: str,
    confidence: float,
    bbox: list[float],
    review_label: str,
    reviewer_note: str = "",
    model_name: str | None = None,
) -> ReviewRecord:
    if review_label not in REVIEW_LABELS:
        raise ValueError(f"Invalid review_label: {review_label}. Must be one of {REVIEW_LABELS}")
    return ReviewRecord(
        review_id=uuid.uuid4().hex[:12],
        image_name=image_name,
        detection_id=detection_id,
        model_name=model_name,
        class_name=class_name,
        confidence=confidence,
        bbox=bbox,
        review_label=review_label,
        reviewer_note=reviewer_note,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def save_review_records(records: list[ReviewRecord], path: str | Path) -> None:
    """Append review records to a JSON Lines file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.__dict__, ensure_ascii=False) + "\n")


def load_review_records(path: str | Path) -> list[ReviewRecord]:
    """Load all review records from a JSON Lines file."""
    p = Path(path)
    if not p.exists():
        return []
    records: list[ReviewRecord] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(ReviewRecord(**data))
    return records


def summarize_review_records(records: list[ReviewRecord]) -> dict:
    """Produce summary counts by review label."""
    summary: dict[str, int] = {label: 0 for label in REVIEW_LABELS}
    for rec in records:
        if rec.review_label in summary:
            summary[rec.review_label] += 1
    return {"total": len(records), "by_label": summary}


def filter_records_for_retraining(records: list[ReviewRecord]) -> list[ReviewRecord]:
    """Select records that should flow back into training."""
    retrain_labels = {"false_positive", "retrain_candidate", "label_error"}
    return [r for r in records if r.review_label in retrain_labels]


DEFAULT_REVIEW_PATH = Path("outputs/reviews/review_records.jsonl")
