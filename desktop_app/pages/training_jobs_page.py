"""Training jobs page — list jobs, view logs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QSplitter, QMessageBox,
)

from core.training_job import list_training_jobs, delete_training_job
from desktop_app.app_context import AppContext
from desktop_app.display import training_status_label
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.widgets.log_viewer import LogViewer


class TrainingJobsPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn"); del_btn.clicked.connect(self._delete_job)
        btn_layout.addWidget(del_btn); btn_layout.addStretch()
        layout.addLayout(btn_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([tr("jobs.col_id"), tr("jobs.col_name"), tr("jobs.col_model"), tr("jobs.col_dataset"), tr("app.status"), tr("jobs.col_start"), tr("jobs.col_end"), tr("jobs.col_best")])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._table)
        self._log_viewer = LogViewer()
        splitter.addWidget(self._log_viewer)
        splitter.setSizes([400, 300])
        layout.addWidget(splitter, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._table.setHorizontalHeaderLabels([tr("jobs.col_id"), tr("jobs.col_name"), tr("jobs.col_model"), tr("jobs.col_dataset"), tr("app.status"), tr("jobs.col_start"), tr("jobs.col_end"), tr("jobs.col_best")])

    def showEvent(self, event): super().showEvent(event); self._refresh()

    def _refresh(self):
        pid = self._ctx.current_project_id
        jobs = list_training_jobs(pid) if pid else list_training_jobs()
        self._table.setRowCount(len(jobs))
        for row, j in enumerate(jobs):
            self._table.setItem(row, 0, QTableWidgetItem(j.job_id))
            self._table.setItem(row, 1, QTableWidgetItem(j.job_name))
            self._table.setItem(row, 2, QTableWidgetItem(j.base_model))
            self._table.setItem(row, 3, QTableWidgetItem(j.dataset_path[:60]))
            self._table.setItem(row, 4, QTableWidgetItem(training_status_label(j.status)))
            self._table.setItem(row, 5, QTableWidgetItem(j.start_time or ""))
            self._table.setItem(row, 6, QTableWidgetItem(j.end_time or ""))
            self._table.setItem(row, 7, QTableWidgetItem(j.best_model_path or ""))

    def _delete_job(self):
        row = self._table.currentRow()
        if row < 0: return
        jid = self._table.item(row, 0).text()
        if QMessageBox.question(self, tr("app.confirm_delete"), tr("jobs.delete_confirm", id=jid)) == QMessageBox.StandardButton.Yes:
            delete_training_job(jid); self._refresh()
            self.data_changed.emit()
