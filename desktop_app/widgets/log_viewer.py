"""Real-time log viewer widget with auto-scroll."""

from __future__ import annotations

from PySide6.QtCore import Qt

from desktop_app.i18n import tr, bind
from desktop_app.theme_manager import ThemeManager
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
)


class LogViewer(QWidget):
    """Read-only text area for training logs, system logs, etc."""

    MAX_LINES = 5000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        clear_btn = QPushButton()
        bind(clear_btn, "log.clear")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)
        save_btn = QPushButton()
        bind(save_btn, "log.save")
        save_btn.setObjectName("secondaryBtn")
        save_btn.clicked.connect(self._save_to_file)
        toolbar.addWidget(save_btn)
        self._auto_scroll_btn = QPushButton()
        bind(self._auto_scroll_btn, "log.auto_scroll_on")
        self._auto_scroll_btn.setObjectName("secondaryBtn")
        self._auto_scroll_btn.setCheckable(True)
        self._auto_scroll_btn.setChecked(True)
        self._auto_scroll_btn.clicked.connect(self._toggle_auto_scroll)
        toolbar.addWidget(self._auto_scroll_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        font = QFont("Consolas", 10)
        self._text.setFont(font)
        c = ThemeManager.current()
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {c.BG_INPUT};
                color: {c.TEXT_PRIMARY};
                border: 1px solid {c.BORDER};
            }}
        """)
        layout.addWidget(self._text, 1)

    def append_line(self, text: str) -> None:
        self._text.appendPlainText(text)
        # Trim old lines if exceeded max
        if self._text.blockCount() > self.MAX_LINES:
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor,
                self._text.blockCount() - self.MAX_LINES,
            )
            cursor.removeSelectedText()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._text.setTextCursor(cursor)
        # Auto scroll
        if self._auto_scroll_btn.isChecked():
            scrollbar = self._text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._text.clear()

    def _save_to_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("log.save_title"), "training_log.txt", tr("log.save_filter")
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text.toPlainText())

    def _toggle_auto_scroll(self) -> None:
        if self._auto_scroll_btn.isChecked():
            bind(self._auto_scroll_btn, "log.auto_scroll_on")
        else:
            bind(self._auto_scroll_btn, "log.auto_scroll_off")

    def text(self) -> str:
        return self._text.toPlainText()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {c.BG_INPUT};
                color: {c.TEXT_PRIMARY};
                border: 1px solid {c.BORDER};
            }}
        """)
