"""Sample export for retraining pipeline.

Converts reviewed samples into organized folder structure under
``outputs/sample_exports/``.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from core.review import ReviewRecord

LABEL_TO_FOLDER: dict[str, str] = {
    "true_defect": "hard_positive",
    "false_positive": "hard_negative",
    "acceptable_minor_defect": "acceptable_minor_defects",
    "unknown_defect": "unknown_defects",
    "label_error": "label_error",
    "retrain_candidate": "retrain_candidate",
}


def build_export_manifest(
    review_records: list[ReviewRecord],
    image_root: str | Path,
    output_dir: str | Path,
) -> list[dict]:
    """Build a manifest of files to export with destination paths."""
    image_root = Path(image_root)
    output_dir = Path(output_dir)
    manifest: list[dict] = []

    for rec in review_records:
        folder = LABEL_TO_FOLDER.get(rec.review_label)
        if folder is None:
            continue

        src = image_root / rec.image_name
        if not src.exists():
            # Try image_name as a relative path
            src = Path(rec.image_name)

        dest = output_dir / folder / rec.image_name

        manifest.append({
            "image_name": rec.image_name,
            "source_path": str(src),
            "export_path": str(dest),
            "review_label": rec.review_label,
            "class_name": rec.class_name,
            "confidence": rec.confidence,
            "bbox": rec.bbox,
            "reviewer_note": rec.reviewer_note,
        })

    return manifest


def export_reviewed_samples(
    review_records: list[ReviewRecord],
    image_root: str | Path,
    output_dir: str | Path,
    copy_images: bool = True,
) -> dict:
    """Export reviewed samples into organized folders.

    Returns a summary dict with counts per folder.
    """
    output_dir = Path(output_dir)
    manifest = build_export_manifest(review_records, image_root, output_dir)

    # Create folders
    for folder in set(LABEL_TO_FOLDER.values()):
        (output_dir / folder).mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    errors: list[str] = []

    for item in manifest:
        src = Path(item["source_path"])
        dest = Path(item["export_path"])

        if copy_images:
            try:
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(src, dest)
                    copied += 1
                else:
                    skipped += 1
                    errors.append(f"Source not found: {src}")
            except Exception as exc:
                skipped += 1
                errors.append(f"Copy error {src}: {exc}")

    # Write manifest CSV
    manifest_csv = output_dir / "manifest.csv"
    if manifest:
        with open(manifest_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=manifest[0].keys())
            writer.writeheader()
            writer.writerows(manifest)

    # Write manifest JSON
    manifest_json = output_dir / "manifest.json"
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Counts per folder
    folder_counts: dict[str, int] = {}
    for item in manifest:
        folder = LABEL_TO_FOLDER.get(item["review_label"], "unknown")
        folder_counts[folder] = folder_counts.get(folder, 0) + 1

    return {
        "total_records": len(review_records),
        "exported": len(manifest),
        "copied": copied,
        "skipped": skipped,
        "errors": errors,
        "folder_counts": folder_counts,
        "output_dir": str(output_dir),
    }
