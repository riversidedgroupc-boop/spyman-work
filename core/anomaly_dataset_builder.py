"""Build anomaly-detection (PatchCore) datasets from capture sessions.

Anomaly datasets contain only OK / background images — the model learns
what "normal" looks like and flags anything else as anomalous.

Output directory structure (anomalib-compatible):
    <dataset_dir>/
        ground_truth/
            defect/          (empty — no anomalies in training)
        test/
            good/            (OK test images)
            defect/          (NG test images if include_ng_test=True)
        train/
            good/            (OK training images)
"""

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
class AnomalyDatasetResult:
    dataset_dir: str
    train_count: int
    test_good_count: int
    test_defect_count: int
    class_names: list[str]
    quality_score: float = 0.0


def build_anomaly_dataset_from_session(
    session_id: str,
    dataset_dir: str,
    *,
    train_ratio: float = 0.8,
    include_ng_test: bool = True,
    project_id: str = "",
    spec_id: str = "",
    version_name: str = "",
    progress_callback: Callable[[str, float], None] | None = None,
) -> AnomalyDatasetResult:
    """Build an anomaly-detection dataset from a capture session.

    Only OK-classified images go into ``train/good/``.
    If *include_ng_test* is True, NG images go into ``test/defect/``,
    otherwise they are skipped entirely.
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

    # Separate OK vs NG
    ok_rows = [
        r for r in rows
        if r.get("classification_label", "") in BACKGROUND_LABELS
    ]
    ng_rows = [
        r for r in rows
        if r.get("classification_label", "") not in BACKGROUND_LABELS
    ]

    if not ok_rows:
        raise ValueError("no OK images found — cannot build anomaly dataset")

    # Collect class names from NG images
    class_names = sorted({
        r.get("classification_label", "defect")
        for r in ng_rows
    }) or ["defect"]

    # Split OK images: train / test
    split_idx = max(1, int(len(ok_rows) * train_ratio))
    train_ok = ok_rows[:split_idx]
    test_ok = ok_rows[split_idx:]

    _report(progress_callback, "creating directories...", 0.05)
    for sub in ("train/good", "test/good", "test/defect", "ground_truth/defect"):
        os.makedirs(os.path.join(dataset_dir, sub), exist_ok=True)

    # Copy training OK images
    _report(progress_callback, f"copying {len(train_ok)} train OK images...", 0.1)
    for i, row in enumerate(train_ok):
        src = row.get("image_path", "")
        if not os.path.isfile(src):
            continue
        image_name = row.get("image_name") or os.path.basename(src)
        shutil.copy2(src, os.path.join(dataset_dir, "train", "good", image_name))
        if i % max(1, len(train_ok) // 10) == 0:
            _report(progress_callback, f"train OK {i+1}/{len(train_ok)}", 0.1 + 0.4 * (i + 1) / len(train_ok))

    # Copy test OK images
    _report(progress_callback, f"copying {len(test_ok)} test OK images...", 0.5)
    for i, row in enumerate(test_ok):
        src = row.get("image_path", "")
        if not os.path.isfile(src):
            continue
        image_name = row.get("image_name") or os.path.basename(src)
        shutil.copy2(src, os.path.join(dataset_dir, "test", "good", image_name))

    # Copy test NG images (optional)
    test_defect_count = 0
    if include_ng_test and ng_rows:
        _report(progress_callback, f"copying {len(ng_rows)} test NG images...", 0.6)
        for i, row in enumerate(ng_rows):
            src = row.get("image_path", "")
            if not os.path.isfile(src):
                continue
            image_name = row.get("image_name") or os.path.basename(src)
            shutil.copy2(src, os.path.join(dataset_dir, "test", "defect", image_name))
            test_defect_count += 1

    # Quality check on train/good
    _report(progress_callback, "running quality check...", 0.90)
    checker = DatasetQualityChecker(os.path.join(dataset_dir, "train", "good"))
    quality_report = checker.full_report()
    quality_score = quality_report["quality_score"]

    # Auto-create DatasetVersion
    if project_id:
        _report(progress_callback, "creating version record...", 0.95)
        create_dataset_version(
            project_id=project_id,
            spec_id=spec_id or session.spec_id,
            capture_session_id=session_id,
            version_name=version_name or _default_version_name_anomaly(),
            source_type="anomaly",
            dataset_path=dataset_dir,
            yaml_path="",
            image_count=len(train_ok) + len(test_ok) + test_defect_count,
            class_names=json.dumps(class_names),
            val_split_ratio=1.0 - train_ratio,
            quality_score=quality_score,
            quality_report=json.dumps(quality_report),
        )

    _report(progress_callback, "done", 1.0)
    return AnomalyDatasetResult(
        dataset_dir=dataset_dir,
        train_count=len(train_ok),
        test_good_count=len(test_ok),
        test_defect_count=test_defect_count,
        class_names=class_names,
        quality_score=quality_score,
    )


def _default_version_name_anomaly() -> str:
    from datetime import datetime
    return datetime.now().strftime("anom_v%Y%m%d_%H%M%S")


def _report(cb: Callable[[str, float], None] | None, msg: str, pct: float) -> None:
    if cb:
        try:
            cb(msg, pct)
        except Exception:
            pass
