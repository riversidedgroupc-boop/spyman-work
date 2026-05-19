"""Tests for camera adapter factory and registry."""
import pytest

from camera_adapters import (
    create_adapter, register_adapter, available_adapter_types,
)
from camera_adapters.base import BaseCameraAdapter
from camera_adapters.folder_watcher import FolderWatcherCameraAdapter


def test_create_folder_watcher():
    adapter = create_adapter("folder_watcher")
    assert isinstance(adapter, FolderWatcherCameraAdapter)
    assert isinstance(adapter, BaseCameraAdapter)


def test_create_unknown_adapter_raises():
    with pytest.raises(ValueError, match="Unknown camera adapter type"):
        create_adapter("nonexistent_adapter_v6")


def test_available_adapter_types_includes_folder_watcher():
    types = available_adapter_types()
    assert "folder_watcher" in types
    assert isinstance(types, list)
    assert types == sorted(types)


def test_register_custom_adapter():
    class CustomAdapter(BaseCameraAdapter):
        def list_devices(self) -> list[dict]:
            return [{"id": "dev1", "name": "Custom Device"}]

        def connect(self, params=None):
            return True

        def disconnect(self):
            pass

        def start_acquisition(self):
            pass

        def stop_acquisition(self):
            pass

        def get_frame(self):
            return None

        def get_status(self) -> dict:
            return {"connected": True}

    register_adapter("custom_test", CustomAdapter)
    assert "custom_test" in available_adapter_types()
    adapter = create_adapter("custom_test")
    assert isinstance(adapter, CustomAdapter)


def test_create_multiple_adapters_independent():
    """Each create_adapter call returns a new instance."""
    a1 = create_adapter("folder_watcher")
    a2 = create_adapter("folder_watcher")
    assert a1 is not a2
    a1.connect({"watch_dir": "/tmp"})
    assert a2.get_status().get("connected") is False  # not affected by a1
