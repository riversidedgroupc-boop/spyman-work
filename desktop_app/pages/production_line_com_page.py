"""Production line communication page — PLC + Encoder configuration."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
    QMessageBox,
    QHBoxLayout,
)

from integration.modbus_tcp import ModbusTcpClient
from integration.tcp_socket import TcpSocketClient
from runtime.encoder_reader import SimulatedEncoderReader, RS422EncoderReader
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.theme_manager import ThemeManager

ENCODER_TYPES = {
    "simulated": SimulatedEncoderReader,
    "rs422": RS422EncoderReader,
}

_PLC_METHOD_OPTIONS = [
    ("plc.method_tcp_socket", "TCP Socket"),
    ("plc.method_modbus_tcp", "Modbus TCP"),
    ("plc.method_serial_port", "Serial Port"),
    ("plc.method_http", "HTTP"),
]


def _replace_combo_options(combo: QComboBox, options: list[tuple[str, str]]) -> None:
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for label_key, value in options:
        combo.addItem(tr(label_key), value)
    if current is not None:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    combo.blockSignals(False)


class ProductionLineComPage(QWidget):
    """PLC communication config + Encoder config in one page."""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._encoder: SimulatedEncoderReader | RS422EncoderReader | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_position)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Section 1: PLC Communication ──
        self._plc_group = QGroupBox()
        bind(self._plc_group, "plc.group", setter="setTitle")
        plc_form = QFormLayout(self._plc_group)

        self._type_combo = QComboBox()
        _replace_combo_options(self._type_combo, _PLC_METHOD_OPTIONS)
        method_label = QLabel()
        bind(method_label, "plc.method")
        plc_form.addRow(method_label, self._type_combo)

        self._host_edit = QLineEdit("127.0.0.1")
        host_label = QLabel()
        bind(host_label, "plc.host")
        plc_form.addRow(host_label, self._host_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(502)
        port_label = QLabel()
        bind(port_label, "plc.port")
        plc_form.addRow(port_label, self._port_spin)

        self._plc_status_label = QLabel()
        bind(self._plc_status_label, "plc.not_connected")
        self._plc_status_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        status_label = QLabel()
        bind(status_label, "app.status")
        plc_form.addRow(status_label, self._plc_status_label)

        layout.addWidget(self._plc_group)

        self._test_btn = QPushButton()
        bind(self._test_btn, "plc.test")
        self._test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self._test_btn)

        # ── Section 2: Encoder Configuration ──
        self._enc_group = QGroupBox()
        bind(self._enc_group, "encoder.group", setter="setTitle")
        enc_form = QFormLayout(self._enc_group)

        self._enc_type_combo = QComboBox()
        self._enc_type_combo.addItems(
            [tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat")]
        )
        type_label = QLabel()
        bind(type_label, "encoder.type")
        enc_form.addRow(type_label, self._enc_type_combo)

        self._ppm_spin = QDoubleSpinBox()
        self._ppm_spin.setRange(100, 100_000)
        self._ppm_spin.setValue(1000)
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        res_label = QLabel()
        bind(res_label, "encoder.resolution")
        enc_form.addRow(res_label, self._ppm_spin)

        self._line_speed = QDoubleSpinBox()
        self._line_speed.setRange(0.1, 200)
        self._line_speed.setValue(80)
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))
        line_speed_label = QLabel()
        bind(line_speed_label, "encoder.line_speed")
        enc_form.addRow(line_speed_label, self._line_speed)

        self._enc_status = QLabel()
        bind(self._enc_status, "encoder.status_disconnected")
        self._enc_status.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        enc_form.addRow("", self._enc_status)

        self._position_label = QLabel()
        bind(self._position_label, "encoder.position_display", pos="0.000")
        self._position_label.setStyleSheet(
            f"font-size: 28px; font-weight: bold; font-family: monospace; color: {ThemeManager.current().SUCCESS};"
        )
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos_label_header = QLabel()
        bind(pos_label_header, "encoder.position")
        enc_form.addRow(pos_label_header, self._position_label)

        layout.addWidget(self._enc_group)

        # Encoder control buttons
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

        self._rs422_note = QLabel()
        bind(self._rs422_note, "encoder.rs422_placeholder")
        self._rs422_note.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-style: italic;")
        self._rs422_note.setWordWrap(True)
        self._rs422_note.setVisible(False)
        layout.addWidget(self._rs422_note)

        layout.addStretch()

    # ------------------------------------------------------------------
    # PLC logic
    # ------------------------------------------------------------------

    def _test_connection(self):
        ct = self._type_combo.currentData() or "TCP Socket"
        try:
            if ct == "TCP Socket":
                client = TcpSocketClient()
                ok = client.connect(
                    {"host": self._host_edit.text(), "port": self._port_spin.value()}
                )
            elif ct == "Modbus TCP":
                client = ModbusTcpClient()
                ok = client.connect(
                    {"host": self._host_edit.text(), "port": self._port_spin.value()}
                )
            else:
                bind(self._plc_status_label, "plc.not_supported", method=ct)
                return

            if ok:
                bind(self._plc_status_label, "plc.connected")
                self._plc_status_label.setStyleSheet(f"color: {ThemeManager.current().SUCCESS};")
            else:
                bind(self._plc_status_label, "plc.connect_failed")
                self._plc_status_label.setStyleSheet(f"color: {ThemeManager.current().ERROR};")
        except NotImplementedError as e:
            self._plc_status_label.setText(str(e))
            self._plc_status_label.setStyleSheet(f"color: {ThemeManager.current().WARNING};")
        except Exception as e:
            self._plc_status_label.setText(tr("app.error") + f": {e}")
            self._plc_status_label.setStyleSheet(f"color: {ThemeManager.current().ERROR};")

    # ------------------------------------------------------------------
    # Encoder logic
    # ------------------------------------------------------------------

    def _do_connect(self):
        idx = self._enc_type_combo.currentIndex()
        if idx == 0:  # simulated
            self._encoder = SimulatedEncoderReader()
            params = {
                "line_speed_mpm": self._line_speed.value(),
                "pulses_per_meter": self._ppm_spin.value(),
            }
            self._encoder.connect(params)
            bind(self._enc_status, "encoder.status_connected_simulated", setter="setText")
            self._enc_status.setStyleSheet(f"color: {ThemeManager.current().SUCCESS};")
            self._rs422_note.setVisible(False)
        elif idx == 1:  # RS422
            self._encoder = RS422EncoderReader()
            self._encoder.connect({})
            bind(self._enc_status, "encoder.status_connected_rs422", setter="setText")
            self._enc_status.setStyleSheet(f"color: {ThemeManager.current().WARNING};")
            self._rs422_note.setVisible(True)
        else:  # EtherCAT
            QMessageBox.information(self, tr("app.tip"), tr("encoder.ethercat_placeholder"))
            return

        self._poll_timer.start(100)
        self._connect_btn.setEnabled(False)
        self._disconnect_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)

    def _do_disconnect(self):
        if self._encoder:
            self._encoder.disconnect()
            self._encoder = None
        self._poll_timer.stop()
        bind(self._enc_status, "encoder.status_disconnected", setter="setText")
        self._enc_status.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        self._rs422_note.setVisible(False)
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)

    def _do_reset(self):
        if self._encoder:
            self._encoder.reset()
            self._position_label.setText("0.000")

    def _poll_position(self):
        if self._encoder is None:
            return
        try:
            pos = self._encoder.read_position_meter()
            bind(
                self._position_label, "encoder.position_display", setter="setText", pos=f"{pos:.3f}"
            )
            speed = self._encoder.read_speed_mpm()
            self._enc_status.setText(tr("encoder.status_fmt", pos=f"{pos:.3f}", speed=f"{speed:.1f}"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # i18n & Theme
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        _replace_combo_options(self._type_combo, _PLC_METHOD_OPTIONS)
        self._enc_type_combo.clear()
        self._enc_type_combo.addItems(
            [tr("encoder.simulated"), tr("encoder.rs422"), tr("encoder.ethercat")]
        )
        self._ppm_spin.setSuffix(" " + tr("encoder.ppm"))
        self._line_speed.setSuffix(" " + tr("encoder.m_min"))

    def _on_theme_changed(self) -> None:
        c = ThemeManager.current()
        self._plc_status_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._enc_status.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._rs422_note.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-style: italic;")
        self._position_label.setStyleSheet(
            f"font-size: 28px; font-weight: bold; font-family: monospace; color: {c.SUCCESS};"
        )
