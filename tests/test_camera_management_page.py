"""Behavior tests for the camera management page."""
from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QApplication

from src.device.camera.binding_store import CameraBinding
from src.device.camera.line_scan.types import DeviceInfo, CameraStatus


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def page(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    import desktop_app.pages.camera_management_page as cm

    monkeypatch.setattr(cm.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(cm.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(cm.QMessageBox, "critical", lambda *args, **kwargs: None)

    widget = cm.CameraManagementPage()
    yield widget
    widget.close()


class FakeBindingStore:
    def __init__(self) -> None:
        self.bindings: dict[str, CameraBinding] = {}
        self.load_count = 0

    def load_all(self) -> list[CameraBinding]:
        self.load_count += 1
        return list(self.bindings.values())

    def save_all(self, bindings: list[CameraBinding] | None = None) -> None:
        if bindings is not None:
            for binding in bindings:
                self.bindings[binding.camera_slot] = binding

    def get_binding(self, slot: str) -> CameraBinding | None:
        return self.bindings.get(slot)

    def set_binding(self, binding: CameraBinding) -> None:
        self.bindings[binding.camera_slot] = binding

    def remove_binding(self, slot: str) -> None:
        self.bindings.pop(slot, None)

    def get_serial_map(self) -> dict[str, str]:
        return {
            slot: binding.serial_number
            for slot, binding in self.bindings.items()
            if binding.enabled and binding.serial_number
        }


class FakeCamera:
    opened_serials: list[str] = []

    def __init__(self) -> None:
        self.params: list[tuple[str, object]] = []
        self.connected = False
        self.grabbing = False

    def open(self, serial_number: str) -> bool:
        self.opened_serials.append(serial_number)
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


def _devices() -> list[DeviceInfo]:
    return [
        DeviceInfo(model="MV-A", serial_number="SN-A", ip_address="192.168.1.10", mac_address="AA"),
        DeviceInfo(model="MV-B", serial_number="SN-B", ip_address="192.168.1.11", mac_address="BB"),
    ]


def _adapter_rows(page) -> list[list[str]]:
    table = page._adapter_table
    return [
        [
            table.item(row, col).text() if table.item(row, col) is not None else ""
            for col in range(table.columnCount())
        ]
        for row in range(table.rowCount())
    ]


class FakeLineScanCamera(FakeCamera):
    devices: list[DeviceInfo] = []

    @staticmethod
    def enumerate_devices() -> list[DeviceInfo]:
        return list(FakeLineScanCamera.devices)


def test_adapter_table_uses_real_hikrobot_line_scan_path(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import desktop_app.pages.camera_management_page as cm

    FakeLineScanCamera.devices = _devices()
    monkeypatch.setattr(cm.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cm, "HikrobotLineScanCamera", FakeLineScanCamera)

    widget = cm.CameraManagementPage()
    try:
        rows = _adapter_rows(widget)

        assert any(row[1] == "hikrobot_line_scan" and "SN-A" in row[3] for row in rows)
        assert all("HikvisionMVSAdapter" not in row and "hikvision_mvs" not in row for row in rows)
    finally:
        widget.close()


def test_adapter_table_height_fits_registered_rows(page) -> None:
    table = page._adapter_table
    expected_height = (
        table.horizontalHeader().height()
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + table.frameWidth() * 2
    )

    assert table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert table.minimumHeight() >= expected_height


def test_scan_refreshes_hikrobot_adapter_devices(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import desktop_app.pages.camera_management_page as cm

    FakeLineScanCamera.devices = []
    monkeypatch.setattr(cm.sdk_loader, "load_sdk", lambda: True)
    monkeypatch.setattr(cm, "HikrobotLineScanCamera", FakeLineScanCamera)

    widget = cm.CameraManagementPage()
    try:
        assert not any("SN-A" in row[3] for row in _adapter_rows(widget))

        FakeLineScanCamera.devices = _devices()
        widget._on_scan()

        assert any(row[1] == "hikrobot_line_scan" and "SN-A" in row[3] for row in _adapter_rows(widget))
    finally:
        widget.close()


def test_discovery_controls_are_grouped_into_clear_rows(page) -> None:
    assert page._discovery_grid.rowCount() >= 2
    assert page._slot_status_grid.rowCount() == 2
    assert page._slot_status_grid.columnCount() == 3


def test_parameter_controls_use_horizontal_rows(page) -> None:
    """Parameter controls are laid out in rows, not a grid (post-refactor)."""
    # _param_group should exist (former _param_grid was replaced with row-based layouts)
    assert page._param_group is not None
    assert hasattr(page, "_exposure_spin")
    assert hasattr(page, "_gain_spin")
    assert hasattr(page, "_line_rate_spin")
    assert hasattr(page, "_width_spin")
    assert hasattr(page, "_reverse_x_cb")
    assert hasattr(page, "_apply_btn")


def test_bind_connect_uses_selected_discovered_device(
    page, monkeypatch: pytest.MonkeyPatch
) -> None:
    import desktop_app.pages.camera_management_page as cm

    FakeCamera.opened_serials = []
    monkeypatch.setattr(cm, "HikrobotLineScanCamera", FakeCamera)
    store = FakeBindingStore()
    page._binding_store = store
    page._discovered = _devices()
    page._refresh_device_choices()
    page._device_combo.setCurrentIndex(1)

    page._on_bind_connect()

    assert FakeCamera.opened_serials == ["SN-B"]
    assert store.get_binding("camera_01").serial_number == "SN-B"


def test_apply_params_sends_all_visible_parameter_controls(page) -> None:
    cam = FakeCamera()
    page._cameras["camera_01"] = cam
    page._slot_combo.setCurrentText("camera_01")
    page._block_h_spin.setValue(1536)
    page._pkt_size_spin.setValue(9000)
    page._inter_delay_spin.setValue(12)
    page._buffer_spin.setValue(32)

    page._on_apply_params()

    applied_names = {name for name, _value in cam.params}
    assert {
        "AcquisitionMode",
        "Height",
        "GevSCPSPacketSize",
        "GevSCPD",
        "BufferCount",
    }.issubset(applied_names)


def test_show_event_does_not_reload_bindings_after_initial_load(page) -> None:
    store = FakeBindingStore()
    page._binding_store = store

    page.showEvent(QShowEvent())

    assert store.load_count == 0


def test_scan_reports_current_sdk_loader_error(page, monkeypatch: pytest.MonkeyPatch) -> None:
    import desktop_app.pages.camera_management_page as cm

    monkeypatch.setattr(cm.sdk_loader, "SDK_ERROR", "missing MvCameraControl.dll")
    monkeypatch.setattr(cm.sdk_loader, "load_sdk", lambda: False)

    page._on_scan()

    assert "missing MvCameraControl.dll" in page._sdk_label.text()
