"""Dataset version data model and CRUD operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.id_utils import generate_id
from core.storage import insert, fetch_one, fetch_all, update, delete


@dataclass
class DatasetVersion:
    version_id: str
    project_id: str
    spec_id: str = ""
    capture_session_id: str | None = None
    version_name: str = ""
    source_type: str = "session"
    dataset_path: str = ""
    yaml_path: str = ""
    image_count: int = 0
    class_names: str = "[]"
    val_split_ratio: float = 0.2
    quality_score: float | None = None
    quality_report: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "capture_session_id": self.capture_session_id,
            "version_name": self.version_name,
            "source_type": self.source_type,
            "dataset_path": self.dataset_path,
            "yaml_path": self.yaml_path,
            "image_count": self.image_count,
            "class_names": self.class_names,
            "val_split_ratio": self.val_split_ratio,
            "quality_score": self.quality_score,
            "quality_report": self.quality_report,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "DatasetVersion":
        return cls(
            version_id=row["version_id"],
            project_id=row["project_id"],
            spec_id=row.get("spec_id", ""),
            capture_session_id=row.get("capture_session_id"),
            version_name=row.get("version_name", ""),
            source_type=row.get("source_type", "session"),
            dataset_path=row.get("dataset_path", ""),
            yaml_path=row.get("yaml_path", ""),
            image_count=int(row.get("image_count", 0)),
            class_names=row.get("class_names", "[]"),
            val_split_ratio=float(row.get("val_split_ratio", 0.2)),
            quality_score=row.get("quality_score"),
            quality_report=row.get("quality_report", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )


def create_dataset_version(**kwargs) -> DatasetVersion:
    version_id = generate_id("DSVER")
    dv = DatasetVersion(version_id=version_id, **kwargs)
    insert("dataset_versions", dv.to_dict())
    return dv


def get_dataset_version(version_id: str) -> DatasetVersion | None:
    row = fetch_one("dataset_versions", version_id, id_column="version_id")
    return DatasetVersion.from_dict(row) if row else None


def list_dataset_versions(project_id: str | None = None, spec_id: str | None = None) -> list[DatasetVersion]:
    if project_id:
        where = "project_id = ?"
        params = (project_id,)
    elif spec_id:
        where = "spec_id = ?"
        params = (spec_id,)
    else:
        where = "1"
        params = ()
    where += " ORDER BY created_at DESC"
    rows = fetch_all("dataset_versions", where=where, params=params)
    return [DatasetVersion.from_dict(r) for r in rows]


def update_dataset_version(version_id: str, **fields) -> None:
    dv = get_dataset_version(version_id)
    if dv is None:
        raise ValueError(f"DatasetVersion not found: {version_id}")
    data: dict[str, Any] = {}
    for k, v in fields.items():
        if hasattr(dv, k):
            data[k] = v
    if data:
        update("dataset_versions", version_id, data, id_column="version_id")


def delete_dataset_version(version_id: str) -> None:
    delete("dataset_versions", version_id, id_column="version_id")
