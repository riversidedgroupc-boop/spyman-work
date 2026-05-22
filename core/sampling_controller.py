"""Sampling mode controller — governs when images are captured.

Strategies:
  - DIRECTORY_WATCH: watch a directory for new images (default)
  - BY_TIME: capture at fixed time intervals
  - BY_DISTANCE: capture at fixed distance intervals (needs encoder)
  - SUSPECTED_ANOMALY: trigger on anomaly detection suspicion
  - MANUAL: user manually triggers capture
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


SAMPLING_MODES = [
    "directory_watch",
    "by_time",
    "by_distance",
    "suspected_anomaly",
    "manual",
]

SAMPLING_MODE_LABELS: dict[str, str] = {
    "directory_watch": "目录监听",
    "by_time": "按时间",
    "by_distance": "按距离",
    "suspected_anomaly": "疑似异常",
    "manual": "手动触发",
}


@dataclass
class SamplingState:
    """Mutable state snapshot returned by the controller."""
    mode: str = "directory_watch"
    last_capture_at: datetime | None = None
    last_position_m: float = 0.0
    capture_count: int = 0
    interval_seconds: float = 1.0
    distance_meters: float = 1.0
    enabled: bool = False
    pending_manual: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class SamplingController:
    """Decides whether a new frame should trigger a capture/inference event.

    Usage::

        ctrl = SamplingController()
        ctrl.configure(mode="by_distance", distance_meters=0.5)

        # In the acquisition loop:
        position = encoder.read_position_meter()
        if ctrl.should_capture(position_m=position, now=datetime.now()):
            frame = adapter.grab()
            pipeline.process(frame)
    """

    def __init__(self) -> None:
        self._state = SamplingState()

    # -- config ----------------------------------------------------------

    def configure(
        self,
        mode: str = "directory_watch",
        interval_seconds: float = 1.0,
        distance_meters: float = 1.0,
        **extra: Any,
    ) -> None:
        if mode not in SAMPLING_MODES:
            raise ValueError(f"Unknown sampling mode: {mode}")
        self._state.mode = mode
        self._state.interval_seconds = max(0.1, interval_seconds)
        self._state.distance_meters = max(0.001, distance_meters)
        self._state.extra = extra
        self._state.last_capture_at = None
        self._state.last_position_m = 0.0
        self._state.capture_count = 0

    def set_enabled(self, enabled: bool) -> None:
        self._state.enabled = enabled

    def trigger_manual(self) -> None:
        """Request a one-shot manual capture."""
        self._state.pending_manual = True

    # -- decision --------------------------------------------------------

    def should_capture(
        self,
        position_m: float = 0.0,
        now: datetime | None = None,
    ) -> bool:
        """Return True if a capture should be taken right now."""
        if not self._state.enabled:
            return False

        now = now or datetime.now()

        mode = self._state.mode

        if mode == "directory_watch":
            # Always capture when frames arrive
            return True

        if mode == "by_time":
            return self._should_by_time(now)

        if mode == "by_distance":
            return self._should_by_distance(position_m)

        if mode == "suspected_anomaly":
            return self._should_suspected_anomaly(position_m, now)

        if mode == "manual":
            return self._should_manual()

        return False

    # -- internal helpers ------------------------------------------------

    def _should_by_time(self, now: datetime) -> bool:
        last = self._state.last_capture_at
        if last is None:
            self._state.last_capture_at = now
            self._state.capture_count += 1
            return True
        elapsed = (now - last).total_seconds()
        if elapsed >= self._state.interval_seconds:
            self._state.last_capture_at = now
            self._state.capture_count += 1
            return True
        return False

    def _should_by_distance(self, position_m: float) -> bool:
        # First capture always fires, same as by_time
        if self._state.last_capture_at is None:
            self._state.last_position_m = position_m
            self._state.last_capture_at = datetime.now()
            self._state.capture_count += 1
            return True
        travelled = abs(position_m - self._state.last_position_m)
        if travelled >= self._state.distance_meters:
            self._state.last_position_m = position_m
            self._state.capture_count += 1
            self._state.last_capture_at = datetime.now()
            return True
        return False

    def _should_suspected_anomaly(self, position_m: float, now: datetime) -> bool:
        # Suspected anomaly mode: delegates to an external anomaly detector.
        # The detector is set via configure(..., anomaly_detector=callable).
        detector: Callable[[float, datetime], bool] | None = self._state.extra.get(
            "anomaly_detector"
        )
        if detector is not None:
            if detector(position_m, now):
                self._state.last_capture_at = now
                self._state.last_position_m = position_m
                self._state.capture_count += 1
                return True
        return False

    def _should_manual(self) -> bool:
        if self._state.pending_manual:
            self._state.pending_manual = False
            self._state.capture_count += 1
            self._state.last_capture_at = datetime.now()
            return True
        return False

    # -- state access ----------------------------------------------------

    @property
    def state(self) -> SamplingState:
        return self._state
