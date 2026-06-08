from __future__ import annotations

from core.runtime_contracts import RuntimeConfig
from runtime.fake_cpp_runtime import FakeCppRuntime


def test_fake_runtime_lifecycle() -> None:
    runtime = FakeCppRuntime()
    config = RuntimeConfig(
        run_id="run_001",
        project_id="project_001",
        spec_id="spec_001",
        backend="cpp_runtime",
    )

    assert runtime.status().state == "stopped"

    started = runtime.start(config)
    assert started.state == "running"
    assert started.uptime_ms >= 0

    stopped = runtime.stop()
    assert stopped.state == "stopped"


def test_fake_runtime_emits_deterministic_event() -> None:
    runtime = FakeCppRuntime()
    config = RuntimeConfig(
        run_id="run_001",
        project_id="project_001",
        spec_id="spec_001",
        backend="cpp_runtime",
    )
    runtime.start(config)

    event = runtime.emit_test_defect(camera_id="cam_1")

    assert event.run_id == "run_001"
    assert event.camera_id == "cam_1"
    assert event.defect_type == "test_defect"
    assert event.bbox_xyxy == [10.0, 20.0, 110.0, 220.0]
