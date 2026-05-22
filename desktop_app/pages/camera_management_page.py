"""Camera management page — discovery, binding, parameters, preview, diagnostics."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import numpy as np

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QTextEdit, QMessageBox, QFrame, QScrollArea, QSplitter,
)

from src.device.camera.binding_store import BindingStore, CameraBinding, SLOT_IDS
from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera
from src.device.camera.hikrobot import sdk_loader
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import DeviceInfo, FramePacket
from src.device.camera.param_templates import CameraParams, ParamTemplateManager
from desktop_app.i18n import tr, I18nManager

logger = logging.getLogger(__name__)

_ROLES = ["top", "left", "right", "spare"]
_PARAM_FLOAT_NAMES = {"ExposureTime", "Gain"}
_PARAM_INT_NAMES = {"Width", "Height", "LineRate", "PayloadSize", "OffsetX", "OffsetY"}
_PARAM_BOOL_NAMES = {"ReverseX", "ReverseY"}
_PARAM_ENUM_NAMES = {"TriggerMode", "TriggerSource", "PixelFormat", "AcquisitionMode"}


class CameraManagementPage(QWidget):
    """All-in-one camera operations: discover, bind, configure, preview, diagnose."""

    camera_connected = Signal(str)  # camera_slot
    camera_disconnected = Signal(str)  # camera_slot

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding_store = BindingStore()
        self._template_mgr = ParamTemplateManager()

        # Active camera instances: slot → device
        self._cameras: dict[str, LineScanDevice] = {}
        # Preview state
        self._preview_active: bool = False
        self._preview_buffer: np.ndarray | None = None
        self._preview_lock = False
        # Discovered devices cache
        self._discovered: list[DeviceInfo] = []
        # Accumulated line count per camera for diagnostics
        self._line_counts: dict[str, int] = {}

        self._setup_ui()
        self._load_bindings()

        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Section 1: Discovery & Binding ──
        self._build_discovery_section()
        outer.addWidget(self._discovery_group)

        # ── Section 2: Parameter Control ──
        self._build_param_section()
        outer.addWidget(self._param_group)

        # ── Section 3 & 4: Preview + Diagnostics side by side ──
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._build_preview_section()
        bottom_splitter.addWidget(self._preview_group)
        self._build_diag_section()
        bottom_splitter.addWidget(self._diag_group)
        bottom_splitter.setStretchFactor(0, 3)
        bottom_splitter.setStretchFactor(1, 2)
        outer.addWidget(bottom_splitter, 1)

    # ------------------------------------------------------------------
    # Discovery & Binding Section
    # ------------------------------------------------------------------

    def _build_discovery_section(self) -> None:
        self._discovery_group = QGroupBox("相机发现与绑定")
        layout = QVBoxLayout(self._discovery_group)

        # Scan row
        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("扫描设备")
        self._scan_btn.clicked.connect(self._on_scan)
        scan_row.addWidget(self._scan_btn)
        self._sdk_label = QLabel("SDK: 未检测")
        self._sdk_label.setStyleSheet("color: #888;")
        scan_row.addWidget(self._sdk_label)
        scan_row.addStretch()
        layout.addLayout(scan_row)

        # Device list
        self._device_list = QTextEdit()
        self._device_list.setReadOnly(True)
        self._device_list.setMaximumHeight(90)
        self._device_list.setStyleSheet("background-color: #1E1E1E; color: #CCC; font-size: 12px;")
        layout.addWidget(self._device_list)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("设备:"))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(360)
        device_row.addWidget(self._device_combo, 1)
        layout.addLayout(device_row)

        # Binding row
        bind_row = QHBoxLayout()
        bind_row.addWidget(QLabel("槽位:"))
        self._slot_combo = QComboBox()
        self._slot_combo.addItems(SLOT_IDS)
        self._slot_combo.currentTextChanged.connect(self._on_slot_changed)
        bind_row.addWidget(self._slot_combo)

        bind_row.addWidget(QLabel("角色:"))
        self._role_combo = QComboBox()
        self._role_combo.addItems(["上方", "左侧", "右侧", "备用"])
        bind_row.addWidget(self._role_combo)

        self._bind_btn = QPushButton("绑定并连接")
        self._bind_btn.clicked.connect(self._on_bind_connect)
        self._bind_btn.setObjectName("primaryBtn")
        bind_row.addWidget(self._bind_btn)

        self._unbind_btn = QPushButton("解绑")
        self._unbind_btn.clicked.connect(self._on_unbind)
        self._unbind_btn.setEnabled(False)
        bind_row.addWidget(self._unbind_btn)
        bind_row.addStretch()
        layout.addLayout(bind_row)

        # Multi-slot status bar
        self._slot_status_labels: dict[str, QLabel] = {}
        status_row = QHBoxLayout()
        for sid in SLOT_IDS:
            lbl = QLabel(self._slot_display(sid))
            lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #888;")
            self._slot_status_labels[sid] = lbl
            status_row.addWidget(lbl)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Global action buttons
        action_row = QHBoxLayout()
        self._connect_all_btn = QPushButton("全部连接")
        self._connect_all_btn.clicked.connect(self._on_connect_all)
        action_row.addWidget(self._connect_all_btn)
        self._disconnect_all_btn = QPushButton("全部断开")
        self._disconnect_all_btn.clicked.connect(self._on_disconnect_all)
        action_row.addWidget(self._disconnect_all_btn)
        self._save_binding_btn = QPushButton("保存绑定")
        self._save_binding_btn.clicked.connect(self._on_save_binding)
        action_row.addWidget(self._save_binding_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    def _slot_display(self, sid: str) -> str:
        """Return short display text for a slot status."""
        binding = self._binding_store.get_binding(sid)
        if binding is None or not binding.serial_number:
            return f"{sid}: ○ 空闲"
        dev = self._cameras.get(sid)
        if dev is not None:
            st = dev.get_status()
            if st.grabbing:
                return f"{sid}: ● 采集中"
            if st.connected:
                return f"{sid}: ● 已连接"
        return f"{sid}: ◐ 已绑定"

    def _refresh_slot_status(self) -> None:
        for sid in SLOT_IDS:
            lbl = self._slot_status_labels.get(sid)
            if lbl:
                lbl.setText(self._slot_display(sid))
                # Color coding
                binding = self._binding_store.get_binding(sid)
                dev = self._cameras.get(sid)
                if dev is not None:
                    st = dev.get_status()
                    if st.grabbing:
                        lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #4CAF50; font-weight: bold;")
                    elif st.connected:
                        lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #FF9800;")
                    elif st.last_error_code != 0:
                        lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #F44336;")
                elif binding is not None and binding.serial_number:
                    lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #888;")
                else:
                    lbl.setStyleSheet("font-size: 11px; padding: 2px 6px; color: #555;")

    def _on_slot_changed(self, _text: str) -> None:
        slot = self._slot_combo.currentText()
        binding = self._binding_store.get_binding(slot)
        if binding:
            role_idx = _ROLES.index(binding.role) if binding.role in _ROLES else 3
            self._role_combo.setCurrentIndex(role_idx)
            self._unbind_btn.setEnabled(True)
        else:
            self._unbind_btn.setEnabled(False)
        self._refresh_device_choices()

    # ------------------------------------------------------------------
    # Parameter Control Section
    # ------------------------------------------------------------------

    def _build_param_section(self) -> None:
        self._param_group = QGroupBox("参数控制")
        layout = QVBoxLayout(self._param_group)

        # Row 1: Exposure, Gain, Trigger Mode, Trigger Source, Pixel Format
        row1 = QHBoxLayout()

        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1.0, 1000000.0)
        self._exposure_spin.setValue(100.0)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.setDecimals(1)
        row1.addWidget(QLabel("曝光:"))
        row1.addWidget(self._exposure_spin)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.0, 40.0)
        self._gain_spin.setValue(1.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        row1.addWidget(QLabel("增益:"))
        row1.addWidget(self._gain_spin)

        row1.addWidget(QLabel("触发:"))
        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["Off", "On"])
        self._trigger_combo.setCurrentText("Off")
        row1.addWidget(self._trigger_combo)

        row1.addWidget(QLabel("触发源:"))
        self._trigger_src_combo = QComboBox()
        self._trigger_src_combo.addItems(["Line0", "Line1", "Line2", "Line3", "Software"])
        row1.addWidget(self._trigger_src_combo)

        row1.addWidget(QLabel("采集模式:"))
        self._acq_mode_combo = QComboBox()
        self._acq_mode_combo.addItems(["Continuous", "SingleFrame"])
        row1.addWidget(self._acq_mode_combo)

        row1.addWidget(QLabel("格式:"))
        self._pixel_fmt_combo = QComboBox()
        self._pixel_fmt_combo.addItems(["Mono8", "Mono10", "Mono12", "BayerRG8", "RGB8"])
        row1.addWidget(self._pixel_fmt_combo)

        layout.addLayout(row1)

        # Row 2: LineRate, Width, BlockHeight, PacketSize, InterDelay, Buffer
        row2 = QHBoxLayout()

        self._line_rate_spin = QSpinBox()
        self._line_rate_spin.setRange(100, 200000)
        self._line_rate_spin.setValue(20000)
        self._line_rate_spin.setSuffix(" Hz")
        row2.addWidget(QLabel("行频:"))
        row2.addWidget(self._line_rate_spin)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(256, 8192)
        self._width_spin.setValue(2048)
        row2.addWidget(QLabel("宽度:"))
        row2.addWidget(self._width_spin)

        self._block_h_spin = QSpinBox()
        self._block_h_spin.setRange(64, 8192)
        self._block_h_spin.setValue(1024)
        row2.addWidget(QLabel("块高:"))
        row2.addWidget(self._block_h_spin)

        self._pkt_size_spin = QSpinBox()
        self._pkt_size_spin.setRange(1500, 65535)
        self._pkt_size_spin.setValue(9000)
        row2.addWidget(QLabel("包大小:"))
        row2.addWidget(self._pkt_size_spin)

        self._inter_delay_spin = QSpinBox()
        self._inter_delay_spin.setRange(0, 10000)
        self._inter_delay_spin.setValue(0)
        self._inter_delay_spin.setSuffix(" us")
        row2.addWidget(QLabel("包间隔:"))
        row2.addWidget(self._inter_delay_spin)

        self._buffer_spin = QSpinBox()
        self._buffer_spin.setRange(1, 256)
        self._buffer_spin.setValue(16)
        row2.addWidget(QLabel("缓存:"))
        row2.addWidget(self._buffer_spin)

        layout.addLayout(row2)

        # Row 3: Reverse X/Y + action buttons
        row3 = QHBoxLayout()
        self._reverse_x_cb = QCheckBox("水平翻转")
        row3.addWidget(self._reverse_x_cb)
        self._reverse_y_cb = QCheckBox("垂直翻转")
        row3.addWidget(self._reverse_y_cb)
        row3.addStretch()

        self._apply_btn = QPushButton("应用到选中相机")
        self._apply_btn.clicked.connect(self._on_apply_params)
        self._apply_btn.setObjectName("primaryBtn")
        row3.addWidget(self._apply_btn)

        self._save_tpl_btn = QPushButton("保存模板")
        self._save_tpl_btn.clicked.connect(self._on_save_template)
        row3.addWidget(self._save_tpl_btn)

        self._load_tpl_btn = QPushButton("加载模板")
        self._load_tpl_btn.clicked.connect(self._on_load_template)
        row3.addWidget(self._load_tpl_btn)

        self._reset_params_btn = QPushButton("恢复默认")
        self._reset_params_btn.clicked.connect(self._on_reset_params)
        row3.addWidget(self._reset_params_btn)

        layout.addLayout(row3)

    # ------------------------------------------------------------------
    # Preview Section
    # ------------------------------------------------------------------

    def _build_preview_section(self) -> None:
        self._preview_group = QGroupBox("实时预览")
        layout = QVBoxLayout(self._preview_group)

        # Image display
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(320, 240)
        self._preview_label.setStyleSheet(
            "background-color: #111; border: 1px solid #333; color: #555;"
        )
        self._preview_label.setText("未开始预览")
        layout.addWidget(self._preview_label, 1)

        # Info bar
        self._preview_info = QLabel("—")
        self._preview_info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._preview_info)

        # Controls
        btn_row = QHBoxLayout()
        self._preview_start_btn = QPushButton("开始预览")
        self._preview_start_btn.clicked.connect(self._on_start_preview)
        btn_row.addWidget(self._preview_start_btn)
        self._preview_stop_btn = QPushButton("停止预览")
        self._preview_stop_btn.setEnabled(False)
        self._preview_stop_btn.clicked.connect(self._on_stop_preview)
        btn_row.addWidget(self._preview_stop_btn)
        self._snapshot_btn = QPushButton("保存快照")
        self._snapshot_btn.clicked.connect(self._on_snapshot)
        self._snapshot_btn.setEnabled(False)
        btn_row.addWidget(self._snapshot_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Preview refresh timer
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_timer.setInterval(66)  # ~15 FPS

    # ------------------------------------------------------------------
    # Diagnostics Section
    # ------------------------------------------------------------------

    def _build_diag_section(self) -> None:
        self._diag_group = QGroupBox("诊断信息")
        layout = QVBoxLayout(self._diag_group)

        self._diag_text = QTextEdit()
        self._diag_text.setReadOnly(True)
        self._diag_text.setStyleSheet(
            "background-color: #1E1E1E; color: #CCC; font-size: 12px;"
        )
        layout.addWidget(self._diag_text, 1)

        # Diagnostics refresh timer
        self._diag_timer = QTimer(self)
        self._diag_timer.timeout.connect(self._refresh_diagnostics)
        self._diag_timer.setInterval(1000)  # 1 Hz

    # ------------------------------------------------------------------
    # Binding persistence
    # ------------------------------------------------------------------

    def _load_bindings(self) -> None:
        """Load saved bindings on startup."""
        bindings = self._binding_store.load_all()
        if bindings:
            logger.info("Loaded %d camera bindings", len(bindings))
        self._refresh_slot_status()

    def _on_save_binding(self) -> None:
        """Persist current bindings to disk."""
        self._binding_store.save_all()
        QMessageBox.information(self, "保存", "相机绑定已保存。")
        logger.info("Bindings saved manually")

    # ------------------------------------------------------------------
    # Scan & Bind
    # ------------------------------------------------------------------

    def _on_scan(self) -> None:
        """Scan for Hikrobot cameras on the network."""
        sdk_ok = sdk_loader.load_sdk()
        if not sdk_ok:
            error = sdk_loader.SDK_ERROR or "unknown error"
            self._sdk_label.setText(f"SDK: 加载失败 — {error}")
            self._sdk_label.setStyleSheet("color: #F44336;")
            self._refresh_device_choices()
            return
        self._sdk_label.setText("SDK: 已加载")
        self._sdk_label.setStyleSheet("color: #4CAF50;")

        try:
            self._discovered = HikrobotLineScanCamera.enumerate_devices()
        except Exception:
            self._discovered = []
            logger.exception("Device enumeration failed")

        self._refresh_device_choices()

        if not self._discovered:
            self._device_list.setPlainText("未发现任何设备。\n请检查网线连接、相机供电和 IP 配置。")
        else:
            lines = []
            for d in self._discovered:
                lines.append(
                    f"序列号: {d.serial_number}  型号: {d.model}  厂商: {d.vendor}\n"
                    f"  IP: {d.ip_address}  MAC: {d.mac_address}"
                )
                if d.user_defined_name:
                    lines[-1] += f"  名称: {d.user_defined_name}"
            self._device_list.setPlainText("\n".join(lines))

    def _refresh_device_choices(self) -> None:
        """Refresh selectable discovered devices without relying on SDK order."""
        self._device_combo.clear()
        slot = self._slot_combo.currentText()
        existing = self._binding_store.get_binding(slot)
        selected_idx = 0
        for index, device in enumerate(self._discovered):
            text = (
                f"{device.serial_number or '(no SN)'} | {device.model or '(unknown model)'} | "
                f"{device.ip_address or '(no IP)'} | {device.mac_address or '(no MAC)'}"
            )
            self._device_combo.addItem(text, device.serial_number)
            if existing and existing.serial_number == device.serial_number:
                selected_idx = index
        if self._discovered:
            self._device_combo.setCurrentIndex(selected_idx)

    def _on_bind_connect(self) -> None:
        """Bind selected discovered device to current slot and connect."""
        if not self._discovered:
            QMessageBox.warning(self, "提示", "请先扫描设备。")
            return

        slot = self._slot_combo.currentText()
        role = _ROLES[self._role_combo.currentIndex()]

        selected_idx = self._device_combo.currentIndex()
        if selected_idx < 0 or selected_idx >= len(self._discovered):
            QMessageBox.warning(self, "提示", "请选择要绑定的相机。")
            return

        device_info = self._discovered[selected_idx]

        # Create binding
        binding = CameraBinding(
            camera_slot=slot,
            enabled=True,
            role=role,
            serial_number=device_info.serial_number,
            mac_address=device_info.mac_address,
            ip_address=device_info.ip_address,
            model=device_info.model,
            param_profile=f"{slot}_params.json",
        )
        self._binding_store.set_binding(binding)

        # Connect
        cam = HikrobotLineScanCamera()
        if not cam.open(device_info.serial_number):
            code, msg = cam.get_last_error()
            QMessageBox.critical(
                self, "连接失败",
                f"无法连接相机 {device_info.serial_number}\n错误 0x{code:08X}: {msg}"
            )
            return

        # Close existing device on this slot if any
        old = self._cameras.pop(slot, None)
        if old:
            try:
                old.stop_grabbing()
                old.close()
            except Exception:
                pass

        self._cameras[slot] = cam
        self._line_counts[slot] = 0
        self._unbind_btn.setEnabled(True)
        self._refresh_slot_status()
        self.camera_connected.emit(slot)
        logger.info("Bound and connected %s → %s (role=%s)", slot, device_info.serial_number, role)

    def _on_unbind(self) -> None:
        """Remove binding and disconnect camera from current slot."""
        slot = self._slot_combo.currentText()
        dev = self._cameras.pop(slot, None)
        if dev:
            try:
                dev.stop_grabbing()
                dev.close()
            except Exception:
                pass
        self._binding_store.remove_binding(slot)
        self._line_counts.pop(slot, None)
        self._unbind_btn.setEnabled(False)
        self._refresh_slot_status()
        self.camera_disconnected.emit(slot)
        logger.info("Unbound %s", slot)

    # ------------------------------------------------------------------
    # Connect / Disconnect All
    # ------------------------------------------------------------------

    def _on_connect_all(self) -> None:
        """Connect all enabled bound cameras."""
        serial_map = self._binding_store.get_serial_map()
        if not serial_map:
            QMessageBox.information(self, "提示", "没有已启用且已绑定的相机。")
            return

        for slot, sn in serial_map.items():
            if slot in self._cameras:
                continue  # already connected
            cam = HikrobotLineScanCamera()
            if cam.open(sn):
                self._cameras[slot] = cam
                self._line_counts[slot] = 0
                self.camera_connected.emit(slot)
                logger.info("Connected %s (SN=%s)", slot, sn)
            else:
                code, msg = cam.get_last_error()
                logger.warning("Failed to connect %s: 0x%08X %s", slot, code, msg)
        self._refresh_slot_status()

    def _on_disconnect_all(self) -> None:
        """Disconnect all cameras."""
        for slot, dev in list(self._cameras.items()):
            try:
                dev.stop_grabbing()
                dev.close()
            except Exception:
                pass
            self.camera_disconnected.emit(slot)
        self._cameras.clear()
        self._line_counts.clear()
        self._refresh_slot_status()
        logger.info("All cameras disconnected")

    # ------------------------------------------------------------------
    # Parameter Control
    # ------------------------------------------------------------------

    def _get_selected_camera(self) -> LineScanDevice | None:
        """Return the camera for the currently selected slot."""
        slot = self._slot_combo.currentText()
        return self._cameras.get(slot)

    def _on_apply_params(self) -> None:
        """Apply current parameter values to the selected camera."""
        cam = self._get_selected_camera()
        if cam is None:
            QMessageBox.warning(self, "提示", "当前槽位没有已连接的相机。")
            return

        params = [
            ("ExposureTime", self._exposure_spin.value()),
            ("Gain", self._gain_spin.value()),
            ("TriggerMode", self._trigger_combo.currentText()),
            ("TriggerSource", self._trigger_src_combo.currentText()),
            ("AcquisitionMode", self._acq_mode_combo.currentText()),
            ("PixelFormat", self._pixel_fmt_combo.currentText()),
            ("LineRate", self._line_rate_spin.value()),
            ("Width", self._width_spin.value()),
            ("Height", self._block_h_spin.value()),
            ("GevSCPSPacketSize", self._pkt_size_spin.value()),
            ("GevSCPD", self._inter_delay_spin.value()),
            ("BufferCount", self._buffer_spin.value()),
            ("ReverseX", self._reverse_x_cb.isChecked()),
            ("ReverseY", self._reverse_y_cb.isChecked()),
        ]
        for name, value in params:
            try:
                cam.set_param(name, value)
                logger.debug("Set %s = %s", name, value)
            except Exception as e:
                logger.warning("Failed to set %s: %s", name, e)

        QMessageBox.information(self, "参数", "参数已应用。")

    def _on_reset_params(self) -> None:
        """Reset UI parameters to defaults."""
        defaults = ParamTemplateManager.get_defaults()
        self._exposure_spin.setValue(defaults.exposure_time)
        self._gain_spin.setValue(defaults.gain)
        self._trigger_combo.setCurrentText(defaults.trigger_mode)
        self._trigger_src_combo.setCurrentText(defaults.trigger_source)
        self._acq_mode_combo.setCurrentText(defaults.acquisition_mode)
        self._pixel_fmt_combo.setCurrentText(defaults.pixel_format)
        self._line_rate_spin.setValue(defaults.line_rate)
        self._width_spin.setValue(defaults.width)
        self._block_h_spin.setValue(defaults.block_height)
        self._pkt_size_spin.setValue(defaults.packet_size)
        self._inter_delay_spin.setValue(defaults.inter_packet_delay)
        self._buffer_spin.setValue(defaults.buffer_count)
        self._reverse_x_cb.setChecked(defaults.reverse_x)
        self._reverse_y_cb.setChecked(defaults.reverse_y)

    def _on_save_template(self) -> None:
        """Save current parameters as a template."""
        params = self._collect_params()
        slot = self._slot_combo.currentText()
        name = f"Camera_{slot[-2:]}_Params"
        path = self._template_mgr.save(name, params)
        QMessageBox.information(self, "模板", f"参数模板已保存到:\n{path}")

    def _on_load_template(self) -> None:
        """Load parameters from a template."""
        templates = self._template_mgr.list_templates()
        if not templates:
            QMessageBox.information(self, "模板", "没有已保存的参数模板。")
            return

        # Use the first template for the current slot, or the first overall
        slot = self._slot_combo.currentText()
        slot_suffix = f"Camera_{slot[-2:]}"
        matching = [t for t in templates if slot_suffix in t]
        name = matching[0] if matching else templates[0]

        params = self._template_mgr.load(name)
        if params is None:
            QMessageBox.warning(self, "错误", f"无法加载模板: {name}")
            return

        self._apply_params_from(params)
        QMessageBox.information(self, "模板", f"已加载模板: {name}")

    def _collect_params(self) -> CameraParams:
        """Build a CameraParams from current UI state."""
        return CameraParams(
            camera_slot=self._slot_combo.currentText(),
            pixel_format=self._pixel_fmt_combo.currentText(),
            exposure_time=self._exposure_spin.value(),
            gain=self._gain_spin.value(),
            trigger_mode=self._trigger_combo.currentText(),
            trigger_source=self._trigger_src_combo.currentText(),
            acquisition_mode=self._acq_mode_combo.currentText(),
            width=self._width_spin.value(),
            block_height=self._block_h_spin.value(),
            line_rate=self._line_rate_spin.value(),
            packet_size=self._pkt_size_spin.value(),
            inter_packet_delay=self._inter_delay_spin.value(),
            buffer_count=self._buffer_spin.value(),
            reverse_x=self._reverse_x_cb.isChecked(),
            reverse_y=self._reverse_y_cb.isChecked(),
        )

    def _apply_params_from(self, params: CameraParams) -> None:
        """Set UI controls to match a CameraParams object."""
        self._exposure_spin.setValue(params.exposure_time)
        self._gain_spin.setValue(params.gain)
        self._trigger_combo.setCurrentText(params.trigger_mode)
        self._trigger_src_combo.setCurrentText(params.trigger_source)
        self._acq_mode_combo.setCurrentText(params.acquisition_mode)
        self._pixel_fmt_combo.setCurrentText(params.pixel_format)
        self._line_rate_spin.setValue(params.line_rate)
        self._width_spin.setValue(params.width)
        self._block_h_spin.setValue(params.block_height)
        self._pkt_size_spin.setValue(params.packet_size)
        self._inter_delay_spin.setValue(params.inter_packet_delay)
        self._buffer_spin.setValue(params.buffer_count)
        self._reverse_x_cb.setChecked(params.reverse_x)
        self._reverse_y_cb.setChecked(params.reverse_y)

    # ------------------------------------------------------------------
    # Live Preview
    # ------------------------------------------------------------------

    def _on_start_preview(self) -> None:
        """Start live preview for the selected camera."""
        cam = self._get_selected_camera()
        if cam is None:
            QMessageBox.warning(self, "提示", "当前槽位没有已连接的相机。请先绑定并连接。")
            return

        self._preview_buffer = None
        self._preview_lock = False

        def on_line(pkt: FramePacket) -> None:
            if self._preview_lock:
                return
            if pkt.line_data is not None:
                # Keep the most recent frame
                self._preview_buffer = pkt.line_data.copy()

        cam.register_line_callback(on_line)
        if not cam.start_grabbing():
            code, msg = cam.get_last_error()
            QMessageBox.critical(self, "预览失败", f"无法开始采集: 0x{code:08X} {msg}")
            return

        self._preview_active = True
        self._preview_timer.start()
        self._diag_timer.start()
        self._preview_start_btn.setEnabled(False)
        self._preview_stop_btn.setEnabled(True)
        self._snapshot_btn.setEnabled(True)
        self._refresh_slot_status()
        logger.info("Preview started")

    def _on_stop_preview(self) -> None:
        """Stop live preview."""
        self._preview_active = False
        self._preview_timer.stop()
        self._diag_timer.stop()

        cam = self._get_selected_camera()
        if cam:
            cam.unregister_line_callback()
            cam.stop_grabbing()

        self._preview_start_btn.setEnabled(True)
        self._preview_stop_btn.setEnabled(False)
        self._snapshot_btn.setEnabled(False)
        self._preview_label.setText("预览已停止")
        self._refresh_slot_status()
        logger.info("Preview stopped")

    def _refresh_preview(self) -> None:
        """Called by QTimer to update the preview image."""
        if self._preview_buffer is None:
            return
        self._preview_lock = True
        try:
            img = self._preview_buffer
            h, w = img.shape[:2]

            # Convert numpy to QPixmap
            if img.ndim == 2:
                # Grayscale
                qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
            elif img.ndim == 3 and img.shape[2] == 3:
                # RGB
                qimg = QImage(img.data, w, h, w * 3, QImage.Format.Format_RGB888)
            else:
                return

            # Scale to fit label
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self._preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)
            self._preview_info.setText(f"{w}×{h} Mono8")
        finally:
            self._preview_lock = False

    def _on_snapshot(self) -> None:
        """Save current preview frame as PNG."""
        if self._preview_buffer is None:
            return
        import cv2
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(os.getcwd(), f"camera_snapshot_{ts}.png")
        cv2.imwrite(fname, self._preview_buffer)
        QMessageBox.information(self, "快照", f"已保存: {fname}")
        logger.info("Snapshot saved: %s", fname)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def _refresh_diagnostics(self) -> None:
        """Called by QTimer to refresh diagnostic information."""
        lines: list[str] = []
        slot = self._slot_combo.currentText()
        cam = self._get_selected_camera()

        if cam is None:
            self._diag_text.setPlainText("无已连接相机")
            return

        st = cam.get_status()
        w = cam.get_param("Width") or 2048
        h = cam.get_param("Height") or 1

        lines.append(f"槽位:         {slot}")
        lines.append(f"序列号:       {st.serial_number}")
        lines.append(f"连接状态:     {'✓ 已连接' if st.connected else '✗ 断开'}")
        lines.append(f"采集状态:     {'✓ 采集中' if st.grabbing else '✗ 停止'}")
        lines.append(f"行频:         {st.line_rate:.0f} Hz")
        lines.append(f"已收行数:     {st.received_line_count}")
        lines.append(f"丢行数:       {st.dropped_line_count}")
        lines.append(f"超时次数:     {st.timeout_count}")
        lines.append(f"图像尺寸:     {w} × {h}")
        lines.append(f"像素格式:     {cam.get_param('PixelFormat') or 'Mono8'}")
        lines.append(f"曝光时间:     {cam.get_param('ExposureTime') or 0:.1f} us")
        lines.append(f"增益:         {cam.get_param('Gain') or 0:.1f} dB")
        err_code = st.last_error_code
        if err_code != 0:
            lines.append(f"最后错误:     0x{err_code:08X} {st.last_error_message}")
        else:
            lines.append(f"最后错误:     —")

        self._diag_text.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._refresh_slot_status()

    def closeEvent(self, event: object) -> None:
        self._on_disconnect_all()
        # Finalize SDK if initialized
        try:
            HikrobotLineScanCamera._finalize_sdk()
        except Exception:
            pass
        super().closeEvent(event)

    def _refresh_text(self, lang: str = "") -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_camera(self, slot: str) -> LineScanDevice | None:
        """Get the device instance for a specific slot."""
        return self._cameras.get(slot)

    def get_all_cameras(self) -> dict[str, LineScanDevice]:
        """Get all connected cameras."""
        return dict(self._cameras)

    def get_connected_slots(self) -> list[str]:
        """Return slots that have connected cameras."""
        return [
            slot for slot, dev in self._cameras.items()
            if dev.get_status().connected
        ]
