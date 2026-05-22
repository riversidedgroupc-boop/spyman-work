"""Tests for CameraManager."""
import pytest
from src.device.camera.manager.camera_manager import CameraManager
from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera


@pytest.fixture
def manager():
    mgr = CameraManager()
    for i in range(1, 4):
        cam = VirtualLineScanCamera(width=512, line_rate=1000)
        cam.open(f"VS_{i:03d}")
        mgr.add_camera(f"Camera_0{i}", cam, enabled=True)
    return mgr


def test_camera_count(manager):
    assert manager.camera_count == 3


def test_get_enabled_ids(manager):
    assert manager.get_enabled_camera_ids() == ["Camera_01", "Camera_02", "Camera_03"]


def test_disable_camera(manager):
    manager.set_enabled("Camera_02", False)
    assert manager.camera_count == 2


def test_start_all(manager):
    results = manager.start_all()
    assert all(results.values())
    for s in manager.get_all_status():
        assert s.grabbing
    manager.stop_all()


def test_disconnect_all(manager):
    manager.disconnect_all()
    for s in manager.get_all_status():
        assert not s.connected


def test_get_camera(manager):
    assert manager.get_camera("Camera_01") is not None
    assert manager.get_camera("Camera_99") is None


def test_remove_camera(manager):
    manager.remove_camera("Camera_03")
    assert manager.camera_count == 2


def test_max_cameras():
    mgr = CameraManager()
    for i in range(6):
        cam = VirtualLineScanCamera()
        cam.open(f"V_{i}")
        mgr.add_camera(f"Camera_{i+1:02d}", cam)
    with pytest.raises(RuntimeError):
        mgr.add_camera("Camera_07", VirtualLineScanCamera())
