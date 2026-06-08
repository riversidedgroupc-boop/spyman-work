"""Focus history recorder — tracks focus results over time for drift analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FocusHistoryRecorder:
    """Records and retrieves focus history for drift tracking."""

    def __init__(self, history_dir: str | Path = "focus_history") -> None:
        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    def record(self, camera_id: str, result: dict[str, Any]) -> None:
        """Record a single-camera focus result.

        Appends to a per-camera history file.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            **result,
        }

        history_file = self._history_dir / f"{camera_id.lower()}_history.jsonl"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info("Recorded focus history for %s: Z=%.3f", camera_id, result.get("best_z_mm", 0))

    def get_last_focus(self, camera_id: str) -> dict[str, Any] | None:
        """Get the most recent focus result for a camera.

        Returns:
            Dict with last result, or None if no history.
        """
        history_file = self._history_dir / f"{camera_id.lower()}_history.jsonl"
        if not history_file.exists():
            return None

        with open(history_file, encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return None

        return json.loads(lines[-1])

    def get_focus_drift(
        self, camera_id: str, current_z: float
    ) -> float | None:
        """Calculate drift from last recorded focus position.

        Args:
            camera_id: Camera ID.
            current_z: Current best Z position.

        Returns:
            Drift in mm, or None if no history.
        """
        last = self.get_last_focus(camera_id)
        if last is None:
            return None

        last_z = last.get("best_z_mm", 0)
        return round(current_z - last_z, 3)

    def record_run(self, multi_result: dict[str, Any]) -> None:
        """Record a multi-camera run summary."""
        summary_file = self._history_dir / f"{multi_result.get('run_id', 'unknown')}_summary.json"
        summary_file.write_text(
            json.dumps(multi_result, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
