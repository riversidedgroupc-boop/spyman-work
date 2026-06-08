"""Focus image and data saver — manages run directory structure."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FocusImageSaver:
    """Saves focus samples, curves, and best images to a run directory."""

    def __init__(self, run_dir: str | Path) -> None:
        self._run_dir = Path(run_dir)
        self._run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def save_sample(
        self, camera_id: str, z_mm: float, image: np.ndarray
    ) -> str:
        """Save a single focus sample image.

        Returns:
            File path string.
        """
        samples_dir = self._run_dir / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)

        filename = f"z_{z_mm:.3f}.png"
        filepath = samples_dir / filename
        cv2.imwrite(str(filepath), image)
        logger.debug("Saved sample: %s", filepath)
        return str(filepath)

    def save_best_image(self, camera_id: str, image: np.ndarray) -> str:
        """Save the best-focus verification image.

        Returns:
            File path string.
        """
        filename = f"best_{camera_id.lower()}.png"
        filepath = self._run_dir / filename
        cv2.imwrite(str(filepath), image)
        logger.info("Saved best image: %s", filepath)
        return str(filepath)

    def save_curve_csv(
        self, camera_id: str, z_positions: list[float], scores: list[float]
    ) -> str:
        """Save focus curve data as CSV.

        Returns:
            File path string.
        """
        filename = f"curve_{camera_id.lower()}.csv"
        filepath = self._run_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["z_mm", "score"])
            for z, s in zip(z_positions, scores):
                writer.writerow([f"{z:.3f}", f"{s:.1f}"])

        logger.info("Saved curve CSV: %s (%d points)", filepath, len(z_positions))
        return str(filepath)

    def save_summary(self, summary: dict[str, Any]) -> str:
        """Save the run summary JSON.

        Returns:
            File path string.
        """
        filepath = self._run_dir / "summary.json"
        filepath.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Saved summary: %s", filepath)
        return str(filepath)

    def save_config_snapshot(self, config: dict[str, Any]) -> str:
        """Save a snapshot of the configuration used for this run."""
        filepath = self._run_dir / "config_snapshot.json"
        filepath.write_text(
            json.dumps(config, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return str(filepath)
