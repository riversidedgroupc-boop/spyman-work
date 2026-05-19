"""Camera configuration page — dynamic N-camera UI driven by spec.camera_count."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, QMessageBox, QScrollArea, QFrame,
)

from core.camera_config import (
    CameraConfig, list_camera_configs, create_camera_config,
    update_camera_config, delete_camera_configs_for_spec,
)
from core.product_spec import get_product_spec
from desktop_app.app_context import AppContext
from desktop_app.dialogs.camera_config_dialog import CameraConfigDialog
from desktop_app.i18n import tr, bind, I18nManager


class CameraConfigPage(QWidget):
    """Shows a config card per camera (spec.camera_count)."""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._cards: dict[int, dict] = {}  # camera_index -> widget refs
        self._configs: dict[int, CameraConfig] = {}  # camera_index -> saved config
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        outer = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        self._title_label = QLabel()
        bind(self._title_label, "nav.camera_config")
        self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(self._title_label)
        header.addStretch()

        self._save_all_btn = QPushButton()
        bind(self._save_all_btn, "app.save_all")
        self._save_all_btn.setObjectName("primaryBtn")
        self._save_all_btn.clicked.connect(self._save_all)
        header.addWidget(self._save_all_btn)
        outer.addLayout(header)

        # Scrollable grid of camera cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        # Placeholder when no spec selected
        self._placeholder = QLabel()
        bind(self._placeholder, "app.select_spec_first")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 14px;")
        outer.addWidget(self._placeholder)

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild_cards()

    def _rebuild_cards(self):
        """Clear and rebuild cards based on current spec's camera_count."""
        spec = self._current_spec()
        if spec is None:
            self._placeholder.setVisible(True)
            for i in range(self._grid.count()):
                w = self._grid.itemAt(i)
                if w and w.widget():
                    w.widget().setVisible(False)
            return

        self._placeholder.setVisible(False)
        camera_count = spec.camera_count

        # Load existing configs from DB
        self._configs.clear()
        for cfg in list_camera_configs(spec.spec_id):
            self._configs[cfg.camera_index] = cfg

        # Clear old cards
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards.clear()

        # Build cards: up to 6 cameras, but only spec.camera_count are enabled
        cols = min(camera_count, 3)  # 1-3 columns
        for idx in range(1, camera_count + 1):
            card = self._build_card(idx)
            row = (idx - 1) // cols
            col = (idx - 1) % cols
            self._grid.addWidget(card, row, col)

    def _build_card(self, camera_index: int) -> QGroupBox:
        """Build one camera config card."""
        cfg = self._configs.get(camera_index)
        grp = QGroupBox()
        bind(grp, "camera.group", setter="setTitle", i=camera_index)

        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        # Status line
        status_row = QHBoxLayout()
        self._cards.setdefault(camera_index, {})
        self._cards[camera_index]["group"] = grp

        enabled_cb = QCheckBox()
        bind(enabled_cb, "camera.enabled")
        enabled_cb.setChecked(cfg.enabled if cfg else True)
        self._cards[camera_index]["enabled_cb"] = enabled_cb
        status_row.addWidget(enabled_cb)

        adapter_lbl = QLabel()
        if cfg:
            adapter_lbl.setText(f"{tr('camera.adapter_type')}: {cfg.adapter_type}")
        else:
            adapter_lbl.setText(f"{tr('camera.adapter_type')}: —")
        adapter_lbl.setStyleSheet("color: #888;")
        self._cards[camera_index]["adapter_lbl"] = adapter_lbl
        status_row.addWidget(adapter_lbl)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Details
        details = QLabel()
        details.setWordWrap(True)
        if cfg:
            lines = []
            if cfg.trigger_mode:
                lines.append(f"Trigger: {cfg.trigger_mode}")
            if cfg.exposure_us:
                lines.append(f"Exposure: {cfg.exposure_us:.0f} us")
            if cfg.gain_db:
                lines.append(f"Gain: {cfg.gain_db:.1f} dB")
            if cfg.model_binding:
                lines.append(f"Model: {cfg.model_binding}")
            details.setText("\n".join(lines) if lines else tr("camera.not_configured"))
        else:
            details.setText(tr("camera.not_configured"))
        details.setStyleSheet("color: #aaa; font-size: 12px;")
        self._cards[camera_index]["details"] = details
        layout.addWidget(details)

        # Configure button
        btn_row = QHBoxLayout()
        config_btn = QPushButton()
        bind(config_btn, "camera.configure")
        config_btn.clicked.connect(lambda checked, i=camera_index: self._open_dialog(i))
        btn_row.addWidget(config_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return grp

    def _open_dialog(self, camera_index: int):
        """Open CameraConfigDialog for the given camera index."""
        spec = self._current_spec()
        if spec is None:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_spec_first"))
            return

        existing = self._configs.get(camera_index)
        dlg = CameraConfigDialog(camera_index, existing, self)
        if dlg.exec() == CameraConfigDialog.DialogCode.Accepted:
            new_cfg = dlg.get_result()
            if existing:
                # Update existing
                update_camera_config(
                    existing.config_id,
                    camera_id=new_cfg.camera_id,
                    camera_name=new_cfg.camera_name,
                    camera_type=new_cfg.camera_type,
                    brand=new_cfg.brand,
                    serial_number=new_cfg.serial_number,
                    ip_address=new_cfg.ip_address,
                    adapter_type=new_cfg.adapter_type,
                    connection_params=new_cfg.connection_params,
                    enabled=new_cfg.enabled,
                    trigger_mode=new_cfg.trigger_mode,
                    exposure_us=new_cfg.exposure_us,
                    gain_db=new_cfg.gain_db,
                    resolution_width=new_cfg.resolution_width,
                    resolution_height=new_cfg.resolution_height,
                    pixel_size_um=new_cfg.pixel_size_um,
                    position_desc=new_cfg.position_desc,
                    save_ng_image=new_cfg.save_ng_image,
                    roi=new_cfg.roi,
                    model_binding=new_cfg.model_binding,
                    notes=new_cfg.notes,
                )
            else:
                created = create_camera_config(
                    spec_id=spec.spec_id,
                    camera_index=camera_index,
                    camera_id=new_cfg.camera_id,
                    camera_name=new_cfg.camera_name,
                    camera_type=new_cfg.camera_type,
                    brand=new_cfg.brand,
                    serial_number=new_cfg.serial_number,
                    ip_address=new_cfg.ip_address,
                    adapter_type=new_cfg.adapter_type,
                    connection_params=new_cfg.connection_params,
                    enabled=new_cfg.enabled,
                    trigger_mode=new_cfg.trigger_mode,
                    exposure_us=new_cfg.exposure_us,
                    gain_db=new_cfg.gain_db,
                    resolution_width=new_cfg.resolution_width,
                    resolution_height=new_cfg.resolution_height,
                    pixel_size_um=new_cfg.pixel_size_um,
                    position_desc=new_cfg.position_desc,
                    save_ng_image=new_cfg.save_ng_image,
                    roi=new_cfg.roi,
                    model_binding=new_cfg.model_binding,
                    notes=new_cfg.notes,
                )
                self._configs[camera_index] = created
            # Rebuild to reflect changes
            self._rebuild_cards()

    def _save_all(self):
        """Save all camera configs (enabled toggles, etc.) to DB."""
        spec = self._current_spec()
        if spec is None:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_spec_first"))
            return

        for camera_index in range(1, spec.camera_count + 1):
            existing = self._configs.get(camera_index)
            card = self._cards.get(camera_index, {})
            enabled_cb = card.get("enabled_cb")
            if enabled_cb is None:
                continue

            enabled = enabled_cb.isChecked()
            if existing:
                if existing.enabled != enabled:
                    update_camera_config(existing.config_id, enabled=enabled)
            else:
                if not enabled:
                    continue  # don't create disabled configs with no data
                create_camera_config(
                    spec_id=spec.spec_id,
                    camera_index=camera_index,
                    adapter_type="folder_watcher",
                    enabled=True,
                )

        QMessageBox.information(self, tr("app.save"), tr("app.config_saved"))
        self._rebuild_cards()
        self.data_changed.emit()

    def _current_spec(self):
        """Get current ProductSpec, or None."""
        sid = self._ctx.current_spec_id
        if not sid:
            return None
        return get_product_spec(sid)

    def _refresh_text(self, lang: str = "") -> None:
        self._rebuild_cards()
