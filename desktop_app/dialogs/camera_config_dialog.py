"""Dialog for editing a single camera configuration."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit, QLineEdit,
    QGroupBox, QHBoxLayout, QLabel, QMessageBox,
)

from camera_adapters import available_adapter_types
from core.camera_config import CameraConfig
from desktop_app.i18n import tr, bind, I18nManager


class CameraConfigDialog(QDialog):
    """Modal dialog for configuring a single camera's parameters."""

    def __init__(self, camera_index: int, existing: CameraConfig | None = None, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index
        self._existing = existing
        self._result_cfg: CameraConfig | None = None
        self._build_ui()
        if existing:
            self._load_existing(existing)
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        bind(self, "camera.dialog_title", setter="setWindowTitle", i=self._camera_index)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        # --- Basic settings ---
        basic_grp = QGroupBox()
        bind(basic_grp, "camera.basic_settings", setter="setTitle")
        basic_form = QFormLayout(basic_grp)

        self._adapter_combo = QComboBox()
        self._adapter_combo.addItems(available_adapter_types())
        adapter_label = QLabel()
        bind(adapter_label, "camera.adapter_type")
        basic_form.addRow(adapter_label, self._adapter_combo)

        self._enabled_cb = QCheckBox()
        self._enabled_cb.setChecked(True)
        enabled_label = QLabel()
        bind(enabled_label, "camera.enabled")
        basic_form.addRow(enabled_label, self._enabled_cb)

        self._camera_id_edit = QLineEdit(f"CAM_{self._camera_index:02d}")
        basic_form.addRow(QLabel("Camera ID"), self._camera_id_edit)

        self._camera_name_edit = QLineEdit()
        basic_form.addRow(QLabel("Camera name"), self._camera_name_edit)

        self._camera_type_edit = QLineEdit()
        self._camera_type_edit.setPlaceholderText("line_scan / area_scan")
        basic_form.addRow(QLabel("Camera type"), self._camera_type_edit)

        self._brand_edit = QLineEdit()
        basic_form.addRow(QLabel("Brand"), self._brand_edit)

        self._serial_edit = QLineEdit()
        basic_form.addRow(QLabel("Serial number"), self._serial_edit)

        self._ip_edit = QLineEdit()
        basic_form.addRow(QLabel("IP address"), self._ip_edit)

        self._position_edit = QLineEdit()
        basic_form.addRow(QLabel("Position"), self._position_edit)

        self._save_ng_cb = QCheckBox()
        self._save_ng_cb.setChecked(True)
        basic_form.addRow(QLabel("Save NG image"), self._save_ng_cb)

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["continuous", "external", "software", "On", "Off"])
        trigger_label = QLabel()
        bind(trigger_label, "camera.trigger_mode")
        basic_form.addRow(trigger_label, self._trigger_combo)

        layout.addWidget(basic_grp)

        # --- Image acquisition ---
        img_grp = QGroupBox()
        bind(img_grp, "camera.image_acq", setter="setTitle")
        img_form = QFormLayout(img_grp)

        self._exposure_spin = QDoubleSpinBox()
        self._exposure_spin.setRange(1, 500_000)
        self._exposure_spin.setValue(5000)
        self._exposure_spin.setSuffix(" us")
        self._exposure_spin.setDecimals(0)
        exposure_label = QLabel()
        bind(exposure_label, "camera.exposure_us")
        img_form.addRow(exposure_label, self._exposure_spin)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0, 48)
        self._gain_spin.setValue(0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        gain_label = QLabel()
        bind(gain_label, "camera.gain_db")
        img_form.addRow(gain_label, self._gain_spin)

        self._res_w_spin = QSpinBox()
        self._res_w_spin.setRange(0, 65536)
        self._res_w_spin.setValue(4096)
        img_form.addRow(QLabel("Resolution width"), self._res_w_spin)

        self._res_h_spin = QSpinBox()
        self._res_h_spin.setRange(0, 65536)
        self._res_h_spin.setValue(1)
        img_form.addRow(QLabel("Resolution height"), self._res_h_spin)

        self._pixel_size_spin = QDoubleSpinBox()
        self._pixel_size_spin.setRange(0, 1000)
        self._pixel_size_spin.setDecimals(3)
        self._pixel_size_spin.setSuffix(" um")
        img_form.addRow(QLabel("Pixel size"), self._pixel_size_spin)

        self._line_rate_spin = QSpinBox()
        self._line_rate_spin.setRange(0, 500000)
        self._line_rate_spin.setValue(20000)
        self._line_rate_spin.setSuffix(" Hz")
        img_form.addRow(QLabel("LineRate"), self._line_rate_spin)

        self._block_height_spin = QSpinBox()
        self._block_height_spin.setRange(1, 65536)
        self._block_height_spin.setValue(1024)
        img_form.addRow(QLabel("Image block height"), self._block_height_spin)

        self._pixel_format_combo = QComboBox()
        self._pixel_format_combo.addItems(["Mono8", "Mono12", "BayerRG8", "BayerGB8"])
        img_form.addRow(QLabel("PixelFormat"), self._pixel_format_combo)

        self._trigger_source_combo = QComboBox()
        self._trigger_source_combo.addItems(["Line0", "Line1", "Line2", "Line3", "Software"])
        img_form.addRow(QLabel("TriggerSource"), self._trigger_source_combo)

        # ROI
        roi_widget = QWidget()
        roi_layout = QHBoxLayout(roi_widget)
        roi_layout.setContentsMargins(0, 0, 0, 0)
        roi_layout.setSpacing(4)
        self._roi_x = QSpinBox(); self._roi_x.setRange(0, 8192); self._roi_x.setSuffix(" x")
        self._roi_y = QSpinBox(); self._roi_y.setRange(0, 8192); self._roi_y.setSuffix(" y")
        self._roi_w = QSpinBox(); self._roi_w.setRange(0, 8192); self._roi_w.setPrefix("w:")
        self._roi_h = QSpinBox(); self._roi_h.setRange(0, 8192); self._roi_h.setPrefix("h:")
        roi_layout.addWidget(QLabel("x:")); roi_layout.addWidget(self._roi_x)
        roi_layout.addWidget(QLabel("y:")); roi_layout.addWidget(self._roi_y)
        roi_layout.addWidget(self._roi_w); roi_layout.addWidget(self._roi_h)
        roi_label = QLabel()
        bind(roi_label, "camera.roi")
        img_form.addRow(roi_label, roi_widget)

        layout.addWidget(img_grp)

        # --- Connection params ---
        conn_grp = QGroupBox()
        bind(conn_grp, "camera.connection_params", setter="setTitle")
        conn_layout = QVBoxLayout(conn_grp)
        self._conn_edit = QTextEdit()
        self._conn_edit.setPlaceholderText('{"watch_dir": "/path/to/images"}')
        self._conn_edit.setMaximumHeight(80)
        conn_layout.addWidget(self._conn_edit)
        layout.addWidget(conn_grp)

        # --- Model binding ---
        bind_grp = QGroupBox()
        bind(bind_grp, "camera.model_binding", setter="setTitle")
        bind_layout = QVBoxLayout(bind_grp)
        self._model_binding_edit = QLineEdit()
        self._model_binding_edit.setPlaceholderText(tr("camera.model_binding_placeholder"))
        bind_layout.addWidget(self._model_binding_edit)
        layout.addWidget(bind_grp)

        # --- Notes ---
        self._notes_edit = QLineEdit()
        notes_label = QLabel()
        bind(notes_label, "camera.notes")
        notes_row = QHBoxLayout()
        notes_row.addWidget(notes_label)
        notes_row.addWidget(self._notes_edit)
        layout.addLayout(notes_row)

        # --- Buttons ---
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_existing(self, cfg: CameraConfig) -> None:
        """Populate UI from an existing CameraConfig."""
        idx = self._adapter_combo.findText(cfg.adapter_type)
        if idx >= 0:
            self._adapter_combo.setCurrentIndex(idx)
        self._enabled_cb.setChecked(cfg.enabled)
        idx2 = self._trigger_combo.findText(cfg.trigger_mode)
        if idx2 >= 0:
            self._trigger_combo.setCurrentIndex(idx2)
        if cfg.exposure_us is not None:
            self._exposure_spin.setValue(cfg.exposure_us)
        if cfg.gain_db is not None:
            self._gain_spin.setValue(cfg.gain_db)
        self._camera_id_edit.setText(cfg.camera_id)
        self._camera_name_edit.setText(cfg.camera_name)
        self._camera_type_edit.setText(cfg.camera_type)
        self._brand_edit.setText(cfg.brand)
        self._serial_edit.setText(cfg.serial_number)
        self._ip_edit.setText(cfg.ip_address)
        self._position_edit.setText(cfg.position_desc)
        self._save_ng_cb.setChecked(cfg.save_ng_image)
        if cfg.resolution_width is not None:
            self._res_w_spin.setValue(cfg.resolution_width)
        if cfg.resolution_height is not None:
            self._res_h_spin.setValue(cfg.resolution_height)
        if cfg.pixel_size_um is not None:
            self._pixel_size_spin.setValue(cfg.pixel_size_um)
        if cfg.line_rate is not None:
            self._line_rate_spin.setValue(cfg.line_rate)
        if cfg.image_block_height is not None:
            self._block_height_spin.setValue(cfg.image_block_height)
        idx3 = self._pixel_format_combo.findText(cfg.pixel_format)
        if idx3 >= 0:
            self._pixel_format_combo.setCurrentIndex(idx3)
        try:
            roi = json.loads(cfg.roi) if cfg.roi else {}
            self._roi_x.setValue(roi.get("x", 0))
            self._roi_y.setValue(roi.get("y", 0))
            self._roi_w.setValue(roi.get("w", 0))
            self._roi_h.setValue(roi.get("h", 0))
            trigger_source = roi.get("trigger_source", "")
            idx4 = self._trigger_source_combo.findText(trigger_source)
            if idx4 >= 0:
                self._trigger_source_combo.setCurrentIndex(idx4)
        except (json.JSONDecodeError, TypeError):
            pass
        self._conn_edit.setPlainText(cfg.connection_params if cfg.connection_params != "{}" else "")
        self._model_binding_edit.setText(cfg.model_binding)
        self._notes_edit.setText(cfg.notes)

    def _on_accept(self) -> None:
        """Validate and build result CameraConfig."""
        conn_text = self._conn_edit.toPlainText().strip()
        if conn_text:
            try:
                json.loads(conn_text)
            except json.JSONDecodeError:
                QMessageBox.warning(self, tr("app.error"), tr("camera.invalid_connection_json"))
                return
        roi = json.dumps({
            "x": self._roi_x.value(),
            "y": self._roi_y.value(),
            "w": self._roi_w.value(),
            "h": self._roi_h.value(),
            "trigger_source": self._trigger_source_combo.currentText(),
        })
        self._result_cfg = CameraConfig(
            config_id=self._existing.config_id if self._existing else "",
            spec_id=self._existing.spec_id if self._existing else "",
            camera_index=self._camera_index,
            camera_id=self._camera_id_edit.text().strip() or f"CAM_{self._camera_index:02d}",
            camera_name=self._camera_name_edit.text().strip(),
            camera_type=self._camera_type_edit.text().strip(),
            brand=self._brand_edit.text().strip(),
            serial_number=self._serial_edit.text().strip(),
            ip_address=self._ip_edit.text().strip(),
            adapter_type=self._adapter_combo.currentText(),
            connection_params=conn_text or "{}",
            enabled=self._enabled_cb.isChecked(),
            trigger_mode=self._trigger_combo.currentText(),
            exposure_us=self._exposure_spin.value() if self._exposure_spin.value() > 0 else None,
            gain_db=self._gain_spin.value() if self._gain_spin.value() > 0 else None,
            resolution_width=self._res_w_spin.value() or None,
            resolution_height=self._res_h_spin.value() or None,
            pixel_size_um=self._pixel_size_spin.value() or None,
            line_rate=self._line_rate_spin.value() or None,
            image_block_height=self._block_height_spin.value(),
            pixel_format=self._pixel_format_combo.currentText(),
            position_desc=self._position_edit.text().strip(),
            save_ng_image=self._save_ng_cb.isChecked(),
            roi=roi,
            model_binding=self._model_binding_edit.text().strip(),
            notes=self._notes_edit.text().strip(),
        )
        self.accept()

    def get_result(self) -> CameraConfig:
        """Return the configured CameraConfig after dialog is accepted."""
        return self._result_cfg

    def _refresh_text(self, lang: str = "") -> None:
        self._adapter_combo.clear()
        self._adapter_combo.addItems(available_adapter_types())
