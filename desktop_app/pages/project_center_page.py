"""Project center page — customer, project, and product spec management."""

from __future__ import annotations

from PySide6.QtCore import Signal

from desktop_app.i18n import tr, bind, I18nManager
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    QLabel,
    QHeaderView,
    QMessageBox,
)

from core.customer import (
    list_customers,
    create_customer,
    update_customer,
    delete_customer,
)
from core.project import (
    list_projects,
    create_project,
    update_project,
    delete_project,
)
from core.product_spec import (
    list_product_specs,
    create_product_spec,
    update_product_spec,
    delete_product_spec,
)
from desktop_app.app_context import AppContext
from desktop_app.display import project_status_label
from desktop_app.dialogs.create_customer_dialog import CreateCustomerDialog
from desktop_app.dialogs.create_project_dialog import CreateProjectDialog
from desktop_app.dialogs.create_product_spec_dialog import CreateProductSpecDialog


class ProjectCenterPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_customer_tab(), tr("project.customers"))
        self._tabs.addTab(self._build_project_tab(), tr("project.projects"))
        self._tabs.addTab(self._build_spec_tab(), tr("project.specs"))
        layout.addWidget(self._tabs)

    def refresh(self) -> None:
        """Refresh all tables and filter combos (called from outside, e.g. top-bar refresh)."""
        self._refresh_customers()
        self._rebuild_project_filter()
        self._refresh_projects()
        self._rebuild_spec_filter()
        self._refresh_specs()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set tab labels, table headers, and filter combos on language change."""
        self._tabs.setTabText(0, tr("project.customers"))
        self._tabs.setTabText(1, tr("project.projects"))
        self._tabs.setTabText(2, tr("project.specs"))

        self._customer_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_name"),
                tr("project.col_short_name"),
                tr("project.col_industry"),
                tr("project.col_contact"),
                tr("project.col_created"),
            ]
        )
        self._project_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_project_name"),
                tr("project.col_customer"),
                tr("project.col_status"),
                tr("project.col_created"),
            ]
        )
        self._spec_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_spec_name"),
                tr("project.col_material"),
                tr("project.col_morphology"),
                tr("project.col_speed_range"),
                tr("project.col_camera_count"),
                tr("project.col_created"),
            ]
        )

        # Rebuild filter combos (placeholder text changes with language)
        self._rebuild_project_filter()
        self._rebuild_spec_filter()

    # ── Customer tab ──

    def _build_customer_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "project.new_customer")
        add_btn.clicked.connect(self._add_customer)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton()
        bind(edit_btn, "app.edit")
        edit_btn.setObjectName("secondaryBtn")
        edit_btn.clicked.connect(self._edit_customer)
        btn_layout.addWidget(edit_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self._delete_customer)
        btn_layout.addWidget(del_btn)
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._customer_table = QTableWidget(0, 6)
        self._customer_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_name"),
                tr("project.col_short_name"),
                tr("project.col_industry"),
                tr("project.col_contact"),
                tr("project.col_created"),
            ]
        )
        self._customer_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._customer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._customer_table.setAlternatingRowColors(True)
        self._customer_table.itemDoubleClicked.connect(lambda _item: self._edit_customer())
        layout.addWidget(self._customer_table, 1)

        self._refresh_customers()
        return w

    def _refresh_customers(self) -> None:
        customers = list_customers()
        self._customer_table.setRowCount(len(customers))
        for row, c in enumerate(customers):
            self._customer_table.setItem(row, 0, QTableWidgetItem(c.customer_id))
            self._customer_table.setItem(row, 1, QTableWidgetItem(c.customer_name))
            self._customer_table.setItem(row, 2, QTableWidgetItem(c.short_name))
            self._customer_table.setItem(row, 3, QTableWidgetItem(c.industry or ""))
            self._customer_table.setItem(row, 4, QTableWidgetItem(c.contact or ""))
            self._customer_table.setItem(row, 5, QTableWidgetItem(c.created_at or ""))

    def _add_customer(self) -> None:
        dlg = CreateCustomerDialog(self)
        if dlg.exec() == CreateCustomerDialog.DialogCode.Accepted:
            data = dlg.get_data()
            create_customer(**data)
            self._refresh_customers()
            self.data_changed.emit()

    def _edit_customer(self) -> None:
        row = self._customer_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        cid = self._customer_table.item(row, 0).text()
        from core.storage import fetch_one

        existing = fetch_one("customers", cid)
        if not existing:
            return
        dlg = CreateCustomerDialog(self, edit_data=existing)
        if dlg.exec() == CreateCustomerDialog.DialogCode.Accepted:
            update_customer(cid, **dlg.get_data())
            self._refresh_customers()
            self.data_changed.emit()

    def _delete_customer(self) -> None:
        row = self._customer_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        cid = self._customer_table.item(row, 0).text()
        name = self._customer_table.item(row, 1).text()
        resp = QMessageBox.question(
            self,
            tr("app.confirm_delete"),
            tr("project.delete_customer_confirm", name=name),
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                delete_customer(cid)
            except Exception as e:
                QMessageBox.critical(self, tr("app.error"), tr("project.delete_cascade_failed") + f"\n\n{e}")
                return
            # Clear context if we just deleted the current customer
            if cid == self._ctx.current_customer_id:
                self._ctx.clear_customer_context()
            self.refresh()
            self.data_changed.emit()

    # ── Project tab ──

    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Customer filter
        filter_layout = QHBoxLayout()
        filter_label = QLabel()
        bind(filter_label, "selector.customer")
        filter_layout.addWidget(filter_label)
        self._project_customer_filter = QComboBox()
        self._project_customer_filter.currentIndexChanged.connect(self._on_project_customer_filter)
        filter_layout.addWidget(self._project_customer_filter, 1)
        layout.addLayout(filter_layout)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "project.new_project")
        add_btn.clicked.connect(self._add_project)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton()
        bind(edit_btn, "app.edit")
        edit_btn.setObjectName("secondaryBtn")
        edit_btn.clicked.connect(self._edit_project)
        btn_layout.addWidget(edit_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self._delete_project)
        btn_layout.addWidget(del_btn)
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._project_table = QTableWidget(0, 5)
        self._project_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_project_name"),
                tr("project.col_customer"),
                tr("project.col_status"),
                tr("project.col_created"),
            ]
        )
        self._project_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._project_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._project_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._project_table.setAlternatingRowColors(True)
        self._project_table.itemDoubleClicked.connect(lambda _item: self._edit_project())
        layout.addWidget(self._project_table, 1)

        self._rebuild_project_filter()
        self._refresh_projects()
        return w

    def _rebuild_project_filter(self) -> None:
        """Populate the customer filter combo for the project tab."""
        self._project_customer_filter.blockSignals(True)
        self._project_customer_filter.clear()
        self._project_customer_filter.addItem(tr("selector.all_customers"), "")
        for c in list_customers():
            self._project_customer_filter.addItem(c.customer_name, c.customer_id)
        # Default to current context customer
        if self._ctx.current_customer_id:
            idx = self._project_customer_filter.findData(self._ctx.current_customer_id)
            if idx >= 0:
                self._project_customer_filter.setCurrentIndex(idx)
        self._project_customer_filter.blockSignals(False)

    def _on_project_customer_filter(self) -> None:
        self._refresh_projects()

    def _refresh_projects(self) -> None:
        customer_id = self._project_customer_filter.currentData() if self._project_customer_filter.currentIndex() >= 0 else ""
        projects = list_projects(customer_id or None)
        self._project_table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            self._project_table.setItem(row, 0, QTableWidgetItem(p.project_id))
            self._project_table.setItem(row, 1, QTableWidgetItem(p.project_name))
            from core.storage import fetch_one

            c = fetch_one("customers", p.customer_id)
            self._project_table.setItem(row, 2, QTableWidgetItem(c["customer_name"] if c else ""))
            self._project_table.setItem(row, 3, QTableWidgetItem(project_status_label(p.status)))
            self._project_table.setItem(row, 4, QTableWidgetItem(p.created_at or ""))

    def _add_project(self) -> None:
        customers = list_customers()
        if not customers:
            QMessageBox.information(self, tr("app.tip"), tr("project.create_customer_first"))
            return
        # Must have explicit parent: filter combo > context > selected table row
        filter_cid = self._project_customer_filter.currentData() if self._project_customer_filter.currentIndex() >= 0 else ""
        cid = filter_cid or self._ctx.current_customer_id
        if not cid:
            # Try the currently selected row in the customer table as a fallback hint
            QMessageBox.information(self, tr("app.tip"), tr("project.select_customer_first"))
            return
        dlg = CreateProjectDialog(self, customer_id=cid)
        if dlg.exec() == CreateProjectDialog.DialogCode.Accepted:
            data = dlg.get_data()
            create_project(dlg.customer_id, **data)
            self._rebuild_project_filter()  # refresh filter in case customer list changed
            self._refresh_projects()
            self.data_changed.emit()

    def _edit_project(self) -> None:
        row = self._project_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        pid = self._project_table.item(row, 0).text()
        from core.storage import fetch_one

        existing = fetch_one("projects", pid, "project_id")
        if not existing:
            return
        dlg = CreateProjectDialog(self, edit_data=existing)
        if dlg.exec() == CreateProjectDialog.DialogCode.Accepted:
            update_project(pid, **dlg.get_data())
            self._refresh_projects()
            self.data_changed.emit()

    def _delete_project(self) -> None:
        row = self._project_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        pid = self._project_table.item(row, 0).text()
        name = self._project_table.item(row, 1).text()
        resp = QMessageBox.question(
            self, tr("app.confirm_delete"), tr("project.delete_project_confirm", name=name)
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                delete_project(pid)
            except Exception as e:
                QMessageBox.critical(self, tr("app.error"), tr("project.delete_cascade_failed") + f"\n\n{e}")
                return
            if pid == self._ctx.current_project_id:
                self._ctx.clear_project_context()
            self.refresh()
            self.data_changed.emit()

    # ── Spec tab ──

    def _build_spec_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Project filter
        filter_layout = QHBoxLayout()
        filter_label = QLabel()
        bind(filter_label, "selector.project")
        filter_layout.addWidget(filter_label)
        self._spec_project_filter = QComboBox()
        self._spec_project_filter.currentIndexChanged.connect(self._on_spec_project_filter)
        filter_layout.addWidget(self._spec_project_filter, 1)
        layout.addLayout(filter_layout)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "project.new_spec")
        add_btn.clicked.connect(self._add_spec)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton()
        bind(edit_btn, "app.edit")
        edit_btn.setObjectName("secondaryBtn")
        edit_btn.clicked.connect(self._edit_spec)
        btn_layout.addWidget(edit_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self._delete_spec)
        btn_layout.addWidget(del_btn)
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._spec_table = QTableWidget(0, 7)
        self._spec_table.setHorizontalHeaderLabels(
            [
                tr("project.col_id"),
                tr("project.col_spec_name"),
                tr("project.col_material"),
                tr("project.col_morphology"),
                tr("project.col_speed_range"),
                tr("project.col_camera_count"),
                tr("project.col_created"),
            ]
        )
        self._spec_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._spec_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._spec_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._spec_table.setAlternatingRowColors(True)
        self._spec_table.itemDoubleClicked.connect(lambda _item: self._edit_spec())
        layout.addWidget(self._spec_table, 1)

        self._rebuild_spec_filter()
        self._refresh_specs()
        return w

    def _rebuild_spec_filter(self) -> None:
        """Populate the project filter combo for the spec tab."""
        self._spec_project_filter.blockSignals(True)
        self._spec_project_filter.clear()
        self._spec_project_filter.addItem(tr("selector.all_projects"), "")
        for p in list_projects():
            self._spec_project_filter.addItem(p.project_name, p.project_id)
        # Default to current context project
        if self._ctx.current_project_id:
            idx = self._spec_project_filter.findData(self._ctx.current_project_id)
            if idx >= 0:
                self._spec_project_filter.setCurrentIndex(idx)
        self._spec_project_filter.blockSignals(False)

    def _on_spec_project_filter(self) -> None:
        self._refresh_specs()

    def _refresh_specs(self) -> None:
        project_id = self._spec_project_filter.currentData() if self._spec_project_filter.currentIndex() >= 0 else ""
        specs = list_product_specs(project_id or None)
        self._spec_table.setRowCount(len(specs))
        for row, s in enumerate(specs):
            self._spec_table.setItem(row, 0, QTableWidgetItem(s.spec_id))
            self._spec_table.setItem(row, 1, QTableWidgetItem(s.product_name))
            self._spec_table.setItem(row, 2, QTableWidgetItem(s.material))
            self._spec_table.setItem(row, 3, QTableWidgetItem(s.geometry_type))
            speed_range = f"{s.line_speed_min_mpm:.0f}–{s.line_speed_max_mpm:.0f} m/min"
            self._spec_table.setItem(row, 4, QTableWidgetItem(speed_range))
            self._spec_table.setItem(row, 5, QTableWidgetItem(str(s.camera_count)))
            self._spec_table.setItem(row, 6, QTableWidgetItem(s.created_at or ""))

    def _add_spec(self) -> None:
        projects = list_projects()
        if not projects:
            QMessageBox.information(self, tr("app.tip"), tr("project.create_project_first"))
            return
        # Must have explicit parent: filter combo > context > selected table row
        filter_pid = self._spec_project_filter.currentData() if self._spec_project_filter.currentIndex() >= 0 else ""
        pid = filter_pid or self._ctx.current_project_id
        if not pid:
            QMessageBox.information(self, tr("app.tip"), tr("project.select_project_first"))
            return
        dlg = CreateProductSpecDialog(self, project_id=pid)
        if dlg.exec() == CreateProductSpecDialog.DialogCode.Accepted:
            data = dlg.get_data()
            create_product_spec(project_id=dlg.project_id, **data)
            self._rebuild_spec_filter()  # refresh filter in case project list changed
            self._refresh_specs()
            self.data_changed.emit()

    def _edit_spec(self) -> None:
        row = self._spec_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        sid = self._spec_table.item(row, 0).text()
        from core.storage import fetch_one

        existing = fetch_one("product_specs", sid, "spec_id")
        if not existing:
            return
        dlg = CreateProductSpecDialog(self, edit_data=existing)
        if dlg.exec() == CreateProductSpecDialog.DialogCode.Accepted:
            update_product_spec(sid, **dlg.get_data())
            self._refresh_specs()
            self.data_changed.emit()

    def _delete_spec(self) -> None:
        row = self._spec_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_first"))
            return
        sid = self._spec_table.item(row, 0).text()
        name = self._spec_table.item(row, 1).text()
        resp = QMessageBox.question(
            self, tr("app.confirm_delete"), tr("project.delete_spec_confirm", name=name)
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                delete_product_spec(sid)
            except Exception as e:
                QMessageBox.critical(self, tr("app.error"), tr("project.delete_cascade_failed") + f"\n\n{e}")
                return
            if sid == self._ctx.current_spec_id:
                self._ctx.clear_spec_context()
            self.refresh()
            self.data_changed.emit()
