"""Encoder configuration page."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QComboBox, QPushButton, QLabel, QMessageBox,
)
from desktop_app.i18n import tr, bind, I18nManager


class EncoderConfigPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._grp = QGroupBox()
        bind(self._grp, "encoder.title", setter="setTitle")
        form = QFormLayout(self._grp)

        self._type_combo = QComboBox()
        self._type_combo.addItems([tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat")])
        type_label = QLabel()
        bind(type_label, "encoder.type")
        form.addRow(type_label, self._type_combo)

        self._ppm_spin = QDoubleSpinBox()
        self._ppm_spin.setRange(100, 100000); self._ppm_spin.setValue(1000)
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        res_label = QLabel()
        bind(res_label, "encoder.resolution")
        form.addRow(res_label, self._ppm_spin)

        self._line_speed = QDoubleSpinBox()
        self._line_speed.setRange(0.1, 200); self._line_speed.setValue(80)
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))
        line_speed_label = QLabel()
        bind(line_speed_label, "encoder.line_speed")
        form.addRow(line_speed_label, self._line_speed)

        self._status = QLabel()
        bind(self._status, "encoder.status")
        self._status.setStyleSheet("color: #4CAF50;")
        form.addRow("", self._status)

        layout.addWidget(self._grp)
        layout.addStretch()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo items and spinbox suffixes on language change."""
        self._type_combo.clear()
        self._type_combo.addItems([tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat")])
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))
