"""Defect trace page — query defect events and NG images."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QComboBox, QSplitter,
)

from core.capture_session import list_capture_sessions, list_captured_images, get_classification_counts
from desktop_app.app_context import AppContext
from desktop_app.display import CLASS_LABEL_OPTIONS, class_label
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.widgets.image_viewer import ImageViewer


class DefectTracePage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Filter bar
        top = QHBoxLayout()
        session_label = QLabel()
        bind(session_label, "trace.session")
        top.addWidget(session_label)
        self._session_combo = QComboBox()
        top.addWidget(self._session_combo, 1)
        label_filter_label = QLabel()
        bind(label_filter_label, "trace.label_filter")
        top.addWidget(label_filter_label)
        self._label_combo = QComboBox()
        self._rebuild_label_combo()
        top.addWidget(self._label_combo)
        refresh_btn = QPushButton()
        bind(refresh_btn, "trace.query")
        refresh_btn.clicked.connect(self._refresh)
        top.addWidget(refresh_btn)
        top.addStretch()
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Image list table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([tr("trace.col_image"), tr("trace.col_camera"), tr("trace.col_label"), tr("trace.col_width"), tr("trace.col_height")])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        # Image viewer
        self._viewer = ImageViewer()
        splitter.addWidget(self._viewer)
        splitter.setSizes([400, 500])

        layout.addWidget(splitter, 1)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._stats_label)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo items and table headers on language change."""
        self._table.setHorizontalHeaderLabels([tr("trace.col_image"), tr("trace.col_camera"), tr("trace.col_label"), tr("trace.col_width"), tr("trace.col_height")])
        # Rebuild session combo
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)
        # Rebuild label combo (preserving non-translated items)
        self._rebuild_label_combo()

    def showEvent(self, event):
        super().showEvent(event)
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)

    def _rebuild_label_combo(self) -> None:
        self._label_combo.clear()
        self._label_combo.addItem(tr("app.all"), "")
        for value, label in CLASS_LABEL_OPTIONS:
            self._label_combo.addItem(label, value)

    def _refresh(self):
        sid = self._session_combo.currentData()
        if not sid:
            return

        label_filter = self._label_combo.currentData() or None

        images = list_captured_images(sid, label=label_filter)
        self._table.setRowCount(len(images))
        for row, img in enumerate(images):
            self._table.setItem(row, 0, QTableWidgetItem(img.get("image_name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(img.get("camera_id", "")))
            self._table.setItem(row, 2, QTableWidgetItem(class_label(img.get("classification_label", ""))))
            self._table.setItem(row, 3, QTableWidgetItem(str(img.get("width", ""))))
            self._table.setItem(row, 4, QTableWidgetItem(str(img.get("height", ""))))

        counts = get_classification_counts(sid)
        dist = ", ".join(f"{class_label(k)}:{v}" for k, v in sorted(counts.items()))
        self._stats_label.setText(tr("trace.stats", total=len(images), distribution=dist))

    def _on_row_selected(self):
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        path = self._resolve_path(name)
        if path and os.path.isfile(path):
            self._viewer.load_image(path)

    def _resolve_path(self, image_name: str) -> str:
        sid = self._session_combo.currentData()
        if not sid:
            return ""
        from core.capture_session import session_output_root, get_capture_session
        sess = get_capture_session(sid)
        if not sess:
            return ""
        output_root = sess.output_dir or session_output_root(sess.project_id)
        raw_dir = os.path.join(output_root, sid, "raw")
        for cam_dir in os.listdir(raw_dir) if os.path.isdir(raw_dir) else []:
            candidate = os.path.join(raw_dir, cam_dir, image_name)
            if os.path.isfile(candidate):
                return candidate
        return ""
