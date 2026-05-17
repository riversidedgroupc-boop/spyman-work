"""Top project selector bar showing current customer/project/spec context."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QPushButton,
)

from core.customer import list_customers
from core.project import list_projects
from core.product_spec import list_product_specs
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.ui_state import load_ui_state, save_ui_state


class ProjectSelector(QWidget):
    customer_changed = Signal(str)
    project_changed = Signal(str)
    spec_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._building = False
        self._restoring = False
        self._build_ui()
        self._connect_signals()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self._customer_label = QLabel()
        bind(self._customer_label, "selector.customer")
        layout.addWidget(self._customer_label)
        self._customer_combo = QComboBox()
        self._customer_combo.setMinimumWidth(150)
        layout.addWidget(self._customer_combo)

        self._project_label = QLabel()
        bind(self._project_label, "selector.project")
        layout.addWidget(self._project_label)
        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(150)
        layout.addWidget(self._project_combo)

        self._spec_label = QLabel()
        bind(self._spec_label, "selector.spec")
        layout.addWidget(self._spec_label)
        self._spec_combo = QComboBox()
        self._spec_combo.setMinimumWidth(150)
        layout.addWidget(self._spec_combo)

        layout.addStretch()

        self._refresh_btn = QPushButton()
        bind(self._refresh_btn, "app.refresh")
        self._refresh_btn.setObjectName("secondaryBtn")
        self._refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_btn)

    def _connect_signals(self) -> None:
        self._customer_combo.currentIndexChanged.connect(self._on_customer_changed)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        self._spec_combo.currentIndexChanged.connect(self._on_spec_changed)

    def _refresh_text(self, lang: str = "") -> None:
        """Rebuild combo placeholders on language change."""
        self.refresh()

    def refresh(self) -> None:
        state = load_ui_state()
        if not self._ctx.current_customer_id and state.get("customer_id"):
            self._restore_from_state(state)

        self._restoring = True
        self._building = True
        self._customer_combo.blockSignals(True)
        self._project_combo.blockSignals(True)
        self._spec_combo.blockSignals(True)
        self._customer_combo.clear()
        self._customer_combo.addItem(tr("selector.select_customer"), "")
        for c in list_customers():
            self._customer_combo.addItem(c.customer_name, c.customer_id)

        # Restore selection
        if self._ctx.current_customer_id:
            for i in range(self._customer_combo.count()):
                if self._customer_combo.itemData(i) == self._ctx.current_customer_id:
                    self._customer_combo.setCurrentIndex(i)
                    break
            self._rebuild_projects(self._ctx.current_customer_id)
            if self._ctx.current_project_id:
                for i in range(self._project_combo.count()):
                    if self._project_combo.itemData(i) == self._ctx.current_project_id:
                        self._project_combo.setCurrentIndex(i)
                        break
                self._rebuild_specs(self._ctx.current_project_id)
                if self._ctx.current_spec_id:
                    for i in range(self._spec_combo.count()):
                        if self._spec_combo.itemData(i) == self._ctx.current_spec_id:
                            self._spec_combo.setCurrentIndex(i)
                            break
        self._customer_combo.blockSignals(False)
        self._project_combo.blockSignals(False)
        self._spec_combo.blockSignals(False)
        self._building = False
        self._restoring = False

    def persist_current_selection(self) -> None:
        """Persist the currently visible selector state before the app exits."""
        save_ui_state(**self._current_state_payload())

    def _restore_from_state(self, state: dict) -> None:
        self._restoring = True
        customer_id = state.get("customer_id", "")
        project_id = state.get("project_id", "")
        spec_id = state.get("spec_id", "")
        customer_name = state.get("customer_name", "")
        project_name = state.get("project_name", "")
        spec_name = state.get("spec_name", "")

        customers = list_customers()
        customer = next((c for c in customers if c.customer_id == customer_id), None)
        if customer is None and customer_name:
            customer = next((c for c in customers if c.customer_name == customer_name), None)
        if customer is None and len(customers) == 1:
            customer = customers[0]
        if customer is None:
            self._restoring = False
            return
        customer_id = customer.customer_id
        customer_name = customer.customer_name

        projects = list_projects(customer_id)
        project = next((p for p in projects if p.project_id == project_id), None)
        if project is None and project_name:
            project = next((p for p in projects if p.project_name == project_name), None)
        if project is None and len(projects) == 1:
            project = projects[0]

        spec = None
        if project is not None:
            project_id = project.project_id
            project_name = project.project_name
            specs = list_product_specs(project_id)
            spec = next((s for s in specs if s.spec_id == spec_id), None)
            if spec is None and spec_name:
                spec = next(
                    (
                        s for s in specs
                        if s.product_name == spec_name
                        or f"{s.product_name} ({s.material}/{s.geometry_type})" == spec_name
                    ),
                    None,
                )
            if spec is None and len(specs) == 1:
                spec = specs[0]

        if customer_id:
            self._ctx.set_current_customer(customer_id, customer_name)
            if project is not None:
                self._ctx.set_current_project(project_id, project_name)
                if spec is not None:
                    spec_id = spec.spec_id
                    spec_name = f"{spec.product_name} ({spec.material}/{spec.geometry_type})"
                    self._ctx.set_current_spec(spec_id, spec_name)
        self._restoring = False
        save_ui_state(
            customer_id=self._ctx.current_customer_id,
            customer_name=self._ctx.current_customer_name,
            project_id=self._ctx.current_project_id,
            project_name=self._ctx.current_project_name,
            spec_id=self._ctx.current_spec_id,
            spec_name=self._ctx.current_spec_name,
        )

    def _current_state_payload(self) -> dict:
        customer_id = self._customer_combo.currentData() or self._ctx.current_customer_id
        project_id = self._project_combo.currentData() or self._ctx.current_project_id
        spec_id = self._spec_combo.currentData() or self._ctx.current_spec_id
        return {
            "customer_id": customer_id,
            "customer_name": self._customer_combo.currentText() if customer_id else self._ctx.current_customer_name,
            "project_id": project_id,
            "project_name": self._project_combo.currentText() if project_id else self._ctx.current_project_name,
            "spec_id": spec_id,
            "spec_name": self._spec_combo.currentText() if spec_id else self._ctx.current_spec_name,
        }

    def _on_customer_changed(self, index: int) -> None:
        if self._building or self._restoring or index < 0:
            return
        customer_id = self._customer_combo.itemData(index)
        name = self._customer_combo.currentText()
        self._ctx.set_current_customer(customer_id, name)
        self._rebuild_projects(customer_id)
        if not self._restoring:
            save_ui_state(
                customer_id=customer_id,
                customer_name=name if customer_id else "",
                project_id="",
                project_name="",
                spec_id="",
                spec_name="",
            )
        self.customer_changed.emit(customer_id)

    def _rebuild_projects(self, customer_id: str) -> None:
        self._building = True
        self._project_combo.clear()
        self._spec_combo.clear()
        if not customer_id:
            self._building = False
            return
        self._project_combo.addItem(tr("selector.select_project"), "")
        for p in list_projects(customer_id):
            self._project_combo.addItem(p.project_name, p.project_id)
        self._building = False

    def _on_project_changed(self, index: int) -> None:
        if self._building or self._restoring or index < 0:
            return
        project_id = self._project_combo.itemData(index)
        name = self._project_combo.currentText()
        self._ctx.set_current_project(project_id, name)
        self._rebuild_specs(project_id)
        if self._spec_combo.count() == 2:
            self._spec_combo.setCurrentIndex(1)
            spec_id = self._spec_combo.currentData()
            if spec_id:
                self._ctx.set_current_spec(spec_id, self._spec_combo.currentText())
        if not self._restoring:
            save_ui_state(**self._current_state_payload())
        self.project_changed.emit(project_id)

    def _rebuild_specs(self, project_id: str) -> None:
        self._building = True
        self._spec_combo.clear()
        if not project_id:
            self._building = False
            return
        self._spec_combo.addItem(tr("selector.select_spec"), "")
        for s in list_product_specs(project_id):
            label = f"{s.product_name} ({s.material}/{s.geometry_type})"
            self._spec_combo.addItem(label, s.spec_id)
        self._building = False

    def _on_spec_changed(self, index: int) -> None:
        if self._building or self._restoring or index < 0:
            return
        spec_id = self._spec_combo.itemData(index)
        name = self._spec_combo.currentText()
        if spec_id:
            self._ctx.set_current_spec(spec_id, name)
        if not self._restoring:
            save_ui_state(**self._current_state_payload())
        if spec_id:
            self.spec_changed.emit(spec_id)
