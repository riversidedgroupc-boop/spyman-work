"""Model version management page."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QDialog, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QMessageBox, QFileDialog, QLabel,
)

from core.model_version import (
    list_model_versions, create_model_version, update_model_version, delete_model_version,
)
from desktop_app.app_context import AppContext
from desktop_app.display import (
    MODEL_STATUS_OPTIONS,
    MODEL_TYPE_OPTIONS,
    model_status_label,
    model_type_label,
)
from desktop_app.i18n import tr, bind, I18nManager


class ModelVersionPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "model.register")
        add_btn.clicked.connect(self._add_model)
        btn_layout.addWidget(add_btn)
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        refresh_btn.setObjectName("secondaryBtn"); refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn"); del_btn.clicked.connect(self._delete_model)
        btn_layout.addWidget(del_btn); btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([tr("model.col_id"), tr("project.col_name"), tr("model.col_type"), tr("app.path"), tr("model.col_base"), tr("app.status"), tr("model.col_created")])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table, 1)

        status_layout = QHBoxLayout()
        status_mgmt_label = QLabel()
        bind(status_mgmt_label, "model.status_mgmt")
        status_layout.addWidget(status_mgmt_label)
        self._status_combo = QComboBox()
        for value, label in MODEL_STATUS_OPTIONS:
            self._status_combo.addItem(label, value)
        status_layout.addWidget(self._status_combo)
        set_btn = QPushButton()
        bind(set_btn, "model.set_status")
        set_btn.clicked.connect(self._set_status)
        status_layout.addWidget(set_btn); status_layout.addStretch()
        layout.addLayout(status_layout)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._table.setHorizontalHeaderLabels([tr("model.col_id"), tr("project.col_name"), tr("model.col_type"), tr("app.path"), tr("model.col_base"), tr("app.status"), tr("model.col_created")])

    def showEvent(self, event): super().showEvent(event); self._refresh()

    def _refresh(self):
        pid = self._ctx.current_project_id
        models = list_model_versions(pid) if pid else list_model_versions()
        self._table.setRowCount(len(models))
        for row, m in enumerate(models):
            self._table.setItem(row, 0, QTableWidgetItem(m.model_id))
            self._table.setItem(row, 1, QTableWidgetItem(m.model_name))
            self._table.setItem(row, 2, QTableWidgetItem(model_type_label(m.model_type)))
            self._table.setItem(row, 3, QTableWidgetItem(m.model_path[:60]))
            self._table.setItem(row, 4, QTableWidgetItem(m.base_model or ""))
            self._table.setItem(row, 5, QTableWidgetItem(model_status_label(m.status)))
            self._table.setItem(row, 6, QTableWidgetItem(m.created_at or ""))

    def _add_model(self):
        pid = self._ctx.current_project_id
        if not pid: QMessageBox.information(self, tr("app.tip"), tr("app.select_project")); return
        dlg = RegisterModelDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            create_model_version(project_id=pid, **dlg.get_data())
            self._refresh(); self.data_changed.emit()

    def _delete_model(self):
        row = self._table.currentRow()
        if row < 0: return
        mid = self._table.item(row, 0).text()
        if QMessageBox.question(self, tr("app.confirm_delete"), tr("model.delete_confirm", id=mid)) == QMessageBox.StandardButton.Yes:
            delete_model_version(mid); self._refresh()

    def _set_status(self):
        row = self._table.currentRow()
        if row < 0: return
        mid = self._table.item(row, 0).text()
        update_model_version(mid, status=self._status_combo.currentData()); self._refresh()


class RegisterModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        bind(self, "model.register_title", setter="setWindowTitle")
        self.setMinimumWidth(450); self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self); form = QFormLayout()
        model_name_label = QLabel()
        bind(model_name_label, "model.model_name")
        self._name_edit = QLineEdit(); form.addRow(model_name_label, self._name_edit)
        model_type_label = QLabel()
        bind(model_type_label, "model.model_type")
        self._type_combo = QComboBox()
        for value, label in MODEL_TYPE_OPTIONS:
            self._type_combo.addItem(label, value)
        form.addRow(model_type_label, self._type_combo)
        self._path_edit = QLineEdit(); self._path_edit.setPlaceholderText(tr("model.model_path_placeholder"))
        path_row = QHBoxLayout(); path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("..."); browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(lambda: self._browse())
        path_row.addWidget(browse_btn)
        model_path_label = QLabel()
        bind(model_path_label, "model.model_path")
        form.addRow(model_path_label, path_row)
        base_model_label = QLabel()
        bind(base_model_label, "model.base_model")
        self._base_edit = QLineEdit(); self._base_edit.setPlaceholderText(tr("model.base_placeholder")); form.addRow(base_model_label, self._base_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "Models (*.pt *.onnx);;All (*)")
        if path: self._path_edit.setText(path)

    def get_data(self):
        return {"model_name": self._name_edit.text().strip() or tr("app.unsaved"), "model_type": self._type_combo.currentData(), "model_path": self._path_edit.text().strip(), "base_model": self._base_edit.text().strip() or None}
