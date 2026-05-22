"""ModelVersion data model and operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update

MODEL_STATUSES = [
    "created", "training", "completed", "evaluating", "evaluated",
    "verified", "candidate", "active", "rolled_back", "archived",
]


@dataclass
class ModelVersion:
    model_id: str
    project_id: str
    spec_id: str = ""
    dataset_version_id: str | None = None
    training_job_id: str | None = None
    model_name: str = ""
    model_type: str = "yolo"
    model_path: str = ""
    base_model: str | None = None
    class_mapping: str = "{}"
    metrics: str | None = None
    status: str = "created"
    is_active: bool = False
    deployed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id, "project_id": self.project_id,
            "spec_id": self.spec_id,
            "dataset_version_id": self.dataset_version_id,
            "training_job_id": self.training_job_id, "model_name": self.model_name,
            "model_type": self.model_type, "model_path": self.model_path,
            "base_model": self.base_model, "class_mapping": self.class_mapping,
            "metrics": self.metrics, "status": self.status,
            "is_active": 1 if self.is_active else 0,
            "deployed_at": self.deployed_at,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModelVersion:
        return cls(
            model_id=d["model_id"], project_id=d["project_id"],
            spec_id=d.get("spec_id", ""),
            dataset_version_id=d.get("dataset_version_id"),
            training_job_id=d.get("training_job_id"), model_name=d.get("model_name", ""),
            model_type=d.get("model_type", "yolo"), model_path=d.get("model_path", ""),
            base_model=d.get("base_model"), class_mapping=d.get("class_mapping", "{}"),
            metrics=d.get("metrics"), status=d.get("status", "created"),
            is_active=bool(d.get("is_active", 0)),
            deployed_at=d.get("deployed_at"),
            created_at=d.get("created_at"), updated_at=d.get("updated_at"),
            notes=d.get("notes"),
        )


def _gen_id() -> str:
    return generate_id("MODEL")


def create_model_version(project_id: str, model_name: str, **kwargs) -> ModelVersion:
    m = ModelVersion(model_id=_gen_id(), project_id=project_id, model_name=model_name, **kwargs)
    insert("model_versions", m.to_dict())
    return m


def get_model_version(model_id: str) -> ModelVersion | None:
    row = fetch_one("model_versions", model_id, "model_id")
    return ModelVersion.from_dict(row) if row else None


def list_model_versions(project_id: str | None = None) -> list[ModelVersion]:
    if project_id:
        rows = fetch_all("model_versions", where="project_id = ? ORDER BY created_at DESC", params=(project_id,))
    else:
        rows = fetch_all("model_versions", where="1 ORDER BY created_at DESC")
    return [ModelVersion.from_dict(r) for r in rows]


def update_model_version(model_id: str, **kwargs) -> ModelVersion | None:
    existing = get_model_version(model_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("model_versions", model_id, existing.to_dict(), "model_id")
    return existing


def delete_model_version(model_id: str) -> None:
    delete("model_versions", model_id, "model_id")


def activate_model(model_id: str) -> ModelVersion | None:
    """Activate a model version for production use.

    Enforces uniqueness: deactivates any other active model in the same project,
    then sets this model to active with deployed_at timestamp.
    """
    model = get_model_version(model_id)
    if model is None:
        return None

    # Deactivate any currently active model in the same product spec. Legacy
    # models without spec_id keep the old project-wide uniqueness behavior.
    if model.spec_id:
        active_rows = fetch_all(
            "model_versions",
            where="project_id = ? AND spec_id = ? AND is_active = 1 AND model_id != ?",
            params=(model.project_id, model.spec_id, model_id),
        )
    else:
        active_rows = fetch_all(
            "model_versions",
            where="project_id = ? AND is_active = 1 AND model_id != ?",
            params=(model.project_id, model_id),
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    for row in active_rows:
        update("model_versions", row["model_id"], {
            "is_active": 0,
            "status": "archived",
            "deployed_at": None,
        }, "model_id")

    model.is_active = True
    model.status = "active"
    model.deployed_at = now
    update("model_versions", model_id, model.to_dict(), "model_id")
    _audit("model_activate", f"{model_id} project={model.project_id} spec={model.spec_id}")
    return model


def rollback_model(model_id: str) -> ModelVersion | None:
    """Roll back a model from active to rolled_back status.

    Clears is_active flag and sets status to 'rolled_back'.
    """
    model = get_model_version(model_id)
    if model is None:
        return None

    model.is_active = False
    model.status = "rolled_back"
    model.deployed_at = None
    update("model_versions", model_id, model.to_dict(), "model_id")
    _audit("model_rollback", f"{model_id} project={model.project_id} spec={model.spec_id}")
    return model


def get_active_model(project_id: str, spec_id: str | None = None) -> ModelVersion | None:
    """Return the currently active model for a project, if any."""
    if spec_id is None:
        rows = fetch_all(
            "model_versions",
            where="project_id = ? AND is_active = 1 LIMIT 1",
            params=(project_id,),
        )
    else:
        rows = fetch_all(
            "model_versions",
            where="project_id = ? AND spec_id = ? AND is_active = 1 LIMIT 1",
            params=(project_id, spec_id),
        )
    return ModelVersion.from_dict(rows[0]) if rows else None


def _audit(action: str, detail: str) -> None:
    try:
        from core.log_manager import LogManager

        LogManager.instance().log_audit(action, detail)
    except Exception:
        pass
