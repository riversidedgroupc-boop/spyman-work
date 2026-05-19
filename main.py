"""CX-vision Phase 5 — Desktop application entry point."""
from __future__ import annotations

import sys
import os

# Ensure the project root is on sys.path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.storage import init_db
from desktop_app.main_window import MainWindow
from desktop_app.constants import APP_NAME, APP_ORG


def main() -> None:
    init_db()

    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
