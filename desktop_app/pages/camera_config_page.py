"""Camera configuration page."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QPushButton, QLabel, QComboBox, QMessageBox,
)

from camera_adapters.folder_watcher import FolderWatcherCameraAdapter
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager


class CameraConfigPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Per-camera config (2-6)
        self._cam_groups: list[QGroupBox] = []
        self._cam_watch_edits: list[QLineEdit] = []
        self._cam_adapter_combos: list[QComboBox] = []

        for i in range(1, 7):
            grp = QGroupBox()
            bind(grp, "camera.group", setter="setTitle", i=i)
            form = QFormLayout(grp)

            adapter_combo = QComboBox()
            adapter_combo.addItems([tr("camera.folder_watcher"), tr("camera.hikvision_stub"), tr("camera.basler_stub")])
            adapter_label = QLabel()
            bind(adapter_label, "camera.adapter")
            form.addRow(adapter_label, adapter_combo)
            self._cam_adapter_combos.append(adapter_combo)

            watch_edit = QLineEdit()
            watch_edit.setPlaceholderText(tr("camera.watch_dir_placeholder", i=i))
            from PySide6.QtWidgets import QFileDialog
            browse_btn = QPushButton()
            bind(browse_btn, "app.browse")
            browse_btn.clicked.connect(lambda checked, e=watch_edit: self._browse(e))
            row = QHBoxLayout(); row.addWidget(watch_edit); row.addWidget(browse_btn)
            watch_label = QLabel()
            bind(watch_label, "camera.watch_dir")
            form.addRow(watch_label, row)
            self._cam_watch_edits.append(watch_edit)

            self._cam_groups.append(grp)
            layout.addWidget(grp)

        save_btn = QPushButton()
        bind(save_btn, "app.save")
        save_btn.clicked.connect(lambda: QMessageBox.information(self, tr("app.save"), tr("app.config_saved")))
        layout.addWidget(save_btn)
        layout.addStretch()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo items on language change."""
        for combo in self._cam_adapter_combos:
            combo.clear()
            combo.addItems([tr("camera.folder_watcher"), tr("camera.hikvision_stub"), tr("camera.basler_stub")])

    def _browse(self, edit):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d: edit.setText(d)
