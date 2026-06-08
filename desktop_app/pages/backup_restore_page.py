"""Backup & Restore page — create, list, restore, delete backups."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QLabel,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QFileDialog,
)

from core.config_backup import list_backups, delete_backup
from desktop_app.workers.backup_worker import BackupWorker
from desktop_app.i18n import tr, bind, I18nManager


class BackupRestorePage(QWidget):
    """Backup management: create, list, restore, delete."""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: BackupWorker | None = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Create backup section ----
        create_grp = QGroupBox()
        bind(create_grp, "backup.create", setter="setTitle")
        cv = QVBoxLayout(create_grp)

        # Name
        name_row = QHBoxLayout()
        name_label = QLabel()
        bind(name_label, "backup.col_name")
        name_row.addWidget(name_label)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("backup.create_desc"))
        name_row.addWidget(self._name_edit)
        cv.addLayout(name_row)

        # Checkboxes
        cb_row = QHBoxLayout()
        self._db_cb = QCheckBox()
        bind(self._db_cb, "backup.include_db")
        self._db_cb.setChecked(True)
        cb_row.addWidget(self._db_cb)
        self._cfg_cb = QCheckBox()
        bind(self._cfg_cb, "backup.include_configs")
        self._cfg_cb.setChecked(True)
        cb_row.addWidget(self._cfg_cb)
        self._models_cb = QCheckBox()
        bind(self._models_cb, "backup.include_models")
        cb_row.addWidget(self._models_cb)
        cb_row.addStretch()
        cv.addLayout(cb_row)

        # Create button
        btn_row = QHBoxLayout()
        self._create_btn = QPushButton()
        bind(self._create_btn, "backup.create")
        self._create_btn.setObjectName("primaryBtn")
        self._create_btn.clicked.connect(self._create_backup)
        btn_row.addWidget(self._create_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        btn_row.addWidget(self._progress)
        btn_row.addStretch()
        cv.addLayout(btn_row)

        layout.addWidget(create_grp)

        # ---- Backup list ----
        list_grp = QGroupBox()
        bind(list_grp, "backup.list_title", setter="setTitle")
        lv = QVBoxLayout(list_grp)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            [
                tr("backup.col_date"),
                tr("backup.col_name"),
                tr("backup.col_size"),
                tr("backup.col_items"),
                "",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lv.addWidget(self._table, 1)

        # Action buttons
        act_row = QHBoxLayout()
        self._restore_btn = QPushButton()
        bind(self._restore_btn, "backup.restore")
        self._restore_btn.clicked.connect(self._restore_backup)
        act_row.addWidget(self._restore_btn)

        self._delete_btn = QPushButton()
        bind(self._delete_btn, "app.delete")
        self._delete_btn.setObjectName("dangerBtn")
        self._delete_btn.clicked.connect(self._delete_backup)
        act_row.addWidget(self._delete_btn)

        act_row.addStretch()
        lv.addLayout(act_row)
        layout.addWidget(list_grp, 1)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_list()

    # ------------------------------------------------------------------
    # Backup list
    # ------------------------------------------------------------------

    def _refresh_list(self):
        backups = list_backups()
        self._table.setRowCount(len(backups))
        for row, meta in enumerate(backups):
            self._table.setItem(row, 0, QTableWidgetItem(meta.created_at))
            self._table.setItem(row, 1, QTableWidgetItem(meta.backup_name))
            size_str = (
                f"{meta.size_bytes / 1024:.1f} KB"
                if meta.size_bytes < 1024 * 1024
                else f"{meta.size_bytes / 1024 / 1024:.1f} MB"
            )
            self._table.setItem(row, 2, QTableWidgetItem(size_str))
            self._table.setItem(row, 3, QTableWidgetItem(", ".join(meta.included_items)))
            self._table.setItem(row, 4, QTableWidgetItem(meta.backup_id))  # hidden

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _create_backup(self):
        name = self._name_edit.text().strip()
        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._create_btn.setEnabled(False)

        self._worker = BackupWorker(
            "create",
            {
                "name": name,
                "include_db": self._db_cb.isChecked(),
                "include_configs": self._cfg_cb.isChecked(),
                "include_models": self._models_cb.isChecked(),
            },
        )
        self._worker.message.connect(lambda m: None)
        self._worker.finished.connect(self._on_create_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_create_done(self):
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)
        self._name_edit.clear()
        self._refresh_list()
        if self._worker:
            result = self._worker.get_result()
            if result:
                QMessageBox.information(
                    self,
                    tr("app.completed"),
                    tr("backup.completed", name=result.backup_name),
                )
        self.data_changed.emit()

    def _restore_backup(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_item"))
            return
        bid = self._table.item(row, 4).text()
        name = self._table.item(row, 1).text()

        reply = QMessageBox.question(
            self,
            tr("app.confirm"),
            tr("backup.confirm_restore", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._progress.setVisible(True)
        self._progress.setMaximum(0)

        self._worker = BackupWorker("restore", {"backup_id": bid})
        self._worker.finished.connect(self._on_restore_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_restore_done(self):
        self._progress.setVisible(False)
        QMessageBox.information(self, tr("app.completed"), tr("backup.restored"))
        self.data_changed.emit()

    def _delete_backup(self):
        row = self._table.currentRow()
        if row < 0:
            return
        bid = self._table.item(row, 4).text()
        name = self._table.item(row, 1).text()

        reply = QMessageBox.question(
            self,
            tr("app.confirm"),
            tr("app.delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_backup(bid)
            self._refresh_list()

    def _on_error(self, err: str):
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)
        QMessageBox.critical(self, tr("app.error"), err)

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        self._table.setHorizontalHeaderLabels(
            [
                tr("backup.col_date"),
                tr("backup.col_name"),
                tr("backup.col_size"),
                tr("backup.col_items"),
                "",
            ]
        )
