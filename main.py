"""CX-vision Phase 5 — Desktop application entry point."""
from __future__ import annotations

import sys
import os

# Ensure the project root is on sys.path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402

from PySide6.QtCore import QSettings  # noqa: E402

from core.storage import init_db  # noqa: E402
from core.workspace_paths import ensure_workspace_dirs  # noqa: E402
from desktop_app.main_window import MainWindow  # noqa: E402
from desktop_app.constants import APP_NAME, APP_ORG  # noqa: E402
from desktop_app.theme_manager import ThemeManager, PALETTE_LIGHT, PALETTE_DARK  # noqa: E402


def main() -> None:
    ensure_workspace_dirs()
    init_db()

    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Chinese-first default font (Microsoft YaHei on Windows, PingFang SC on macOS)
    _default_font = QFont()
    _default_font.setFamilies([
        "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC",
        "WenQuanYi Micro Hei", "system-ui", "sans-serif",
    ])
    _default_font.setPixelSize(13)
    app.setFont(_default_font)

    # Theme manager — restore persisted preference, default to light
    tm = ThemeManager.instance()
    settings = QSettings(APP_ORG, APP_NAME)
    stored_theme = settings.value("theme/appearance", "light")
    if stored_theme == "dark":
        tm.set_theme(PALETTE_DARK)
    # Persist on change
    tm.theme_changed.connect(
        lambda: settings.setValue(
            "theme/appearance", "dark" if tm.is_dark() else "light"
        )
    )

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
