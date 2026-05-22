"""Log Center page — multi-tab log viewer with filtering and search."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QFileDialog, QMessageBox,
)

from core.log_manager import LogManager
from desktop_app.workers.log_worker import LogTailWorker
from desktop_app.i18n import tr, bind, I18nManager


LEVEL_MAP = {
    "DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4,
}
LEVEL_NAMES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

TAB_KEYS = {
    "app": "log_center.tab_app",
    "camera": "log_center.tab_camera",
    "inference": "log_center.tab_inference",
    "system": "log_center.tab_system",
    "error": "log_center.tab_error",
    "audit": "log_center.tab_audit",
}


class LogCenterPage(QWidget):
    """6-tab log viewer with level filter, search, and export."""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lm: LogManager | None = None
        self._worker: LogTailWorker | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._refresh_current_tab)
        self._full_content: dict[str, str] = {}  # category -> full text
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Toolbar ---
        toolbar = QHBoxLayout()

        level_label = QLabel()
        bind(level_label, "log_center.filter_level")
        toolbar.addWidget(level_label)
        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL"] + LEVEL_NAMES)
        self._level_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(self._level_combo)

        search_label = QLabel()
        bind(search_label, "log_center.filter_search")
        toolbar.addWidget(search_label)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("log_center.filter_search"))
        self._search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_edit)

        self._auto_cb = QCheckBox()
        bind(self._auto_cb, "log_center.auto_refresh")
        self._auto_cb.setChecked(False)
        self._auto_cb.toggled.connect(self._toggle_auto_refresh)
        toolbar.addWidget(self._auto_cb)

        export_btn = QPushButton()
        bind(export_btn, "log_center.export")
        export_btn.clicked.connect(self._export_current)
        toolbar.addWidget(export_btn)

        clear_btn = QPushButton()
        bind(clear_btn, "log_center.clear")
        clear_btn.clicked.connect(self._clear_current)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- Tab widget ---
        self._tabs = QTabWidget()
        self._viewers: dict[str, QTextEdit] = {}
        for cat in LogManager.CATEGORIES:
            viewer = QTextEdit()
            viewer.setReadOnly(True)
            viewer.setStyleSheet(
                "background-color: #1E1E1E; color: #D4D4D4;"
                "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;"
            )
            tab_key = TAB_KEYS.get(cat, cat)
            self._tabs.addTab(viewer, tr(tab_key))
            self._viewers[cat] = viewer
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if self._lm is None:
            try:
                self._lm = LogManager.instance()
            except RuntimeError:
                self._lm = LogManager()
        self._load_all_logs()

    # ------------------------------------------------------------------
    # Log loading
    # ------------------------------------------------------------------

    def _load_all_logs(self):
        if self._lm is None:
            return
        for cat in LogManager.CATEGORIES:
            path = self._lm.get_log_path(cat)
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self._full_content[cat] = content
                except Exception:
                    self._full_content[cat] = ""
            else:
                self._full_content[cat] = ""
        self._apply_filter()

    def _refresh_current_tab(self):
        if self._lm is None:
            return
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        cat = LogManager.CATEGORIES[idx]
        path = self._lm.get_log_path(cat)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self._full_content[cat] = f.read()
            except Exception:
                pass
        self._apply_filter()

    def _on_tab_changed(self, _idx: int):
        self._apply_filter()

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        cat = LogManager.CATEGORIES[idx]
        content = self._full_content.get(cat, "")
        viewer = self._viewers.get(cat)
        if viewer is None:
            return

        level_filter = self._level_combo.currentText()
        search_text = self._search_edit.text().lower()

        lines = content.split("\n")
        if level_filter == "ALL" and not search_text:
            viewer.setPlainText(content)
            return

        filtered: list[str] = []
        min_level = LEVEL_MAP.get(level_filter, -1)
        for line in lines:
            if min_level >= 0:
                # Level is between timestamp and message: "2025-... | INFO     | ..."
                matched = False
                for lvl_name, lvl_val in LEVEL_MAP.items():
                    if f"| {lvl_name}" in line and lvl_val >= min_level:
                        matched = True
                        break
                if not matched:
                    continue
            if search_text and search_text not in line.lower():
                continue
            filtered.append(line)

        viewer.setPlainText("\n".join(filtered))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_auto_refresh(self, enabled: bool):
        if enabled:
            self._poll_timer.start(2000)  # 2-second poll
            # Start tail worker
            idx = self._tabs.currentIndex()
            if idx >= 0:
                cat = LogManager.CATEGORIES[idx]
                path = self._lm.get_log_path(cat) if self._lm else ""
                if path:
                    self._start_tail_worker(path)
        else:
            self._poll_timer.stop()
            self._stop_tail_worker()

    def _start_tail_worker(self, path: str):
        self._stop_tail_worker()
        self._worker = LogTailWorker(path, poll_interval_ms=2000)
        self._worker.message.connect(self._on_tail_line)
        self._worker.start()

    def _stop_tail_worker(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(1000)
            self._worker = None

    def _on_tail_line(self, line: str):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        cat = LogManager.CATEGORIES[idx]
        viewer = self._viewers.get(cat)
        if viewer:
            viewer.append(line)
            # Keep buffer manageable
            if viewer.document().blockCount() > 5000:
                viewer.clear()
                viewer.setPlainText(self._full_content.get(cat, "")[-100000:])

    def _export_current(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        cat = LogManager.CATEGORIES[idx]
        viewer = self._viewers.get(cat)
        if viewer is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, tr("log_center.export"), f"{cat}.log",
            "Log Files (*.log *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(viewer.toPlainText())
            except Exception as e:
                QMessageBox.warning(self, tr("app.error"), str(e))

    def _clear_current(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        cat = LogManager.CATEGORIES[idx]
        viewer = self._viewers.get(cat)
        if viewer:
            viewer.clear()
            self._full_content[cat] = ""

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        for i, cat in enumerate(LogManager.CATEGORIES):
            tab_key = TAB_KEYS.get(cat, cat)
            self._tabs.setTabText(i, tr(tab_key))
