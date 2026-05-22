"""Verify LineScanDevice ABC enforces interface contract."""
import pytest

from src.device.camera.line_scan.interface import LineScanDevice


def test_cannot_instantiate_abc_directly():
    """LineScanDevice is abstract and cannot be instantiated."""
    with pytest.raises(TypeError):
        LineScanDevice()  # type: ignore[abstract]


class PartialImpl(LineScanDevice):
    """Missing all abstract methods — should not be instantiable."""

    @staticmethod
    def enumerate_devices():
        return []


def test_partial_implementation_still_abstract():
    """Implementing only some methods is not enough."""
    with pytest.raises(TypeError):
        PartialImpl()  # type: ignore[abstract]


def test_full_implementation_instantiates():
    """A class implementing all abstract methods can be created."""

    class FullImpl(LineScanDevice):
        @staticmethod
        def enumerate_devices():
            return []

        def open(self, serial_number):
            return True

        def close(self):
            pass

        def start_grabbing(self):
            return True

        def stop_grabbing(self):
            pass

        def get_status(self):
            from src.device.camera.line_scan.types import CameraStatus

            return CameraStatus(connected=True)

        def set_param(self, name, value):
            pass

        def get_param(self, name):
            return None

        def register_line_callback(self, callback):
            pass

        def unregister_line_callback(self):
            pass

    cam = FullImpl()
    assert cam is not None
