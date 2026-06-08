"""Camera slot config dialog — scan/bind device + edit parameters per slot."""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QFrame,
    QWidget,
)

from src.device.camera.binding_store import BindingStore, CameraBinding
from src.device.camera.hikrobot import sdk_loader
from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import DeviceInfo
from core.camera_config import (
    CameraConfig,
    create_camera_config,
    update_camera_config,
)
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class CameraSlotConfigDialog(QDialog):
    """Modal dialog: scan/bind device + edit camera parameters for a single slot."""

    def __init__(
        self,
        slot_index: int,
        slot_name: str = "",
        role: str = "",
        *,
        binding_store: BindingStore | None = None,
        cameras: dict[str, LineScanDevice] | None = None,
        existing_config: CameraConfig | None = None,
        spec_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slot_index = slot_index
        self._slot_name = slot_name
        self._role = role
        self._binding_store = binding_store or BindingStore()
        self._cameras: dict[str, LineScanDevice] = cameras or {}
        self._existing_cfg = existing_config
        self._spec_id = spec_id or ""
        self._discovered: list[DeviceInfo] = []
        self._selected_device: DeviceInfo | None = None

        self.setWindowTitle(tr("camera_workbench.slot_config_title", name=slot_name))
        self.setMinimumSize(600, 720)
        self.setModal(True)

        self._build_ui()
        self._load_existing_params()
        self._refresh_adapter_status()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # ── Binding info header ──
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(4)

        self._info_label = QLabel(
            tr("camera_workbench.slot_info", name=self._slot_name, role=self._role)
        )
        font = self._info_label.font()
        font.setBold(True)
        font.setPointSize(12)
        self._info_label.setFont(font)
        info_layout.addWidget(self._info_label)

        binding = self._binding_store.get_binding(self._slot_name)
        if binding and binding.serial_number:
            self._bound_sn_label = QLabel(
                tr("camera_workbench.bound_device", sn=binding.serial_number, model=binding.model or "")
            )
        else:
            self._bound_sn_label = QLabel(tr("camera_workbench.status_empty"))
        self._bound_sn_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        info_layout.addWidget(self._bound_sn_label)
        outer.addWidget(info_frame)

        # ── Adapter status ──
        adapter_group = QGroupBox(tr("device.registered_adapters"))
        adapter_layout = QVBoxLayout(adapter_group)
        self._adapter_labels: dict[str, QLabel] = {}
        for key, label_key, default_desc in [
            ("folder_watcher", "camera.folder_watcher", "device.ready"),
            ("hikrobot_line_scan", "camera.hikvision_stub", "device.sdk_missing"),
            ("basler_pylon", "camera.basler_stub", "device.sdk_missing"),
        ]:
            row = QHBoxLayout()
            name_label = QLabel(tr(label_key))
            name_label.setMinimumWidth(160)
            row.addWidget(name_label)
            status_label = QLabel(tr(default_desc))
            self._adapter_labels[key] = status_label
            row.addWidget(status_label)
            row.addStretch()
            adapter_layout.addLayout(row)
        outer.addWidget(adapter_group)

        # ── Scan + device list ──
        self._scan_btn = QPushButton("🔍 " + tr("camera_workbench.scan_devices"))
        self._scan_btn.clicked.connect(self._on_scan)
        outer.addWidget(self._scan_btn)

        self._device_list_label = QLabel(tr("camera.scan"))
        outer.addWidget(self._device_list_label)

        self._device_list = QListWidget()
        self._device_list.setMinimumHeight(80)
        self._device_list.setMaximumHeight(120)
        self._device_list.currentRowChanged.connect(self._on_device_selected)
        outer.addWidget(self._device_list)

        # ── Confirm bind button ──
        self._bind_btn = QPushButton(tr("camera_workbench.confirm_bind"))
        self._bind_btn.setEnabled(False)
        c = ThemeManager.current()
        self._bind_btn.setStyleSheet(
            f"background: {c.PRIMARY}; color: #fff; font-weight: bold; padding: 4px 12px; border-radius: 4px;"
        )
        self._bind_btn.clicked.connect(self._on_confirm_bind)
        outer.addWidget(self._bind_btn)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep)

        # ── Parameter editing form ──
        param_group = QGroupBox(tr("camera_workbench.camera_params"))
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        # Row 0
        grid.addWidget(QLabel(tr("camera_workbench.exposure_label")), 0, 0)
        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1.0, 1000000.0)
        self._exposure_spin.setValue(5000.0)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.setDecimals(1)
        grid.addWidget(self._exposure_spin, 1, 0)

        grid.addWidget(QLabel(tr("camera_workbench.gain_label")), 0, 1)
        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.0, 40.0)
        self._gain_spin.setValue(1.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        grid.addWidget(self._gain_spin, 1, 1)

        grid.addWidget(QLabel(tr("camera_workbench.trigger_mode_label")), 0, 2)
        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["Off", "On"])
        grid.addWidget(self._trigger_combo, 1, 2)

        # Row 1
        grid.addWidget(QLabel(tr("camera_workbench.trigger_src_label")), 2, 0)
        self._trigger_src_combo = QComboBox()
        self._trigger_src_combo.addItems(["Line0", "Line1", "Line2", "Line3", "Software"])
        grid.addWidget(self._trigger_src_combo, 3, 0)

        grid.addWidget(QLabel(tr("camera_workbench.line_rate_label")), 2, 1)
        self._line_rate_spin = QSpinBox()
        self._line_rate_spin.setRange(100, 200000)
        self._line_rate_spin.setValue(20000)
        self._line_rate_spin.setSuffix(" Hz")
        grid.addWidget(self._line_rate_spin, 3, 1)

        grid.addWidget(QLabel(tr("camera_workbench.block_height_label")), 2, 2)
        self._block_h_spin = QSpinBox()
        self._block_h_spin.setRange(64, 8192)
        self._block_h_spin.setValue(1024)
        grid.addWidget(self._block_h_spin, 3, 2)

        # Row 2
        grid.addWidget(QLabel(tr("camera_workbench.pixel_format_label")), 4, 0)
        self._pixel_fmt_combo = QComboBox()
        self._pixel_fmt_combo.addItems(["Mono8", "Mono10", "Mono12", "BayerRG8", "RGB8"])
        grid.addWidget(self._pixel_fmt_combo, 5, 0)

        grid.addWidget(QLabel(tr("camera_workbench.width_label")), 4, 1)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(256, 8192)
        self._width_spin.setValue(2048)
        grid.addWidget(self._width_spin, 5, 1)

        grid.addWidget(QLabel(tr("camera_workbench.packet_size_label")), 4, 2)
        self._pkt_size_spin = QSpinBox()
        self._pkt_size_spin.setRange(1500, 65535)
        self._pkt_size_spin.setValue(9000)
        grid.addWidget(self._pkt_size_spin, 5, 2)

        # Row 3
        grid.addWidget(QLabel(tr("camera_workbench.inter_delay_label")), 6, 0)
        self._inter_delay_spin = QSpinBox()
        self._inter_delay_spin.setRange(0, 10000)
        self._inter_delay_spin.setValue(0)
        self._inter_delay_spin.setSuffix(" us")
        grid.addWidget(self._inter_delay_spin, 7, 0)

        grid.addWidget(QLabel(tr("camera_workbench.buffer_label")), 6, 1)
        self._buffer_spin = QSpinBox()
        self._buffer_spin.setRange(1, 256)
        self._buffer_spin.setValue(16)
        grid.addWidget(self._buffer_spin, 7, 1)

        rev_layout = QHBoxLayout()
        self._reverse_x_cb = QCheckBox(tr("camera_mgmt.reverse_x"))
        self._reverse_y_cb = QCheckBox(tr("camera_mgmt.reverse_y"))
        rev_layout.addWidget(self._reverse_x_cb)
        rev_layout.addWidget(self._reverse_y_cb)
        rev_layout.addStretch()
        grid.addLayout(rev_layout, 7, 2)

        param_layout.addLayout(grid)
        outer.addWidget(param_group)

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._apply_btn = QPushButton(tr("camera_workbench.apply_to_camera"))
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        self._save_btn = QPushButton(tr("camera_workbench.save_to_spec"))
        self._save_btn.setStyleSheet(
            f"background: {c.SUCCESS}; color: #fff; font-weight: bold; "
            f"padding: 5px 14px; border-radius: 4px; border: none;"
        )
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        btn_row.addStretch()

        self._close_btn = QPushButton(tr("app.close"))
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        outer.addLayout(btn_row)

    # ── Load existing config into form ─────────────────────────────────

    def _load_existing_params(self) -> None:
        cfg = self._existing_cfg
        if cfg is None:
            return
        if cfg.exposure_us is not None:
            self._exposure_spin.setValue(cfg.exposure_us)
        if cfg.gain_db is not None:
            self._gain_spin.setValue(cfg.gain_db)
        if cfg.trigger_mode:
            idx = self._trigger_combo.findText(cfg.trigger_mode)
            if idx >= 0:
                self._trigger_combo.setCurrentIndex(idx)
        if cfg.line_rate is not None:
            self._line_rate_spin.setValue(cfg.line_rate)
        if cfg.image_block_height is not None:
            self._block_h_spin.setValue(cfg.image_block_height)
        if cfg.pixel_format:
            idx = self._pixel_fmt_combo.findText(cfg.pixel_format)
            if idx >= 0:
                self._pixel_fmt_combo.setCurrentIndex(idx)
        if cfg.resolution_width is not None:
            self._width_spin.setValue(cfg.resolution_width)

        # Load extended params from connection_params JSON
        try:
            ext = json.loads(cfg.connection_params) if cfg.connection_params else {}
        except (json.JSONDecodeError, TypeError):
            ext = {}
        if isinstance(ext, dict):
            trigger_src = ext.get("trigger_source", "Line0")
            idx = self._trigger_src_combo.findText(trigger_src)
            if idx >= 0:
                self._trigger_src_combo.setCurrentIndex(idx)
            self._pkt_size_spin.setValue(int(ext.get("packet_size", 9000)))
            self._inter_delay_spin.setValue(int(ext.get("inter_packet_delay", 0)))
            self._buffer_spin.setValue(int(ext.get("buffer_count", 16)))
            self._reverse_x_cb.setChecked(bool(ext.get("reverse_x", False)))
            self._reverse_y_cb.setChecked(bool(ext.get("reverse_y", False)))

    # ── Adapter status ─────────────────────────────────────────────────

    def _refresh_adapter_status(self) -> None:
        c = ThemeManager.current()
        self._adapter_labels["folder_watcher"].setText(tr("device.ready", count=0))
        self._adapter_labels["folder_watcher"].setStyleSheet(f"color: {c.SUCCESS};")
        if sdk_loader.load_sdk():
            self._adapter_labels["hikrobot_line_scan"].setText("SDK loaded")
            self._adapter_labels["hikrobot_line_scan"].setStyleSheet(f"color: {c.SUCCESS};")
        else:
            self._adapter_labels["hikrobot_line_scan"].setText(tr("device.sdk_missing"))
            self._adapter_labels["hikrobot_line_scan"].setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        try:
            from camera_adapters.basler_pylon import BaslerPylonAdapter
            b = BaslerPylonAdapter()
            devs = b.list_devices()
            if devs:
                self._adapter_labels["basler_pylon"].setText(tr("device.ready", count=len(devs)))
                self._adapter_labels["basler_pylon"].setStyleSheet(f"color: {c.SUCCESS};")
            else:
                self._adapter_labels["basler_pylon"].setText(tr("device.no_devices"))
                self._adapter_labels["basler_pylon"].setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        except Exception:
            self._adapter_labels["basler_pylon"].setText(tr("device.sdk_missing"))
            self._adapter_labels["basler_pylon"].setStyleSheet(f"color: {c.TEXT_SECONDARY};")

    # ── Scan ───────────────────────────────────────────────────────────

    def _on_scan(self) -> None:
        sdk_ok = sdk_loader.load_sdk()
        self._refresh_adapter_status()
        if not sdk_ok:
            self._device_list_label.setText(
                tr("camera_mgmt.sdk_load_failed", error=sdk_loader.SDK_ERROR or "unknown")
            )
            return
        self._device_list_label.setText(tr("commissioning.sdk_loaded"))
        try:
            self._discovered = HikrobotLineScanCamera.enumerate_devices()
        except Exception:
            self._discovered = []
            logger.exception("Device enumeration failed in slot config dialog")
        self._refresh_device_list()

    def _refresh_device_list(self) -> None:
        self._device_list.clear()
        self._selected_device = None
        self._bind_btn.setEnabled(False)
        if not self._discovered:
            self._device_list_label.setText(tr("camera_mgmt.no_devices_hint"))
            return
        self._device_list_label.setText(
            tr("camera_workbench.found_devices", n=len(self._discovered))
        )
        for d in self._discovered:
            text = f"{d.serial_number or '(no SN)'} — {d.model or ''} — {d.ip_address or ''}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, d.serial_number)
            self._device_list.addItem(item)

    def _on_device_selected(self, row: int) -> None:
        if 0 <= row < len(self._discovered):
            self._selected_device = self._discovered[row]
            self._bind_btn.setEnabled(True)
        else:
            self._selected_device = None
            self._bind_btn.setEnabled(False)

    def _on_confirm_bind(self) -> None:
        if self._selected_device is None:
            return
        binding = CameraBinding(
            camera_slot=self._slot_name,
            enabled=True,
            role=self._role,
            serial_number=self._selected_device.serial_number or "",
            mac_address=self._selected_device.mac_address or "",
            ip_address=self._selected_device.ip_address or "",
            model=self._selected_device.model or "",
            param_profile=f"{self._slot_name}_params.json",
        )
        self._binding_store.set_binding(binding)
        self._binding_store.save_all()
        self._bound_sn_label.setText(
            tr("camera_workbench.bound_device",
               sn=binding.serial_number, model=binding.model or "")
        )
        self._bind_btn.setEnabled(False)
        QMessageBox.information(self, tr("app.tip"), tr("camera_workbench.device_bound"))

    # ── Apply params to connected camera ───────────────────────────────

    def _on_apply(self) -> None:
        cam = self._cameras.get(self._slot_name)
        if cam is None:
            QMessageBox.warning(self, tr("app.tip"), tr("camera_mgmt.no_connected_camera"))
            return
        params: list[tuple[str, Any]] = [
            ("ExposureTime", self._exposure_spin.value()),
            ("Gain", self._gain_spin.value()),
            ("TriggerMode", self._trigger_combo.currentText()),
            ("TriggerSource", self._trigger_src_combo.currentText()),
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
                logger.debug("Set %s = %s on %s", name, value, self._slot_name)
            except Exception as e:
                logger.warning("Failed to set %s: %s", name, e)
        QMessageBox.information(self, tr("camera_mgmt.dlg_params"), tr("camera_mgmt.params_applied"))

    # ── Save to spec ──────────────────────────────────────────────────

    def _on_save(self) -> None:
        if not self._spec_id:
            QMessageBox.warning(self, tr("app.tip"), tr("camera_workbench.empty_spec"))
            return

        binding = self._binding_store.get_binding(self._slot_name)

        # Build extended params for connection_params
        extended: dict[str, Any] = {
            "trigger_source": self._trigger_src_combo.currentText(),
            "packet_size": self._pkt_size_spin.value(),
            "inter_packet_delay": self._inter_delay_spin.value(),
            "buffer_count": self._buffer_spin.value(),
            "reverse_x": self._reverse_x_cb.isChecked(),
            "reverse_y": self._reverse_y_cb.isChecked(),
            "acquisition_mode": "Continuous",
        }

        fields: dict[str, Any] = {
            "adapter_type": "hikrobot_line_scan",
            "enabled": True,
            "trigger_mode": self._trigger_combo.currentText(),
            "exposure_us": self._exposure_spin.value(),
            "gain_db": self._gain_spin.value(),
            "line_rate": self._line_rate_spin.value(),
            "image_block_height": self._block_h_spin.value(),
            "pixel_format": self._pixel_fmt_combo.currentText(),
            "resolution_width": self._width_spin.value(),
            "position_desc": self._role,
            "connection_params": json.dumps(extended, ensure_ascii=False),
        }
        if binding:
            fields["serial_number"] = binding.serial_number
            fields["ip_address"] = binding.ip_address
            fields["brand"] = "Hikrobot"

        if self._existing_cfg is not None:
            update_camera_config(self._existing_cfg.config_id, **fields)
        else:
            self._existing_cfg = create_camera_config(
                self._spec_id, camera_index=self._slot_index, **fields
            )

        QMessageBox.information(self, tr("app.tip"), tr("camera_workbench.config_saved_to_spec"))

    def get_selected_device(self) -> DeviceInfo | None:
        """Return the device the user selected, or None if cancelled."""
        return self._selected_device

    # ── Theme / i18n ───────────────────────────────────────────────────

    def _on_theme_changed(self) -> None:
        c = ThemeManager.current()
        self._bound_sn_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._bind_btn.setStyleSheet(
            f"background: {c.PRIMARY}; color: #fff; font-weight: bold; padding: 4px 12px; border-radius: 4px;"
        )
        self._save_btn.setStyleSheet(
            f"background: {c.SUCCESS}; color: #fff; font-weight: bold; "
            f"padding: 5px 14px; border-radius: 4px; border: none;"
        )
        self._refresh_adapter_status()

    def _refresh_text(self, lang: str | None = None) -> None:
        _ = lang
        self.setWindowTitle(tr("camera_workbench.slot_config_title", name=self._slot_name))
        self._scan_btn.setText("🔍 " + tr("camera_workbench.scan_devices"))
        self._bind_btn.setText(tr("camera_workbench.confirm_bind"))
        self._apply_btn.setText(tr("camera_workbench.apply_to_camera"))
        self._save_btn.setText(tr("camera_workbench.save_to_spec"))
        self._close_btn.setText(tr("app.close"))
