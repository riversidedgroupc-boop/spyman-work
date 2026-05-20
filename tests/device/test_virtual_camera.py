"""Tests for VirtualLineScanCamera."""
import time

import numpy as np

from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera


def test_enumerate_returns_device():
    devices = VirtualLineScanCamera.enumerate_devices()
    assert len(devices) == 1
    assert devices[0].vendor == "Virtual"


def test_open_and_close():
    cam = VirtualLineScanCamera()
    assert cam.open("TEST_001")
    assert cam.get_status().connected
    cam.close()
    assert not cam.get_status().connected


def test_start_and_stop_grabbing():
    cam = VirtualLineScanCamera(width=1024, line_rate=1000.0)
    cam.open("TEST_002")
    assert cam.start_grabbing()
    assert cam.get_status().grabbing
    time.sleep(0.05)
    cam.stop_grabbing()
    assert not cam.get_status().grabbing


def test_line_callback_receives_packets():
    cam = VirtualLineScanCamera(width=512, line_rate=5000.0)
    received: list = []

    def on_line(packet):
        received.append(packet)

    cam.open("TEST_003")
    cam.register_line_callback(on_line)
    cam.start_grabbing()
    time.sleep(0.1)
    cam.stop_grabbing()

    assert len(received) > 10
    pkt = received[0]
    assert pkt.width == 512
    assert pkt.height == 1
    assert pkt.line_data.shape == (1, 512)
    assert pkt.line_data.dtype == np.uint8


def test_set_and_get_param():
    cam = VirtualLineScanCamera()
    cam.open("TEST_004")
    cam.set_param("ExposureTime", 50.0)
    assert cam.get_param("ExposureTime") == 50.0
    cam.set_param("LineRate", 10000.0)
    assert cam.get_param("LineRate") == 10000.0
