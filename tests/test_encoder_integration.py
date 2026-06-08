"""Tests for encoder integration with acquisition pipeline."""
import threading

import pytest

from tests import wait_for_condition

from runtime.frame_buffer import FrameBuffer
from runtime.acquisition_pipeline import AcquisitionPipeline
from runtime.encoder_reader import SimulatedEncoderReader, RS422EncoderReader


class StubCameraAdapter:
    """Simple stub that returns a few frames then stops."""

    def __init__(self, frame_count: int = 5):
        self._count = 0
        self._running = False
        self._connected = False
        self._max = frame_count

    def connect(self, params=None):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def start_acquisition(self):
        self._running = True

    def stop_acquisition(self):
        self._running = False

    def get_frame(self):
        if not self._running or self._count >= self._max:
            return None
        import numpy as np
        self._count += 1
        return (np.random.rand(40, 60, 3) * 255).astype("uint8")

    def get_status(self) -> dict:
        return {"connected": self._connected, "frame_count": self._count}


def test_acquisition_pipeline_set_encoder():
    """Encoder can be attached to the acquisition pipeline."""
    acq = AcquisitionPipeline(buffer_size=30)
    encoder = SimulatedEncoderReader()
    encoder.connect({"line_speed_mpm": 60.0, "pulses_per_meter": 500.0})

    acq.set_encoder(encoder)
    assert acq.get_encoder() is encoder


def test_acquisition_pipeline_get_status_includes_encoder_position():
    """get_status() reports encoder position when encoder is set."""
    acq = AcquisitionPipeline(buffer_size=30)
    acq.add_camera("cam1", StubCameraAdapter(frame_count=3))

    encoder = SimulatedEncoderReader()
    encoder.connect({"line_speed_mpm": 60.0, "pulses_per_meter": 500.0})
    acq.set_encoder(encoder)

    acq.start()
    wait_for_condition(lambda: any(
        "encoder_position_m" in s for s in acq.get_status()
    ), timeout=2.0)
    acq.stop()

    statuses = acq.get_status()
    assert len(statuses) >= 1
    assert "encoder_position_m" in statuses[0]
    assert isinstance(statuses[0]["encoder_position_m"], float)


def test_acquisition_pipeline_attaches_position_to_frames():
    """Frames stored in buffer include position_meter when encoder is set."""
    acq = AcquisitionPipeline(buffer_size=30)
    acq.add_camera("cam1", StubCameraAdapter(frame_count=3))

    encoder = SimulatedEncoderReader()
    encoder.connect({"line_speed_mpm": 120.0, "pulses_per_meter": 1000.0})
    acq.set_encoder(encoder)

    acq.start()
    wait_for_condition(lambda: acq.get_buffer().size() > 0, timeout=2.0)
    acq.stop()

    buf = acq.get_buffer()
    frames_with_pos = 0
    while buf.size() > 0:
        frame = buf.get()
        if frame and "position_meter" in frame:
            frames_with_pos += 1
            assert isinstance(frame["position_meter"], float)
            assert frame["position_meter"] >= 0

    assert frames_with_pos > 0, "Expected frames to have position_meter"


def test_acquisition_pipeline_no_encoder_no_position():
    """Without encoder, frames get position_meter defaulting to 0.0."""
    acq = AcquisitionPipeline(buffer_size=30)
    acq.add_camera("cam1", StubCameraAdapter(frame_count=3))

    acq.start()
    wait_for_condition(lambda: acq.get_buffer().size() > 0, timeout=2.0)
    acq.stop()

    buf = acq.get_buffer()
    frame = buf.get()
    if frame:
        # position_meter always present (default 0.0) after Phase 4 sampling controller integration
        assert frame.get("position_meter") == 0.0


def test_simulated_encoder_position_increases_over_acquisition():
    """Encoder position increases during acquisition loop."""
    encoder = SimulatedEncoderReader()
    encoder.connect({"line_speed_mpm": 120.0, "pulses_per_meter": 500.0})

    p1 = encoder.read_position_meter()
    wait_for_condition(lambda: encoder.read_position_meter() > p1, timeout=2.0)
    p2 = encoder.read_position_meter()

    assert p2 > p1, f"Position should increase: {p1:.3f} -> {p2:.3f}"
    # At 120 mpm = 2 m/s, expect some meaningful distance
    assert (p2 - p1) > 0


def test_rs422_stub_always_zero():
    """RS422 stub returns zeros and connects without issue."""
    encoder = RS422EncoderReader()
    assert encoder.connect({})
    assert encoder.read_position_meter() == 0.0
    assert encoder.read_speed_mpm() == 0.0
    assert encoder.get_status()["connected"] is True
    encoder.disconnect()
    assert encoder.get_status()["connected"] is False
