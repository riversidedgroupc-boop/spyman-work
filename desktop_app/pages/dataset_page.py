"""Dataset page — generate dataset versions from classified samples."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal

from desktop_app.i18n import tr, bind, I18nManager
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QLabel,
)

from core.capture_session import (
    list_capture_sessions, get_classification_counts,
    session_output_root, get_capture_session,
)
from desktop_app.display import session_status_label
from desktop_app.app_context import AppContext


class DatasetPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._hint_label = QLabel()
        bind(self._hint_label, "dataset.available_sessions")
        layout.addWidget(self._hint_label)
        self._session_table = QTableWidget(0, 6)
        self._session_table.setHorizontalHeaderLabels([
            tr("dataset.col_id"), tr("dataset.col_name"), tr("app.status"),
            tr("capture.col_captured"), tr("dataset.col_classified"),
            tr("dataset.col_distribution"),
        ])
        self._session_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._session_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._session_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._session_table, 1)

        btn_layout = QHBoxLayout()
        self._generate_btn = QPushButton()
        bind(self._generate_btn, "dataset.generate")
        self._generate_btn.clicked.connect(self._generate_dataset)
        btn_layout.addWidget(self._generate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._session_table.setHorizontalHeaderLabels([
            tr("dataset.col_id"), tr("dataset.col_name"), tr("app.status"),
            tr("capture.col_captured"), tr("dataset.col_classified"),
            tr("dataset.col_distribution"),
        ])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        pid = self._ctx.current_project_id
        sessions = list_capture_sessions(pid) if pid else []
        self._session_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self._session_table.setItem(row, 0, QTableWidgetItem(s.session_id))
            self._session_table.setItem(row, 1, QTableWidgetItem(s.session_name))
            self._session_table.setItem(row, 2, QTableWidgetItem(session_status_label(s.status)))
            self._session_table.setItem(row, 3, QTableWidgetItem(str(s.captured_image_count)))
            counts = get_classification_counts(s.session_id)
            total_classified = sum(counts.values())
            self._session_table.setItem(row, 4, QTableWidgetItem(str(total_classified)))
            dist = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
            self._session_table.setItem(row, 5, QTableWidgetItem(dist))

    def _generate_dataset(self) -> None:
        row = self._session_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return
        sid = self._session_table.item(row, 0).text()
        sess = get_capture_session(sid)
        if not sess:
            return

        from core.project import get_project_data_dir
        output_root = sess.output_dir or session_output_root(sess.project_id)
        raw_dir = os.path.join(output_root, sid, "raw")

        version = datetime.now().strftime("v%Y%m%d_%H%M%S")
        proj_data_dir = get_project_data_dir(sess.project_id)
        dataset_dir = os.path.join(proj_data_dir, "datasets", version)
        os.makedirs(dataset_dir, exist_ok=True)

        from core.dataset_builder import build_yolo_dataset_from_session

        try:
            result = build_yolo_dataset_from_session(sid, dataset_dir)
        except Exception as e:
            QMessageBox.warning(self, tr("app.error"), str(e))
            return

        message = tr("dataset.generated", path=result.dataset_dir, version=version)
        if result.missing_bbox_count:
            message += f"\n\n{result.missing_bbox_count} 张 NG 图片缺少 YOLO bbox 标注，已生成空标签文件。"
        QMessageBox.information(self, tr("app.completed"), message)
        self.data_changed.emit()
