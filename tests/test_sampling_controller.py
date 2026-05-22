"""Tests for SamplingController — 5 sampling strategies."""
from datetime import datetime, timedelta

import pytest

from core.sampling_controller import SamplingController, SamplingState, SAMPLING_MODES


def test_default_mode_is_directory_watch():
    ctrl = SamplingController()
    assert ctrl.state.mode == "directory_watch"
    assert ctrl.state.enabled is False


def test_configure_rejects_unknown_mode():
    ctrl = SamplingController()
    with pytest.raises(ValueError):
        ctrl.configure(mode="invalid_mode")


def test_directory_watch_always_captures_when_enabled():
    ctrl = SamplingController()
    ctrl.configure(mode="directory_watch")
    ctrl.set_enabled(True)
    assert ctrl.should_capture() is True
    assert ctrl.should_capture() is True  # Every call returns True


def test_directory_watch_never_captures_when_disabled():
    ctrl = SamplingController()
    ctrl.configure(mode="directory_watch")
    ctrl.set_enabled(False)
    assert ctrl.should_capture() is False


def test_by_time_first_capture_always_true():
    ctrl = SamplingController()
    ctrl.configure(mode="by_time", interval_seconds=1.0)
    ctrl.set_enabled(True)
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert ctrl.should_capture(now=now) is True


def test_by_time_skips_if_interval_not_elapsed():
    ctrl = SamplingController()
    ctrl.configure(mode="by_time", interval_seconds=2.0)
    ctrl.set_enabled(True)
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert ctrl.should_capture(now=now) is True  # First capture
    assert ctrl.should_capture(now=now + timedelta(seconds=0.5)) is False
    assert ctrl.should_capture(now=now + timedelta(seconds=1.0)) is False


def test_by_time_captures_after_interval_elapsed():
    ctrl = SamplingController()
    ctrl.configure(mode="by_time", interval_seconds=1.0)
    ctrl.set_enabled(True)
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert ctrl.should_capture(now=now) is True
    assert ctrl.should_capture(now=now + timedelta(seconds=1.5)) is True


def test_by_distance_first_capture():
    ctrl = SamplingController()
    ctrl.configure(mode="by_distance", distance_meters=1.0)
    ctrl.set_enabled(True)
    assert ctrl.should_capture(position_m=0.0) is True
    assert ctrl.state.capture_count == 1


def test_by_distance_skips_if_not_enough_distance():
    ctrl = SamplingController()
    ctrl.configure(mode="by_distance", distance_meters=1.0)
    ctrl.set_enabled(True)
    ctrl.should_capture(position_m=0.0)  # First capture
    assert ctrl.should_capture(position_m=0.3) is False
    assert ctrl.should_capture(position_m=0.8) is False


def test_by_distance_captures_when_distance_reached():
    ctrl = SamplingController()
    ctrl.configure(mode="by_distance", distance_meters=1.0)
    ctrl.set_enabled(True)
    ctrl.should_capture(position_m=0.0)
    assert ctrl.should_capture(position_m=1.2) is True
    assert ctrl.state.capture_count == 2


def test_manual_triggers_only_when_requested():
    ctrl = SamplingController()
    ctrl.configure(mode="manual")
    ctrl.set_enabled(True)
    assert ctrl.should_capture() is False
    ctrl.trigger_manual()
    assert ctrl.should_capture() is True
    assert ctrl.should_capture() is False  # Only fires once


def test_suspected_anomaly_no_detector():
    ctrl = SamplingController()
    ctrl.configure(mode="suspected_anomaly")
    ctrl.set_enabled(True)
    assert ctrl.should_capture(position_m=0.0) is False


def test_suspected_anomaly_with_detector():
    ctrl = SamplingController()
    detector_calls = []

    def detector(pos, now):
        detector_calls.append(pos)
        return pos > 5.0

    ctrl.configure(mode="suspected_anomaly", anomaly_detector=detector)
    ctrl.set_enabled(True)
    assert ctrl.should_capture(position_m=3.0) is False
    assert len(detector_calls) == 1
    assert ctrl.should_capture(position_m=7.0) is True
    assert ctrl.state.capture_count == 1


def test_sampling_state_fields():
    state = SamplingState()
    assert state.mode == "directory_watch"
    assert state.last_capture_at is None
    assert state.capture_count == 0
    assert state.interval_seconds == 1.0
    assert state.distance_meters == 1.0


def test_all_sampling_modes_registered():
    assert "directory_watch" in SAMPLING_MODES
    assert "by_time" in SAMPLING_MODES
    assert "by_distance" in SAMPLING_MODES
    assert "suspected_anomaly" in SAMPLING_MODES
    assert "manual" in SAMPLING_MODES
    assert len(SAMPLING_MODES) == 5
