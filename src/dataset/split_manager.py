"""Train/val/test split management for copper tube defect dataset."""

from __future__ import annotations

import random
from pathlib import Path

from src.fusion.decision_types import ImageRecord


class SplitManager:
    """Manages dataset splits (train/val/test) stored as text files.

    Each split file contains one image path (or stem) per line.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    @staticmethod
    def load_split(split_file: str | Path) -> list[str]:
        """Load list of image paths/names from a split text file.

        Lines starting with '#' are treated as comments and skipped.
        Blank lines are ignored.

        Args:
            split_file: Path to the split file.

        Returns:
            List of image path strings. Returns empty list if the file
            does not exist.
        """
        path = Path(split_file)
        if not path.exists():
            return []

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            result.append(stripped)
        return result

    @staticmethod
    def save_split(
        image_paths: list[str | Path],
        split_file: str | Path,
    ) -> None:
        """Save a list of image paths to a split file.

        Args:
            image_paths: Image paths to write.
            split_file: Destination file path.
        """
        out = Path(split_file)
        out.parent.mkdir(parents=True, exist_ok=True)

        with out.open("w", encoding="utf-8") as f:
            for img in image_paths:
                f.write(f"{img}\n")

    @staticmethod
    def filter_by_split(
        records: list[ImageRecord],
        split_file: str | Path,
    ) -> list[ImageRecord]:
        """Filter ImageRecord list to only those whose path appears in the split.

        Matches by exact string comparison and by filename stem.

        Args:
            records: List of ImageRecord objects.
            split_file: Path to the split file.

        Returns:
            ImageRecord objects whose image_path matches an entry in the split.
        """
        split_paths = SplitManager.load_split(split_file)
        if not split_paths:
            return []

        split_set = set(split_paths)
        # Also index by stem for flexible matching
        split_stems = {Path(s).stem for s in split_paths}

        result: list[ImageRecord] = []
        for r in records:
            if r.image_path in split_set:
                result.append(r)
            elif Path(r.image_path).stem in split_stems:
                result.append(r)

        return result

    def create_random_split(
        self,
        records: list[ImageRecord],
        test_ratio: float = 0.2,
    ) -> tuple[list[ImageRecord], list[ImageRecord]]:
        """Create a random train/test split from a list of records.

        Args:
            records: Full list of ImageRecord objects.
            test_ratio: Fraction of data to use for test (0.0 - 1.0).
            seed: Random seed for reproducibility.

        Returns:
            Tuple of (train_records, test_records).
        """
        if test_ratio < 0.0 or test_ratio > 1.0:
            raise ValueError(f"test_ratio must be in [0, 1], got {test_ratio}")

        shuffled = list(records)
        rng = random.Random(self.seed)
        rng.shuffle(shuffled)

        if test_ratio == 0.0:
            return shuffled, []
        if test_ratio == 1.0:
            return [], shuffled

        split_idx = int(len(shuffled) * (1.0 - test_ratio))
        train = shuffled[:split_idx]
        test = shuffled[split_idx:]

        return train, test
