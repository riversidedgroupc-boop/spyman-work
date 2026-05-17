"""Device configuration page — unified device management."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QGroupBox,
)

from camera_adapters.folder_watcher import FolderWatcherCameraAdapter
from camera_adapters.hikvision_mvs import HikvisionMVSAdapter
from camera_adapters.basler_pylon import BaslerPylonAdapter
from desktop_app.i18n import tr, bind, I18nManager


class DeviceConfigPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        adapter_label = QLabel()
        bind(adapter_label, "device.registered_adapters")
        layout.addWidget(adapter_label)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([tr("device.col_adapter"), tr("device.col_type"), tr("device.col_status"), tr("device.col_devices")])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        # Camera status
        self._status_group = QGroupBox()
        bind(self._status_group, "device.adapter_status", setter="setTitle")
        status_layout = QVBoxLayout(self._status_group)
        self._status_text = QLabel(self._get_status_text())
        self._status_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        status_layout.addWidget(self._status_text)
        layout.addWidget(self._status_group)

        self._refresh()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._table.setHorizontalHeaderLabels([tr("device.col_adapter"), tr("device.col_type"), tr("device.col_status"), tr("device.col_devices")])
        self._refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    def _refresh(self):
        adapters = [
            FolderWatcherCameraAdapter(),
            HikvisionMVSAdapter(),
            BaslerPylonAdapter(),
        ]
        self._table.setRowCount(len(adapters))
        for row, ad in enumerate(adapters):
            self._table.setItem(row, 0, QTableWidgetItem(ad.adapter_name))
            self._table.setItem(row, 1, QTableWidgetItem(ad.__class__.__name__))
            try:
                devices = ad.list_devices()
                self._table.setItem(row, 2, QTableWidgetItem(tr("device.ready", count=len(devices)) if devices else tr("device.no_devices")))
                self._table.setItem(row, 3, QTableWidgetItem(", ".join(d.get("name", "") for d in devices) if devices else "—"))
            except NotImplementedError as e:
                self._table.setItem(row, 2, QTableWidgetItem(tr("device.sdk_missing")))
                self._table.setItem(row, 3, QTableWidgetItem(str(e)))
            except Exception as e:
                self._table.setItem(row, 2, QTableWidgetItem(tr("device.status_error")))
                self._table.setItem(row, 3, QTableWidgetItem(str(e)))

    def _get_status_text(self) -> str:
        return tr("device.status_text")
