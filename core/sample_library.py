"""Historical sample library with cross-project search and provenance tracking.

Supports:
- Indexing samples into the cross-project library
- Searching by material, surface, geometry, defect type, label, project
- Importing (copying) historical samples into current project datasets
- Referencing (linking without copying) historical samples
- Preserving full provenance chain
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.id_utils import generate_id
from core.storage import fetch_all, fetch_one, insert, get_connection


SOURCE_KIND_CURRENT = "current_capture"
SOURCE_KIND_IMPORT = "historical_import"
SOURCE_KIND_REFERENCE = "historical_reference"

VALID_SOURCE_KINDS = {SOURCE_KIND_CURRENT, SOURCE_KIND_IMPORT, SOURCE_KIND_REFERENCE}


@dataclass
class SampleLibraryEntry:
    entry_id: str
    current_project_id: str
    current_dataset_version_id: str | None = None
    source_kind: str = SOURCE_KIND_CURRENT
    source_project_id: str | None = None
    source_dataset_version_id: str | None = None
    source_capture_session_id: str | None = None
    source_image_id: str | None = None
    source_image_path: str | None = None
    current_image_path: str = ""
    original_label: str = ""
    current_label: str = ""
    human_review_status: str = "unreviewed"
    device_config_snapshot: str = "{}"
    import_reason: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "current_project_id": self.current_project_id,
            "current_dataset_version_id": self.current_dataset_version_id,
            "source_kind": self.source_kind,
            "source_project_id": self.source_project_id,
            "source_dataset_version_id": self.source_dataset_version_id,
            "source_capture_session_id": self.source_capture_session_id,
            "source_image_id": self.source_image_id,
            "source_image_path": self.source_image_path,
            "current_image_path": self.current_image_path,
            "original_label": self.original_label,
            "current_label": self.current_label,
            "human_review_status": self.human_review_status,
            "device_config_snapshot": self.device_config_snapshot,
            "import_reason": self.import_reason,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SampleLibraryEntry:
        return cls(
            entry_id=d["entry_id"],
            current_project_id=d["current_project_id"],
            current_dataset_version_id=d.get("current_dataset_version_id"),
            source_kind=d.get("source_kind", SOURCE_KIND_CURRENT),
            source_project_id=d.get("source_project_id"),
            source_dataset_version_id=d.get("source_dataset_version_id"),
            source_capture_session_id=d.get("source_capture_session_id"),
            source_image_id=d.get("source_image_id"),
            source_image_path=d.get("source_image_path"),
            current_image_path=d.get("current_image_path", ""),
            original_label=d.get("original_label", ""),
            current_label=d.get("current_label", ""),
            human_review_status=d.get("human_review_status", "unreviewed"),
            device_config_snapshot=d.get("device_config_snapshot", "{}"),
            import_reason=d.get("import_reason", ""),
            created_at=d.get("created_at", ""),
        )


# ── CRUD ───────────────────────────────────────────────────────────────

def _gen_id() -> str:
    return generate_id("SLE")


def add_to_library(
    current_project_id: str,
    current_image_path: str,
    *,
    source_kind: str = SOURCE_KIND_CURRENT,
    source_project_id: str | None = None,
    source_image_path: str | None = None,
    source_image_id: str | None = None,
    source_capture_session_id: str | None = None,
    source_dataset_version_id: str | None = None,
    original_label: str = "",
    current_label: str = "",
    human_review_status: str = "unreviewed",
    device_config_snapshot: str = "{}",
    import_reason: str = "",
    current_dataset_version_id: str | None = None,
) -> SampleLibraryEntry:
    if source_kind not in VALID_SOURCE_KINDS:
        raise ValueError(f"Invalid source_kind: {source_kind}")

    entry = SampleLibraryEntry(
        entry_id=_gen_id(),
        current_project_id=current_project_id,
        current_dataset_version_id=current_dataset_version_id,
        source_kind=source_kind,
        source_project_id=source_project_id,
        source_dataset_version_id=source_dataset_version_id,
        source_capture_session_id=source_capture_session_id,
        source_image_id=source_image_id,
        source_image_path=source_image_path,
        current_image_path=current_image_path,
        original_label=original_label,
        current_label=current_label or original_label,
        human_review_status=human_review_status,
        device_config_snapshot=device_config_snapshot,
        import_reason=import_reason,
    )
    insert("sample_library_entries", entry.to_dict())
    return entry


def get_entry(entry_id: str) -> SampleLibraryEntry | None:
    row = fetch_one("sample_library_entries", entry_id, "entry_id")
    return SampleLibraryEntry.from_dict(row) if row else None


def list_entries(project_id: str | None = None) -> list[SampleLibraryEntry]:
    if project_id:
        rows = fetch_all(
            "sample_library_entries",
            where="current_project_id = ? ORDER BY created_at DESC",
            params=(project_id,),
        )
    else:
        rows = fetch_all("sample_library_entries", where="1 ORDER BY created_at DESC")
    return [SampleLibraryEntry.from_dict(r) for r in rows]


# ── Search ─────────────────────────────────────────────────────────────

@dataclass
class SampleSearchFilter:
    material: str = ""
    surface_type: str = ""
    geometry_type: str = ""
    defect_type: str = ""
    label: str = ""  # OK / NG / specific defect name
    source_project_id: str = ""
    exclude_project_id: str = ""  # exclude current project
    source_kind: str = ""  # filter by source_kind
    human_review_status: str = ""


def search_samples(filt: SampleSearchFilter | None = None) -> list[SampleLibraryEntry]:
    """Search sample library across projects by material/surface/defect/label etc.

    Joins product_specs to filter by material, surface_type, geometry_type.
    """
    conn = get_connection()
    query = """
        SELECT sle.* FROM sample_library_entries sle
        LEFT JOIN product_specs ps ON ps.project_id = sle.source_project_id
        WHERE 1=1
    """
    params: list[str] = []

    if filt:
        if filt.material:
            query += " AND ps.material = ?"
            params.append(filt.material)
        if filt.surface_type:
            query += " AND ps.surface_type = ?"
            params.append(filt.surface_type)
        if filt.geometry_type:
            query += " AND ps.geometry_type = ?"
            params.append(filt.geometry_type)
        if filt.label:
            query += " AND (sle.current_label = ? OR sle.original_label = ?)"
            params.extend([filt.label, filt.label])
        if filt.source_project_id:
            query += " AND sle.source_project_id = ?"
            params.append(filt.source_project_id)
        if filt.exclude_project_id:
            query += " AND sle.current_project_id != ?"
            params.append(filt.exclude_project_id)
        if filt.source_kind:
            query += " AND sle.source_kind = ?"
            params.append(filt.source_kind)
        if filt.human_review_status:
            query += " AND sle.human_review_status = ?"
            params.append(filt.human_review_status)

    query += " ORDER BY sle.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [SampleLibraryEntry.from_dict(dict(r)) for r in rows]


# ── Import / Reference ─────────────────────────────────────────────────

@dataclass
class ImportResult:
    imported_count: int
    referenced_count: int
    skipped_count: int
    entries: list[SampleLibraryEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def import_samples(
    entry_ids: list[str],
    target_project_id: str,
    target_dataset_dir: str,
    *,
    import_reason: str = "",
) -> ImportResult:
    """Copy historical sample images into current project and record provenance.

    Images are physically copied into *target_dataset_dir*.
    New library entries are created with source_kind='historical_import'.
    """
    result = ImportResult(imported_count=0, referenced_count=0, skipped_count=0)

    for eid in entry_ids:
        entry = get_entry(eid)
        if entry is None:
            result.skipped_count += 1
            result.errors.append(f"Entry not found: {eid}")
            continue

        src_path = entry.current_image_path or entry.source_image_path or ""
        if not src_path or not os.path.isfile(src_path):
            result.skipped_count += 1
            result.errors.append(f"Source image missing: {src_path}")
            continue

        image_name = os.path.basename(src_path)
        dest_path = os.path.join(target_dataset_dir, image_name)

        try:
            os.makedirs(target_dataset_dir, exist_ok=True)
            shutil.copy2(src_path, dest_path)
        except OSError as e:
            result.skipped_count += 1
            result.errors.append(f"Copy failed: {src_path} -> {dest_path}: {e}")
            continue

        new_entry = add_to_library(
            current_project_id=target_project_id,
            current_image_path=dest_path,
            source_kind=SOURCE_KIND_IMPORT,
            source_project_id=entry.current_project_id,
            source_dataset_version_id=entry.current_dataset_version_id,
            source_capture_session_id=entry.source_capture_session_id,
            source_image_id=entry.source_image_id,
            source_image_path=src_path,
            original_label=entry.current_label or entry.original_label,
            current_label=entry.current_label or entry.original_label,
            human_review_status=entry.human_review_status,
            device_config_snapshot=entry.device_config_snapshot,
            import_reason=import_reason or f"Imported from {entry.current_project_id}",
        )
        result.entries.append(new_entry)
        result.imported_count += 1

    return result


def reference_samples(
    entry_ids: list[str],
    target_project_id: str,
    *,
    import_reason: str = "",
) -> ImportResult:
    """Reference historical samples without copying images.

    Creates library entries with source_kind='historical_reference' that
    point to the original asset location.
    """
    result = ImportResult(imported_count=0, referenced_count=0, skipped_count=0)

    for eid in entry_ids:
        entry = get_entry(eid)
        if entry is None:
            result.skipped_count += 1
            result.errors.append(f"Entry not found: {eid}")
            continue

        new_entry = add_to_library(
            current_project_id=target_project_id,
            current_image_path=entry.current_image_path or entry.source_image_path or "",
            source_kind=SOURCE_KIND_REFERENCE,
            source_project_id=entry.current_project_id,
            source_dataset_version_id=entry.current_dataset_version_id,
            source_capture_session_id=entry.source_capture_session_id,
            source_image_id=entry.source_image_id,
            source_image_path=entry.source_image_path or entry.current_image_path,
            original_label=entry.current_label or entry.original_label,
            current_label=entry.current_label or entry.original_label,
            human_review_status=entry.human_review_status,
            device_config_snapshot=entry.device_config_snapshot,
            import_reason=import_reason or f"Referenced from {entry.current_project_id}",
        )
        result.entries.append(new_entry)
        result.referenced_count += 1

    return result


# ── Summary ────────────────────────────────────────────────────────────

def get_source_kind_counts(project_id: str) -> dict[str, int]:
    """Return count of samples by source_kind for a project."""
    rows = fetch_all(
        "sample_library_entries",
        where="current_project_id = ?",
        params=(project_id,),
    )
    counts: dict[str, int] = {}
    for r in rows:
        kind = r.get("source_kind", SOURCE_KIND_CURRENT)
        counts[kind] = counts.get(kind, 0) + 1
    return counts
