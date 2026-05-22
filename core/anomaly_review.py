"""Anomaly review model — stores anomaly candidate review records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update


@dataclass
class AnomalyReview:
    review_id: str
    field_session_id: str
    image_path: str = ""
    crop_path: str = ""
    heatmap_path: str = ""
    anomaly_score: float = 0.0
    cluster_id: str = ""
    review_status: str = "unreviewed"
    assigned_defect_type_id: str | None = None
    reviewer: str = ""
    reviewed_at: str | None = None
    notes: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.field_session_id.strip():
            raise ValueError("field_session_id 不能为空")
        valid_statuses = {
            "unreviewed", "confirmed_defect", "acceptable_texture",
            "noise_or_reflection", "normal", "unknown_pending",
        }
        if self.review_status not in valid_statuses:
            raise ValueError(f"review_status 无效: {self.review_status}")

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "field_session_id": self.field_session_id,
            "image_path": self.image_path,
            "crop_path": self.crop_path,
            "heatmap_path": self.heatmap_path,
            "anomaly_score": self.anomaly_score,
            "cluster_id": self.cluster_id,
            "review_status": self.review_status,
            "assigned_defect_type_id": self.assigned_defect_type_id,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> AnomalyReview:
        return cls(
            review_id=d["review_id"],
            field_session_id=d["field_session_id"],
            image_path=d.get("image_path", ""),
            crop_path=d.get("crop_path", ""),
            heatmap_path=d.get("heatmap_path", ""),
            anomaly_score=float(d.get("anomaly_score", 0.0)),
            cluster_id=d.get("cluster_id", ""),
            review_status=d.get("review_status", "unreviewed"),
            assigned_defect_type_id=d.get("assigned_defect_type_id"),
            reviewer=d.get("reviewer", ""),
            reviewed_at=d.get("reviewed_at"),
            notes=d.get("notes", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("ARV")


def create_anomaly_review(
    field_session_id: str,
    image_path: str = "",
    crop_path: str = "",
    heatmap_path: str = "",
    anomaly_score: float = 0.0,
    cluster_id: str = "",
    review_status: str = "unreviewed",
    notes: str = "",
) -> AnomalyReview:
    r = AnomalyReview(
        review_id=_gen_id(),
        field_session_id=field_session_id,
        image_path=image_path,
        crop_path=crop_path,
        heatmap_path=heatmap_path,
        anomaly_score=anomaly_score,
        cluster_id=cluster_id,
        review_status=review_status,
        notes=notes,
    )
    insert("anomaly_reviews", r.to_dict())
    return r


def get_anomaly_review(review_id: str) -> AnomalyReview | None:
    row = fetch_one("anomaly_reviews", review_id, id_column="review_id")
    return AnomalyReview.from_dict(row) if row else None


def list_anomaly_reviews(
    field_session_id: str | None = None,
    review_status: str | None = None,
) -> list[AnomalyReview]:
    conditions = []
    params: list[str] = []
    if field_session_id:
        conditions.append("field_session_id = ?")
        params.append(field_session_id)
    if review_status:
        conditions.append("review_status = ?")
        params.append(review_status)
    where = " AND ".join(conditions) if conditions else "1"
    rows = fetch_all("anomaly_reviews", where=f"{where} ORDER BY created_at DESC", params=tuple(params))
    return [AnomalyReview.from_dict(r) for r in rows]


def update_anomaly_review(review_id: str, **kwargs) -> AnomalyReview | None:
    existing = get_anomaly_review(review_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    # Re-construct to trigger __post_init__ validation
    validated = AnomalyReview.from_dict(existing.to_dict())
    update("anomaly_reviews", review_id, validated.to_dict(), id_column="review_id")
    return validated


def delete_anomaly_review(review_id: str) -> None:
    delete("anomaly_reviews", review_id, id_column="review_id")


def confirm_as_defect(
    review_id: str,
    defect_type_id: str,
    reviewer: str,
) -> AnomalyReview | None:
    """Convenience: confirm an anomaly candidate as a known defect."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    return update_anomaly_review(
        review_id,
        review_status="confirmed_defect",
        assigned_defect_type_id=defect_type_id,
        reviewer=reviewer,
        reviewed_at=now,
    )
