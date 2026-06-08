"""Dialog for creating or editing a customer."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QLabel,
)

from desktop_app.i18n import tr, bind


class CreateCustomerDialog(QDialog):
    def __init__(self, parent=None, edit_data: dict | None = None) -> None:
        super().__init__(parent)
        self._edit_data = edit_data
        bind(
            self,
            "customer.title_edit" if edit_data else "customer.title_new",
            setter="setWindowTitle",
        )
        self.setMinimumWidth(420)
        self._build_ui()
        if edit_data:
            self._populate(edit_data)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("customer.name_placeholder"))
        name_label = QLabel()
        bind(name_label, "customer.name")
        form.addRow(name_label, self._name_edit)

        self._short_edit = QLineEdit()
        self._short_edit.setPlaceholderText(tr("customer.short_placeholder"))
        short_label = QLabel()
        bind(short_label, "customer.short_name")
        form.addRow(short_label, self._short_edit)

        self._industry_edit = QLineEdit()
        self._industry_edit.setPlaceholderText(tr("customer.industry_placeholder"))
        industry_label = QLabel()
        bind(industry_label, "customer.industry")
        form.addRow(industry_label, self._industry_edit)

        self._contact_edit = QLineEdit()
        self._contact_edit.setPlaceholderText(tr("customer.contact"))
        contact_label = QLabel()
        bind(contact_label, "customer.contact")
        form.addRow(contact_label, self._contact_edit)

        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText(tr("customer.location"))
        location_label = QLabel()
        bind(location_label, "customer.location")
        form.addRow(location_label, self._location_edit)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText(tr("app.notes"))
        notes_label = QLabel()
        bind(notes_label, "app.notes")
        form.addRow(notes_label, self._notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, data: dict) -> None:
        self._name_edit.setText(data.get("customer_name", ""))
        self._short_edit.setText(data.get("short_name", ""))
        self._industry_edit.setText(data.get("industry", ""))
        self._contact_edit.setText(data.get("contact", ""))
        self._location_edit.setText(data.get("location", ""))
        self._notes_edit.setText(data.get("notes", ""))

    def _validate_and_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("customer.name_required"))
            return
        if not self._short_edit.text().strip():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("customer.short_required"))
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "customer_name": self._name_edit.text().strip(),
            "short_name": self._short_edit.text().strip(),
            "industry": self._industry_edit.text().strip() or None,
            "contact": self._contact_edit.text().strip() or None,
            "location": self._location_edit.text().strip() or None,
            "notes": self._notes_edit.text().strip() or None,
        }
