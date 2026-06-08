from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _find_exe() -> str | None:
    """Return path to cx_vision_runtime.exe, or None if not built / not runnable."""
    path = (
        Path(__file__).resolve().parents[1]
        / "cpp_runtime"
        / "build"
        / "cx_vision_runtime.exe"
    )
    if not path.exists():
        return None
    # Probe that it launches (gracefully skip when OS policy blocks execution)
    try:
        subprocess.run(
            [str(path), "status"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
    except Exception:
        return None
    return str(path)


@pytest.fixture
def real_exe_path():
    path = _find_exe()
    if path is None:
        pytest.skip("cpp_runtime/build/cx_vision_runtime.exe is not built or not runnable")
    return path


def test_start_with_missing_config_file_returns_error(real_exe_path, tmp_path):
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "missing_config.json"

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_MISSING"


def test_start_with_invalid_config_file_returns_error(real_exe_path, tmp_path):
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "bad_config.json"
    config_file.write_text("not valid json {{{", encoding="utf-8")

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_config_missing_run_id_returns_error(real_exe_path, tmp_path):
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "partial_config.json"
    config_file.write_text(
        json.dumps({"project_id": "p1", "spec_id": "s1", "backend": "cpp_runtime"}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_valid_config_file_returns_running(real_exe_path, tmp_path):
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "runtime_config.json"
    config_file.write_text(
        json.dumps(
            {
                "run_id": "run_001",
                "project_id": "project_001",
                "spec_id": "spec_001",
                "backend": "cpp_runtime",
                "cameras": [],
                "model_artifacts": {},
                "confidence": 0.5,
                "iou": 0.45,
                "save_policy": "save_ng_only",
                "output_dir": "",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 0
    assert payload["state"] == "running"
    assert payload["error_code"] == ""


def test_start_without_config_file_still_works(real_exe_path, tmp_path):
    """Backward compat: start without --config-file still returns running."""
    state_file = tmp_path / "state.json"
    proc = subprocess.run(
        [real_exe_path, "start", "--state-file", str(state_file)],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 0
    assert payload["state"] == "running"


def test_start_with_syntactically_invalid_json_that_has_keys_returns_error(
    real_exe_path, tmp_path,
):
    """Invalid JSON that contains all required substrings still fails.

    Input ``not-json "run_id":"r1","project_id":"p1"...`` is not a valid
    JSON object; the parser must reject it with CONFIG_FILE_INVALID.
    """
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "fake_json.config"
    config_file.write_text(
        'not-json "run_id":"r1","project_id":"p1","spec_id":"s1","backend":"b1"',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_unbalanced_braces_returns_error(real_exe_path, tmp_path):
    """Unbalanced JSON braces are rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "unbalanced.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1",',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_missing_comma_between_members_returns_error(
    real_exe_path, tmp_path,
):
    """Config with missing comma between JSON members is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "missing_comma.json"
    config_file.write_text(
        '{"run_id":"r1" "project_id":"p1","spec_id":"s1","backend":"cpp_runtime"}',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_trailing_comma_returns_error(real_exe_path, tmp_path):
    """Config with trailing comma before closing brace is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "trailing_comma.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime",}',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_required_fields_nested_only_returns_error(
    real_exe_path, tmp_path,
):
    """Required config fields must be top-level object members."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "nested_required_fields.json"
    config_file.write_text(
        '{"meta":{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime"}}',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_cameras_object_returns_error(real_exe_path, tmp_path):
    """Config with cameras as object (not array) is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "cameras_obj.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":{}}',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_model_artifacts_array_returns_error(real_exe_path, tmp_path):
    """Config with model_artifacts as array (not object) is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "artifacts_arr.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","model_artifacts":[]}',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_cameras_array_and_model_artifacts_object_returns_running(
    real_exe_path, tmp_path,
):
    """Config with valid cameras:[] and model_artifacts:{} is accepted."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "valid_struct.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":[],"model_artifacts":{}}',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            real_exe_path,
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}"
    assert payload["state"] == "running"
    assert payload["error_code"] == ""


def test_start_with_model_artifacts_number_value_returns_error(real_exe_path, tmp_path):
    """Config with model_artifacts containing non-string value is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "bad_artifacts_value.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1",'
        '"backend":"cpp_runtime","model_artifacts":{"yolo":123}}',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(real_exe_path),
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_cameras_string_entry_returns_error(real_exe_path, tmp_path):
    """Config with cameras array containing non-object entry is rejected."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "bad_camera_entry.json"
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1",'
        '"backend":"cpp_runtime","cameras":["cam1"]}',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(real_exe_path),
            "start",
            "--state-file",
            str(state_file),
            "--config-file",
            str(config_file),
        ],
        capture_output=True,
        text=True,
        timeout=5.0,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"
