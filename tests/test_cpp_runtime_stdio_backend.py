"""Tests for CppRuntimeStdioBackend (Phase 5A — stdin/stdout transport).

Requires ``cx_vision_runtime.exe`` to be built.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from core.runtime_contracts import CameraRuntimeConfig, RuntimeConfig, RuntimeStatus
from runtime.cpp_runtime_stdio import CppRuntimeStdioBackend
from runtime.runtime_backend import RuntimeBackend, create_backend


@pytest.fixture
def real_exe_path():
    path = (
        Path(__file__).resolve().parents[1]
        / "cpp_runtime"
        / "build"
        / "cx_vision_runtime.exe"
    )
    if not path.exists():
        pytest.skip("cpp_runtime/build/cx_vision_runtime.exe is not built")
    try:
        subprocess.run(
            [str(path), "status"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except OSError:
        pytest.skip("cx_vision_runtime.exe cannot start in this environment")
    return str(path)


class TestCppRuntimeStdioBackend:
    """Integration tests with real cx_vision_runtime.exe serve mode."""

    def test_backend_is_runtime_backend(self) -> None:
        backend = CppRuntimeStdioBackend(executable_path="/fake/exe")
        assert isinstance(backend, RuntimeBackend)

    def test_serve_starts_and_returns_idle_status(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            status = backend.status()
            assert status.state == "idle"
            assert status.error_code == ""
        finally:
            backend.shutdown()

    def test_start_transitions_to_running(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_001",
                project_id="p1",
                spec_id="s1",
                backend="cpp_runtime_stdio",
            )
            s = backend.start(config)
            assert s.state == "running"
            s2 = backend.status()
            assert s2.state == "running"
        finally:
            backend.shutdown()

    def test_start_writes_config_file(self, real_exe_path, tmp_path) -> None:
        """start() writes a runtime_config.json with correct fields."""
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_cfg",
                project_id="proj_xyz",
                spec_id="spec_xyz",
                backend="cpp_runtime_stdio",
                cameras=[
                    CameraRuntimeConfig(
                        camera_id="CAM_01",
                        camera_type="area_scan",
                        width=1920,
                    )
                ],
                model_artifacts={"yolo": "C:\\models\\yolo.engine"},
                confidence=0.7,
                iou=0.5,
                save_policy="save_ng_only",
                output_dir=str(tmp_path),
            )
            s = backend.start(config)
            assert s.state == "running"

            # Verify config file was written
            assert backend._config_file is not None
            assert backend._config_file.exists()
            with open(backend._config_file, encoding="utf-8") as f:
                saved = json.load(f)
            assert saved["run_id"] == "stdio_cfg"
            assert saved["project_id"] == "proj_xyz"
            assert saved["spec_id"] == "spec_xyz"
            assert saved["cameras"][0]["camera_id"] == "CAM_01"
            assert saved["model_artifacts"]["yolo"] == "C:\\models\\yolo.engine"
        finally:
            backend.shutdown()

    def test_stop_transitions_to_idle(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_002",
                project_id="p1",
                spec_id="s1",
                backend="cpp_runtime_stdio",
            )
            backend.start(config)
            s = backend.stop()
            assert s.state == "idle"
            s2 = backend.status()
            assert s2.state == "idle"
        finally:
            backend.shutdown()

    def test_start_stop_start_cycle(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_003",
                project_id="p1",
                spec_id="s1",
                backend="cpp_runtime_stdio",
            )
            s = backend.start(config)
            assert s.state == "running"
            s = backend.stop()
            assert s.state == "idle"
            s = backend.start(config)
            assert s.state == "running"
        finally:
            backend.shutdown()

    def test_shutdown_exits_process(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        backend.status()
        backend.shutdown()
        assert backend._process is None

    def test_stop_when_idle_returns_error(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            s = backend.stop()
            assert s.state == "error"
            assert "NOT_RUNNING" in s.error_code
        finally:
            backend.shutdown()

    def test_start_when_already_running_returns_error(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_004",
                project_id="p1",
                spec_id="s1",
                backend="cpp_runtime_stdio",
            )
            backend.start(config)
            s = backend.start(config)
            assert s.state == "error"
            assert "ALREADY_RUNNING" in s.error_code
        finally:
            backend.shutdown()

    def test_uptime_increases_while_running(self, real_exe_path) -> None:
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            config = RuntimeConfig(
                run_id="stdio_005",
                project_id="p1",
                spec_id="s1",
                backend="cpp_runtime_stdio",
            )
            backend.start(config)
            time.sleep(0.3)
            s = backend.status()
            assert s.state == "running"
            assert s.uptime_ms >= 200
        finally:
            backend.shutdown()

    def test_create_via_factory(self, real_exe_path) -> None:
        backend = create_backend(
            "cpp_runtime_stdio",
            executable_path=real_exe_path,
        )
        try:
            assert isinstance(backend, CppRuntimeStdioBackend)
            s = backend.status()
            assert s.state == "idle"
        finally:
            backend.shutdown()


class TestCppRuntimeStdioBackendErrorHandling:
    """Tests for error modes."""

    def test_stdio_timeout_on_nonexistent_exe(self) -> None:
        backend = CppRuntimeStdioBackend(
            executable_path="D:/__nonexistent__/no_such_exe.exe",
            startup_timeout=0.5,
        )
        with pytest.raises((RuntimeError, FileNotFoundError)):
            backend.status()
        backend.shutdown()

    def test_malformed_json_input_returns_error(self, real_exe_path) -> None:
        """C++ serve process should return error event for malformed JSON input."""
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            backend.status()  # ensure process is running
            backend._send_line("this is not valid json {{{")
            # Read the error response — should not hang or crash
            event = backend._event_queue.get(timeout=5.0)
            assert event.get("type") == "error"
            assert "MALFORMED" in event["payload"]["code"]
        finally:
            backend.shutdown()

    def test_missing_command_field_returns_error(self, real_exe_path) -> None:
        """C++ serve process should reject JSON without 'command' field."""
        backend = CppRuntimeStdioBackend(executable_path=real_exe_path)
        try:
            backend.status()
            backend._send_line(json.dumps({"hello": "world"}))
            event = backend._event_queue.get(timeout=5.0)
            assert event.get("type") == "error"
            assert "BAD_REQUEST" in event["payload"]["code"]
        finally:
            backend.shutdown()
