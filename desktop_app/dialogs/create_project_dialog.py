"""Dialog for creating or editing a project."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QLabel,
)

from core.customer import list_customers
from desktop_app.display import PROJECT_TYPE_OPTIONS
from desktop_app.i18n import tr, bind


class CreateProjectDialog(QDialog):
    def __init__(self, parent=None, customer_id: str = "", edit_data: dict | None = None) -> None:
        super().__init__(parent)
        self._customer_id = customer_id
        self._edit_data = edit_data
        bind(self, "proj.title_edit" if edit_data else "proj.title_new", setter="setWindowTitle")
        self.setMinimumWidth(420)
        self._build_ui()
        if edit_data:
            self._populate(edit_data)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Customer selector (for new projects — pick which customer this belongs to)
        self._customer_combo = QComboBox()
        customers = list_customers()
        for c in customers:
            self._customer_combo.addItem(c.customer_name, c.customer_id)
        if self._customer_id:
            idx = self._customer_combo.findData(self._customer_id)
            if idx >= 0:
                self._customer_combo.setCurrentIndex(idx)
        elif customers:
            self._customer_combo.setCurrentIndex(0)
        self._customer_combo.setVisible(not self._edit_data and len(customers) > 1)
        if not self._edit_data:
            customer_label = QLabel()
            bind(customer_label, "selector.customer")
            form.addRow(customer_label, self._customer_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("proj.name_placeholder"))
        name_label = QLabel()
        bind(name_label, "proj.name")
        form.addRow(name_label, self._name_edit)

        self._type_combo = QComboBox()
        for value, label in PROJECT_TYPE_OPTIONS:
            self._type_combo.addItem(label, value)
        type_label = QLabel()
        bind(type_label, "proj.type")
        form.addRow(type_label, self._type_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, data: dict) -> None:
        self._name_edit.setText(data.get("project_name", ""))
        ptype = data.get("project_type", "surface_inspection")
        idx = self._type_combo.findData(ptype)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)

    def _validate_and_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("proj.name_required"))
            return
        self.accept()

    @property
    def customer_id(self) -> str:
        if self._edit_data:
            return self._customer_id
        return self._customer_combo.currentData() or self._customer_id

    def get_data(self) -> dict:
        return {
            "project_name": self._name_edit.text().strip(),
            "project_type": self._type_combo.currentData(),
        }
