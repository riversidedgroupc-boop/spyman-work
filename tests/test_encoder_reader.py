"""Tests for encoder reader abstraction."""
import time

import pytest

from runtime.encoder_reader import SimulatedEncoderReader, RS422EncoderReader


def test_simulated_encoder_connect():
    enc = SimulatedEncoderReader()
    assert enc.connect({"line_speed_mpm": 60.0, "pulses_per_meter": 500.0})
    status = enc.get_status()
    assert status["connected"] is True
    assert status["speed_mpm"] == 60.0
    assert status["pulses_per_meter"] == 500.0


def test_simulated_encoder_position_increases():
    enc = SimulatedEncoderReader()
    enc.connect({"line_speed_mpm": 120.0})
    pos1 = enc.read_position_meter()
    time.sleep(0.3)
    pos2 = enc.read_position_meter()
    assert pos2 > pos1, f"Expected position to increase: {pos1} -> {pos2}"


def test_simulated_encoder_reset():
    enc = SimulatedEncoderReader()
    enc.connect({"line_speed_mpm": 60.0})
    time.sleep(0.2)
    pos = enc.read_position_meter()
    assert pos > 0
    enc.reset()
    assert enc.read_position_meter() < pos


def test_simulated_encoder_disconnect():
    enc = SimulatedEncoderReader()
    enc.connect({})
    assert enc.get_status()["connected"]
    enc.disconnect()
    assert not enc.get_status()["connected"]


def test_rs422_stub():
    enc = RS422EncoderReader()
    assert enc.connect({})
    assert enc.read_position_meter() == 0.0
    assert enc.read_speed_mpm() == 0.0
    assert enc.get_status()["connected"]
    enc.disconnect()
