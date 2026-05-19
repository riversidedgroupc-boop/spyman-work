"""ProductSpec data model and operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.storage import delete, fetch_all, fetch_one, insert, update

VALID_MATERIALS = [
    "铜", "铜合金", "铝", "铝合金", "不锈钢", "碳钢", "钛合金", "塑料", "复合材料", "其他",
]
VALID_GEOMETRY_TYPES = [
    "管", "棒", "线", "板", "带", "扁管", "异形件", "其他",
]


@dataclass
class ProductSpec:
    spec_id: str
    project_id: str
    product_name: str
    material: str = ""
    geometry_type: str = ""
    surface_type: str = ""
    diameter_mm: float | None = None
    width_mm: float | None = None
    thickness_mm: float | None = None
    length_mm: float | None = None
    line_speed_min_mpm: float = 10.0
    line_speed_max_mpm: float = 200.0
    target_speed_mpm: float = 80.0
    min_defect_size_mm: float | None = None
    camera_count: int = 3
    camera_layout: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.product_name.strip():
            raise ValueError("product_name 不能为空")
        if not self.project_id.strip():
            raise ValueError("spec 必须绑定 project")
        if not self.material.strip():
            raise ValueError("material 不能为空")
        if not self.geometry_type.strip():
            raise ValueError("geometry_type 不能为空")
        if self.line_speed_min_mpm < 0:
            raise ValueError("line_speed_min_mpm 必须 >= 0")
        if self.line_speed_max_mpm > 200:
            raise ValueError("line_speed_max_mpm 必须 <= 200")
        if self.line_speed_min_mpm > self.line_speed_max_mpm:
            raise ValueError("line_speed_min_mpm 必须 <= line_speed_max_mpm")
        if self.target_speed_mpm < self.line_speed_min_mpm or self.target_speed_mpm > self.line_speed_max_mpm:
            raise ValueError("target_speed_mpm 必须在 min/max 范围内")
        if self.camera_count < 1 or self.camera_count > 6:
            raise ValueError("camera_count 必须在 1-6 之间")

    def to_dict(self) -> dict:
        return {
            "spec_id": self.spec_id,
            "project_id": self.project_id,
            "product_name": self.product_name,
            "material": self.material,
            "geometry_type": self.geometry_type,
            "surface_type": self.surface_type,
            "diameter_mm": self.diameter_mm,
            "width_mm": self.width_mm,
            "thickness_mm": self.thickness_mm,
            "length_mm": self.length_mm,
            "line_speed_min_mpm": self.line_speed_min_mpm,
            "line_speed_max_mpm": self.line_speed_max_mpm,
            "target_speed_mpm": self.target_speed_mpm,
            "min_defect_size_mm": self.min_defect_size_mm,
            "camera_count": self.camera_count,
            "camera_layout": self.camera_layout,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProductSpec:
        return cls(
            spec_id=d["spec_id"],
            project_id=d["project_id"],
            product_name=d["product_name"],
            material=d.get("material", ""),
            geometry_type=d.get("geometry_type", ""),
            surface_type=d.get("surface_type", ""),
            diameter_mm=d.get("diameter_mm"),
            width_mm=d.get("width_mm"),
            thickness_mm=d.get("thickness_mm"),
            length_mm=d.get("length_mm"),
            line_speed_min_mpm=d.get("line_speed_min_mpm", 10.0),
            line_speed_max_mpm=d.get("line_speed_max_mpm", 200.0),
            target_speed_mpm=d.get("target_speed_mpm", 80.0),
            min_defect_size_mm=d.get("min_defect_size_mm"),
            camera_count=d.get("camera_count", 3),
            camera_layout=d.get("camera_layout"),
            notes=d.get("notes"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return datetime.now().strftime("SPEC_%Y%m%d_%H%M%S_%f")


def create_product_spec(
    project_id: str,
    product_name: str,
    material: str,
    geometry_type: str,
    surface_type: str = "",
    diameter_mm: float | None = None,
    width_mm: float | None = None,
    thickness_mm: float | None = None,
    length_mm: float | None = None,
    line_speed_min_mpm: float = 10.0,
    line_speed_max_mpm: float = 200.0,
    target_speed_mpm: float = 80.0,
    min_defect_size_mm: float | None = None,
    camera_count: int = 3,
    camera_layout: str | None = None,
    notes: str | None = None,
) -> ProductSpec:
    s = ProductSpec(
        spec_id=_gen_id(),
        project_id=project_id,
        product_name=product_name,
        material=material,
        geometry_type=geometry_type,
        surface_type=surface_type,
        diameter_mm=diameter_mm,
        width_mm=width_mm,
        thickness_mm=thickness_mm,
        length_mm=length_mm,
        line_speed_min_mpm=line_speed_min_mpm,
        line_speed_max_mpm=line_speed_max_mpm,
        target_speed_mpm=target_speed_mpm,
        min_defect_size_mm=min_defect_size_mm,
        camera_count=camera_count,
        camera_layout=camera_layout,
        notes=notes,
    )
    insert("product_specs", s.to_dict())
    return s


def get_product_spec(spec_id: str) -> ProductSpec | None:
    row = fetch_one("product_specs", spec_id, "spec_id")
    return ProductSpec.from_dict(row) if row else None


def list_product_specs(project_id: str | None = None) -> list[ProductSpec]:
    if project_id:
        rows = fetch_all("product_specs", where="project_id = ? ORDER BY created_at DESC", params=(project_id,))
    else:
        rows = fetch_all("product_specs", where="1 ORDER BY created_at DESC")
    return [ProductSpec.from_dict(r) for r in rows]


def update_product_spec(spec_id: str, **kwargs) -> ProductSpec | None:
    existing = get_product_spec(spec_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("product_specs", spec_id, existing.to_dict(), "spec_id")
    return existing


def delete_product_spec(spec_id: str) -> None:
    delete("product_specs", spec_id, "spec_id")
