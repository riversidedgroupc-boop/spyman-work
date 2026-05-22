"""Field session model — represents one customer field visit or retest session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update


@dataclass
class FieldSession:
    field_session_id: str
    project_id: str
    spec_id: str
    session_type: str = "baseline_collection"
    status: str = "created"
    hardware_snapshot: str = "{}"
    acquisition_config_snapshot: str = "{}"
    notes: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id 不能为空")
        valid_types = {
            "baseline_collection", "anomaly_exploration",
            "first_training", "production_retest", "deployment",
        }
        if self.session_type not in valid_types:
            raise ValueError(f"session_type 无效: {self.session_type}")

    def to_dict(self) -> dict:
        return {
            "field_session_id": self.field_session_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "session_type": self.session_type,
            "status": self.status,
            "hardware_snapshot": self.hardware_snapshot,
            "acquisition_config_snapshot": self.acquisition_config_snapshot,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> FieldSession:
        return cls(
            field_session_id=d["field_session_id"],
            project_id=d["project_id"],
            spec_id=d.get("spec_id", ""),
            session_type=d.get("session_type", "baseline_collection"),
            status=d.get("status", "created"),
            hardware_snapshot=d.get("hardware_snapshot", "{}"),
            acquisition_config_snapshot=d.get("acquisition_config_snapshot", "{}"),
            notes=d.get("notes", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("FLD")


def create_field_session(
    project_id: str,
    spec_id: str,
    session_type: str = "baseline_collection",
    status: str = "created",
    hardware_snapshot: str = "{}",
    acquisition_config_snapshot: str = "{}",
    notes: str = "",
) -> FieldSession:
    s = FieldSession(
        field_session_id=_gen_id(),
        project_id=project_id,
        spec_id=spec_id,
        session_type=session_type,
        status=status,
        hardware_snapshot=hardware_snapshot,
        acquisition_config_snapshot=acquisition_config_snapshot,
        notes=notes,
    )
    insert("field_sessions", s.to_dict())
    return s


def get_field_session(field_session_id: str) -> FieldSession | None:
    row = fetch_one("field_sessions", field_session_id, id_column="field_session_id")
    return FieldSession.from_dict(row) if row else None


def list_field_sessions(project_id: str | None = None) -> list[FieldSession]:
    if project_id:
        rows = fetch_all("field_sessions", where="project_id = ? ORDER BY created_at DESC", params=(project_id,))
    else:
        rows = fetch_all("field_sessions", where="1 ORDER BY created_at DESC")
    return [FieldSession.from_dict(r) for r in rows]


def update_field_session(field_session_id: str, **kwargs) -> FieldSession | None:
    existing = get_field_session(field_session_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    # Re-construct to trigger __post_init__ validation
    validated = FieldSession.from_dict(existing.to_dict())
    update("field_sessions", field_session_id, validated.to_dict(), id_column="field_session_id")
    return validated


def delete_field_session(field_session_id: str) -> None:
    delete("field_sessions", field_session_id, id_column="field_session_id")
