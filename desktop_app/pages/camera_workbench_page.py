"""Camera Workbench — unified camera discovery, binding, configuration, preview and diagnostics."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

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
    QTextEdit,
    QMessageBox,
    QSplitter,
    QFrame,
    QLineEdit,
    QSizePolicy,
    QScrollArea,
)

from src.device.camera.binding_store import BindingStore, CameraBinding
from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera
from src.device.camera.hikrobot import sdk_loader
from src.device.camera.line_scan.interface import LineScanDevice
from src.device.camera.line_scan.types import DeviceInfo, FramePacket
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager
from desktop_app.ui_loader import load_ui
from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog
from core.camera_config import (
    CameraConfig,
    list_camera_configs,
)
from core.product_spec import get_product_spec

logger = logging.getLogger(__name__)

_SLOT_CARD_MIN_HEIGHT = 92
_SLOT_GRID_SPACING = 6
_SLOT_GROUP_EXTRA_HEIGHT = 96
_SLOT_SECTION_TITLE = "相机"

_DEFAULT_ROLES = ["上方 Top", "左侧 Left", "右侧 Right", "备用 Spare 1", "备用 Spare 2", "备用 Spare 3"]


class _SlotCardWidget(QFrame):
    """A single camera slot card within the workbench grid."""

    clicked = Signal(int)  # camera_index

    def __init__(
        self,
        camera_index: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_index = camera_index
        self._selected = False
        self._status = "empty"  # "configured" | "bound" | "empty"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(220)
        self.setMinimumHeight(_SLOT_CARD_MIN_HEIGHT)
        self.setMaximumHeight(_SLOT_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build()

    @property
    def camera_index(self) -> int:
        return self._camera_index

    def _build(self) -> None:
        c = ThemeManager.current()
        self.setStyleSheet(
            f"_SlotCardWidget {{ border: 1px solid {c.BORDER}; border-radius: 8px; "
            f"padding: 6px; background: {c.BG_PANEL}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(3)

        # Status dot + header row
        header_row = QHBoxLayout()
        header_row.setSpacing(5)
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(
            "background: #DDD; border-radius: 4px;"
        )
        header_row.addWidget(self._status_dot)

        self._name_label = QLabel(f"camera_{self._camera_index:02d}")
        font = self._name_label.font()
        font.setBold(True)
        font.setPointSize(10)
        self._name_label.setFont(font)
        header_row.addWidget(self._name_label)
        header_row.addStretch()

        self._role_label = QLabel(_DEFAULT_ROLES[min(self._camera_index - 1, len(_DEFAULT_ROLES) - 1)])
        self._role_label.setStyleSheet(
            f"font-size: 10px; color: {c.TEXT_SECONDARY}; "
            f"background: {c.BG_MAIN}; padding: 1px 6px; border-radius: 4px;"
        )
        self._role_label.setCursor(Qt.CursorShape.IBeamCursor)
        self._role_label.mousePressEvent = self._on_role_click
        header_row.addWidget(self._role_label)
        layout.addLayout(header_row)

        # Serial number
        sn_row = QHBoxLayout()
        sn_label = QLabel(tr("camera_mgmt.device_label") + ":")
        sn_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 10px;")
        sn_row.addWidget(sn_label)
        self._serial_label = QLabel("—")
        self._serial_label.setStyleSheet("color: #BBB; font-size: 10px; font-weight: bold;")
        sn_row.addWidget(self._serial_label)
        sn_row.addStretch()
        layout.addLayout(sn_row)

        # Status
        st_row = QHBoxLayout()
        st_lbl = QLabel(tr("camera_mgmt.slot_label") + ":")
        st_lbl.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 10px;")
        st_row.addWidget(st_lbl)
        self._status_label = QLabel(tr("camera_workbench.status_empty"))
        self._status_label.setStyleSheet("color: #BBB; font-size: 10px; font-weight: bold;")
        st_row.addWidget(self._status_label)
        st_row.addStretch()
        layout.addLayout(st_row)

        # Actions
        actions = QHBoxLayout()
        actions.setSpacing(4)

        self._bind_btn = QPushButton(tr("camera_workbench.bind_device"))
        self._bind_btn.setMinimumHeight(24)
        self._bind_btn.setFixedHeight(24)
        self._bind_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self._bind_btn.clicked.connect(self._on_bind_clicked)
        actions.addWidget(self._bind_btn)

        self._unbind_btn = QPushButton(tr("camera_workbench.unbind_device"))
        self._unbind_btn.setMinimumHeight(24)
        self._unbind_btn.setFixedHeight(24)
        self._unbind_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self._unbind_btn.setEnabled(False)
        self._unbind_btn.clicked.connect(self._on_unbind_clicked)
        actions.addWidget(self._unbind_btn)

        self._connect_btn = QPushButton(tr("camera_workbench.connect_camera"))
        self._connect_btn.setMinimumHeight(24)
        self._connect_btn.setFixedHeight(24)
        self._connect_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        actions.addWidget(self._connect_btn)

        actions.addStretch()
        layout.addLayout(actions)

    # ── Mouse events ─────────────────────────────────────────────────

    def mousePressEvent(self, event):  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit(self._camera_index)

    def _on_bind_clicked(self) -> None:
        self._bind_btn.clicked  # suppress unused warning
        self.clicked.emit(self._camera_index)  # select first, then parent handles bind

    def _on_unbind_clicked(self) -> None:
        self._unbind_btn.clicked

    def _on_connect_clicked(self) -> None:
        self._connect_btn.clicked

    def _on_role_click(self, event) -> None:
        """Inline edit role text."""
        current = self._role_label.text()
        edit = QLineEdit(current)
        edit.setStyleSheet(
            f"font-size: 11px; padding: 1px 6px; border: 1px solid "
            f"{ThemeManager.current().PRIMARY}; border-radius: 4px;"
        )
        edit.setFixedWidth(90)
        edit.selectAll()

        def finish():
            v = edit.text().strip()
            if v and v != current:
                self._role_label.setText(v)
            edit.deleteLater()

        edit.editingFinished.connect(finish)

        # Replace label temporarily
        parent_layout = self._role_label.parentWidget().layout()
        if parent_layout:
            idx = parent_layout.indexOf(self._role_label)
            self._role_label.hide()
            parent_layout.insertWidget(idx, edit)
            edit.setFocus()

            def cleanup():
                self._role_label.show()
            edit.destroyed.connect(cleanup)

    # ── Public setters ────────────────────────────────────────────────

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        c = ThemeManager.current()
        if selected:
            self.setStyleSheet(
                f"_SlotCardWidget {{ border: 2px solid {c.PRIMARY}; border-radius: 8px; "
                f"padding: 6px; background: {c.PRIMARY_LIGHT}; }}"
            )
        else:
            self.setStyleSheet(
                f"_SlotCardWidget {{ border: 1px solid {c.BORDER}; border-radius: 8px; "
                f"padding: 6px; background: {c.BG_PANEL}; }}"
            )

    def set_status(self, status: str) -> None:
        """Set status: 'configured' | 'bound' | 'empty'."""
        self._status = status
        c = ThemeManager.current()
        if status == "configured":
            self._status_dot.setStyleSheet(f"background: {c.SUCCESS}; border-radius: 4px;")
            self._status_label.setText(tr("camera_workbench.status_configured"))
            self._status_label.setStyleSheet(f"color: {c.SUCCESS}; font-size: 10px; font-weight: bold;")
        elif status == "bound":
            self._status_dot.setStyleSheet(f"background: {c.WARNING}; border-radius: 4px;")
            self._status_label.setText(tr("camera_workbench.status_bound"))
            self._status_label.setStyleSheet(f"color: {c.WARNING}; font-size: 10px; font-weight: bold;")
        else:
            self._status_dot.setStyleSheet("background: #DDD; border-radius: 4px;")
            self._status_label.setText(tr("camera_workbench.status_empty"))
            self._status_label.setStyleSheet("color: #BBB; font-size: 10px; font-weight: bold;")

        self._unbind_btn.setEnabled(status != "empty")
        self._connect_btn.setEnabled(status != "empty")

    def set_serial(self, serial: str) -> None:
        c = ThemeManager.current()
        if serial:
            self._serial_label.setText(serial)
            self._serial_label.setStyleSheet(
                f"color: {c.TEXT_PRIMARY}; font-size: 10px; font-weight: bold;"
            )
        else:
            self._serial_label.setText("—")
            self._serial_label.setStyleSheet("color: #BBB; font-size: 10px; font-weight: bold;")

    def set_role(self, role: str) -> None:
        self._role_label.setText(role)

    def get_role(self) -> str:
        return self._role_label.text()

    def set_enabled(self, enabled: bool) -> None:
        self.setVisible(enabled)


class CameraWorkbenchPage(QWidget):
    """Merged page: discovery + binding + configuration + preview + diagnostics."""

    camera_connected = Signal(str)
    camera_disconnected = Signal(str)
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._binding_store = BindingStore()
        self._cameras: dict[str, LineScanDevice] = {}
        self._discovered: list[DeviceInfo] = []
        self._configs: dict[int, CameraConfig] = {}
        self._selected_slot: int | None = None
        self._slot_cards: dict[int, _SlotCardWidget] = {}
        self._preview_active = False
        self._preview_buffer: np.ndarray | None = None
        self._preview_lock = False
        self._line_counts: dict[str, int] = {}
        self._spec_id: str | None = None

        self._setup_ui()
        self._load_bindings()
        self._rebuild_slots()

        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        self._refresh_text()

    # ══════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        ui_path = Path(__file__).resolve().parents[1] / "ui" / "camera_workbench_page.ui"
        self._ui = load_ui(ui_path, self)
        self._ui.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_area.setWidget(self._ui)
        outer.addWidget(self._scroll_area, 1)

        self._bind_ui_objects()
        self._install_dynamic_layouts()
        self._wire_ui_signals()

        # Timers (runtime only, not from .ui)
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_timer.setInterval(66)

        self._diag_timer = QTimer(self)
        self._diag_timer.timeout.connect(self._refresh_diagnostics)
        self._diag_timer.setInterval(1000)

    # ── UI Loader helpers ──────────────────────────────────────────────

    def _require_child(self, widget_type: type, name: str):
        child = self._ui.findChild(widget_type, name)
        if child is None:
            raise RuntimeError(f"Missing widget in camera_workbench_page.ui: {name}")
        return child

    def _bind_ui_objects(self) -> None:
        self._context_bar = self._require_child(QFrame, "contextBar")
        self._slot_group = self._require_child(QGroupBox, "slotGroup")
        self._slot_title = self._require_child(QLabel, "slotTitle")
        self._scan_btn = self._require_child(QPushButton, "scanButton")
        self._found_label = self._require_child(QLabel, "foundLabel")
        self._slot_grid_host = self._require_child(QWidget, "slotGridHost")
        self._connect_all_btn = self._require_child(QPushButton, "connectAllButton")
        self._slot_header_layout = self._require_child(QHBoxLayout, "slotHeaderLayout")
        self._connect_all_row = self._require_child(QHBoxLayout, "connectAllRow")
        self._slot_group_layout = self._require_child(QVBoxLayout, "slotGroupLayout")

        self._preview_diag_splitter = self._require_child(QSplitter, "previewDiagSplitter")
        self._preview_group = self._require_child(QGroupBox, "previewGroup")
        self._preview_label = self._require_child(QLabel, "previewLabel")
        self._preview_info = self._require_child(QLabel, "previewInfo")
        self._preview_start_btn = self._require_child(QPushButton, "previewStartButton")
        self._preview_stop_btn = self._require_child(QPushButton, "previewStopButton")
        self._snapshot_btn = self._require_child(QPushButton, "snapshotButton")
        self._diag_group = self._require_child(QGroupBox, "diagGroup")
        self._diag_text = self._require_child(QTextEdit, "diagText")

        self._empty_placeholder = self._require_child(QLabel, "emptyPlaceholder")
        self._ctx_badge = self._require_child(QLabel, "ctxBadge")

        # Context bar layouts (QLayout subclasses are QObject, findChild works)
        self._ctx_customer = self._require_child(QHBoxLayout, "ctxCustomerLayout")
        self._ctx_project = self._require_child(QHBoxLayout, "ctxProjectLayout")
        self._ctx_spec = self._require_child(QHBoxLayout, "ctxSpecLayout")
        self._ctx_count = self._require_child(QHBoxLayout, "ctxCountLayout")

        # Wire "value_label" property on context layouts (used by _refresh_context_bar)
        self._ctx_customer.setProperty("value_label", self._require_child(QLabel, "ctxCustomerValue"))
        self._ctx_project.setProperty("value_label", self._require_child(QLabel, "ctxProjectValue"))
        self._ctx_spec.setProperty("value_label", self._require_child(QLabel, "ctxSpecValue"))
        self._ctx_count.setProperty("value_label", self._require_child(QLabel, "ctxCountValue"))

    def _install_dynamic_layouts(self) -> None:
        self._compact_slot_header()
        self._slot_grid = QGridLayout(self._slot_grid_host)
        self._slot_grid.setContentsMargins(8, 8, 8, 8)
        self._slot_grid.setSpacing(_SLOT_GRID_SPACING)
        self._slot_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Permanently hide the Designer-authored paramGroup — params now live in
        # the per-slot CameraSlotConfigDialog.
        self._param_group = self._require_child(QGroupBox, "paramGroup")
        self._param_group.hide()
        self._install_main_split_layout()
        self._normalize_preview_runtime_size()

    def _compact_slot_header(self) -> None:
        """Keep camera list actions in one header row."""
        self._slot_group.setTitle("")
        self._slot_title.setText(_SLOT_SECTION_TITLE)

        found_index = self._slot_header_layout.indexOf(self._found_label)
        if found_index >= 0:
            self._slot_header_layout.takeAt(found_index)

        old_index = self._connect_all_row.indexOf(self._connect_all_btn)
        if old_index >= 0:
            self._connect_all_row.takeAt(old_index)

        scan_index = self._slot_header_layout.indexOf(self._scan_btn)
        if self._slot_header_layout.indexOf(self._connect_all_btn) < 0 and scan_index >= 0:
            self._slot_header_layout.insertWidget(scan_index + 1, self._connect_all_btn)

        for idx in range(self._slot_group_layout.count()):
            item = self._slot_group_layout.itemAt(idx)
            if item and item.layout() is self._connect_all_row:
                self._slot_group_layout.takeAt(idx)
                break

        self._slot_status_layout = QHBoxLayout()
        self._slot_status_layout.setContentsMargins(0, 4, 0, 4)
        self._slot_status_layout.setSpacing(0)
        self._found_label.setWordWrap(True)
        self._found_label.setMinimumHeight(22)
        self._found_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._slot_status_layout.addWidget(self._found_label, 1)

        header_pos = -1
        for idx in range(self._slot_group_layout.count()):
            item = self._slot_group_layout.itemAt(idx)
            if item and item.layout() is self._slot_header_layout:
                header_pos = idx
                break
        self._slot_group_layout.insertLayout(max(0, header_pos + 1), self._slot_status_layout)

    def _install_main_split_layout(self) -> None:
        """Move Designer sections into the final left-list / right-preview layout."""
        root_layout = self._ui.layout()
        if root_layout is None:
            return

        for widget in (self._slot_group, self._param_group, self._preview_diag_splitter):
            root_layout.removeWidget(widget)

        self._left_panel = QWidget(self._ui)
        self._left_panel.setMinimumWidth(300)
        self._left_panel.setMaximumWidth(380)
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._slot_list_scroll = QScrollArea(self._left_panel)
        self._slot_list_scroll.setWidgetResizable(True)
        self._slot_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._slot_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._slot_list_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._slot_list_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._slot_list_scroll.setWidget(self._slot_group)
        left_layout.addWidget(self._slot_list_scroll, 1)

        self._right_panel = QWidget(self._ui)
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._preview_diag_splitter.setOrientation(Qt.Orientation.Vertical)
        self._preview_diag_splitter.setStretchFactor(0, 1)
        self._preview_diag_splitter.setStretchFactor(1, 0)
        self._preview_diag_splitter.setSizes([620, 180])
        right_layout.addWidget(self._preview_diag_splitter, 1)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self._ui)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.addWidget(self._left_panel)
        self._main_splitter.addWidget(self._right_panel)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([360, 1100])

        context_index = root_layout.indexOf(self._context_bar)
        root_layout.insertWidget(context_index + 1, self._main_splitter, 1)

    def _refresh_scroll_content_size(self) -> None:
        """Keep scroll content tall enough that Qt scrolls instead of clipping sections."""
        layout = self._ui.layout()
        if layout is None:
            return
        layout.activate()
        self._ui.setMinimumHeight(layout.sizeHint().height())

    def _normalize_preview_runtime_size(self) -> None:
        """Reserve the right workspace primarily for the current camera preview."""
        self._preview_diag_splitter.setMinimumHeight(560)
        self._preview_group.setMinimumHeight(420)
        self._diag_group.setMinimumHeight(140)
        self._diag_group.setMaximumHeight(240)
        self._preview_label.setMinimumHeight(360)

    def _wire_ui_signals(self) -> None:
        self._scan_btn.clicked.connect(self._on_scan)
        self._connect_all_btn.clicked.connect(self._on_connect_all)
        self._preview_start_btn.clicked.connect(self._on_start_preview)
        self._preview_stop_btn.clicked.connect(self._on_stop_preview)
        self._snapshot_btn.clicked.connect(self._on_snapshot)

    # ── Context bar ──────────────────────────────────────────────────

    def _build_context_bar(self) -> None:
        self._context_bar = QFrame()
        self._context_bar.setObjectName("workbenchStateFrame")
        layout = QHBoxLayout(self._context_bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        self._ctx_customer = self._make_ctx_pair(tr("project.customer"))
        layout.addLayout(self._ctx_customer)
        self._ctx_project = self._make_ctx_pair(tr("project.project"))
        layout.addLayout(self._ctx_project)
        self._ctx_spec = self._make_ctx_pair(tr("spec.title"))
        layout.addLayout(self._ctx_spec)
        self._ctx_count = self._make_ctx_pair(tr("project.col_camera_count"))
        layout.addLayout(self._ctx_count)

        layout.addStretch()
        self._ctx_badge = QLabel()
        self._ctx_badge.setStyleSheet(
            "padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self._ctx_badge)

    @staticmethod
    def _make_ctx_pair(label_text: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(6)
        lbl = QLabel(f"{label_text}:")
        c = ThemeManager.current()
        lbl.setStyleSheet(f"font-size: 10px; color: {c.TEXT_SECONDARY}; text-transform: uppercase;")
        layout.addWidget(lbl)
        val = QLabel("—")
        val.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {c.TEXT_PRIMARY};")
        layout.addWidget(val)
        layout.setProperty("value_label", val)
        return layout

    # ── Slot section ─────────────────────────────────────────────────

    def _build_slot_section(self) -> None:
        self._slot_group = QGroupBox()
        layout = QVBoxLayout(self._slot_group)

        # Header
        header = QHBoxLayout()
        self._slot_title = QLabel(_SLOT_SECTION_TITLE)
        font = self._slot_title.font()
        font.setBold(True)
        self._slot_title.setFont(font)
        header.addWidget(self._slot_title)
        header.addStretch()

        self._scan_btn = QPushButton("🔍 " + tr("camera_workbench.scan_devices"))
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setObjectName("secondaryBtn")
        header.addWidget(self._scan_btn)

        self._found_label = QLabel()
        self._found_label.setVisible(False)
        c = ThemeManager.current()
        self._found_label.setStyleSheet(f"color: {c.SUCCESS}; font-size: 11px;")
        header.addWidget(self._found_label)
        layout.addLayout(header)

        # Slot grid
        self._slot_grid = QGridLayout()
        self._slot_grid.setSpacing(10)
        layout.addLayout(self._slot_grid)

        # Connect all row
        action_row = QHBoxLayout()
        action_row.addStretch()
        self._connect_all_btn = QPushButton(tr("camera.connect_all"))
        self._connect_all_btn.clicked.connect(self._on_connect_all)
        action_row.addWidget(self._connect_all_btn)
        layout.addLayout(action_row)

    # ── Preview + Diagnostics ────────────────────────────────────────

    def _build_preview_diag_section(self) -> None:
        self._preview_diag_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Preview
        self._preview_group = QGroupBox(tr("camera_mgmt.preview_group"))
        pv_layout = QVBoxLayout(self._preview_group)

        self._preview_label = QLabel(tr("camera_mgmt.preview_not_started"))
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(240, 160)
        c = ThemeManager.current()
        self._preview_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER}; color: {c.TEXT_SECONDARY};"
        )
        pv_layout.addWidget(self._preview_label, 1)

        self._preview_info = QLabel("—")
        self._preview_info.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        pv_layout.addWidget(self._preview_info)

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
        pv_layout.addLayout(btn_row)

        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_timer.setInterval(66)

        self._preview_diag_splitter.addWidget(self._preview_group)

        # Diagnostics
        self._diag_group = QGroupBox(tr("camera_mgmt.diag_group"))
        dg_layout = QVBoxLayout(self._diag_group)

        self._diag_text = QTextEdit()
        self._diag_text.setReadOnly(True)
        self._diag_text.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
        )
        dg_layout.addWidget(self._diag_text, 1)

        self._diag_timer = QTimer(self)
        self._diag_timer.timeout.connect(self._refresh_diagnostics)
        self._diag_timer.setInterval(1000)

        self._preview_diag_splitter.addWidget(self._diag_group)
        self._preview_diag_splitter.setStretchFactor(0, 3)
        self._preview_diag_splitter.setStretchFactor(1, 2)

    # ══════════════════════════════════════════════════════════════════
    # Slot Management
    # ══════════════════════════════════════════════════════════════════

    def _rebuild_slots(self) -> None:
        """Rebuild all slot cards based on current spec."""
        # Clear old cards
        for card in self._slot_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._slot_cards.clear()

        # Get current spec
        spec_id = self._ctx.current_spec_id
        self._spec_id = spec_id
        if not spec_id:
            self._show_empty_state()
            return

        spec = get_product_spec(spec_id)
        if not spec:
            self._show_empty_state()
            return

        camera_count = getattr(spec, "camera_count", 0) or 0
        if camera_count <= 0:
            self._show_empty_state()
            return

        self._show_slot_state()

        # Load configs
        self._configs = {}
        for cfg in list_camera_configs(spec_id):
            self._configs[cfg.camera_index] = cfg

        # Camera slots are a vertical list so the preview keeps the main width.
        cols = 1

        # Load bindings
        bindings = self._binding_store.load_all()
        binding_map: dict[str, CameraBinding] = {b.camera_slot: b for b in bindings}

        for idx in range(1, camera_count + 1):
            slot_id = f"camera_{idx:02d}"
            card = _SlotCardWidget(idx)
            card.clicked.connect(self._on_slot_selected)

            # Determine status
            has_config = idx in self._configs
            has_binding = slot_id in binding_map

            if has_config:
                cfg = self._configs[idx]
                card.set_status("configured")
                card.set_serial(cfg.serial_number or "")
                if cfg.position_desc:
                    card.set_role(cfg.position_desc)
            elif has_binding:
                b = binding_map[slot_id]
                card.set_status("bound")
                card.set_serial(b.serial_number or "")
                if b.role and b.role != "spare":
                    role_map = {"top": "上方 Top", "left": "左侧 Left", "right": "右侧 Right", "spare": "备用 Spare"}
                    card.set_role(role_map.get(b.role, b.role))
            else:
                card.set_status("empty")
                card.set_serial("")

            # Wire card buttons to the main page handlers
            card._bind_btn.clicked.connect(lambda checked=False, i=idx: self._on_bind_slot(i))
            card._unbind_btn.clicked.connect(lambda checked=False, i=idx: self._on_unbind_slot(i))
            card._connect_btn.clicked.connect(lambda checked=False, i=idx: self._on_connect_slot(i))

            row = (idx - 1) // cols
            col = (idx - 1) % cols
            self._slot_grid.addWidget(card, row, col)
            self._slot_cards[idx] = card

        # Update title
        self._slot_title.setText(_SLOT_SECTION_TITLE)
        self._resize_slot_grid(camera_count, cols)

        # Update context bar
        self._refresh_context_bar()

    def _resize_slot_grid(self, camera_count: int, cols: int) -> None:
        """Give slot cards enough height without leaving a large blank gap."""
        rows = max(1, (camera_count + cols - 1) // cols)
        margins = self._slot_grid.contentsMargins()
        host_height = (
            rows * _SLOT_CARD_MIN_HEIGHT
            + (rows - 1) * _SLOT_GRID_SPACING
            + margins.top()
            + margins.bottom()
        )
        self._slot_grid_host.setMinimumHeight(host_height)
        self._slot_grid_host.setMaximumHeight(host_height)
        viewport_height = (
            self._slot_list_scroll.viewport().height()
            if hasattr(self, "_slot_list_scroll")
            else 0
        )
        group_height = max(host_height + _SLOT_GROUP_EXTRA_HEIGHT, viewport_height)
        self._slot_group.setMinimumHeight(group_height)
        self._slot_group.setMaximumHeight(16777215)
        self._refresh_scroll_content_size()

    def _show_empty_state(self) -> None:
        if hasattr(self, "_main_splitter"):
            self._main_splitter.hide()
        self._slot_group.hide()
        self._preview_diag_splitter.hide()
        self._empty_placeholder.show()
        self._refresh_scroll_content_size()

    def _show_slot_state(self) -> None:
        self._empty_placeholder.hide()
        if hasattr(self, "_main_splitter"):
            self._main_splitter.show()
        self._slot_group.show()
        self._preview_diag_splitter.show()

    def _on_slot_selected(self, camera_index: int) -> None:
        self._selected_slot = camera_index
        # Highlight selected card
        for idx, card in self._slot_cards.items():
            card.set_selected(idx == camera_index)

        if self._preview_active:
            self._on_stop_preview()
        self._preview_buffer = None
        self._preview_label.clear()
        self._preview_label.setText(tr("camera_mgmt.preview_not_started"))
        self._preview_info.setText(f"camera_{camera_index:02d}")
        self._refresh_diagnostics()

    # ══════════════════════════════════════════════════════════════════
    # Context Bar
    # ══════════════════════════════════════════════════════════════════

    def _refresh_context_bar(self) -> None:
        c = ThemeManager.current()

        def _set_val(layout: QHBoxLayout, text: str, muted: bool = False) -> None:
            val_label: QLabel = layout.property("value_label")
            if val_label:
                val_label.setText(text)
                val_label.setStyleSheet(
                    f"font-size: 12px; {'font-weight: normal; color: ' + c.TEXT_SECONDARY if muted else 'font-weight: bold; color: ' + c.TEXT_PRIMARY};"
                )

        _set_val(self._ctx_customer, self._ctx.current_customer_name or "—",
                 muted=not self._ctx.current_customer_id)
        _set_val(self._ctx_project, self._ctx.current_project_name or "—",
                 muted=not self._ctx.current_project_id)
        _set_val(self._ctx_spec, self._ctx.current_spec_name or "—",
                 muted=not self._ctx.current_spec_id)

        spec_id = self._ctx.current_spec_id
        if spec_id:
            spec = get_product_spec(spec_id)
            count = getattr(spec, "camera_count", 0) if spec else 0
            _set_val(self._ctx_count, str(count))
        else:
            _set_val(self._ctx_count, "—", muted=True)

        # Badge
        configured = len(self._configs)
        total = getattr(get_product_spec(spec_id) if spec_id else None, "camera_count", 0) or 0
        if spec_id and total > 0:
            all_ok = configured >= total
            self._ctx_badge.setText(f"已配置 {configured}/{total}")
            self._ctx_badge.setStyleSheet(
                f"padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: bold; "
                f"background: {'#E8F5E9' if all_ok else '#FFF3E0'}; "
                f"color: {'#2E7D32' if all_ok else '#E65100'};"
            )
        else:
            self._ctx_badge.setText("未选择规格")
            self._ctx_badge.setStyleSheet(
                f"padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: bold; "
                f"background: {c.BG_MAIN}; color: #999;"
            )

    # ══════════════════════════════════════════════════════════════════
    # Scan
    # ══════════════════════════════════════════════════════════════════

    def _on_scan(self) -> None:
        """Scan for Hikrobot cameras on the network."""
        sdk_ok = sdk_loader.load_sdk()
        if not sdk_ok:
            error = sdk_loader.SDK_ERROR or "unknown error"
            c = ThemeManager.current()
            self._found_label.setText(tr("camera_mgmt.sdk_load_failed", error=error))
            self._found_label.setStyleSheet(f"color: {c.ERROR}; font-size: 11px;")
            self._found_label.setVisible(True)
            return

        try:
            self._discovered = HikrobotLineScanCamera.enumerate_devices()
        except Exception:
            self._discovered = []
            logger.exception("Device enumeration failed")

        c = ThemeManager.current()
        if self._discovered:
            self._found_label.setText(
                tr("camera_workbench.found_devices", n=len(self._discovered))
            )
            self._found_label.setStyleSheet(f"color: {c.SUCCESS}; font-size: 11px;")
        else:
            self._found_label.setText(tr("camera_mgmt.no_devices_hint"))
            self._found_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        self._found_label.setVisible(True)

    # ══════════════════════════════════════════════════════════════════
    # Bind / Unbind / Connect
    # ══════════════════════════════════════════════════════════════════

    def _on_bind_slot(self, camera_index: int) -> None:
        """Open the per-slot config dialog (handles bind + params in one dialog)."""
        self._on_slot_selected(camera_index)
        self._open_slot_config_dialog(camera_index)

    def _open_slot_config_dialog(self, camera_index: int) -> None:
        """Build and show the CameraSlotConfigDialog for a slot; refresh on close."""
        slot_id = f"camera_{camera_index:02d}"
        role = _DEFAULT_ROLES[min(camera_index - 1, len(_DEFAULT_ROLES) - 1)]
        if camera_index in self._slot_cards:
            role = self._slot_cards[camera_index].get_role()

        existing_cfg = self._configs.get(camera_index)

        dlg = CameraSlotConfigDialog(
            camera_index,
            slot_id,
            role,
            binding_store=self._binding_store,
            cameras=self._cameras,
            existing_config=existing_cfg,
            spec_id=self._spec_id or "",
            parent=self,
        )
        dlg.exec()

        # Rebuild to reflect any binding/config changes
        self._rebuild_slots()

    def _on_unbind_slot(self, camera_index: int) -> None:
        """Unbind device from a slot."""
        slot_id = f"camera_{camera_index:02d}"
        dev = self._cameras.pop(slot_id, None)
        if dev:
            try:
                dev.stop_grabbing()
                dev.close()
            except Exception:
                pass
        self._binding_store.remove_binding(slot_id)
        self._binding_store.save_all()
        self._line_counts.pop(slot_id, None)

        if camera_index in self._slot_cards:
            self._slot_cards[camera_index].set_serial("")
            self._slot_cards[camera_index].set_status("empty")

        self.camera_disconnected.emit(slot_id)
        logger.info("Unbound %s", slot_id)

    def _on_connect_slot(self, camera_index: int) -> None:
        """Connect to the camera bound to a slot."""
        slot_id = f"camera_{camera_index:02d}"
        binding = self._binding_store.get_binding(slot_id)
        if binding is None or not binding.serial_number:
            return

        # Close existing device on this slot
        old = self._cameras.pop(slot_id, None)
        if old:
            try:
                old.stop_grabbing()
                old.close()
            except Exception:
                pass

        cam = HikrobotLineScanCamera()
        if not cam.open(binding.serial_number):
            code, msg = cam.get_last_error()
            QMessageBox.critical(
                self,
                tr("commissioning.connect_failed"),
                tr("camera_mgmt.connect_error_fmt", sn=binding.serial_number, code=code, msg=msg),
            )
            return

        self._cameras[slot_id] = cam
        self._line_counts[slot_id] = 0
        self.camera_connected.emit(slot_id)
        logger.info("Connected %s → %s", slot_id, binding.serial_number)

    def _on_connect_all(self) -> None:
        """Connect all bound cameras."""
        bindings = self._binding_store.load_all()
        for binding in bindings:
            slot_id = binding.camera_slot
            if not binding.serial_number:
                continue
            if slot_id in self._cameras and self._cameras[slot_id].get_status().connected:
                continue
            cam = HikrobotLineScanCamera()
            if cam.open(binding.serial_number):
                old = self._cameras.pop(slot_id, None)
                if old:
                    try:
                        old.stop_grabbing()
                        old.close()
                    except Exception:
                        pass
                self._cameras[slot_id] = cam
                self._line_counts[slot_id] = 0
                self.camera_connected.emit(slot_id)

    # ══════════════════════════════════════════════════════════════════
    # Preview & Diagnostics (ported from CameraManagementPage)
    # ══════════════════════════════════════════════════════════════════

    def _get_selected_camera(self) -> LineScanDevice | None:
        if self._selected_slot is None:
            return None
        return self._cameras.get(f"camera_{self._selected_slot:02d}")

    def _on_start_preview(self) -> None:
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
        logger.info("Preview started")

    def _on_stop_preview(self) -> None:
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

    def _refresh_preview(self) -> None:
        if self._preview_buffer is None:
            return
        self._preview_lock = True
        try:
            img = self._preview_buffer
            h, w = img.shape[:2]
            if img.ndim == 2:
                qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
            elif img.ndim == 3 and img.shape[2] == 3:
                qimg = QImage(img.data, w, h, w * 3, QImage.Format.Format_RGB888)
            else:
                return
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
        if self._preview_buffer is None:
            return
        import cv2
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(os.getcwd(), f"camera_snapshot_{ts}.png")
        cv2.imwrite(fname, self._preview_buffer)
        QMessageBox.information(
            self, tr("camera_mgmt.dlg_snapshot"), tr("camera_mgmt.snapshot_saved", fname=fname)
        )

    def _refresh_diagnostics(self) -> None:
        cam = self._get_selected_camera()
        if cam is None:
            self._diag_text.setPlainText(tr("camera_mgmt.no_camera_diag"))
            return

        st = cam.get_status()
        slot_id = f"camera_{self._selected_slot:02d}" if self._selected_slot else "—"
        lines: list[str] = []
        lines.append(tr("camera_mgmt.diag_slot") + f"         {slot_id}")
        lines.append(tr("camera_mgmt.diag_serial") + f"       {st.serial_number}")
        lines.append(
            tr("camera_mgmt.diag_conn_status") + "     "
            + (tr("camera_mgmt.diag_connected_yes") if st.connected else tr("camera_mgmt.diag_connected_no"))
        )
        lines.append(
            tr("camera_mgmt.diag_grab_status") + "     "
            + (tr("camera_mgmt.diag_grabbing_yes") if st.grabbing else tr("camera_mgmt.diag_grabbing_no"))
        )
        lines.append(tr("camera_mgmt.diag_line_rate") + f"         {st.line_rate:.0f} Hz")
        lines.append(tr("camera_mgmt.diag_received") + f"     {st.received_line_count}")
        lines.append(tr("camera_mgmt.diag_dropped") + f"       {st.dropped_line_count}")
        lines.append(tr("camera_mgmt.diag_timeout") + f"     {st.timeout_count}")
        w = cam.get_param("Width") or 2048
        h = cam.get_param("Height") or 1
        lines.append(tr("camera_mgmt.diag_image_size") + f"     {w} × {h}")
        lines.append(tr("camera_mgmt.diag_pixel_format") + f"     {cam.get_param('PixelFormat') or 'Mono8'}")
        lines.append(tr("camera_mgmt.diag_exposure") + f"     {cam.get_param('ExposureTime') or 0:.1f} us")
        lines.append(tr("camera_mgmt.diag_gain") + f"         {cam.get_param('Gain') or 0:.1f} dB")
        err_code = st.last_error_code
        if err_code != 0:
            lines.append(tr("camera_mgmt.diag_last_error") + f"     0x{err_code:08X} {st.last_error_message}")
        else:
            lines.append(tr("camera_mgmt.diag_last_error") + "     —")
        self._diag_text.setPlainText("\n".join(lines))

    # ══════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════

    def _load_bindings(self) -> None:
        self._binding_store.load_all()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh_context_bar()
        self._rebuild_slots()

    def closeEvent(self, event: object) -> None:  # noqa: N802
        if self._preview_active:
            self._on_stop_preview()
        for dev in self._cameras.values():
            try:
                dev.stop_grabbing()
                dev.close()
            except Exception:
                pass
        try:
            HikrobotLineScanCamera._finalize_sdk()
        except Exception:
            pass
        super().closeEvent(event)

    def _refresh_text(self, lang: str | None = None) -> None:
        _ = lang
        self._slot_title.setText(_SLOT_SECTION_TITLE)
        self._scan_btn.setText("🔍 " + tr("camera_workbench.scan_devices"))
        self._connect_all_btn.setText(tr("camera.connect_all"))
        self._preview_start_btn.setText(tr("camera.start_preview"))
        self._preview_stop_btn.setText(tr("camera.stop_preview"))
        self._snapshot_btn.setText(tr("camera.snapshot"))
        self._preview_group.setTitle(tr("camera_mgmt.preview_group"))
        self._diag_group.setTitle(tr("camera_mgmt.diag_group"))
        if not self._preview_active:
            stopped_texts = {
                I18nManager._lookup("camera_mgmt.preview_stopped", "zh"),
                I18nManager._lookup("camera_mgmt.preview_stopped", "en"),
            }
            preview_key = (
                "camera_mgmt.preview_stopped"
                if self._preview_label.text() in stopped_texts
                else "camera_mgmt.preview_not_started"
            )
            self._preview_label.setText(tr(preview_key))
        self._empty_placeholder.setText(tr("camera_workbench.empty_spec"))
        self._rebuild_slots()

    def _on_theme_changed(self) -> None:
        c = ThemeManager.current()
        self._preview_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER}; color: {c.TEXT_SECONDARY};"
        )
        self._preview_info.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        self._diag_text.setStyleSheet(
            f"background-color: {c.BG_INPUT}; color: {c.TEXT_PRIMARY}; font-size: 12px;"
        )
        self._empty_placeholder.setStyleSheet(
            f"font-size: 14px; color: {c.TEXT_SECONDARY}; padding: 60px;"
        )
        for card in self._slot_cards.values():
            if card._selected:
                card.set_selected(True)
        self._refresh_context_bar()
        self._refresh_scroll_content_size()

    # ══════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════

    def get_camera(self, slot: str) -> LineScanDevice | None:
        return self._cameras.get(slot)

    def get_all_cameras(self) -> dict[str, LineScanDevice]:
        return dict(self._cameras)

    def get_connected_slots(self) -> list[str]:
        return [s for s, d in self._cameras.items() if d.get_status().connected]

    def refresh(self) -> None:
        """Refresh current context, slot cards, and diagnostics."""
        self._load_bindings()
        self._rebuild_slots()
        self._refresh_context_bar()
        self._refresh_diagnostics()
        self._refresh_scroll_content_size()
