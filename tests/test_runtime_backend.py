from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.runtime_contracts import CameraRuntimeConfig, RuntimeConfig
from runtime.runtime_backend import (
    CppRuntimeProcessBackend,
    FakeCppRuntimeBackend,
    PythonRuntimeBackend,
    RuntimeBackend,
    create_backend,
)


class TestPythonRuntimeBackend:
    def test_backend_is_runtime_backend(self) -> None:
        backend = PythonRuntimeBackend()
        assert isinstance(backend, RuntimeBackend)

    def test_initial_status_stopped(self) -> None:
        backend = PythonRuntimeBackend()
        status = backend.status()
        assert status.state == "stopped"

    def test_start_stop_lifecycle(self) -> None:
        backend = PythonRuntimeBackend()
        config = RuntimeConfig(
            run_id="run_001",
            project_id="project_001",
            spec_id="spec_001",
            backend="python_runtime",
            cameras=[
                CameraRuntimeConfig(
                    camera_id="cam_1",
                    camera_type="area_scan",
                    width=1920,
                )
            ],
        )

        status = backend.start(config)
        assert status.state == "running"
        assert status.uptime_ms >= 0

        status = backend.stop()
        assert status.state == "stopped"


class TestFakeCppRuntimeBackend:
    def test_backend_is_runtime_backend(self) -> None:
        backend = FakeCppRuntimeBackend()
        assert isinstance(backend, RuntimeBackend)

    def test_initial_status_stopped(self) -> None:
        backend = FakeCppRuntimeBackend()
        status = backend.status()
        assert status.state == "stopped"

    def test_start_stop_lifecycle(self) -> None:
        backend = FakeCppRuntimeBackend()
        config = RuntimeConfig(
            run_id="run_001",
            project_id="project_001",
            spec_id="spec_001",
            backend="fake_cpp_runtime",
        )

        status = backend.start(config)
        assert status.state == "running"

        status = backend.stop()
        assert status.state == "stopped"


class TestCppRuntimeProcessBackend:
    @pytest.fixture
    def real_exe_path(self, tmp_path_factory):
        path = (
            Path(__file__).resolve().parents[1]
            / "cpp_runtime"
            / "build"
            / "cx_vision_runtime.exe"
        )
        if not path.exists():
            pytest.skip("cpp_runtime/build/cx_vision_runtime.exe is not built")
        probe_state = tmp_path_factory.mktemp("cpp_runtime_probe") / "state.json"
        try:
            probe = subprocess.run(
                [str(path), "status", "--state-file", str(probe_state)],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
        except OSError as exc:
            pytest.skip(f"cx_vision_runtime.exe cannot start in this environment: {exc}")
        if probe.returncode != 0:
            pytest.fail(
                "cx_vision_runtime.exe preflight failed: "
                f"{(probe.stdout or probe.stderr).strip()}"
            )
        return str(path)

    def test_backend_is_runtime_backend(self) -> None:
        backend = CppRuntimeProcessBackend(executable_path="/fake/exe")
        assert isinstance(backend, RuntimeBackend)

    def test_state_file_path_defaults_to_none(self) -> None:
        """When state_file_path is not given, extra_args stays None."""
        backend = CppRuntimeProcessBackend(executable_path="/fake/exe")
        assert backend._client._transport.extra_args is None

    def test_state_file_path_propagates_to_transport(self) -> None:
        backend = CppRuntimeProcessBackend(
            executable_path="/fake/exe",
            state_file_path="/tmp/state.json",
        )
        assert backend._client._transport.extra_args == [
            "--state-file",
            "/tmp/state.json",
        ]

    def test_real_exe_start_status_stop_lifecycle(
        self, real_exe_path, tmp_path
    ) -> None:
        """Integration test with real cx_vision_runtime.exe."""
        state_file = tmp_path / "state.json"

        backend = CppRuntimeProcessBackend(
            executable_path=real_exe_path,
            state_file_path=str(state_file),
        )
        config = RuntimeConfig(
            run_id="int_001",
            project_id="int_project",
            spec_id="int_spec",
            backend="cpp_runtime",
        )

        # Initial status: no state file -> stopped.
        s = backend.status()
        assert s.state == "stopped"

        # Start -> running.
        s = backend.start(config)
        assert s.state == "running"

        # Status -> reads from state file, should be running.
        s = backend.status()
        assert s.state == "running"

        # Stop -> stopped.
        s = backend.stop()
        assert s.state == "stopped"

        # Status after stop -> stopped.
        s = backend.status()
        assert s.state == "stopped"

    def test_real_exe_corrupted_state_file_returns_error(
        self, real_exe_path, tmp_path
    ) -> None:
        """Corrupted state file returns STATE_FILE_INVALID."""
        state_file = tmp_path / "bad_state.json"
        state_file.write_text("not valid json {{{")

        backend = CppRuntimeProcessBackend(
            executable_path=real_exe_path,
            state_file_path=str(state_file),
        )

        s = backend.status()
        assert s.state == "error"
        assert s.error_code == "STATE_FILE_INVALID"
        assert str(state_file) in s.error_message

    def test_real_exe_missing_state_file_returns_stopped(
        self, real_exe_path, tmp_path
    ) -> None:
        """Missing state file returns stopped (not error)."""
        state_file = tmp_path / "nonexistent.json"

        backend = CppRuntimeProcessBackend(
            executable_path=real_exe_path,
            state_file_path=str(state_file),
        )

        s = backend.status()
        assert s.state == "stopped"
        assert s.error_code == ""

    def test_real_exe_spaced_state_file_json_returns_state(
        self, real_exe_path, tmp_path
    ) -> None:
        """State file parser accepts ordinary JSON spacing."""
        state_file = tmp_path / "spaced_state.json"
        state_file.write_text('{"state": "running"}')
        backend = CppRuntimeProcessBackend(
            executable_path=real_exe_path,
            state_file_path=str(state_file),
        )

        s = backend.status()

        assert s.state == "running"
        assert s.error_code == ""

    def test_real_exe_unwritable_state_file_returns_error(
        self, real_exe_path, tmp_path
    ) -> None:
        """Unwritable state file returns STATE_FILE_WRITE_FAILED."""
        state_file = tmp_path / "missing_dir" / "state.json"
        backend = CppRuntimeProcessBackend(
            executable_path=real_exe_path,
            state_file_path=str(state_file),
        )
        config = RuntimeConfig(
            run_id="int_002",
            project_id="int_project",
            spec_id="int_spec",
            backend="cpp_runtime",
        )

        s = backend.start(config)

        assert s.state == "error"
        assert s.error_code == "STATE_FILE_WRITE_FAILED"
        assert str(state_file) in s.error_message


class TestCreateBackend:
    def test_create_python_backend_by_name(self) -> None:
        backend = create_backend("python_runtime")
        assert isinstance(backend, PythonRuntimeBackend)

    def test_create_fake_cpp_backend_by_name(self) -> None:
        backend = create_backend("fake_cpp_runtime")
        assert isinstance(backend, FakeCppRuntimeBackend)

    def test_create_cpp_backend_with_executable_path(self) -> None:
        backend = create_backend("cpp_runtime", executable_path="/fake/exe")
        assert isinstance(backend, CppRuntimeProcessBackend)

    def test_create_cpp_backend_without_executable_path_raises(self) -> None:
        with pytest.raises(ValueError, match="executable_path"):
            create_backend("cpp_runtime")

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            create_backend("invalid_backend")

    def test_accepts_runtime_backend_instance(self) -> None:
        custom = PythonRuntimeBackend()
        backend = create_backend(custom)
        assert backend is custom

    def test_create_cpp_backend_with_state_file_path(self) -> None:
        backend = create_backend(
            "cpp_runtime",
            executable_path="/fake/exe",
            state_file_path="/tmp/state.json",
        )
        assert isinstance(backend, CppRuntimeProcessBackend)
        assert backend._client._transport.extra_args == [
            "--state-file",
            "/tmp/state.json",
        ]

    def test_create_cpp_backend_with_config_file_path(self) -> None:
        backend = create_backend(
            "cpp_runtime",
            executable_path="/fake/exe",
            state_file_path="/tmp/state.json",
            config_file_path="/tmp/config.json",
        )
        assert isinstance(backend, CppRuntimeProcessBackend)
        assert backend._client._config_file_path == "/tmp/config.json"
        assert backend._client._transport.config_file_path == "/tmp/config.json"
