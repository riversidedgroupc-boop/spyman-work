from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.runtime_contracts import (
    CameraRuntimeConfig,
    DefectEvent,
    RuntimeCommand,
    RuntimeConfig,
    RuntimeStatus,
)


def test_runtime_config_round_trips_json() -> None:
    config = RuntimeConfig(
        run_id="run_001",
        project_id="project_001",
        spec_id="spec_001",
        backend="cpp_runtime",
        cameras=[
            CameraRuntimeConfig(
                camera_id="cam_1",
                camera_type="line_scan",
                serial_number="SN001",
                width=2048,
                block_height=1024,
                pixel_format="Mono8",
            )
        ],
        model_artifacts={"yolo": "D:/models/best.engine"},
        confidence=0.5,
        iou=0.45,
    )

    payload = config.model_dump_json()
    restored = RuntimeConfig.model_validate_json(payload)

    assert restored.run_id == "run_001"
    assert restored.cameras[0].camera_id == "cam_1"
    assert restored.model_artifacts["yolo"].endswith("best.engine")


def test_runtime_command_rejects_unknown_command() -> None:
    with pytest.raises(ValidationError):
        RuntimeCommand(command="reboot")


def test_runtime_status_defaults_are_safe() -> None:
    status = RuntimeStatus(state="stopped")

    assert status.state == "stopped"
    assert status.fps_by_camera == {}
    assert status.error_code == ""


def test_defect_event_serializes_for_cpp_platform() -> None:
    event = DefectEvent(
        event_id="evt_001",
        run_id="run_001",
        camera_id="cam_1",
        timestamp_ms=1_717_000_000_000,
        meter_position=12.34,
        defect_type="scratch",
        confidence=0.92,
        bbox_xyxy=[10.0, 20.0, 110.0, 220.0],
        image_path="D:/data/ng/evt_001.png",
        model_version="model_001",
    )

    payload = json.loads(event.model_dump_json())

    assert payload["event_id"] == "evt_001"
    assert payload["bbox_xyxy"] == [10.0, 20.0, 110.0, 220.0]


def test_defect_event_handles_special_characters() -> None:
    """Fields with quotes, backslashes, or newlines must produce valid JSON.

    This is a contract requirement for the C++ platform: any string field
    that reaches ToJsonLine() must be escaped so the output is valid JSON.
    """
    event = DefectEvent(
        event_id='evt_001',
        run_id='run_001',
        camera_id='cam_1',
        timestamp_ms=1_700_000_000_000,
        meter_position=1.0,
        defect_type='scratch with "quotes" and \\backslash',
        confidence=0.88,
        bbox_xyxy=[1.0, 2.0, 3.0, 4.0],
        image_path='D:\\path\\with\\backslashes\\img.png',
        model_version='v1.0\n(beta)',
    )

    payload_str = event.model_dump_json()
    payload = json.loads(payload_str)

    assert '"quotes"' in payload["defect_type"]
    assert payload["image_path"] == "D:\\path\\with\\backslashes\\img.png"


def test_runtime_config_accepts_fake_cpp_runtime_backend() -> None:
    """fake_cpp_runtime must be a valid backend value for testing."""
    config = RuntimeConfig(
        run_id="run_001",
        project_id="project_001",
        spec_id="spec_001",
        backend="fake_cpp_runtime",
    )
    assert config.backend == "fake_cpp_runtime"
