"""PLC configuration page."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QLabel, QMessageBox,
)
from integration.modbus_tcp import ModbusTcpClient
from integration.tcp_socket import TcpSocketClient
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager


class PlcConfigPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._grp = QGroupBox()
        bind(self._grp, "plc.group", setter="setTitle")
        form = QFormLayout(self._grp)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["TCP Socket", "Modbus TCP", "Serial Port", "HTTP"])
        method_label = QLabel()
        bind(method_label, "plc.method")
        form.addRow(method_label, self._type_combo)

        self._host_edit = QLineEdit("127.0.0.1")
        host_label = QLabel()
        bind(host_label, "plc.host")
        form.addRow(host_label, self._host_edit)

        self._port_spin = QSpinBox(); self._port_spin.setRange(1, 65535); self._port_spin.setValue(502)
        port_label = QLabel()
        bind(port_label, "plc.port")
        form.addRow(port_label, self._port_spin)

        self._status_label = QLabel()
        bind(self._status_label, "plc.not_connected")
        self._status_label.setStyleSheet("color: #888;")
        status_label = QLabel()
        bind(status_label, "app.status")
        form.addRow(status_label, self._status_label)

        layout.addWidget(self._grp)

        self._test_btn = QPushButton()
        bind(self._test_btn, "plc.test")
        self._test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self._test_btn)
        layout.addStretch()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set status label on language change."""
        # Status label is set conditionally — just re-apply current state
        pass

    def _test_connection(self):
        ct = self._type_combo.currentText()
        try:
            if ct == "TCP Socket":
                client = TcpSocketClient()
                ok = client.connect({"host": self._host_edit.text(), "port": self._port_spin.value()})
            elif ct == "Modbus TCP":
                client = ModbusTcpClient()
                ok = client.connect({"host": self._host_edit.text(), "port": self._port_spin.value()})
            else:
                bind(self._status_label, "plc.not_supported", method=ct)
                return

            if ok:
                bind(self._status_label, "plc.connected")
                self._status_label.setStyleSheet("color: #4CAF50;")
            else:
                bind(self._status_label, "plc.connect_failed")
                self._status_label.setStyleSheet("color: #F44336;")
        except NotImplementedError as e:
            self._status_label.setText(str(e)); self._status_label.setStyleSheet("color: #FF9800;")
        except Exception as e:
            self._status_label.setText(tr("app.error") + f": {e}"); self._status_label.setStyleSheet("color: #F44336;")
