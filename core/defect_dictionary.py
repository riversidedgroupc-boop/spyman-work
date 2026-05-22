"""Defect dictionary model — stores defect categories discovered at the customer site."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update


@dataclass
class DefectType:
    defect_type_id: str
    project_id: str
    spec_id: str = ""
    code: str = ""
    display_name_zh: str = ""
    display_name_en: str = ""
    severity: str = "medium"
    description: str = ""
    is_ng: bool = True
    sample_image_paths: str = "[]"
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id 不能为空")
        valid_severities = {"critical", "high", "medium", "low", "info"}
        if self.severity not in valid_severities:
            raise ValueError(f"severity 无效: {self.severity}")

    def to_dict(self) -> dict:
        return {
            "defect_type_id": self.defect_type_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "code": self.code,
            "display_name_zh": self.display_name_zh,
            "display_name_en": self.display_name_en,
            "severity": self.severity,
            "description": self.description,
            "is_ng": 1 if self.is_ng else 0,
            "sample_image_paths": self.sample_image_paths,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> DefectType:
        return cls(
            defect_type_id=d["defect_type_id"],
            project_id=d["project_id"],
            spec_id=d.get("spec_id", ""),
            code=d.get("code", ""),
            display_name_zh=d.get("display_name_zh", ""),
            display_name_en=d.get("display_name_en", ""),
            severity=d.get("severity", "medium"),
            description=d.get("description", ""),
            is_ng=bool(d.get("is_ng", 1)),
            sample_image_paths=d.get("sample_image_paths", "[]"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("DEF")


def create_defect_type(
    project_id: str,
    code: str = "",
    display_name_zh: str = "",
    display_name_en: str = "",
    spec_id: str = "",
    severity: str = "medium",
    description: str = "",
    is_ng: bool = True,
    sample_image_paths: str = "[]",
) -> DefectType:
    dt = DefectType(
        defect_type_id=_gen_id(),
        project_id=project_id,
        spec_id=spec_id,
        code=code,
        display_name_zh=display_name_zh,
        display_name_en=display_name_en,
        severity=severity,
        description=description,
        is_ng=is_ng,
        sample_image_paths=sample_image_paths,
    )
    insert("defect_types", dt.to_dict())
    return dt


def get_defect_type(defect_type_id: str) -> DefectType | None:
    row = fetch_one("defect_types", defect_type_id, id_column="defect_type_id")
    return DefectType.from_dict(row) if row else None


def list_defect_types(project_id: str | None = None) -> list[DefectType]:
    if project_id:
        rows = fetch_all("defect_types", where="project_id = ? ORDER BY created_at DESC", params=(project_id,))
    else:
        rows = fetch_all("defect_types", where="1 ORDER BY created_at DESC")
    return [DefectType.from_dict(r) for r in rows]


def get_active_defect_types(project_id: str) -> list[DefectType]:
    """Return only defect types where is_ng=True (actual defects, not pseudo-classes)."""
    rows = fetch_all(
        "defect_types",
        where="project_id = ? AND is_ng = 1 ORDER BY created_at DESC",
        params=(project_id,),
    )
    return [DefectType.from_dict(r) for r in rows]


def update_defect_type(defect_type_id: str, **kwargs) -> DefectType | None:
    existing = get_defect_type(defect_type_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    # Re-construct to trigger __post_init__ validation
    validated = DefectType.from_dict(existing.to_dict())
    update("defect_types", defect_type_id, validated.to_dict(), id_column="defect_type_id")
    return validated


def delete_defect_type(defect_type_id: str) -> None:
    delete("defect_types", defect_type_id, id_column="defect_type_id")
