"""InspectionProject data model and operations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update

PROJECT_DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "project_data"
)


@dataclass
class InspectionProject:
    project_id: str
    customer_id: str
    project_name: str
    project_type: str = "surface_inspection"
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.project_name.strip():
            raise ValueError("project_name 不能为空")
        if not self.customer_id.strip():
            raise ValueError("project 必须绑定 customer")
        valid_statuses = {"active", "paused", "completed", "archived"}
        if self.status not in valid_statuses:
            raise ValueError(f"status 必须是 {valid_statuses} 之一")

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "customer_id": self.customer_id,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "status": self.status,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> InspectionProject:
        return cls(
            project_id=d["project_id"],
            customer_id=d["customer_id"],
            project_name=d["project_name"],
            project_type=d.get("project_type", "surface_inspection"),
            status=d.get("status", "active"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("PROJ")


def create_project(
    customer_id: str,
    project_name: str,
    project_type: str = "surface_inspection",
    status: str = "active",
) -> InspectionProject:
    p = InspectionProject(
        project_id=_gen_id(),
        customer_id=customer_id,
        project_name=project_name,
        project_type=project_type,
        status=status,
    )
    insert("projects", p.to_dict())
    _create_project_dirs(customer_id, p.project_id)
    return p


def get_project(project_id: str) -> InspectionProject | None:
    row = fetch_one("projects", project_id, "project_id")
    return InspectionProject.from_dict(row) if row else None


def list_projects(customer_id: str | None = None) -> list[InspectionProject]:
    if customer_id:
        rows = fetch_all("projects", where="customer_id = ? ORDER BY created_at DESC", params=(customer_id,))
    else:
        rows = fetch_all("projects", where="1 ORDER BY created_at DESC")
    return [InspectionProject.from_dict(r) for r in rows]


def update_project(project_id: str, **kwargs) -> InspectionProject | None:
    existing = get_project(project_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("projects", project_id, existing.to_dict(), "project_id")
    return existing


def delete_project(project_id: str) -> None:
    delete("projects", project_id, "project_id")


def get_project_data_dir(project_id: str) -> str:
    p = get_project(project_id)
    if not p:
        return ""
    return os.path.join(
        PROJECT_DATA_ROOT, f"customer_{p.customer_id}", f"project_{project_id}"
    )


def _create_project_dirs(customer_id: str, project_id: str) -> str:
    base = os.path.join(PROJECT_DATA_ROOT, f"customer_{customer_id}", f"project_{project_id}")
    subdirs = [
        "configs",
        "sample_sessions",
        "datasets",
        "models",
        "predictions",
        "reports",
        "production_records",
    ]
    for d in subdirs:
        os.makedirs(os.path.join(base, d), exist_ok=True)
    return base
