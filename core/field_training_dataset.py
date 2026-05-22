"""Build YOLO training dataset from field session anomaly reviews."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from core.anomaly_review import list_anomaly_reviews
from core.dataset_version import create_dataset_version
from core.defect_dictionary import list_defect_types
from core.field_session import get_field_session


# ── Constants ──────────────────────────────────────────────────────

_NEGATIVE_SOURCE_STATUSES = {"normal", "acceptable_texture", "noise_or_reflection"}
_EXCLUDED_STATUSES = {"unreviewed", "unknown_pending"}


# ── Result dataclass ───────────────────────────────────────────────

@dataclass
class FieldTrainingDatasetResult:
    dataset_dir: str
    yaml_path: str
    dataset_version_id: str | None
    field_session_id: str
    image_count: int
    positive_count: int
    negative_count: int
    skipped_unknown_count: int
    skipped_missing_bbox_count: int
    skipped_unassigned_count: int
    class_names: list[str]
    class_mapping: dict[str, int]
    source_review_ids: list[str]
    summary_path: str


# ── Helpers ────────────────────────────────────────────────────────

def _find_label_path(image_path: str) -> str | None:
    """Find sidecar .txt label for an image file."""
    base = os.path.splitext(image_path)[0]
    candidate = base + ".txt"
    return candidate if os.path.isfile(candidate) else None


def _has_bbox(label_path: str | None) -> bool:
    """Check if label file contains at least one valid YOLO bbox line."""
    if not label_path:
        return False
    try:
        with open(label_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 5:
                    return True
    except (OSError, UnicodeDecodeError):
        return False
    return False


def _resolve_class_name(defect_type, class_mapping: dict[str, int]) -> str | None:
    """For assigning class index to bbox lines — return matching class name."""
    for name in class_mapping:
        if (defect_type.code and defect_type.code == name) or \
           (defect_type.display_name_en and defect_type.display_name_en == name) or \
           (defect_type.display_name_zh and defect_type.display_name_zh == name):
            return name
    return None


# ── Main builder ───────────────────────────────────────────────────

def build_yolo_dataset_from_field_reviews(
    field_session_id: str,
    dataset_dir: str,
    *,
    project_id: str,
    spec_id: str = "",
    version_name: str = "",
    val_ratio: float = 0.2,
    include_negative_samples: bool = False,
    progress_callback: Callable[[str, float], None] | None = None,
) -> FieldTrainingDatasetResult:
    """Build YOLO detection dataset from confirmed defect anomaly reviews.

    Only reviews with ``review_status == "confirmed_defect"``, a non-null
    ``assigned_defect_type_id``, existing image path, and valid bbox label
    file are included as positive samples.

    Returns:
        FieldTrainingDatasetResult with paths, counts, class mapping, and
        source traceability.
    """
    _report(progress_callback, "checking field session...", 0.02)
    session = get_field_session(field_session_id)
    if not session:
        raise ValueError(f"field session not found: {field_session_id}")

    _report(progress_callback, "loading anomaly reviews...", 0.05)
    reviews = list_anomaly_reviews(field_session_id=field_session_id)

    _report(progress_callback, "loading defect types...", 0.08)
    defect_types_map: dict[str, object] = {}
    for dt in list_defect_types(project_id=project_id):
        defect_types_map[dt.defect_type_id] = dt

    # ── Classify reviews ──────────────────────────────────────────

    confirmed: list = []         # (review, defect_type)
    negative_maybe: list = []    # reviews with normal/texture/noise status
    skipped_unknown: list = []
    skipped_unassigned: list = []

    for r in reviews:
        if r.review_status == "confirmed_defect":
            if r.assigned_defect_type_id and r.assigned_defect_type_id in defect_types_map:
                confirmed.append((r, defect_types_map[r.assigned_defect_type_id]))
            else:
                skipped_unassigned.append(r)
        elif r.review_status in _NEGATIVE_SOURCE_STATUSES:
            negative_maybe.append(r)
        elif r.review_status in _EXCLUDED_STATUSES:
            skipped_unknown.append(r)

    _report(progress_callback, f"filtered: {len(confirmed)} confirmed, "
            f"{len(skipped_unassigned)} unassigned, {len(skipped_unknown)} excluded", 0.10)

    if not confirmed:
        raise ValueError(
            "No confirmed defects with assigned defect types are available for YOLO training. "
            f"Found {len(reviews)} reviews, "
            f"{sum(1 for r in reviews if r.review_status == 'confirmed_defect')} confirmed, "
            f"{len(skipped_unassigned)} unassigned."
        )

    # ── Build class mapping ───────────────────────────────────────

    class_mapping: dict[str, int] = {}
    for _, dt in confirmed:
        name = dt.code or dt.display_name_en or dt.display_name_zh
        if name and name not in class_mapping:
            class_mapping[name] = len(class_mapping)

    if not class_mapping:
        raise ValueError("No valid defect type names found in confirmed reviews.")

    class_names = [name for name, _ in sorted(class_mapping.items(), key=lambda x: x[1])]

    _report(progress_callback, f"class mapping: {class_mapping}", 0.12)

    # ── Validate bbox ─────────────────────────────────────────────

    bbox_missing: list = []
    valid_pairs: list = []  # (review, defect_type, label_path)

    for r, dt in confirmed:
        image_path = r.image_path
        if not image_path or not os.path.isfile(image_path):
            bbox_missing.append(r)
            continue
        label_path = _find_label_path(image_path)
        if not _has_bbox(label_path):
            bbox_missing.append(r)
            continue
        valid_pairs.append((r, dt, label_path))

    if not valid_pairs:
        raise ValueError(
            "No confirmed defects with bbox labels are available for YOLO training. "
            f"Found {len(confirmed)} confirmed reviews, "
            f"{len(bbox_missing)} missing bbox/image."
        )

    _report(progress_callback, f"{len(valid_pairs)} valid samples, "
            f"{len(bbox_missing)} missing bbox", 0.15)

    # ── Create directories ────────────────────────────────────────

    os.makedirs(dataset_dir, exist_ok=True)
    for split in ("train", "val"):
        os.makedirs(os.path.join(dataset_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "labels", split), exist_ok=True)

    # ── Copy positive samples ─────────────────────────────────────

    n_total = len(valid_pairs)
    val_every = max(2, round(1 / max(val_ratio, 0.001))) if len(valid_pairs) > 1 and val_ratio > 0 else 0
    used_names_by_split: dict[str, set[str]] = {"train": set(), "val": set()}

    source_review_ids: list[str] = []
    positive_count = 0

    for idx, (r, dt, label_path) in enumerate(valid_pairs):
        split = "val" if val_every and (idx + 1) % val_every == 0 else "train"
        img_src = r.image_path

        # Unique output name
        img_base = os.path.basename(img_src)
        out_name = img_base
        if out_name in used_names_by_split[split]:
            stem, ext = os.path.splitext(img_base)
            out_name = f"{r.review_id}_{stem}{ext}"
        used_names_by_split[split].add(out_name)

        dst_image = os.path.join(dataset_dir, "images", split, out_name)
        shutil.copy2(img_src, dst_image)

        # Copy label — remap class indices to stable mapping
        dst_label = os.path.join(dataset_dir, "labels", split,
                                 os.path.splitext(out_name)[0] + ".txt")
        _copy_label_with_remap(label_path, dst_label, dt, class_mapping)

        source_review_ids.append(r.review_id)
        positive_count += 1

        if idx % max(1, n_total // 10) == 0:
            _report(progress_callback, f"copying positives... {idx + 1}/{n_total}", 0.20 + 0.4 * idx / n_total)

    # ── Negative samples (optional) ───────────────────────────────

    negative_count = 0
    if include_negative_samples:
        neg_with_images = [
            r for r in negative_maybe
            if r.image_path and os.path.isfile(r.image_path)
        ]
        n_neg = len(neg_with_images)
        for idx, r in enumerate(neg_with_images):
            split = "val" if val_every and (positive_count + idx + 1) % val_every == 0 else "train"
            img_src = r.image_path
            img_base = os.path.basename(img_src)
            out_name = img_base
            if out_name in used_names_by_split[split]:
                stem, ext = os.path.splitext(img_base)
                out_name = f"{r.review_id}_{stem}{ext}"
            used_names_by_split[split].add(out_name)
            dst_image = os.path.join(dataset_dir, "images", split, out_name)
            shutil.copy2(img_src, dst_image)
            # Empty label file
            dst_label = os.path.join(dataset_dir, "labels", split,
                                     os.path.splitext(out_name)[0] + ".txt")
            with open(dst_label, "w", encoding="utf-8") as f:
                pass
            negative_count += 1
            if idx % max(1, n_neg // 5) == 0:
                _report(progress_callback, f"copying negatives... {idx + 1}/{n_neg}", 0.65 + 0.1 * idx / max(n_neg, 1))

    # ── Write data.yaml ───────────────────────────────────────────

    _report(progress_callback, "writing data.yaml...", 0.78)
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    _write_yaml(yaml_path, dataset_dir, class_names)

    # ── Write dataset_summary.json ────────────────────────────────

    _report(progress_callback, "writing summary...", 0.82)
    summary_path = os.path.join(dataset_dir, "dataset_summary.json")
    summary = {
        "field_session_id": field_session_id,
        "project_id": project_id,
        "spec_id": spec_id,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "skipped_unknown_count": len(skipped_unknown),
        "skipped_missing_bbox_count": len(bbox_missing),
        "skipped_unassigned_count": len(skipped_unassigned),
        "class_mapping": class_mapping,
        "source_review_ids": source_review_ids,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── Create dataset_version ────────────────────────────────────

    _report(progress_callback, "creating dataset version...", 0.90)
    total_images = positive_count + negative_count
    dv = create_dataset_version(
        project_id=project_id,
        spec_id=spec_id,
        capture_session_id=None,
        version_name=version_name or _default_version_name(),
        source_type="field_reviews",
        dataset_path=dataset_dir,
        yaml_path=yaml_path,
        image_count=total_images,
        class_names=json.dumps(class_names),
        val_split_ratio=val_ratio,
        quality_report=json.dumps(summary, ensure_ascii=False),
    )

    _report(progress_callback, "done", 1.0)

    return FieldTrainingDatasetResult(
        dataset_dir=dataset_dir,
        yaml_path=yaml_path,
        dataset_version_id=dv.version_id,
        field_session_id=field_session_id,
        image_count=total_images,
        positive_count=positive_count,
        negative_count=negative_count,
        skipped_unknown_count=len(skipped_unknown),
        skipped_missing_bbox_count=len(bbox_missing),
        skipped_unassigned_count=len(skipped_unassigned),
        class_names=class_names,
        class_mapping=class_mapping,
        source_review_ids=source_review_ids,
        summary_path=summary_path,
    )


# ── Internal helpers ───────────────────────────────────────────────

def _report(cb: Callable[[str, float], None] | None, msg: str, pct: float) -> None:
    if cb:
        try:
            cb(msg, pct)
        except Exception:
            pass


def _default_version_name() -> str:
    return datetime.now().strftime("v%Y%m%d_%H%M%S")


def _write_yaml(yaml_path: str, dataset_dir: str, class_names: list[str]) -> None:
    root = os.path.abspath(dataset_dir).replace("\\", "/")
    lines = [
        f"path: {root}",
        "train: images/train",
        "val: images/val",
        f"nc: {len(class_names)}",
        "names:",
    ]
    for idx, name in enumerate(class_names):
        lines.append(f"  {idx}: {name}")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _copy_label_with_remap(
    src_label: str,
    dst_label: str,
    defect_type,
    class_mapping: dict[str, int],
) -> None:
    """Copy label file, remapping class indices to the stable class_mapping.

    The source label file uses the original (potentially inconsistent) class
    index. We look up the defect type name, map to the stable index, and
    rewrite all lines accordingly.
    """
    target_name = _resolve_class_name(defect_type, class_mapping)
    if target_name is None:
        # Fallback: copy as-is
        shutil.copy2(src_label, dst_label)
        return

    class_index = class_mapping[target_name]

    try:
        with open(src_label, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        shutil.copy2(src_label, dst_label)
        return

    with open(dst_label, "w", encoding="utf-8") as f:
        for line in lines:
            line = line.strip()
            if not line:
                f.write("\n")
                continue
            parts = line.split()
            if len(parts) >= 5:
                # Replace class index (first field) with stable index
                parts[0] = str(class_index)
            f.write(" ".join(parts) + "\n")
