"""Bottom status bar widget."""
from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel

from desktop_app.i18n import tr, bind


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._context_label = QLabel()
        bind(self._context_label, "status.no_project")
        self._context_label.setStyleSheet("color: #B0B0B0; padding: 0 8px;")
        self.addPermanentWidget(self._context_label)

    def set_context_text(self, text: str) -> None:
        self._context_label.setText(text)
        self.showMessage(text, 3000)
