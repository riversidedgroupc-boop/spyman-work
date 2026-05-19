"""Dataset quality checker — validate class balance, image integrity, label correspondence."""
from __future__ import annotations

import json
import os


class DatasetQualityChecker:
    """Check dataset quality and compute a quality score (0-100)."""

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.issues: list[str] = []

    def check_class_balance(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        labels_dir = os.path.join(self.dataset_path, "labels")
        if not os.path.isdir(labels_dir):
            self.issues.append("labels directory missing")
            return counts
        for fname in os.listdir(labels_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(labels_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split()
                        if parts:
                            class_id = parts[0]
                            counts[class_id] = counts.get(class_id, 0) + 1
            except Exception:
                self.issues.append(f"cannot parse label file: {fname}")
        if not counts:
            self.issues.append("no valid label files found")
        return counts

    def check_image_integrity(self) -> list[str]:
        corrupt: list[str] = []
        import cv2
        images_dir = os.path.join(self.dataset_path, "images")
        if not os.path.isdir(images_dir):
            self.issues.append("images directory missing")
            return corrupt
        for fname in sorted(os.listdir(images_dir)):
            fpath = os.path.join(images_dir, fname)
            img = cv2.imread(fpath)
            if img is None:
                corrupt.append(fname)
                self.issues.append(f"corrupt/unreadable image: {fname}")
        return corrupt

    def check_label_correspondence(self) -> tuple[list[str], list[str]]:
        images_dir = os.path.join(self.dataset_path, "images")
        labels_dir = os.path.join(self.dataset_path, "labels")
        missing_labels: list[str] = []
        missing_images: list[str] = []
        if not os.path.isdir(images_dir) or not os.path.isdir(labels_dir):
            return missing_labels, missing_images
        image_stems = set()
        for fname in os.listdir(images_dir):
            stem, _ = os.path.splitext(fname)
            image_stems.add(stem)
        label_stems = set()
        for fname in os.listdir(labels_dir):
            if fname.endswith(".txt"):
                stem, _ = os.path.splitext(fname)
                label_stems.add(stem)
        for stem in sorted(image_stems - label_stems):
            missing_labels.append(stem)
            self.issues.append(f"missing label for image: {stem}")
        for stem in sorted(label_stems - image_stems):
            missing_images.append(stem)
            self.issues.append(f"orphan label (no image): {stem}")
        return missing_labels, missing_images

    def compute_quality_score(self) -> float:
        issues_count = len(self.issues)
        if issues_count == 0:
            return 100.0
        if issues_count <= 3:
            return 80.0
        if issues_count <= 10:
            return 60.0
        if issues_count <= 20:
            return 40.0
        return 20.0

    def full_report(self) -> dict:
        class_counts = self.check_class_balance()
        corrupt = self.check_image_integrity()
        missing_labels, missing_images = self.check_label_correspondence()
        score = self.compute_quality_score()
        return {
            "quality_score": score,
            "class_counts": class_counts,
            "total_classes": len(class_counts),
            "corrupt_images": len(corrupt),
            "corrupt_image_list": corrupt[:50],
            "missing_labels": len(missing_labels),
            "missing_labels_list": missing_labels[:50],
            "orphan_labels": len(missing_images),
            "issues": self.issues[:100],
        }
