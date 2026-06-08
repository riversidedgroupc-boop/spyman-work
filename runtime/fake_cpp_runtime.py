from __future__ import annotations

import time
from dataclasses import dataclass

from core.runtime_contracts import DefectEvent, RuntimeConfig, RuntimeStatus


@dataclass
class FakeCppRuntime:
    _config: RuntimeConfig | None = None
    _started_at: float | None = None
    _ng_count: int = 0

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        self._config = config
        self._started_at = time.monotonic()
        return self.status()

    def stop(self) -> RuntimeStatus:
        self._config = None
        self._started_at = None
        return self.status()

    def status(self) -> RuntimeStatus:
        if self._config is None or self._started_at is None:
            return RuntimeStatus(state="stopped")
        uptime_ms = int((time.monotonic() - self._started_at) * 1000)
        return RuntimeStatus(
            state="running",
            uptime_ms=uptime_ms,
            fps_by_camera={c.camera_id: 30.0 for c in self._config.cameras},
            ng_count=self._ng_count,
        )

    def emit_test_defect(self, camera_id: str) -> DefectEvent:
        if self._config is None:
            raise RuntimeError("Fake runtime is not running")
        self._ng_count += 1
        return DefectEvent(
            event_id=f"fake_evt_{self._ng_count:06d}",
            run_id=self._config.run_id,
            camera_id=camera_id,
            timestamp_ms=int(time.time() * 1000),
            meter_position=1.23,
            defect_type="test_defect",
            confidence=0.9,
            bbox_xyxy=[10.0, 20.0, 110.0, 220.0],
            image_path="",
            model_version="fake_model",
        )
