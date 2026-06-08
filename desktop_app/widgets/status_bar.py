"""Bottom status bar widget."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel

from desktop_app.i18n import tr, bind
from desktop_app.theme_manager import ThemeManager


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._context_label = QLabel()
        bind(self._context_label, "status.no_project")
        self._context_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; padding: 0 8px;")
        self.addPermanentWidget(self._context_label)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def set_context_text(self, text: str) -> None:
        self._context_label.setText(text)
        self.showMessage(text, 3000)

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._context_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; padding: 0 8px;")

