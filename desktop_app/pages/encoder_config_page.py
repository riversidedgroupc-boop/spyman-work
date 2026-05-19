"""Encoder configuration page — simulated / RS422 / EtherCAT encoder setup."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QComboBox, QPushButton, QLabel, QMessageBox, QHBoxLayout,
)

from runtime.encoder_reader import SimulatedEncoderReader, RS422EncoderReader
from desktop_app.i18n import tr, bind, I18nManager


ENCODER_TYPES = {
    "simulated": SimulatedEncoderReader,
    "rs422": RS422EncoderReader,
}


class EncoderConfigPage(QWidget):
    """Encoder configuration with live position display in simulated mode."""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._encoder: SimulatedEncoderReader | RS422EncoderReader | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_position)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._grp = QGroupBox()
        bind(self._grp, "encoder.title", setter="setTitle")
        form = QFormLayout(self._grp)

        # Encoder type
        self._type_combo = QComboBox()
        self._type_combo.addItems([
            tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat"),
        ])
        type_label = QLabel()
        bind(type_label, "encoder.type")
        form.addRow(type_label, self._type_combo)

        # Resolution (pulses per meter)
        self._ppm_spin = QDoubleSpinBox()
        self._ppm_spin.setRange(100, 100_000)
        self._ppm_spin.setValue(1000)
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        res_label = QLabel()
        bind(res_label, "encoder.resolution")
        form.addRow(res_label, self._ppm_spin)

        # Line speed (for simulated mode)
        self._line_speed = QDoubleSpinBox()
        self._line_speed.setRange(0.1, 200)
        self._line_speed.setValue(80)
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))
        line_speed_label = QLabel()
        bind(line_speed_label, "encoder.line_speed")
        form.addRow(line_speed_label, self._line_speed)

        # Status
        self._status = QLabel()
        bind(self._status, "encoder.status_disconnected")
        self._status.setStyleSheet("color: #888;")
        form.addRow("", self._status)

        # Live position readout
        self._position_label = QLabel()
        bind(self._position_label, "encoder.position_display", pos="0.000")
        self._position_label.setStyleSheet(
            "font-size: 28px; font-weight: bold; font-family: monospace; color: #4CAF50;"
        )
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos_label_header = QLabel()
        bind(pos_label_header, "encoder.position")
        form.addRow(pos_label_header, self._position_label)

        layout.addWidget(self._grp)

        # Control buttons
        btn_row = QHBoxLayout()
        self._connect_btn = QPushButton()
        bind(self._connect_btn, "encoder.connect")
        self._connect_btn.clicked.connect(self._do_connect)
        btn_row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton()
        bind(self._disconnect_btn, "encoder.disconnect")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._do_disconnect)
        btn_row.addWidget(self._disconnect_btn)

        self._reset_btn = QPushButton()
        bind(self._reset_btn, "encoder.reset")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._do_reset)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # RS422 placeholder
        self._rs422_note = QLabel()
        bind(self._rs422_note, "encoder.rs422_placeholder")
        self._rs422_note.setStyleSheet("color: #666; font-style: italic;")
        self._rs422_note.setWordWrap(True)
        self._rs422_note.setVisible(False)
        layout.addWidget(self._rs422_note)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Encoder lifecycle
    # ------------------------------------------------------------------

    def _do_connect(self):
        """Connect to the selected encoder type."""
        idx = self._type_combo.currentIndex()
        if idx == 0:  # simulated
            self._encoder = SimulatedEncoderReader()
            params = {
                "line_speed_mpm": self._line_speed.value(),
                "pulses_per_meter": self._ppm_spin.value(),
            }
            self._encoder.connect(params)
            bind(self._status, "encoder.status_connected_simulated", setter="setText")
            self._status.setStyleSheet("color: #4CAF50;")
            self._rs422_note.setVisible(False)
        elif idx == 1:  # RS422
            self._encoder = RS422EncoderReader()
            self._encoder.connect({})
            bind(self._status, "encoder.status_connected_rs422", setter="setText")
            self._status.setStyleSheet("color: #FFC107;")
            self._rs422_note.setVisible(True)
        else:  # EtherCAT
            QMessageBox.information(self, tr("app.tip"), tr("encoder.ethercat_placeholder"))
            return

        self._poll_timer.start(100)  # 10 Hz position updates
        self._connect_btn.setEnabled(False)
        self._disconnect_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)

    def _do_disconnect(self):
        """Disconnect from current encoder."""
        if self._encoder:
            self._encoder.disconnect()
            self._encoder = None
        self._poll_timer.stop()
        bind(self._status, "encoder.status_disconnected", setter="setText")
        self._status.setStyleSheet("color: #888;")
        self._rs422_note.setVisible(False)
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)

    def _do_reset(self):
        """Reset encoder position counter."""
        if self._encoder:
            self._encoder.reset()
            self._position_label.setText("0.000")

    def _poll_position(self):
        """Read position from encoder and update display."""
        if self._encoder is None:
            return
        try:
            pos = self._encoder.read_position_meter()
            bind(self._position_label, "encoder.position_display",
                 setter="setText", pos=f"{pos:.3f}")
            speed = self._encoder.read_speed_mpm()
            status_text = self._status.text()
            if speed > 0:
                status_text = tr("encoder.status_fmt", pos=f"{pos:.3f}", speed=f"{speed:.1f}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        self._type_combo.clear()
        self._type_combo.addItems([
            tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat"),
        ])
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))
