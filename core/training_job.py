"""TrainingJob data model and operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update

VALID_STATUSES = {"created", "queued", "running", "completed", "failed", "candidate", "archived"}


@dataclass
class TrainingJob:
    job_id: str
    project_id: str
    spec_id: str
    dataset_path: str = ""
    job_name: str = ""
    model_family: str = "yolo"
    base_model: str = "yolov8n.pt"
    task_type: str = "detection"
    training_config: str = "{}"
    status: str = "created"
    start_time: str | None = None
    end_time: str | None = None
    output_dir: str | None = None
    best_model_path: str | None = None
    last_model_path: str | None = None
    metrics: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "dataset_path": self.dataset_path,
            "job_name": self.job_name,
            "model_family": self.model_family,
            "base_model": self.base_model,
            "task_type": self.task_type,
            "training_config": self.training_config,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "output_dir": self.output_dir,
            "best_model_path": self.best_model_path,
            "last_model_path": self.last_model_path,
            "metrics": self.metrics,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> TrainingJob:
        return cls(
            job_id=d["job_id"], project_id=d["project_id"], spec_id=d["spec_id"],
            dataset_path=d.get("dataset_path", ""), job_name=d.get("job_name", ""),
            model_family=d.get("model_family", "yolo"),
            base_model=d.get("base_model", "yolov8n.pt"),
            task_type=d.get("task_type", "detection"),
            training_config=d.get("training_config", "{}"),
            status=d.get("status", "created"),
            start_time=d.get("start_time"), end_time=d.get("end_time"),
            output_dir=d.get("output_dir"),
            best_model_path=d.get("best_model_path"),
            last_model_path=d.get("last_model_path"),
            metrics=d.get("metrics"), notes=d.get("notes"),
            created_at=d.get("created_at"), updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("JOB")


def create_training_job(
    project_id: str, spec_id: str, job_name: str, dataset_path: str = "",
    model_family: str = "yolo", base_model: str = "yolov8n.pt",
    task_type: str = "detection", training_config: str = "{}",
) -> TrainingJob:
    j = TrainingJob(
        job_id=_gen_id(), project_id=project_id, spec_id=spec_id,
        job_name=job_name, dataset_path=dataset_path,
        model_family=model_family, base_model=base_model,
        task_type=task_type, training_config=training_config,
    )
    insert("training_jobs", j.to_dict())
    return j


def get_training_job(job_id: str) -> TrainingJob | None:
    row = fetch_one("training_jobs", job_id, "job_id")
    return TrainingJob.from_dict(row) if row else None


def list_training_jobs(project_id: str | None = None) -> list[TrainingJob]:
    if project_id:
        rows = fetch_all("training_jobs", where="project_id = ? ORDER BY created_at DESC", params=(project_id,))
    else:
        rows = fetch_all("training_jobs", where="1 ORDER BY created_at DESC")
    return [TrainingJob.from_dict(r) for r in rows]


def update_training_job(job_id: str, **kwargs) -> TrainingJob | None:
    existing = get_training_job(job_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("training_jobs", job_id, existing.to_dict(), "job_id")
    return existing


def delete_training_job(job_id: str) -> None:
    delete("training_jobs", job_id, "job_id")
