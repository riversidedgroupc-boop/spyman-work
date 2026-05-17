"""Model comparison page — side-by-side metrics comparison."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox,
)

from core.model_version import list_model_versions, get_model_version
from desktop_app.app_context import AppContext
from desktop_app.display import model_status_label, model_type_label
from desktop_app.i18n import tr, bind, I18nManager


class ModelComparisonPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint_label = QLabel()
        bind(hint_label, "compare.hint")
        layout.addWidget(hint_label)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "compare.add")
        add_btn.clicked.connect(self._add_to_comparison)
        btn_layout.addWidget(add_btn)
        clear_btn = QPushButton()
        bind(clear_btn, "compare.clear")
        clear_btn.setObjectName("secondaryBtn"); clear_btn.clicked.connect(self._clear_comparison)
        btn_layout.addWidget(clear_btn); btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._model_table = QTableWidget(0, 5)
        self._model_table.setHorizontalHeaderLabels([tr("model.col_id"), tr("project.col_name"), tr("model.col_type"), tr("app.path"), tr("app.status")])
        self._model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._model_table, 1)

        compared_label = QLabel()
        bind(compared_label, "compare.compared")
        layout.addWidget(compared_label)
        self._compare_table = QTableWidget(0, 4)
        self._compare_table.setHorizontalHeaderLabels([tr("project.col_name"), tr("model.col_type"), tr("app.status"), tr("compare.col_metrics")])
        self._compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._compare_table, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._model_table.setHorizontalHeaderLabels([tr("model.col_id"), tr("project.col_name"), tr("model.col_type"), tr("app.path"), tr("app.status")])
        self._compare_table.setHorizontalHeaderLabels([tr("project.col_name"), tr("model.col_type"), tr("app.status"), tr("compare.col_metrics")])

    def showEvent(self, event): super().showEvent(event); self._refresh()

    def _refresh(self):
        pid = self._ctx.current_project_id
        models = list_model_versions(pid) if pid else list_model_versions()
        self._model_table.setRowCount(len(models))
        for row, m in enumerate(models):
            self._model_table.setItem(row, 0, QTableWidgetItem(m.model_id))
            self._model_table.setItem(row, 1, QTableWidgetItem(m.model_name))
            self._model_table.setItem(row, 2, QTableWidgetItem(model_type_label(m.model_type)))
            self._model_table.setItem(row, 3, QTableWidgetItem(m.model_path[:60]))
            self._model_table.setItem(row, 4, QTableWidgetItem(model_status_label(m.status)))

    def _add_to_comparison(self):
        row = self._model_table.currentRow()
        if row < 0: QMessageBox.information(self, tr("app.tip"), tr("app.select_model")); return
        mid = self._model_table.item(row, 0).text()
        m = get_model_version(mid)
        if not m: return
        rc = self._compare_table.rowCount(); self._compare_table.setRowCount(rc + 1)
        self._compare_table.setItem(rc, 0, QTableWidgetItem(m.model_name))
        self._compare_table.setItem(rc, 1, QTableWidgetItem(model_type_label(m.model_type)))
        self._compare_table.setItem(rc, 2, QTableWidgetItem(model_status_label(m.status)))
        ms = ""
        if m.metrics:
            try:
                metrics = json.loads(m.metrics)
                ms = ", ".join(f"{k}={v}" for k, v in metrics.items())
            except Exception: ms = str(m.metrics)
        self._compare_table.setItem(rc, 3, QTableWidgetItem(ms))

    def _clear_comparison(self):
        self._compare_table.setRowCount(0)
