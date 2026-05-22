"""Project-level Python startup defaults."""

from __future__ import annotations

import os
from pathlib import Path


def _set_default_ultralytics_config_dir() -> None:
    if os.environ.get("YOLO_CONFIG_DIR"):
        return
    config_dir = Path(__file__).resolve().parent / "outputs" / "ultralytics"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(config_dir)


_set_default_ultralytics_config_dir()
