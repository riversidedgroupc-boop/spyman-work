"""Build desktop-generated capture sessions into YOLO-style datasets."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from typing import Callable

from core.capture_session import get_capture_session, list_captured_images
from core.dataset_quality import DatasetQualityChecker
from core.dataset_version import create_dataset_version


IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
BACKGROUND_LABELS = {"", "OK", "UNKNOWN", "INTERFERENCE", "UNCERTAIN"}


@dataclass
class DatasetBuildResult:
    dataset_dir: str
    yaml_path: str
    image_count: int
    label_file_count: int
    missing_bbox_count: int
    class_names: list[str]
    quality_score: float = 0.0


def build_yolo_dataset_from_session(
    session_id: str,
    dataset_dir: str,
    val_ratio: float = 0.2,
    *,
    project_id: str = "",
    spec_id: str = "",
    version_name: str = "",
    progress_callback: Callable[[str, float], None] | None = None,
) -> DatasetBuildResult:
    """Create a YOLO detection dataset from captured images.

    Existing sidecar ``.txt`` labels next to raw images are copied. Images without
    sidecar labels get an empty label file, which is valid YOLO background data and
    makes missing bbox coverage explicit through ``missing_bbox_count``.

    If *project_id* is given, a DatasetVersion record is automatically created
    with quality score after the build completes.
    """
    session = get_capture_session(session_id)
    if not session:
        raise ValueError(f"capture session not found: {session_id}")

    rows = [
        r for r in list_captured_images(session_id)
        if os.path.splitext(r.get("image_name", ""))[1].lower() in IMAGE_EXTENSIONS
    ]
    if not rows:
        raise ValueError("no captured images found for dataset generation")

    _report(progress_callback, "creating directories...", 0.05)
    os.makedirs(dataset_dir, exist_ok=True)
    for split in ("train", "val"):
        os.makedirs(os.path.join(dataset_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "labels", split), exist_ok=True)

    class_names = sorted({
        r.get("classification_label", "")
        for r in rows
        if r.get("classification_label", "") not in BACKGROUND_LABELS
    }) or ["defect"]

    label_file_count = 0
    missing_bbox_count = 0
    val_every = 0
    if len(rows) > 1 and val_ratio > 0:
        val_every = max(2, round(1 / min(val_ratio, 0.5)))

    total = len(rows)
    for index, row in enumerate(rows):
        src = row.get("image_path", "")
        if not os.path.isfile(src):
            continue
        split = "val" if val_every and (index + 1) % val_every == 0 else "train"
        image_name = row.get("image_name") or os.path.basename(src)
        dst_image = os.path.join(dataset_dir, "images", split, image_name)
        shutil.copy2(src, dst_image)

        src_label = os.path.splitext(src)[0] + ".txt"
        dst_label = os.path.join(
            dataset_dir,
            "labels",
            split,
            os.path.splitext(image_name)[0] + ".txt",
        )
        if os.path.isfile(src_label):
            shutil.copy2(src_label, dst_label)
            label_file_count += 1
        else:
            open(dst_label, "w", encoding="utf-8").close()
            if row.get("classification_label", "") not in BACKGROUND_LABELS:
                missing_bbox_count += 1

        if index % max(1, total // 20) == 0:
            _report(progress_callback, f"copying files... {index+1}/{total}", 0.1 + 0.7 * (index + 1) / total)

    _report(progress_callback, "writing dataset YAML...", 0.85)
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    _write_dataset_yaml(yaml_path, dataset_dir, class_names)

    # --- Quality check ---
    _report(progress_callback, "running quality check...", 0.90)
    checker = DatasetQualityChecker(dataset_dir)
    quality_report = checker.full_report()
    quality_score = quality_report["quality_score"]

    # --- Auto-create DatasetVersion record ---
    if project_id:
        _report(progress_callback, "creating version record...", 0.95)
        create_dataset_version(
            project_id=project_id,
            spec_id=spec_id or session.spec_id,
            capture_session_id=session_id,
            version_name=version_name or _default_version_name(),
            source_type="session",
            dataset_path=dataset_dir,
            yaml_path=yaml_path,
            image_count=len(rows),
            class_names=json.dumps(class_names),
            val_split_ratio=val_ratio,
            quality_score=quality_score,
            quality_report=json.dumps(quality_report),
        )

    _report(progress_callback, "done", 1.0)
    return DatasetBuildResult(
        dataset_dir=dataset_dir,
        yaml_path=yaml_path,
        image_count=len(rows),
        label_file_count=label_file_count,
        missing_bbox_count=missing_bbox_count,
        class_names=class_names,
        quality_score=quality_score,
    )


def _default_version_name() -> str:
    from datetime import datetime
    return datetime.now().strftime("v%Y%m%d_%H%M%S")


def _report(cb: Callable[[str, float], None] | None, msg: str, pct: float) -> None:
    if cb:
        try:
            cb(msg, pct)
        except Exception:
            pass


def _write_dataset_yaml(yaml_path: str, dataset_dir: str, class_names: list[str]) -> None:
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
