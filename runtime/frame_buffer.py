"""Thread-safe ring buffer for acquired frames."""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


class FrameBuffer:
    """Fixed-size ring buffer for camera frames."""

    def __init__(self, max_size: int = 100):
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = Lock()
        self._dropped = 0

    def put(self, frame: dict) -> None:
        """Put frame dict: {"camera_id": str, "image": ndarray, "timestamp": float, ...}."""
        with self._lock:
            if len(self._buffer) >= self._buffer.maxlen:
                self._dropped += 1
            self._buffer.append(frame)

    def get(self) -> dict | None:
        with self._lock:
            if self._buffer:
                return self._buffer.popleft()
            return None

    def get_latest(self) -> dict | None:
        with self._lock:
            if self._buffer:
                return self._buffer.pop()
            return None

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def put_with_position(self, camera_id: str, image: Any, position_meter: float) -> None:
        """Put a frame with position metadata."""
        import time
        self.put({
            "camera_id": camera_id,
            "image": image,
            "timestamp": time.time(),
            "position_meter": position_meter,
        })

    def get_per_camera(self, camera_id: str) -> dict | None:
        """Get the latest frame for a specific camera_id (non-destructive peek)."""
        with self._lock:
            for frame in reversed(self._buffer):
                if frame.get("camera_id") == camera_id:
                    return frame
            return None

    def drop_older_than(self, max_age_sec: float) -> int:
        """Drop frames older than max_age_sec. Returns number dropped."""
        import time
        now = time.time()
        dropped = 0
        with self._lock:
            while self._buffer and (now - self._buffer[0].get("timestamp", 0)) > max_age_sec:
                self._buffer.popleft()
                dropped += 1
        return dropped

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._dropped = 0
