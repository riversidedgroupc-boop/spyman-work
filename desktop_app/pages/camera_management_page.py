"""Camera management page — discovery, binding, parameters, preview, diagnostics.

.. deprecated::
    Superseded by CameraWorkbenchPage in the device_setup container
    (MainWindow._device_tabs). No longer registered as a standalone
    navigation entry. Kept for reference; remove after 2026-Q3 if no
    downstream consumers are found.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import time
from typing import Any, Protocol

import numpy as np

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QTextEdit,
    QMessageBox,
    QSplitter,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from src.device.camera.binding_store import BindingStore, CameraBinding, SLOT_IDS
from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera
from src.device.camera.hikrobot import sdk_loader
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import DeviceInfo, FramePacket
from src.device.camera.param_templates import CameraParams, ParamTemplateManager
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager
from camera_adapters.folder_watcher import FolderWatcherCameraAdapter
from camera_adapters.basler_pylon import BaslerPylonAdapter

# Deprecation markers — kept as module constants to avoid E402
_DEPRECATED: bool = True
_DEPRECATED_REPLACEMENT: str = "CameraWorkbenchPage in device_setup"

logger = logging.getLogger(__name__)

_ROLES = ["top", "left", "right", "spare"]
_PARAM_FLOAT_NAMES = {"ExposureTime", "Gain"}
_PARAM_INT_NAMES = {"Width", "Height", "LineRate", "PayloadSize", "OffsetX", "OffsetY"}
_PARAM_BOOL_NAMES = {"ReverseX", "ReverseY"}
_PARAM_ENUM_NAMES = {"TriggerMode", "TriggerSource", "PixelFormat", "AcquisitionMode"}


@dataclass(frozen=True)
class _AdapterDisplayRow:
    name: str
    adapter_type: str
    status: str
    devices: str


class _CameraAdapterStatus(Protocol):
    def list_devices(self) -> list[dict[str, Any]]:
        """Return displayable devices for the adapter table."""


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
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Section 0: Registered Adapters ──
        self._build_adapter_section()
        outer.addWidget(self._adapter_group)

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

    def _build_adapter_section(self) -> None:
        self._adapter_group = QGroupBox(tr("camera_mgmt.adapter_group"))
        layout = QVBoxLayout(self._adapter_group)
        self._adapter_table = QTableWidget(0, 4)
        self._adapter_table.setHorizontalHeaderLabels(
            [
                tr("device.col_adapter"),
                tr("device.col_type"),
                tr("device.col_status"),
                tr("device.col_devices"),
            ]
        )
        self._adapter_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._adapter_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._adapter_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._adapter_table.setWordWrap(False)
        self._adapter_table.verticalHeader().setVisible(False)
        self._adapter_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._adapter_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = self._adapter_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._adapter_table)
        self._refresh_adapters()

    def _refresh_adapters(self) -> None:
        rows = [
            self._adapter_row(FolderWatcherCameraAdapter(), "Folder Watcher", "folder_watcher"),
            self._hikrobot_line_scan_row(),
            self._adapter_row(BaslerPylonAdapter(), "Basler Pylon", "basler_pylon"),
        ]
        self._adapter_table.setRowCount(len(rows))
        for row, adapter in enumerate(rows):
            self._adapter_table.setItem(row, 0, QTableWidgetItem(adapter.name))
            self._adapter_table.setItem(row, 1, QTableWidgetItem(adapter.adapter_type))
            self._adapter_table.setItem(row, 2, QTableWidgetItem(adapter.status))
            self._adapter_table.setItem(row, 3, QTableWidgetItem(adapter.devices))
        self._resize_adapter_table()

    def _adapter_row(
        self,
        adapter: _CameraAdapterStatus,
        display_name: str,
        adapter_type: str,
    ) -> _AdapterDisplayRow:
        try:
            devices = adapter.list_devices()
        except NotImplementedError:
            return _AdapterDisplayRow(
                display_name,
                adapter_type,
                tr("device.sdk_missing"),
                "-",
            )
        except Exception as exc:
            logger.exception("Camera adapter status failed: %s", adapter_type)
            return _AdapterDisplayRow(
                display_name,
                adapter_type,
                tr("device.status_error"),
                str(exc),
            )

        return _AdapterDisplayRow(
            display_name,
            adapter_type,
            tr("device.ready", count=len(devices)) if devices else tr("device.no_devices"),
            self._format_adapter_devices(devices),
        )

    def _hikrobot_line_scan_row(self) -> _AdapterDisplayRow:
        display_name = "Hikrobot Line Scan (MVS)"
        adapter_type = "hikrobot_line_scan"
        if not sdk_loader.load_sdk():
            return _AdapterDisplayRow(
                display_name,
                adapter_type,
                tr("device.sdk_missing"),
                sdk_loader.SDK_ERROR or "-",
            )

        try:
            devices = HikrobotLineScanCamera.enumerate_devices()
        except Exception as exc:
            logger.exception("Hikrobot line scan enumeration failed")
            return _AdapterDisplayRow(
                display_name,
                adapter_type,
                tr("device.status_error"),
                str(exc),
            )

        return _AdapterDisplayRow(
            display_name,
            adapter_type,
            tr("device.ready", count=len(devices)) if devices else tr("device.no_devices"),
            self._format_line_scan_devices(devices),
        )

    def _format_adapter_devices(self, devices: list[dict[str, Any]]) -> str:
        names = [
            str(device.get("name") or device.get("id") or "").strip()
            for device in devices
        ]
        names = [name for name in names if name]
        return ", ".join(names) if names else "-"

    def _format_line_scan_devices(self, devices: list[DeviceInfo]) -> str:
        labels: list[str] = []
        for device in devices:
            parts = [
                device.serial_number,
                device.model,
                device.ip_address,
            ]
            label = " / ".join(part for part in parts if part)
            if device.user_defined_name:
                label = f"{label} ({device.user_defined_name})" if label else device.user_defined_name
            if label:
                labels.append(label)
        return ", ".join(labels) if labels else "-"

    def _resize_adapter_table(self) -> None:
        self._adapter_table.resizeRowsToContents()
        height = (
            self._adapter_table.horizontalHeader().height()
            + sum(self._adapter_table.rowHeight(row) for row in range(self._adapter_table.rowCount()))
            + self._adapter_table.frameWidth() * 2
            + 6
        )
        self._adapter_table.setMinimumHeight(height)
        self._adapter_table.setMaximumHeight(height)

    def _build_discovery_section(self) -> None:
        self._discovery_group = QGroupBox(tr("camera_mgmt.discovery_group"))
        layout = QVBoxLayout(self._discovery_group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        scan_row = QHBoxLayout()
        scan_row.setSpacing(10)
        self._scan_btn = QPushButton(tr("camera.scan"))
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setMinimumWidth(112)
        scan_row.addWidget(self._scan_btn)
        self._sdk_label = QLabel(tr("commissioning.sdk_not_detected"))
        self._sdk_label.setObjectName("secondaryLabel")
        scan_row.addWidget(self._sdk_label)
        scan_row.addStretch()
        layout.addLayout(scan_row)

        self._device_list = QTextEdit()
        self._device_list.setReadOnly(True)
        self._device_list.setMinimumHeight(64)
        self._device_list.setMaximumHeight(92)
        c = ThemeManager.current()
        self._device_list.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
        )
        layout.addWidget(self._device_list)

        self._discovery_grid = QGridLayout()
        self._discovery_grid.setHorizontalSpacing(10)
        self._discovery_grid.setVerticalSpacing(8)
        self._discovery_grid.setColumnStretch(1, 3)
        self._discovery_grid.setColumnStretch(3, 1)
        self._discovery_grid.setColumnStretch(5, 2)

        device_label = QLabel(tr("camera_mgmt.device_label"))
        device_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(360)
        self._discovery_grid.addWidget(device_label, 0, 0)
        self._discovery_grid.addWidget(self._device_combo, 0, 1, 1, 5)

        slot_label = QLabel(tr("camera_mgmt.slot_label"))
        slot_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._slot_combo = QComboBox()
        self._slot_combo.addItems(SLOT_IDS)
        self._slot_combo.currentTextChanged.connect(self._on_slot_changed)
        self._slot_combo.setMinimumWidth(120)
        self._discovery_grid.addWidget(slot_label, 1, 0)
        self._discovery_grid.addWidget(self._slot_combo, 1, 1)

        role_label = QLabel(tr("camera_mgmt.role_label"))
        role_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._role_combo = QComboBox()
        self._role_combo.addItems(
            [
                tr("camera_mgmt.role_top"),
                tr("camera_mgmt.role_left"),
                tr("camera_mgmt.role_right"),
                tr("camera_mgmt.role_spare"),
            ]
        )
        self._role_combo.setMinimumWidth(112)
        self._discovery_grid.addWidget(role_label, 1, 2)
        self._discovery_grid.addWidget(self._role_combo, 1, 3)

        self._bind_btn = QPushButton(tr("camera.bind_connect"))
        self._bind_btn.clicked.connect(self._on_bind_connect)
        self._bind_btn.setObjectName("primaryBtn")
        self._bind_btn.setMinimumWidth(128)
        self._discovery_grid.addWidget(self._bind_btn, 1, 4)

        self._unbind_btn = QPushButton(tr("camera.unbind"))
        self._unbind_btn.clicked.connect(self._on_unbind)
        self._unbind_btn.setEnabled(False)
        self._unbind_btn.setMinimumWidth(88)
        self._discovery_grid.addWidget(self._unbind_btn, 1, 5)
        layout.addLayout(self._discovery_grid)

        self._slot_status_labels: dict[str, QLabel] = {}
        self._slot_status_grid = QGridLayout()
        self._slot_status_grid.setHorizontalSpacing(14)
        self._slot_status_grid.setVerticalSpacing(4)
        for index, sid in enumerate(SLOT_IDS):
            lbl = QLabel(self._slot_display(sid))
            c = ThemeManager.current()
            lbl.setStyleSheet(f"font-size: 11px; padding: 2px 6px; color: {c.TEXT_SECONDARY};")
            lbl.setMinimumWidth(150)
            self._slot_status_labels[sid] = lbl
            self._slot_status_grid.addWidget(lbl, index // 3, index % 3)
        layout.addLayout(self._slot_status_grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._connect_all_btn = QPushButton(tr("camera.connect_all"))
        self._connect_all_btn.clicked.connect(self._on_connect_all)
        self._connect_all_btn.setMinimumWidth(112)
        action_row.addWidget(self._connect_all_btn)
        self._disconnect_all_btn = QPushButton(tr("camera.disconnect_all"))
        self._disconnect_all_btn.clicked.connect(self._on_disconnect_all)
        self._disconnect_all_btn.setMinimumWidth(112)
        action_row.addWidget(self._disconnect_all_btn)
        self._save_binding_btn = QPushButton(tr("camera.save_binding"))
        self._save_binding_btn.clicked.connect(self._on_save_binding)
        self._save_binding_btn.setMinimumWidth(112)
        action_row.addWidget(self._save_binding_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    def _slot_display(self, sid: str) -> str:
        """Return short display text for a slot status."""
        binding = self._binding_store.get_binding(sid)
        if binding is None or not binding.serial_number:
            return tr("camera_mgmt.slot_free", sid=sid)
        dev = self._cameras.get(sid)
        if dev is not None:
            st = dev.get_status()
            if st.grabbing:
                return tr("camera_mgmt.slot_grabbing", sid=sid)
            if st.connected:
                return tr("camera_mgmt.slot_connected", sid=sid)
        return tr("camera_mgmt.slot_bound", sid=sid)

    def _slot_status_color(self, status: str) -> str:
        """Return CSS color value for slot status from current palette."""
        c = ThemeManager.current()
        return {
            "grabbing": c.SUCCESS,
            "connected": c.WARNING,
            "error": c.ERROR,
            "bound": c.TEXT_SECONDARY,
            "free": c.TEXT_SECONDARY,
        }.get(status, c.TEXT_SECONDARY)

    def _refresh_slot_status(self) -> None:
        for sid in SLOT_IDS:
            lbl = self._slot_status_labels.get(sid)
            if lbl:
                lbl.setText(self._slot_display(sid))
                # Color coding
                binding = self._binding_store.get_binding(sid)
                dev = self._cameras.get(sid)
                color = self._slot_status_color("free")
                bold = ""
                if dev is not None:
                    st = dev.get_status()
                    if st.grabbing:
                        color = self._slot_status_color("grabbing")
                        bold = "; font-weight: bold"
                    elif st.connected:
                        color = self._slot_status_color("connected")
                    elif st.last_error_code != 0:
                        color = self._slot_status_color("error")
                elif binding is not None and binding.serial_number:
                    color = self._slot_status_color("bound")
                lbl.setStyleSheet(f"font-size: 11px; padding: 2px 6px; color: {color}{bold};")

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
        self._param_group = QGroupBox(tr("camera_mgmt.param_group"))
        layout = QVBoxLayout(self._param_group)

        # Row 1: Exposure, Gain, Trigger Mode, Trigger Source, Pixel Format
        row1 = QHBoxLayout()

        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1.0, 1000000.0)
        self._exposure_spin.setValue(100.0)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.setDecimals(1)
        row1.addWidget(QLabel(tr("camera_mgmt.exposure_label")))
        row1.addWidget(self._exposure_spin)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.0, 40.0)
        self._gain_spin.setValue(1.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        row1.addWidget(QLabel(tr("camera_mgmt.gain_label")))
        row1.addWidget(self._gain_spin)

        row1.addWidget(QLabel(tr("camera_mgmt.trigger_label")))
        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["Off", "On"])
        self._trigger_combo.setCurrentText("Off")
        row1.addWidget(self._trigger_combo)

        row1.addWidget(QLabel(tr("camera_mgmt.trigger_src_label")))
        self._trigger_src_combo = QComboBox()
        self._trigger_src_combo.addItems(["Line0", "Line1", "Line2", "Line3", "Software"])
        row1.addWidget(self._trigger_src_combo)

        row1.addWidget(QLabel(tr("camera_mgmt.acq_mode_label")))
        self._acq_mode_combo = QComboBox()
        self._acq_mode_combo.addItems(["Continuous", "SingleFrame"])
        row1.addWidget(self._acq_mode_combo)

        row1.addWidget(QLabel(tr("camera_mgmt.pixel_format_label")))
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
        row2.addWidget(QLabel(tr("camera_mgmt.line_rate_label")))
        row2.addWidget(self._line_rate_spin)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(256, 8192)
        self._width_spin.setValue(2048)
        row2.addWidget(QLabel(tr("camera_mgmt.width_label")))
        row2.addWidget(self._width_spin)

        self._block_h_spin = QSpinBox()
        self._block_h_spin.setRange(64, 8192)
        self._block_h_spin.setValue(1024)
        row2.addWidget(QLabel(tr("camera_mgmt.block_height_label")))
        row2.addWidget(self._block_h_spin)

        self._pkt_size_spin = QSpinBox()
        self._pkt_size_spin.setRange(1500, 65535)
        self._pkt_size_spin.setValue(9000)
        row2.addWidget(QLabel(tr("camera_mgmt.packet_size_label")))
        row2.addWidget(self._pkt_size_spin)

        self._inter_delay_spin = QSpinBox()
        self._inter_delay_spin.setRange(0, 10000)
        self._inter_delay_spin.setValue(0)
        self._inter_delay_spin.setSuffix(" us")
        row2.addWidget(QLabel(tr("camera_mgmt.inter_delay_label")))
        row2.addWidget(self._inter_delay_spin)

        self._buffer_spin = QSpinBox()
        self._buffer_spin.setRange(1, 256)
        self._buffer_spin.setValue(16)
        row2.addWidget(QLabel(tr("camera_mgmt.buffer_label")))
        row2.addWidget(self._buffer_spin)

        layout.addLayout(row2)

        # Row 3: Reverse X/Y + action buttons
        row3 = QHBoxLayout()
        self._reverse_x_cb = QCheckBox(tr("camera_mgmt.reverse_x"))
        row3.addWidget(self._reverse_x_cb)
        self._reverse_y_cb = QCheckBox(tr("camera_mgmt.reverse_y"))
        row3.addWidget(self._reverse_y_cb)
        row3.addStretch()

        self._apply_btn = QPushButton(tr("camera.apply_params"))
        self._apply_btn.clicked.connect(self._on_apply_params)
        self._apply_btn.setObjectName("primaryBtn")
        row3.addWidget(self._apply_btn)

        self._save_tpl_btn = QPushButton(tr("camera.save_template"))
        self._save_tpl_btn.clicked.connect(self._on_save_template)
        row3.addWidget(self._save_tpl_btn)

        self._load_tpl_btn = QPushButton(tr("camera.load_template"))
        self._load_tpl_btn.clicked.connect(self._on_load_template)
        row3.addWidget(self._load_tpl_btn)

        self._reset_params_btn = QPushButton(tr("camera.reset_params"))
        self._reset_params_btn.clicked.connect(self._on_reset_params)
        row3.addWidget(self._reset_params_btn)

        layout.addLayout(row3)

    # ------------------------------------------------------------------
    # Preview Section
    # ------------------------------------------------------------------

    def _build_preview_section(self) -> None:
        self._preview_group = QGroupBox(tr("camera_mgmt.preview_group"))
        layout = QVBoxLayout(self._preview_group)

        # Image display
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(320, 240)
        c = ThemeManager.current()
        self._preview_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER}; color: {c.TEXT_SECONDARY};"
        )
        self._preview_label.setText(tr("camera_mgmt.preview_not_started"))
        layout.addWidget(self._preview_label, 1)

        # Info bar
        self._preview_info = QLabel("—")
        c = ThemeManager.current()
        self._preview_info.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self._preview_info)

        # Controls
        btn_row = QHBoxLayout()
        self._preview_start_btn = QPushButton(tr("camera.start_preview"))
        self._preview_start_btn.clicked.connect(self._on_start_preview)
        btn_row.addWidget(self._preview_start_btn)
        self._preview_stop_btn = QPushButton(tr("camera.stop_preview"))
        self._preview_stop_btn.setEnabled(False)
        self._preview_stop_btn.clicked.connect(self._on_stop_preview)
        btn_row.addWidget(self._preview_stop_btn)
        self._snapshot_btn = QPushButton(tr("camera.snapshot"))
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
        self._diag_group = QGroupBox(tr("camera_mgmt.diag_group"))
        layout = QVBoxLayout(self._diag_group)

        self._diag_text = QTextEdit()
        self._diag_text.setReadOnly(True)
        c = ThemeManager.current()
        self._diag_text.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
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
        QMessageBox.information(self, tr("camera_mgmt.dlg_save"), tr("camera_mgmt.saved"))
        logger.info("Bindings saved manually")

    # ------------------------------------------------------------------
    # Scan & Bind
    # ------------------------------------------------------------------

    def _on_scan(self) -> None:
        """Scan for Hikrobot cameras on the network."""
        sdk_ok = sdk_loader.load_sdk()
        if not sdk_ok:
            error = sdk_loader.SDK_ERROR or "unknown error"
            self._sdk_label.setText(tr("camera_mgmt.sdk_load_failed", error=error))
            c = ThemeManager.current()
            self._sdk_label.setStyleSheet(f"color: {c.ERROR};")
            self._refresh_device_choices()
            self._refresh_adapters()
            return
        self._sdk_label.setText(tr("commissioning.sdk_loaded"))
        c = ThemeManager.current()
        self._sdk_label.setStyleSheet(f"color: {c.SUCCESS};")

        try:
            self._discovered = HikrobotLineScanCamera.enumerate_devices()
        except Exception:
            self._discovered = []
            logger.exception("Device enumeration failed")

        self._refresh_device_choices()
        self._refresh_adapters()

        if not self._discovered:
            self._device_list.setPlainText(tr("camera_mgmt.no_devices_hint"))
        else:
            lines = []
            for d in self._discovered:
                lines.append(
                    f"SN: {d.serial_number}  Model: {d.model}  Vendor: {d.vendor}\n"
                    f"  IP: {d.ip_address}  MAC: {d.mac_address}"
                )
                if d.user_defined_name:
                    lines[-1] += f"  Name: {d.user_defined_name}"
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
            QMessageBox.warning(self, tr("app.tip"), tr("camera_mgmt.scan_first"))
            return

        slot = self._slot_combo.currentText()
        role = _ROLES[self._role_combo.currentIndex()]

        selected_idx = self._device_combo.currentIndex()
        if selected_idx < 0 or selected_idx >= len(self._discovered):
            QMessageBox.warning(self, tr("app.tip"), tr("camera_mgmt.select_camera"))
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
                self,
                tr("commissioning.connect_failed"),
                tr(
                    "camera_mgmt.connect_error_fmt",
                    sn=device_info.serial_number,
                    code=code,
                    msg=msg,
                ),
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
            QMessageBox.information(self, tr("app.tip"), tr("camera_mgmt.no_enabled_cameras"))
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
            QMessageBox.warning(self, tr("app.tip"), tr("camera_mgmt.no_connected_camera"))
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

        QMessageBox.information(
            self, tr("camera_mgmt.dlg_params"), tr("camera_mgmt.params_applied")
        )

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
        QMessageBox.information(
            self, tr("camera_mgmt.dlg_template"), tr("camera_mgmt.template_saved", path=path)
        )

    def _on_load_template(self) -> None:
        """Load parameters from a template."""
        templates = self._template_mgr.list_templates()
        if not templates:
            QMessageBox.information(
                self, tr("camera_mgmt.dlg_template"), tr("camera_mgmt.no_template")
            )
            return

        # Use the first template for the current slot, or the first overall
        slot = self._slot_combo.currentText()
        slot_suffix = f"Camera_{slot[-2:]}"
        matching = [t for t in templates if slot_suffix in t]
        name = matching[0] if matching else templates[0]

        params = self._template_mgr.load(name)
        if params is None:
            QMessageBox.warning(
                self, tr("app.error"), tr("camera_mgmt.template_load_error", name=name)
            )
            return

        self._apply_params_from(params)
        QMessageBox.information(
            self, tr("camera_mgmt.dlg_template"), tr("camera_mgmt.template_loaded", name=name)
        )

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
            QMessageBox.warning(self, tr("app.tip"), tr("camera_mgmt.connect_first"))
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
            QMessageBox.critical(
                self,
                tr("camera_mgmt.dlg_preview_failed"),
                tr("camera_mgmt.preview_failed", code=code, msg=msg),
            )
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
        self._preview_label.setText(tr("camera_mgmt.preview_stopped"))
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
        QMessageBox.information(
            self, tr("camera_mgmt.dlg_snapshot"), tr("camera_mgmt.snapshot_saved", fname=fname)
        )
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
            self._diag_text.setPlainText(tr("camera_mgmt.no_camera_diag"))
            return

        st = cam.get_status()
        w = cam.get_param("Width") or 2048
        h = cam.get_param("Height") or 1

        lines.append(tr("camera_mgmt.diag_slot") + f"         {slot}")
        lines.append(tr("camera_mgmt.diag_serial") + f"       {st.serial_number}")
        lines.append(
            tr("camera_mgmt.diag_conn_status")
            + "     "
            + (
                tr("camera_mgmt.diag_connected_yes")
                if st.connected
                else tr("camera_mgmt.diag_connected_no")
            )
        )
        lines.append(
            tr("camera_mgmt.diag_grab_status")
            + "     "
            + (
                tr("camera_mgmt.diag_grabbing_yes")
                if st.grabbing
                else tr("camera_mgmt.diag_grabbing_no")
            )
        )
        lines.append(tr("camera_mgmt.diag_line_rate") + f"         {st.line_rate:.0f} Hz")
        lines.append(tr("camera_mgmt.diag_received") + f"     {st.received_line_count}")
        lines.append(tr("camera_mgmt.diag_dropped") + f"       {st.dropped_line_count}")
        lines.append(tr("camera_mgmt.diag_timeout") + f"     {st.timeout_count}")
        lines.append(tr("camera_mgmt.diag_image_size") + f"     {w} × {h}")
        lines.append(
            tr("camera_mgmt.diag_pixel_format") + f"     {cam.get_param('PixelFormat') or 'Mono8'}"
        )
        lines.append(
            tr("camera_mgmt.diag_exposure") + f"     {cam.get_param('ExposureTime') or 0:.1f} us"
        )
        lines.append(tr("camera_mgmt.diag_gain") + f"         {cam.get_param('Gain') or 0:.1f} dB")
        err_code = st.last_error_code
        if err_code != 0:
            lines.append(
                tr("camera_mgmt.diag_last_error") + f"     0x{err_code:08X} {st.last_error_message}"
            )
        else:
            lines.append(tr("camera_mgmt.diag_last_error") + "     —")

        self._diag_text.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._refresh_adapters()
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
        # Adapter table headers
        self._adapter_group.setTitle(tr("camera_mgmt.adapter_group"))
        self._adapter_table.setHorizontalHeaderLabels(
            [
                tr("device.col_adapter"),
                tr("device.col_type"),
                tr("device.col_status"),
                tr("device.col_devices"),
            ]
        )
        self._refresh_adapters()
        # Group boxes
        self._discovery_group.setTitle(tr("camera_mgmt.discovery_group"))
        self._param_group.setTitle(tr("camera_mgmt.param_group"))
        self._preview_group.setTitle(tr("camera_mgmt.preview_group"))
        self._diag_group.setTitle(tr("camera_mgmt.diag_group"))
        # Buttons
        self._scan_btn.setText(tr("camera.scan"))
        self._bind_btn.setText(tr("camera.bind_connect"))
        self._unbind_btn.setText(tr("camera.unbind"))
        self._connect_all_btn.setText(tr("camera.connect_all"))
        self._disconnect_all_btn.setText(tr("camera.disconnect_all"))
        self._save_binding_btn.setText(tr("camera.save_binding"))
        self._apply_btn.setText(tr("camera.apply_params"))
        self._save_tpl_btn.setText(tr("camera.save_template"))
        self._load_tpl_btn.setText(tr("camera.load_template"))
        self._reset_params_btn.setText(tr("camera.reset_params"))
        self._preview_start_btn.setText(tr("camera.start_preview"))
        self._preview_stop_btn.setText(tr("camera.stop_preview"))
        self._snapshot_btn.setText(tr("camera.snapshot"))
        # Role combo
        self._role_combo.setItemText(0, tr("camera_mgmt.role_top"))
        self._role_combo.setItemText(1, tr("camera_mgmt.role_left"))
        self._role_combo.setItemText(2, tr("camera_mgmt.role_right"))
        self._role_combo.setItemText(3, tr("camera_mgmt.role_spare"))
        # Checkboxes
        self._reverse_x_cb.setText(tr("camera_mgmt.reverse_x"))
        self._reverse_y_cb.setText(tr("camera_mgmt.reverse_y"))
        # Refresh status
        self._refresh_slot_status()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._device_list.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
        )
        self._preview_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER}; color: {c.TEXT_SECONDARY};"
        )
        self._preview_info.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        self._diag_text.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
        )
        self._refresh_slot_status()

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
        return [slot for slot, dev in self._cameras.items() if dev.get_status().connected]
