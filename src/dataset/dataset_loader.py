"""Dataset loader for copper tube surface defect images and annotations."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from src.dataset.annotation_parser import (
    find_label_file,
    has_label,
    parse_yolo_annotation,
)
from src.dataset.label_schema import class_id_to_name, get_label_group
from src.fusion.decision_types import BBoxPrediction, ImageRecord
from src.utils.file_utils import collect_images


class DatasetLoader:
    """Loads images and YOLO annotations into ImageRecord objects.

    Provides filtering, statistics, and sampling capabilities.
    """

    def __init__(
        self,
        image_dir: str | Path,
        label_dir: str | Path,
        class_map: dict[int, str] | None = None,
        valid_extensions: set[str] | None = None,
    ):
        self.image_dir = Path(image_dir)
        self.label_dir = Path(label_dir)
        self.class_map = class_map or {}
        self.valid_extensions = valid_extensions or {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def scan(self) -> list[ImageRecord]:
        """Scan image directory and load all available annotations.

        Returns:
            List of ImageRecord objects for all found images.
        """
        image_paths = collect_images(self.image_dir, self.valid_extensions)
        records: list[ImageRecord] = []

        for img_path in image_paths:
            record = self._build_record(img_path)
            records.append(record)

        return records

    def _build_record(self, image_path: Path) -> ImageRecord:
        """Build a single ImageRecord from an image path."""
        label_path = find_label_file(image_path, self.label_dir)
        has_ann = label_path is not None

        annotations: list[BBoxPrediction] = []
        true_label = "unknown"

        if has_ann and label_path is not None:
            # We need image dimensions for pixel conversion; use a safe default
            # and parse from normalized coordinates
            raw = parse_yolo_annotation(label_path, 1, 1)
            for item in raw:
                bbox = BBoxPrediction(
                    type="bbox",
                    class_name=item["class_name"],
                    confidence=item["confidence"],
                    bbox_xyxy=item["bbox_xyxy"],  # normalized
                )
                annotations.append(bbox)

            # Derive the overall image label from the dominant defect class
            if annotations:
                # Use the first annotation's class as the primary label
                true_label = annotations[0].class_name

        return ImageRecord(
            image_path=str(image_path),
            true_label=true_label,
            has_annotation=has_ann,
            annotations=annotations,
        )

    def get_statistics(self) -> dict:
        """Compute dataset statistics.

        Returns:
            Dict with keys: total_images, annotated, unannotated,
            counts_by_class, counts_by_group.
        """
        records = self.scan()
        total = len(records)
        annotated = sum(1 for r in records if r.has_annotation)
        unannotated = total - annotated

        counts_by_class: dict[str, int] = {}
        counts_by_group: dict[str, int] = {"ok": 0, "ng": 0, "borderline": 0, "unknown": 0}

        for r in records:
            group = get_label_group(r.true_label)
            counts_by_group[group] = counts_by_group.get(group, 0) + 1

            label = r.true_label
            counts_by_class[label] = counts_by_class.get(label, 0) + 1

        return {
            "total_images": total,
            "annotated": annotated,
            "unannotated": unannotated,
            "counts_by_class": counts_by_class,
            "counts_by_group": counts_by_group,
        }

    @staticmethod
    def filter_by_group(
        records: list[ImageRecord],
        group: str,
    ) -> list[ImageRecord]:
        """Filter records by label group.

        Args:
            records: List of ImageRecord objects.
            group: One of 'ok', 'ng', 'borderline', 'acceptable_micro', 'unknown'.

        Returns:
            Filtered list of ImageRecord objects.
        """
        if group == "acceptable_micro":
            from src.dataset.label_schema import ACCEPTABLE_MICRO_CLASSES

            return [r for r in records if r.true_label in ACCEPTABLE_MICRO_CLASSES]

        return [r for r in records if get_label_group(r.true_label) == group]

    @staticmethod
    def get_image(
        records: list[ImageRecord],
        image_path: str | Path,
    ) -> Optional[ImageRecord]:
        """Find an ImageRecord by exact image path match.

        Args:
            records: List of ImageRecord objects.
            image_path: The image path to search for.

        Returns:
            Matching ImageRecord or None.
        """
        target = str(image_path)
        for r in records:
            if r.image_path == target:
                return r
        return None

    @staticmethod
    def sample(
        records: list[ImageRecord],
        n: int,
        group: str | None = None,
    ) -> list[ImageRecord]:
        """Randomly sample n records, optionally filtered by group.

        Args:
            records: List of ImageRecord objects.
            n: Number of records to sample.
            group: Optional group filter ('ok', 'ng', 'borderline', etc.).

        Returns:
            Sampled list of up to n ImageRecord objects.
        """
        pool = records
        if group is not None:
            pool = DatasetLoader.filter_by_group(records, group)

        if n >= len(pool):
            return list(pool)

        return random.sample(pool, n)
