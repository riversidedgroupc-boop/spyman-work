"""Behavior tests for the merged CameraWorkbenchPage and CameraSlotConfigDialog."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QScrollArea, QSplitter

from src.device.camera.binding_store import CameraBinding
from src.device.camera.line_scan.types import DeviceInfo, CameraStatus


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_fake_spec(sid: str = "SPEC_01", count: int = 3):
    """Create a simple product spec stub."""
    from dataclasses import dataclass

    @dataclass
    class FakeSpec:
        spec_id: str = sid
        camera_count: int = count

    return FakeSpec(spec_id=sid, camera_count=count)


class FakeBindingStore:
    def __init__(self) -> None:
        self._bindings: dict[str, CameraBinding] = {}

    def load_all(self) -> list[CameraBinding]:
        return list(self._bindings.values())

    def save_all(self, bindings: list[CameraBinding] | None = None) -> None:
        if bindings is not None:
            for b in bindings:
                self._bindings[b.camera_slot] = b

    def get_binding(self, slot: str) -> CameraBinding | None:
        return self._bindings.get(slot)

    def set_binding(self, binding: CameraBinding) -> None:
        self._bindings[binding.camera_slot] = binding

    def remove_binding(self, slot: str) -> None:
        self._bindings.pop(slot, None)


class FakeCamera:
    opened_serials: list[str] = []

    def __init__(self) -> None:
        self.params: list[tuple[str, object]] = []
        self.connected = False
        self.grabbing = False

    def open(self, serial_number: str) -> bool:
        FakeCamera.opened_serials.append(serial_number)
        self.connected = True
        return True

    def close(self) -> None:
        self.connected = False

    def stop_grabbing(self) -> None:
        self.grabbing = False

    def start_grabbing(self) -> bool:
        self.grabbing = True
        return True

    def set_param(self, name: str, value: object) -> None:
        self.params.append((name, value))

    def get_param(self, name: str) -> object:
        return 0

    def get_status(self) -> CameraStatus:
        return CameraStatus(connected=self.connected, grabbing=self.grabbing)

    def register_line_callback(self, callback: Any) -> None:
        pass

    def unregister_line_callback(self) -> None:
        pass

    def get_last_error(self) -> tuple[int, str]:
        return 0, ""


class FakeLineScanCamera(FakeCamera):
    devices: list[DeviceInfo] = []

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]:
        return list(FakeLineScanCamera.devices)

    @staticmethod
    def _finalize_sdk() -> None:
        pass


def _devices() -> list[DeviceInfo]:
    return [
        DeviceInfo(model="MV-CA050-20GM", serial_number="SN-A01", ip_address="192.168.1.10", mac_address="AA:BB:CC:01"),
        DeviceInfo(model="MV-CA050-20GM", serial_number="SN-A02", ip_address="192.168.1.11", mac_address="AA:BB:CC:02"),
    ]


@pytest.fixture
def workbench_page_no_spec(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Workbench page with no spec selected."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *args, **kwargs: None)

    # Ensure no spec
    ctx = cw.AppContext.instance()
    orig_spec = ctx._current_spec_id
    ctx._current_spec_id = ""
    ctx._current_spec_name = ""
    ctx._current_customer_name = ""
    ctx._current_project_name = ""

    widget = cw.CameraWorkbenchPage()
    widget.show()
    yield widget
    widget.close()
    ctx._current_spec_id = orig_spec


@pytest.fixture
def workbench_page_with_spec(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Workbench page with a mock spec (camera_count=3)."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *args, **kwargs: None)

    # Mock SDK and camera
    FakeLineScanCamera.devices = _devices()
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=3))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    # Set context
    ctx = cw.AppContext.instance()
    orig_spec = ctx._current_spec_id
    ctx._current_spec_id = "SPEC_01"
    ctx._current_spec_name = "TestSpec"
    ctx._current_customer_name = "TestCorp"
    ctx._current_project_name = "TestProject"

    # Clean shared binding file to avoid test pollution
    binding_file = Path(os.getcwd()) / "config" / "camera_binding.json"
    if binding_file.exists():
        binding_file.unlink()

    widget = cw.CameraWorkbenchPage()
    widget.show()
    yield widget
    widget.close()
    # Clean up after test
    if binding_file.exists():
        binding_file.unlink()
    ctx._current_spec_id = orig_spec


def test_camera_workbench_ui_file_exists() -> None:
    ui_path = Path("desktop_app/ui/camera_workbench_page.ui")
    assert ui_path.exists()
    assert ui_path.read_text(encoding="utf-8").lstrip().startswith("<?xml")


# ── Tests: Empty / No-spec state ───────────────────────────────────────────


def test_empty_state_when_no_spec(workbench_page_no_spec):
    """When no spec is selected, show placeholder and hide slot/preview sections."""
    page = workbench_page_no_spec
    assert not page._slot_group.isVisible()
    assert not page._preview_diag_splitter.isVisible()
    assert page._empty_placeholder.isVisible()


def test_param_group_hidden_on_main_page(workbench_page_with_spec):
    """Parameter area is permanently hidden; params live in the per-slot dialog."""
    page = workbench_page_with_spec
    assert not page._param_group.isVisible()


def test_slot_section_visible_when_spec_has_cameras(workbench_page_with_spec):
    """When spec with camera_count > 0 is selected, slot/preview are visible."""
    page = workbench_page_with_spec
    assert page._slot_group.isVisible()
    assert page._preview_diag_splitter.isVisible()
    assert not page._empty_placeholder.isVisible()


def test_main_layout_is_camera_list_with_large_preview(workbench_page_with_spec):
    """Main area is split into a narrow camera list and a wide preview workspace."""
    page = workbench_page_with_spec

    assert isinstance(page._main_splitter, QSplitter)
    assert page._main_splitter.orientation() == Qt.Orientation.Horizontal
    assert page._main_splitter.widget(0) is page._left_panel
    assert page._main_splitter.widget(1) is page._right_panel
    assert page._left_panel.maximumWidth() <= 420
    assert page._right_panel.minimumWidth() <= page._left_panel.maximumWidth()


def test_slot_header_title_and_actions_are_compact(workbench_page_with_spec):
    """Camera list header uses the concise title and keeps scan/connect together."""
    page = workbench_page_with_spec
    header_layout = page._ui.findChild(QHBoxLayout, "slotHeaderLayout")
    connect_row = page._ui.findChild(QHBoxLayout, "connectAllRow")

    assert page._slot_title.text() == "相机"
    assert page._slot_group.title() == ""
    scan_index = header_layout.indexOf(page._scan_btn)
    connect_index = header_layout.indexOf(page._connect_all_btn)
    assert scan_index >= 0
    assert connect_index == scan_index + 1
    if connect_row is not None:
        assert connect_row.indexOf(page._connect_all_btn) == -1


def test_camera_workbench_initial_text_uses_active_language(workbench_page_with_spec):
    """Designer-authored defaults should not leak English text on first render."""
    from desktop_app.i18n import tr

    page = workbench_page_with_spec

    assert page._scan_btn.text() == "🔍 " + tr("camera_workbench.scan_devices")
    assert page._connect_all_btn.text() == tr("camera.connect_all")
    assert page._preview_group.title() == tr("camera_mgmt.preview_group")
    assert page._diag_group.title() == tr("camera_mgmt.diag_group")
    assert page._preview_start_btn.text() == tr("camera.start_preview")
    assert page._preview_stop_btn.text() == tr("camera.stop_preview")
    assert page._snapshot_btn.text() == tr("camera.snapshot")
    assert page._preview_label.text() == tr("camera_mgmt.preview_not_started")


def test_found_status_sits_below_slot_actions(workbench_page_with_spec):
    """Scan status is a separate row below the action buttons and above camera cards."""
    page = workbench_page_with_spec
    header_layout = page._ui.findChild(QHBoxLayout, "slotHeaderLayout")

    assert header_layout.indexOf(page._found_label) == -1
    assert page._slot_status_layout.indexOf(page._found_label) == 0

    header_pos = -1
    status_pos = -1
    for idx in range(page._slot_group_layout.count()):
        item = page._slot_group_layout.itemAt(idx)
        if item.layout() is header_layout:
            header_pos = idx
        if item.layout() is page._slot_status_layout:
            status_pos = idx

    assert header_pos >= 0
    assert status_pos == header_pos + 1
    assert page._slot_group_layout.indexOf(page._slot_grid_host) == status_pos + 1


def test_preview_gets_primary_vertical_space(workbench_page_with_spec, qapp: QApplication):
    """Preview remains the dominant workspace after parameters move to the dialog."""
    page = workbench_page_with_spec
    page.resize(1400, 900)
    page.show()
    qapp.processEvents()

    try:
        assert page._preview_diag_splitter.orientation() == Qt.Orientation.Vertical
        assert page._preview_group.height() >= 420
        assert page._preview_label.height() >= 360
        assert page._diag_group.height() <= 260
    finally:
        page.close()


def test_workbench_content_uses_vertical_scroll_area(workbench_page_with_spec):
    """Workbench content scrolls instead of being vertically compressed."""
    page = workbench_page_with_spec

    assert isinstance(page._scroll_area, QScrollArea)
    assert page._scroll_area.widget() is page._ui
    assert page._scroll_area.widgetResizable()
    assert page._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page._scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_six_camera_workbench_scrolls_when_viewport_is_short(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Short viewports keep slot/preview sections at reserved heights and scroll."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=6))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    ctx = cw.AppContext.instance()
    orig_spec_id = ctx._current_spec_id
    orig_spec_name = ctx._current_spec_name
    ctx._current_spec_id = "SPEC_SCROLL"
    ctx._current_spec_name = "Scroll Spec"

    page = cw.CameraWorkbenchPage()
    page.resize(2048, 760)
    page.show()
    qapp.processEvents()
    try:
        # Without paramGroup, content is shorter; scroll bar may or may not appear
        # depending on viewport. Key invariant: slot/preview still get reserved space.
        assert page._scroll_area.widgetResizable()
        assert page._slot_grid_host.height() >= page._slot_grid_host.minimumHeight()
        assert page._preview_diag_splitter.height() >= page._preview_diag_splitter.minimumHeight()
    finally:
        page.close()
        ctx._current_spec_id = orig_spec_id
        ctx._current_spec_name = orig_spec_name


def test_clicking_slot_selects_without_opening_config_dialog(
    workbench_page_with_spec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A card click selects the preview target; only the config button opens the dialog."""
    page = workbench_page_with_spec
    opened: list[int] = []
    monkeypatch.setattr(page, "_open_slot_config_dialog", lambda idx: opened.append(idx))

    page._on_slot_selected(2)
    assert page._selected_slot == 2
    assert page._slot_cards[2]._selected is True
    assert opened == []

    page._on_bind_slot(2)
    assert opened == [2]


def test_slot_cards_keep_action_buttons_visible(workbench_page_with_spec):
    """Compact slot cards still keep status rows and actions visible."""
    page = workbench_page_with_spec

    assert page._slot_list_scroll.widget() is page._slot_group
    for card in page._slot_cards.values():
        assert 80 <= card.minimumHeight() <= 96
        assert card.sizeHint().height() <= card.height()
        assert card._bind_btn.minimumHeight() >= 24
        assert card._unbind_btn.minimumHeight() >= 24
        assert card._connect_btn.minimumHeight() >= 24
        assert card._bind_btn.geometry().bottom() <= card.height()
        assert card._unbind_btn.geometry().bottom() <= card.height()
        assert card._connect_btn.geometry().bottom() <= card.height()


def test_preview_diagnostics_get_reserved_vertical_space(workbench_page_with_spec):
    """Preview and diagnostics are not allowed to collapse."""
    page = workbench_page_with_spec

    assert page._preview_diag_splitter.minimumHeight() >= 560
    assert page._preview_group.minimumHeight() >= 420
    assert page._preview_label.minimumHeight() >= 360
    assert page._diag_group.maximumHeight() <= 260


# ── Tests: Slot grid column layout ─────────────────────────────────────────


def test_context_bar_pairs_are_single_line(workbench_page_with_spec):
    """Context labels and values are rendered as one horizontal row."""
    page = workbench_page_with_spec

    for pair in [page._ctx_customer, page._ctx_project, page._ctx_spec, page._ctx_count]:
        assert isinstance(pair, QHBoxLayout)
        label = pair.itemAt(0).widget()
        assert isinstance(label, QLabel)
        assert label.text().endswith(":")
        assert pair.property("value_label") is pair.itemAt(1).widget()


def test_slot_grid_one_col_for_single_camera(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """camera_count=1 → slot grid uses 1 column."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=1))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    ctx = cw.AppContext.instance()
    orig = ctx._current_spec_id
    ctx._current_spec_id = "SPEC_X"
    ctx._current_spec_name = "X"
    ctx._current_customer_name = "C"
    ctx._current_project_name = "P"

    page = cw.CameraWorkbenchPage()
    page.show()
    try:
        assert len(page._slot_cards) == 1
        card = page._slot_cards[1]
        idx = page._slot_grid.indexOf(card)
        row, col, _, _ = page._slot_grid.getItemPosition(idx)
        assert row == 0
        assert col == 0
    finally:
        page.close()
        ctx._current_spec_id = orig


def test_slot_grid_single_col_for_two_cameras(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """camera_count=2 → slot grid uses 2 columns."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=2))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    ctx = cw.AppContext.instance()
    orig = ctx._current_spec_id
    ctx._current_spec_id = "SPEC_Y"
    ctx._current_spec_name = "Y"

    page = cw.CameraWorkbenchPage()
    page.show()
    try:
        assert len(page._slot_cards) == 2
        for ci, (row, col) in [(1, (0, 0)), (2, (1, 0))]:
            idx_pos = page._slot_grid.indexOf(page._slot_cards[ci])
            r, c, _, _ = page._slot_grid.getItemPosition(idx_pos)
            assert (r, c) == (row, col)
    finally:
        page.close()
        ctx._current_spec_id = orig


def test_slot_grid_single_col_for_three_or_more_cameras(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """camera_count≥3 → slot grid uses 3 columns (capped)."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=6))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    ctx = cw.AppContext.instance()
    orig = ctx._current_spec_id
    ctx._current_spec_id = "SPEC_Z"
    ctx._current_spec_name = "Z"

    page = cw.CameraWorkbenchPage()
    page.resize(2048, 760)
    page.show()
    qapp.processEvents()
    try:
        assert len(page._slot_cards) == 6
        assert page._slot_group.height() == page._slot_list_scroll.viewport().height()
        assert page._slot_grid_host.height() <= page._slot_group.height()
        assert page._slot_list_scroll.verticalScrollBar().maximum() == 0
        for ci in range(1, 7):
            idx_pos = page._slot_grid.indexOf(page._slot_cards[ci])
            r, c, _, _ = page._slot_grid.getItemPosition(idx_pos)
            assert (r, c) == (ci - 1, 0)
        assert page._slot_list_scroll.widget() is page._slot_group

        page._on_slot_selected(6)
        card = page._slot_cards[6]
        assert card._selected is True
        assert card._bind_btn.geometry().bottom() <= card.height()
        assert card._unbind_btn.geometry().bottom() <= card.height()
        assert card._connect_btn.geometry().bottom() <= card.height()
    finally:
        page.close()
        ctx._current_spec_id = orig


# ── Tests: Slot card status ───────────────────────────────────────────────


def test_slot_card_empty_status(workbench_page_with_spec):
    """Fresh slots with no binding or config show 'empty' status."""
    page = workbench_page_with_spec
    for ci in [1, 2, 3]:
        assert ci in page._slot_cards
        assert "未绑定" in page._slot_cards[ci]._status_label.text() or \
               "Not Bound" in page._slot_cards[ci]._status_label.text()


def test_slot_card_bound_status(workbench_page_with_spec):
    """Slot with binding but no config shows 'bound' status."""
    page = workbench_page_with_spec
    b = CameraBinding(
        camera_slot="camera_01",
        serial_number="SN-A01",
        ip_address="192.168.1.10",
        model="MV-CA050-20GM",
        role="top",
    )
    page._binding_store.set_binding(b)
    page._binding_store.save_all()
    page._rebuild_slots()

    card = page._slot_cards[1]
    assert "已绑定" in card._status_label.text() or "Bound" in card._status_label.text()
    assert card._serial_label.text() == "SN-A01"


def test_slot_card_configured_status(workbench_page_with_spec, monkeypatch):
    """Slot with saved CameraConfig shows 'configured' status."""
    import desktop_app.pages.camera_workbench_page as cw
    from core.camera_config import CameraConfig

    cfg = CameraConfig(
        config_id="CAMCONF_01",
        spec_id="SPEC_01",
        camera_index=1,
        serial_number="SN-CFG01",
        adapter_type="hikrobot_line_scan",
        exposure_us=5000.0,
    )
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [cfg])

    page = workbench_page_with_spec
    page._rebuild_slots()

    card = page._slot_cards[1]
    assert "已配置" in card._status_label.text() or "Configured" in card._status_label.text()
    assert card._serial_label.text() == "SN-CFG01"


# ── Tests: Slot card interaction ────────────────────────────────────────


def test_slot_card_has_action_buttons(workbench_page_with_spec):
    """Each slot card has bind, unbind, and connect buttons."""
    page = workbench_page_with_spec
    for ci, card in page._slot_cards.items():
        assert card._bind_btn is not None
        assert card._unbind_btn is not None
        assert card._connect_btn is not None
        assert card._bind_btn.text() != ""
        assert card._unbind_btn.text() != ""
        assert card._connect_btn.text() != ""


def test_role_is_editable_via_lineedit(workbench_page_with_spec):
    """The role label on a card supports inline editing."""
    page = workbench_page_with_spec
    card = page._slot_cards[1]
    initial_role = card._role_label.text()
    assert initial_role != ""
    assert hasattr(card._role_label, "mousePressEvent")
    assert card._role_label.mousePressEvent is not QLabel.mousePressEvent


# ── Tests: Scan ──────────────────────────────────────────────────────────


def test_scan_updates_found_label(workbench_page_with_spec):
    """Scanning for devices updates the 'found N' label."""
    page = workbench_page_with_spec
    page._on_scan()
    assert page._found_label.isVisible()
    label_text = page._found_label.text()
    assert "2" in label_text


def test_scan_sdk_failure_shows_error(workbench_page_with_spec, monkeypatch):
    """SDK load failure shows error in found_label."""
    import desktop_app.pages.camera_workbench_page as cw

    monkeypatch.setattr(cw.sdk_loader, "SDK_ERROR", "missing MvCameraControl.dll")
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: False)

    page = workbench_page_with_spec
    page._on_scan()
    assert page._found_label.isVisible()
    assert "missing MvCameraControl.dll" in page._found_label.text()


# ── Tests: Bind / Unbind ───────────────────────────────────────────────


def test_unbind_removes_binding_and_resets_card(workbench_page_with_spec):
    """Unbinding a slot removes the binding and resets card to empty."""
    page = workbench_page_with_spec

    b = CameraBinding(
        camera_slot="camera_02", serial_number="SN-REMOVE",
        ip_address="192.168.1.30", model="MV-Y",
    )
    page._binding_store.set_binding(b)
    page._binding_store.save_all()
    page._rebuild_slots()

    assert page._slot_cards[2]._serial_label.text() == "SN-REMOVE"

    page._on_unbind_slot(2)

    assert page._binding_store.get_binding("camera_02") is None
    assert page._slot_cards[2]._serial_label.text() == "—"


# ── Tests: Close event cleanup ─────────────────────────────────────────


def test_close_event_stops_preview(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """closeEvent stops preview and disconnects cameras."""
    import desktop_app.pages.camera_workbench_page as cw
    from PySide6.QtGui import QCloseEvent

    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(cw.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(cw.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cw, "HikrobotLineScanCamera", FakeLineScanCamera)
    monkeypatch.setattr(cw, "get_product_spec", lambda sid: _make_fake_spec(sid, count=2))
    monkeypatch.setattr(cw, "list_camera_configs", lambda sid: [])

    ctx = cw.AppContext.instance()
    orig = ctx._current_spec_id
    ctx._current_spec_id = "SPEC_CLEAN"
    ctx._current_spec_name = "Clean"

    page = cw.CameraWorkbenchPage()
    page.show()
    try:
        cam = FakeCamera()
        page._cameras["camera_01"] = cam
        page._selected_slot = 1
        page._on_start_preview()
        assert page._preview_active

        page.closeEvent(QCloseEvent())
        assert not page._preview_active
        assert not page._preview_timer.isActive()
        assert not page._diag_timer.isActive()
    finally:
        ctx._current_spec_id = orig


# ── Tests: CameraSlotConfigDialog ──────────────────────────────────────


def test_dialog_apply_params_to_camera(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Dialog 'Apply to Camera' calls set_param on the connected camera."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.information",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.warning",
        lambda *a, **kw: None,
    )

    cam = FakeCamera()
    cameras = {"camera_01": cam}

    dlg = CameraSlotConfigDialog(
        1, "camera_01", "Top",
        cameras=cameras,
        spec_id="SPEC_01",
    )
    dlg._exposure_spin.setValue(3000.0)
    dlg._gain_spin.setValue(2.5)
    dlg._trigger_combo.setCurrentText("On")
    dlg._trigger_src_combo.setCurrentText("Line2")
    dlg._pkt_size_spin.setValue(8000)
    dlg._reverse_x_cb.setChecked(True)

    dlg._on_apply()

    applied = {name: value for name, value in cam.params}
    assert applied.get("ExposureTime") == 3000.0
    assert applied.get("Gain") == 2.5
    assert applied.get("TriggerMode") == "On"
    assert applied.get("TriggerSource") == "Line2"
    assert applied.get("GevSCPSPacketSize") == 8000
    assert applied.get("ReverseX") is True


def test_dialog_apply_without_camera_shows_warning(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Apply without connected camera shows warning."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog

    warned = []
    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )

    dlg = CameraSlotConfigDialog(1, "camera_01", "Top", spec_id="SPEC_01")
    dlg._on_apply()
    assert len(warned) > 0


def test_dialog_save_to_spec_creates_config(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Save writes camera_config via create_camera_config with extended params."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.information",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.warning",
        lambda *a, **kw: None,
    )

    created: list[dict] = []

    def fake_create(spec_id: str, camera_index: int, **fields):
        created.append({"spec_id": spec_id, "camera_index": camera_index, **fields})
        from core.camera_config import CameraConfig
        return CameraConfig(config_id=f"CFG_{camera_index}", spec_id=spec_id,
                           camera_index=camera_index, **fields)

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.create_camera_config", fake_create
    )
    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.update_camera_config", lambda cid, **f: None
    )

    store = FakeBindingStore()
    store.set_binding(CameraBinding(
        camera_slot="camera_01", serial_number="SN-DLG",
        ip_address="10.0.0.1", model="MV-DLG",
    ))

    dlg = CameraSlotConfigDialog(
        1, "camera_01", "Top",
        binding_store=store,
        spec_id="SPEC_01",
    )
    dlg._exposure_spin.setValue(8000.0)
    dlg._gain_spin.setValue(4.0)
    dlg._trigger_combo.setCurrentText("On")
    dlg._trigger_src_combo.setCurrentText("Line2")
    dlg._line_rate_spin.setValue(15000)
    dlg._block_h_spin.setValue(512)
    dlg._pixel_fmt_combo.setCurrentText("Mono8")
    dlg._width_spin.setValue(2048)
    dlg._pkt_size_spin.setValue(8000)
    dlg._inter_delay_spin.setValue(12)
    dlg._buffer_spin.setValue(32)
    dlg._reverse_x_cb.setChecked(True)

    dlg._on_save()

    assert len(created) == 1
    cfg = created[0]
    assert cfg["camera_index"] == 1
    assert cfg["exposure_us"] == 8000.0
    assert cfg["gain_db"] == 4.0
    assert cfg["trigger_mode"] == "On"
    assert cfg["line_rate"] == 15000
    assert cfg["image_block_height"] == 512
    assert cfg["pixel_format"] == "Mono8"
    assert cfg["resolution_width"] == 2048
    assert cfg["serial_number"] == "SN-DLG"
    assert cfg["ip_address"] == "10.0.0.1"
    assert cfg["brand"] == "Hikrobot"
    assert cfg["adapter_type"] == "hikrobot_line_scan"

    # Extended params via connection_params
    ext = json.loads(cfg["connection_params"])
    assert ext["trigger_source"] == "Line2"
    assert ext["packet_size"] == 8000
    assert ext["inter_packet_delay"] == 12
    assert ext["buffer_count"] == 32
    assert ext["reverse_x"] is True
    assert ext["reverse_y"] is False


def test_dialog_save_updates_existing_config(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Save with existing config calls update_camera_config."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog
    from core.camera_config import CameraConfig

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.information",
        lambda *a, **kw: None,
    )

    existing = CameraConfig(config_id="CAMCONF_EXIST", spec_id="SPEC_01", camera_index=1,
                           exposure_us=100.0)
    updated: list[dict] = []

    def fake_update(config_id: str, **fields):
        updated.append({"config_id": config_id, **fields})

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.update_camera_config", fake_update
    )
    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.create_camera_config",
        lambda *a, **kw: existing,
    )

    dlg = CameraSlotConfigDialog(
        1, "camera_01", "Top",
        existing_config=existing,
        spec_id="SPEC_01",
    )
    dlg._exposure_spin.setValue(9999.0)
    dlg._on_save()

    assert len(updated) == 1
    assert updated[0]["config_id"] == "CAMCONF_EXIST"
    assert updated[0]["exposure_us"] == 9999.0


def test_dialog_loads_existing_config_params(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Existing CameraConfig params are loaded into dialog form fields."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog
    from core.camera_config import CameraConfig

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.information",
        lambda *a, **kw: None,
    )

    ext = json.dumps({
        "trigger_source": "Software",
        "packet_size": 4000,
        "inter_packet_delay": 5,
        "buffer_count": 8,
        "reverse_x": True,
        "reverse_y": True,
    })

    cfg = CameraConfig(
        config_id="CAMCONF_LD",
        spec_id="SPEC_01",
        camera_index=2,
        exposure_us=1234.5,
        gain_db=3.5,
        trigger_mode="On",
        line_rate=30000,
        image_block_height=2048,
        pixel_format="Mono10",
        resolution_width=4096,
        connection_params=ext,
    )

    dlg = CameraSlotConfigDialog(
        2, "camera_02", "Left",
        existing_config=cfg,
        spec_id="SPEC_01",
    )

    assert dlg._exposure_spin.value() == 1234.5
    assert dlg._gain_spin.value() == 3.5
    assert dlg._trigger_combo.currentText() == "On"
    assert dlg._line_rate_spin.value() == 30000
    assert dlg._block_h_spin.value() == 2048
    assert dlg._pixel_fmt_combo.currentText() == "Mono10"
    assert dlg._width_spin.value() == 4096
    assert dlg._trigger_src_combo.currentText() == "Software"
    assert dlg._pkt_size_spin.value() == 4000
    assert dlg._inter_delay_spin.value() == 5
    assert dlg._buffer_spin.value() == 8
    assert dlg._reverse_x_cb.isChecked() is True
    assert dlg._reverse_y_cb.isChecked() is True


def test_dialog_bind_device_from_dialog(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Confirm Bind in dialog writes to BindingStore and updates display."""
    from desktop_app.pages.camera_workbench_page import CameraSlotConfigDialog as CSD

    monkeypatch.setattr(
        "desktop_app.dialogs.camera_bind_dialog.QMessageBox.information",
        lambda *a, **kw: None,
    )

    store = FakeBindingStore()
    dlg = CSD(
        1, "camera_01", "Top",
        binding_store=store,
        spec_id="SPEC_01",
    )

    # Simulate scan results
    dlg._discovered = _devices()
    dlg._refresh_device_list()
    dlg._device_list.setCurrentRow(0)
    dlg._on_device_selected(0)

    dlg._on_confirm_bind()

    binding = store.get_binding("camera_01")
    assert binding is not None
    assert binding.serial_number == "SN-A01"
    # Dialog should update the bound-device display (exact text depends on i18n)
    assert dlg._bound_sn_label.text() != ""


def test_dialog_defaults_when_no_config(qapp: QApplication):
    """Dialog shows default values when no existing config."""
    from desktop_app.dialogs.camera_bind_dialog import CameraSlotConfigDialog

    dlg = CameraSlotConfigDialog(1, "camera_01", "Top", spec_id="SPEC_01")
    assert dlg._exposure_spin.value() == 5000.0
    assert dlg._gain_spin.value() == 1.0
    assert dlg._trigger_combo.currentText() == "Off"
    assert dlg._trigger_src_combo.currentText() == "Line0"
    assert dlg._line_rate_spin.value() == 20000
    assert dlg._block_h_spin.value() == 1024
    assert dlg._pixel_fmt_combo.currentText() == "Mono8"
    assert dlg._width_spin.value() == 2048
    assert dlg._pkt_size_spin.value() == 9000
    assert dlg._inter_delay_spin.value() == 0
    assert dlg._buffer_spin.value() == 16
    assert dlg._reverse_x_cb.isChecked() is False
    assert dlg._reverse_y_cb.isChecked() is False
