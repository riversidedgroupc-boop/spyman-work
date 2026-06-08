"""Runtime Qt Designer .ui loader helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QWidget


def load_ui(ui_path: Path, parent: QWidget | None = None) -> QWidget:
    """Load a Qt Designer .ui file at runtime."""
    ui_file = QFile(str(ui_path))
    if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Unable to open UI file: {ui_path}")
    try:
        loaded = QUiLoader().load(ui_file, parent)
    finally:
        ui_file.close()

    if loaded is None:
        raise RuntimeError(f"Unable to load UI file: {ui_path}")
    return loaded
