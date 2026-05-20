"""Commissioning panel — camera discovery, connection test, parameter tuning, encoder calibration."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QDoubleSpinBox, QTextEdit, QMessageBox, QFrame,
)

from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera
from src.device.camera.hikrobot.sdk_loader import load_sdk, SDK_ERROR as _SDK_LOAD_ERROR
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import DeviceInfo

logger = logging.getLogger(__name__)


class CommissioningPanel(QWidget):
    """Camera commissioning and diagnostic panel.

    Provides:
    - Camera discovery and connection testing
    - Exposure / gain / line rate tuning
    - Encoder calibration wizard placeholder
    """

    camera_connected = Signal(str)      # camera_id
    camera_disconnected = Signal(str)   # camera_id
    param_changed = Signal(str, str, object)  # camera_id, param_name, value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._device: "LineScanDevice | None" = None
        self._discovered: list[DeviceInfo] = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Camera Discovery ──
        discover_grp = QGroupBox("相机发现")
        discover_layout = QVBoxLayout(discover_grp)

        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton("扫描设备")
        self._scan_btn.clicked.connect(self._on_scan)
        btn_row.addWidget(self._scan_btn)
        self._sdk_status = QLabel("SDK: 未检测")
        self._sdk_status.setStyleSheet("color: #888;")
        btn_row.addWidget(self._sdk_status)
        btn_row.addStretch()
        discover_layout.addLayout(btn_row)

        self._device_list = QTextEdit()
        self._device_list.setReadOnly(True)
        self._device_list.setMaximumHeight(120)
        self._device_list.setStyleSheet("background-color: #1E1E1E; color: #CCC;")
        discover_layout.addWidget(self._device_list)
        layout.addWidget(discover_grp)

        # ── Connection ──
        conn_grp = QGroupBox("连接测试")
        conn_layout = QFormLayout(conn_grp)

        self._serial_input = QLineEdit()
        self._serial_input.setPlaceholderText("输入相机序列号")
        conn_layout.addRow("序列号:", self._serial_input)

        btn_row2 = QHBoxLayout()
        self._connect_btn = QPushButton("连接")
        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn = QPushButton("断开")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        btn_row2.addWidget(self._connect_btn)
        btn_row2.addWidget(self._disconnect_btn)
        conn_layout.addRow(btn_row2)

        self._conn_status = QLabel("未连接")
        self._conn_status.setStyleSheet("color: #CC4444;")
        conn_layout.addRow("状态:", self._conn_status)
        layout.addWidget(conn_grp)

        # ── Parameter Tuning ──
        tuning_grp = QGroupBox("相机调参")
        tuning_layout = QFormLayout(tuning_grp)

        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1.0, 1000000.0)
        self._exposure_spin.setValue(20.0)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.setDecimals(1)
        self._exposure_spin.valueChanged.connect(
            lambda v: self._emit_param("ExposureTime", v)
        )
        tuning_layout.addRow("曝光时间:", self._exposure_spin)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.0, 40.0)
        self._gain_spin.setValue(0.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        self._gain_spin.valueChanged.connect(lambda v: self._emit_param("Gain", v))
        tuning_layout.addRow("增益:", self._gain_spin)

        self._line_rate_spin = QDoubleSpinBox()
        self._line_rate_spin.setRange(100, 200000)
        self._line_rate_spin.setValue(20000)
        self._line_rate_spin.setSuffix(" Hz")
        self._line_rate_spin.setDecimals(0)
        self._line_rate_spin.valueChanged.connect(
            lambda v: self._emit_param("LineRate", int(v))
        )
        tuning_layout.addRow("行频:", self._line_rate_spin)

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["Off", "On"])
        self._trigger_combo.setCurrentText("On")
        self._trigger_combo.currentTextChanged.connect(
            lambda v: self._emit_param("TriggerMode", v)
        )
        tuning_layout.addRow("触发模式:", self._trigger_combo)

        self._trigger_src_combo = QComboBox()
        self._trigger_src_combo.addItems(["Line0", "Line1", "Line2", "Line3"])
        self._trigger_src_combo.currentTextChanged.connect(
            lambda v: self._emit_param("TriggerSource", v)
        )
        tuning_layout.addRow("触发源:", self._trigger_src_combo)

        layout.addWidget(tuning_grp)

        # ── Encoder Calibration (placeholder) ──
        enc_grp = QGroupBox("编码器标定")
        enc_layout = QFormLayout(enc_grp)

        self._known_dist = QDoubleSpinBox()
        self._known_dist.setRange(100.0, 5000.0)
        self._known_dist.setValue(1000.0)
        self._known_dist.setSuffix(" mm")
        enc_layout.addRow("已知距离:", self._known_dist)

        self._calibrate_btn = QPushButton("开始标定 (占位)")
        self._calibrate_btn.setEnabled(False)
        enc_layout.addRow(self._calibrate_btn)
        self._cal_result = QLabel("—")
        enc_layout.addRow("标定结果:", self._cal_result)
        layout.addWidget(enc_grp)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _emit_param(self, name: str, value: object) -> None:
        if self._device is not None:
            self.param_changed.emit("Camera_01", name, value)

    def _on_scan(self) -> None:
        sdk_ok = load_sdk()
        if not sdk_ok:
            self._sdk_status.setText(f"SDK: 加载失败 — {_SDK_LOAD_ERROR}")
            self._sdk_status.setStyleSheet("color: #CC4444;")
            return
        self._sdk_status.setText("SDK: 已加载")
        self._sdk_status.setStyleSheet("color: #44AA44;")

        try:
            self._discovered = HikrobotLineScanCamera.enumerate_devices()
        except Exception:
            self._discovered = []
            logger.exception("Device enumeration failed")

        if not self._discovered:
            self._device_list.setPlainText("未发现任何设备。\n请检查网线连接和 IP 配置。")
        else:
            lines = []
            for d in self._discovered:
                lines.append(
                    f"序列号: {d.serial_number}\n"
                    f"  型号: {d.model}  厂商: {d.vendor}\n"
                    f"  IP: {d.ip_address}  MAC: {d.mac_address}\n"
                    f"  用户名: {d.user_defined_name}\n"
                )
            self._device_list.setPlainText("\n".join(lines))

    def _on_connect(self) -> None:
        serial = self._serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "提示", "请输入相机序列号")
            return

        if not load_sdk():
            QMessageBox.critical(self, "错误", f"SDK 未加载: {_SDK_LOAD_ERROR}")
            return

        self._device = HikrobotLineScanCamera()
        ok = self._device.open(serial)
        if not ok:
            code, msg = self._device.get_last_error()
            QMessageBox.critical(self, "连接失败", f"错误 0x{code:08X}: {msg}")
            self._device = None
            return

        self._conn_status.setText(f"已连接 — {serial}")
        self._conn_status.setStyleSheet("color: #44AA44;")
        self._connect_btn.setEnabled(False)
        self._disconnect_btn.setEnabled(True)
        self._calibrate_btn.setEnabled(True)
        self.camera_connected.emit("Camera_01")
        logger.info("CommissioningPanel: connected to %s", serial)

    def _on_disconnect(self) -> None:
        if self._device is not None:
            self._device.close()
            self._device = None

        self._conn_status.setText("未连接")
        self._conn_status.setStyleSheet("color: #CC4444;")
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)
        self._calibrate_btn.setEnabled(False)
        self.camera_disconnected.emit("Camera_01")
        logger.info("CommissioningPanel: disconnected")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_connected_device(self) -> "LineScanDevice | None":
        return self._device

    def get_discovered_devices(self) -> list[DeviceInfo]:
        return list(self._discovered)
