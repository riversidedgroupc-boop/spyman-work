"""Defect trace page — query defect events and NG images."""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QComboBox, QSplitter,
    QDateEdit, QProgressBar,
)

from core.capture_session import list_capture_sessions, list_captured_images, get_classification_counts
from core.production_event import list_defect_events
from core.model_version import list_model_versions
from desktop_app.app_context import AppContext
from desktop_app.display import CLASS_LABEL_OPTIONS, class_label
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.widgets.image_viewer import ImageViewer


class DefectTracePage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._defect_events_data: list = []  # Full DefectEvent objects for row selection
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Data source toggle
        src_row = QHBoxLayout()
        src_label = QLabel()
        bind(src_label, "trace.source")
        src_row.addWidget(src_label)
        self._source_combo = QComboBox()
        self._source_combo.addItem(tr("trace.source_samples"), "captured_images")
        self._source_combo.addItem(tr("trace.source_events"), "production_defect_events")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        src_row.addWidget(self._source_combo)
        src_row.addStretch()
        layout.addLayout(src_row)

        # Filter bar — session/label mode
        self._sample_filter = QHBoxLayout()
        session_label = QLabel()
        bind(session_label, "trace.session")
        self._sample_filter.addWidget(session_label)
        self._session_combo = QComboBox()
        self._sample_filter.addWidget(self._session_combo, 1)
        label_filter_label = QLabel()
        bind(label_filter_label, "trace.label_filter")
        self._sample_filter.addWidget(label_filter_label)
        self._label_combo = QComboBox()
        self._rebuild_label_combo()
        self._sample_filter.addWidget(self._label_combo)
        layout.addLayout(self._sample_filter)

        # Filter bar — defect event mode
        self._event_filter = QHBoxLayout()
        ev_cam_label = QLabel()
        bind(ev_cam_label, "trace.col_camera")
        self._event_filter.addWidget(ev_cam_label)
        self._ev_camera_combo = QComboBox()
        self._ev_camera_combo.addItem(tr("app.all"), "")
        for i in range(1, 7):
            self._ev_camera_combo.addItem(f"cam{i}", f"cam{i}")
        self._event_filter.addWidget(self._ev_camera_combo)

        ev_type_label = QLabel()
        bind(ev_type_label, "defect.defect_type")
        self._event_filter.addWidget(ev_type_label)
        self._ev_type_combo = QComboBox()
        self._ev_type_combo.addItem(tr("app.all"), "")
        for value, label in CLASS_LABEL_OPTIONS:
            self._ev_type_combo.addItem(label, value)
        self._event_filter.addWidget(self._ev_type_combo)

        ev_model_label = QLabel()
        bind(ev_model_label, "defect.model_version")
        self._event_filter.addWidget(ev_model_label)
        self._ev_model_combo = QComboBox()
        self._ev_model_combo.addItem(tr("app.all"), "")
        self._event_filter.addWidget(self._ev_model_combo)

        ev_from_label = QLabel()
        bind(ev_from_label, "trace.date_from")
        self._event_filter.addWidget(ev_from_label)
        self._ev_date_from = QDateEdit()
        self._ev_date_from.setCalendarPopup(True)
        self._ev_date_from.setDate(datetime.now().date() - timedelta(days=7))
        self._event_filter.addWidget(self._ev_date_from)

        ev_to_label = QLabel()
        bind(ev_to_label, "trace.date_to")
        self._event_filter.addWidget(ev_to_label)
        self._ev_date_to = QDateEdit()
        self._ev_date_to.setCalendarPopup(True)
        self._ev_date_to.setDate(datetime.now().date())
        self._event_filter.addWidget(self._ev_date_to)
        layout.addLayout(self._event_filter)
        self._event_filter_widgets = [
            self._ev_camera_combo, self._ev_type_combo, self._ev_model_combo,
            self._ev_date_from, self._ev_date_to,
        ]
        # Find all labels in event filter to hide/show
        for i in range(self._event_filter.count()):
            w = self._event_filter.itemAt(i).widget()
            if w:
                self._event_filter_widgets.append(w)

        # Query button
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton()
        bind(refresh_btn, "trace.query")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

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

        # Stats + position histogram
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._stats_label)

        self._histogram = QProgressBar()
        self._histogram.setRange(0, 100)
        self._histogram.setVisible(False)
        self._histogram.setFormat("")
        layout.addWidget(self._histogram)

        # Initially show sample mode
        self._on_source_changed(0)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo items and table headers on language change."""
        src = self._source_combo.currentData()
        self._set_table_headers(src)
        # Rebuild source combo texts
        self._source_combo.setItemText(0, tr("trace.source_samples"))
        self._source_combo.setItemText(1, tr("trace.source_events"))
        # Rebuild session combo
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)
        # Rebuild label combo
        self._rebuild_label_combo()
        # Rebuild model combo
        self._ev_model_combo.clear()
        self._ev_model_combo.addItem(tr("app.all"), "")
        if pid:
            for m in list_model_versions(pid):
                self._ev_model_combo.addItem(m.model_name, m.model_id)
        # Rebuild camera combo all text
        self._ev_camera_combo.setItemText(0, tr("app.all"))

    def showEvent(self, event):
        super().showEvent(event)
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)
        self._ev_model_combo.clear()
        self._ev_model_combo.addItem(tr("app.all"), "")
        if pid:
            for m in list_model_versions(pid):
                self._ev_model_combo.addItem(m.model_name, m.model_id)

    def _on_source_changed(self, _index: int):
        src = self._source_combo.currentData()
        is_samples = src == "captured_images"
        # Toggle filter rows
        for i in range(self._sample_filter.count()):
            w = self._sample_filter.itemAt(i).widget()
            if w:
                w.setVisible(is_samples)
        for i in range(self._event_filter.count()):
            w = self._event_filter.itemAt(i).widget()
            if w:
                w.setVisible(not is_samples)
        self._histogram.setVisible(not is_samples)
        self._set_table_headers(src)

    def _set_table_headers(self, src: str):
        if src == "captured_images":
            self._table.setColumnCount(5)
            self._table.setHorizontalHeaderLabels([
                tr("trace.col_image"), tr("trace.col_camera"),
                tr("trace.col_label"), tr("trace.col_width"), tr("trace.col_height"),
            ])
        else:
            self._table.setColumnCount(7)
            self._table.setHorizontalHeaderLabels([
                tr("production.col_time"), tr("trace.col_camera"),
                tr("defect.defect_type"), tr("defect.model_version"),
                tr("inference.col_conf"), tr("defect.position_meter"),
                tr("trace.col_image"),
            ])

    def _rebuild_label_combo(self) -> None:
        self._label_combo.clear()
        self._label_combo.addItem(tr("app.all"), "")
        for value, label in CLASS_LABEL_OPTIONS:
            self._label_combo.addItem(label, value)

    def _refresh(self):
        src = self._source_combo.currentData()
        if src == "captured_images":
            self._refresh_samples()
        else:
            self._refresh_events()

    def _refresh_samples(self):
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

    def _refresh_events(self):
        pid = self._ctx.current_project_id
        if not pid:
            return

        events = list_defect_events(project_id=pid)

        # Client-side filters
        camera_filter = self._ev_camera_combo.currentData() or ""
        type_filter = self._ev_type_combo.currentData() or ""
        model_filter = self._ev_model_combo.currentData() or ""
        date_from = self._ev_date_from.date().toPython()
        date_to = self._ev_date_to.date().toPython()
        # Extend date_to to end of day
        date_to = datetime.combine(date_to, datetime.max.time())

        def _match(evt) -> bool:
            if camera_filter and evt.camera_id != camera_filter:
                return False
            if type_filter and evt.defect_type != type_filter:
                return False
            if model_filter and evt.model_version != model_filter:
                return False
            try:
                et = datetime.strptime(evt.event_time, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                return False
            if et < datetime.combine(date_from, datetime.min.time()) or et > date_to:
                return False
            return True

        filtered = [e for e in events if _match(e)]
        self._defect_events_data = filtered
        self._table.setRowCount(len(filtered))
        for row, evt in enumerate(filtered):
            time_str = evt.event_time[-12:] if len(evt.event_time) > 12 else evt.event_time
            self._table.setItem(row, 0, QTableWidgetItem(time_str))
            self._table.setItem(row, 1, QTableWidgetItem(evt.camera_id))
            self._table.setItem(row, 2, QTableWidgetItem(evt.defect_type or "—"))
            self._table.setItem(row, 3, QTableWidgetItem(evt.model_version or "—"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{evt.max_confidence:.3f}" if evt.max_confidence else "—"))
            pos_str = f"{evt.position_meter:.3f}" if evt.position_meter is not None else "—"
            self._table.setItem(row, 5, QTableWidgetItem(pos_str))
            img_name = os.path.basename(evt.ng_image_path) if evt.ng_image_path else "—"
            self._table.setItem(row, 6, QTableWidgetItem(img_name))

        # Stats
        type_counts = Counter(e.defect_type for e in filtered if e.defect_type)
        dist = ", ".join(f"{k}:{v}" for k, v in sorted(type_counts.items()))
        self._stats_label.setText(tr("trace.stats_events", total=len(filtered), distribution=dist))

        # Position histogram
        self._show_position_histogram(filtered)

    def _show_position_histogram(self, events):
        positions = [e.position_meter for e in events if e.position_meter is not None]
        if not positions or len(positions) < 2:
            self._histogram.setVisible(False)
            return

        self._histogram.setVisible(True)
        min_p, max_p = min(positions), max(positions)
        if max_p - min_p < 0.001:
            self._histogram.setValue(50)
            return

        # Find the bin with most events
        bins = 10
        bin_width = (max_p - min_p) / bins
        hist = [0] * bins
        for p in positions:
            idx = min(int((p - min_p) / bin_width), bins - 1)
            hist[idx] += 1
        max_count = max(hist) if hist else 1
        peak_bin = hist.index(max_count)
        # Show progress bar indicating where the densest position is
        self._histogram.setValue(int((peak_bin / (bins - 1)) * 100) if bins > 1 else 50)
        self._histogram.setToolTip(
            tr("trace.histogram_tip", min_p=f"{min_p:.2f}", max_p=f"{max_p:.2f}",
               count=len(positions))
        )

    def _on_row_selected(self):
        row = self._table.currentRow()
        if row < 0:
            return
        src = self._source_combo.currentData()
        if src == "captured_images":
            name = self._table.item(row, 0).text()
            path = self._resolve_path(name)
            if path and os.path.isfile(path):
                self._viewer.load_image(path)
        else:
            # For defect events, use stored DefectEvent objects to get full path
            if row < len(self._defect_events_data):
                evt = self._defect_events_data[row]
                ng_path = evt.ng_image_path
                if ng_path and os.path.isfile(ng_path):
                    self._viewer.load_image(ng_path)

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
