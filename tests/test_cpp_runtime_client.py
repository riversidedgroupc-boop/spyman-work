from __future__ import annotations

import json
import subprocess
import sys

import pytest

from core.runtime_contracts import RuntimeCommand, RuntimeConfig, RuntimeStatus
from runtime.cpp_runtime_client import (
    CppRuntimeClient,
    CppRuntimeProcessTransport,
    InMemoryRuntimeTransport,
)


def test_client_sends_start_command() -> None:
    transport = InMemoryRuntimeTransport()
    client = CppRuntimeClient(transport=transport)
    config = RuntimeConfig(
        run_id="run_001",
        project_id="project_001",
        spec_id="spec_001",
        backend="cpp_runtime",
    )

    status = client.start(config)

    assert status.state == "running"
    assert transport.commands[0].command == "start"
    assert transport.commands[0].config is not None


def test_client_sends_stop_command() -> None:
    transport = InMemoryRuntimeTransport()
    client = CppRuntimeClient(transport=transport)

    status = client.stop()

    assert status.state == "stopped"
    assert transport.commands[0] == RuntimeCommand(command="stop")


def test_client_reads_status() -> None:
    transport = InMemoryRuntimeTransport(status=RuntimeStatus(state="running"))
    client = CppRuntimeClient(transport=transport)

    status = client.status()

    assert status.state == "running"


class TestCppRuntimeProcessTransport:
    @pytest.fixture
    def fake_exe(self, tmp_path):
        """Create a fake exe script that echoes RuntimeStatus JSON to stdout."""
        exe_path = tmp_path / "fake_cx_vision_runtime.py"
        script = (
            "import sys, json\n"
            "cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'\n"
            "if cmd == 'status':\n"
            '    print(json.dumps({"state":"stopped","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}))\n'
            "elif cmd == 'start':\n"
            '    print(json.dumps({"state":"running","uptime_ms":100,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}))\n'
            "elif cmd == 'stop':\n"
            '    print(json.dumps({"state":"stopped","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}))\n'
            "else:\n"
            "    sys.stderr.write('BAD_COMMAND')\n"
            "    sys.exit(2)\n"
        )
        exe_path.write_text(script)
        return str(exe_path)

    @pytest.fixture
    def python_exe(self):
        import sys
        return sys.executable

    @pytest.fixture
    def fake_exe_with_state(self, tmp_path):
        """Create a fake exe script that supports --state-file flag."""
        exe_path = tmp_path / "fake_cx_vision_runtime.py"
        script = (
            "import json, os, sys\n"
            "cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'\n"
            "state_file = None\n"
            "for i, a in enumerate(sys.argv):\n"
            "    if a == '--state-file' and i + 1 < len(sys.argv):\n"
            "        state_file = sys.argv[i + 1]\n"
            "        break\n"
            "if cmd == 'status':\n"
            "    if state_file and os.path.exists(state_file):\n"
            "        with open(state_file) as f:\n"
            "            data = json.load(f)\n"
            '        if data.get("state") == "running":\n'
            '            print(json.dumps({"state":"running","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}))\n'
            "            sys.exit(0)\n"
            '    print(json.dumps({"state":"stopped","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}))\n'
            "elif cmd == 'start':\n"
            "    status = {'state':'running','uptime_ms':100,'queue_size':0,"
            "'dropped_frames':0,'ng_count':0,'error_code':'','error_message':''}\n"
            "    if state_file:\n"
            "        with open(state_file, 'w') as f:\n"
            "            json.dump(status, f)\n"
            "    print(json.dumps(status))\n"
            "elif cmd == 'stop':\n"
            "    status = {'state':'stopped','uptime_ms':0,'queue_size':0,"
            "'dropped_frames':0,'ng_count':0,'error_code':'','error_message':''}\n"
            "    if state_file:\n"
            "        with open(state_file, 'w') as f:\n"
            "            json.dump(status, f)\n"
            "    print(json.dumps(status))\n"
            "else:\n"
            "    sys.stderr.write('BAD_COMMAND')\n"
            "    sys.exit(2)\n"
        )
        exe_path.write_text(script)
        return str(exe_path)

    def test_status_returns_parsed_json(self, fake_exe, python_exe) -> None:
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, fake_exe],
        )
        status = transport.request(RuntimeCommand(command="status"))
        assert status.state == "stopped"

    def test_start_returns_running(self, fake_exe, python_exe) -> None:
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, fake_exe],
        )
        status = transport.request(RuntimeCommand(command="start"))
        assert status.state == "running"
        assert status.uptime_ms == 100

    def test_stop_returns_stopped(self, fake_exe, python_exe) -> None:
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, fake_exe],
        )
        status = transport.request(RuntimeCommand(command="stop"))
        assert status.state == "stopped"

    def test_missing_executable_raises(self) -> None:
        transport = CppRuntimeProcessTransport(
            executable_path=["/nonexistent/path/to/exe"],
        )
        with pytest.raises(FileNotFoundError):
            transport.request(RuntimeCommand(command="status"))

    def test_os_error_start_failure_raises_runtime_error(self, monkeypatch) -> None:
        def fake_run(*args, **kwargs):
            raise OSError("blocked by policy")

        monkeypatch.setattr(subprocess, "run", fake_run)
        transport = CppRuntimeProcessTransport(
            executable_path=["/blocked/runtime.exe"],
        )

        with pytest.raises(RuntimeError, match="failed to start"):
            transport.request(RuntimeCommand(command="status"))

    def test_nonzero_exit_with_invalid_stdout_raises(self, tmp_path, python_exe) -> None:
        # Create a script that exits non-zero and prints garbage (not valid JSON)
        bad_exe = tmp_path / "bad_runtime.py"
        bad_exe.write_text(
            "import sys\n"
            "print('this is not json')\n"
            "sys.exit(3)\n"
        )
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, str(bad_exe)],
        )
        with pytest.raises(RuntimeError, match="exited with code 3"):
            transport.request(RuntimeCommand(command="status"))

    def test_nonzero_exit_with_valid_status_json_returns_status(
        self, tmp_path, python_exe
    ) -> None:
        # Script exits non-zero but stdout is still valid RuntimeStatus JSON
        ok_exe = tmp_path / "ok_error_runtime.py"
        ok_exe.write_text(
            "import json\n"
            "print(json.dumps({"
            '  "state":"error","uptime_ms":0,"queue_size":0,'
            '  "dropped_frames":0,"ng_count":0,'
            '  "error_code":"E_SENSOR","error_message":"sensor timeout"}))\n'
            "import sys; sys.exit(1)\n"
        )
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, str(ok_exe)],
        )

        status = transport.request(RuntimeCommand(command="status"))

        assert status.state == "error"
        assert status.error_code == "E_SENSOR"
        assert status.error_message == "sensor timeout"

    def test_extra_args_passed_to_subprocess(
        self, fake_exe, python_exe, tmp_path
    ) -> None:
        """Verify extra_args are appended to the subprocess command line."""
        out_path = tmp_path / "argv.json"
        state_path = tmp_path / "state.json"
        spy_path = tmp_path / "spy.py"
        spy_path.write_text(
            "import sys, json\n"
            "out = " + json.dumps(str(out_path)) + "\n"
            "with open(out, 'w') as f:\n"
            "    json.dump(sys.argv, f)\n"
            "print(json.dumps({"
            '"state":"stopped","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,'
            '"error_code":"","error_message":""}))\n'
        )
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, str(spy_path)],
            extra_args=["--state-file", str(state_path)],
        )
        transport.request(RuntimeCommand(command="status"))
        captured = json.loads(out_path.read_text())
        # sys.argv: [script_path, "status", "--state-file", state_path]
        assert captured[2] == "--state-file"
        assert captured[3] == str(state_path)

    def test_extra_args_defaults_to_none(self) -> None:
        """CppRuntimeProcessTransport.extra_args defaults to None."""
        transport = CppRuntimeProcessTransport(
            executable_path=["/nonexistent/path/to/exe"],
        )
        assert transport.extra_args is None

    def test_extra_args_with_real_state_file_lifecycle(
        self, fake_exe_with_state, python_exe, tmp_path
    ) -> None:
        """Simulate start -> status -> stop lifecycle with --state-file."""
        state_path = tmp_path / "runtime_state.json"

        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, fake_exe_with_state],
            extra_args=["--state-file", str(state_path)],
        )

        # Start
        status = transport.request(RuntimeCommand(command="start"))
        assert status.state == "running"
        assert state_path.exists()

        # Status -> should read "running" from state file
        status = transport.request(RuntimeCommand(command="status"))
        assert status.state == "running"

        # Stop
        status = transport.request(RuntimeCommand(command="stop"))
        assert status.state == "stopped"

        # Status after stop -> should read "stopped" from state file
        status = transport.request(RuntimeCommand(command="status"))
        assert status.state == "stopped"

    def test_start_with_config_file_passes_config_file_arg(
        self, python_exe, tmp_path
    ) -> None:
        """start command passes --config-file to subprocess only when config_file_path is set."""
        out_path = tmp_path / "argv.json"
        config_path = tmp_path / "runtime_config.json"
        spy_path = tmp_path / "spy.py"
        spy_path.write_text(
            "import json, sys\n"
            "out = " + json.dumps(str(out_path)) + "\n"
            "with open(out, 'w') as f:\n"
            "    json.dump(sys.argv, f)\n"
            "print(json.dumps({"
            '"state":"running","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,'
            '"error_code":"","error_message":""}))\n'
        )
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, str(spy_path)],
            extra_args=["--state-file", str(tmp_path / "state.json")],
            config_file_path=str(config_path),
        )

        status = transport.request(RuntimeCommand(command="start"))
        captured = json.loads(out_path.read_text())

        assert status.state == "running"
        assert "--config-file" in captured
        idx = captured.index("--config-file")
        assert captured[idx + 1] == str(config_path)

        # Verify config_file is NOT passed for status command
        captured.clear()
        out_path.unlink()
        out_path.touch()
        transport.request(RuntimeCommand(command="status"))
        captured2 = json.loads(out_path.read_text())
        assert "--config-file" not in captured2

    def test_start_writes_config_json_before_spawning(
        self, python_exe, tmp_path
    ) -> None:
        """CppRuntimeClient.start writes config JSON when config_file_path is set."""
        config_path = tmp_path / "runtime_config.json"
        spy_path = tmp_path / "spy.py"
        spy_path.write_text(
            "import json, sys\n"
            "print(json.dumps({"
            '"state":"running","uptime_ms":0,"queue_size":0,'
            '"dropped_frames":0,"ng_count":0,'
            '"error_code":"","error_message":""}))\n'
        )
        transport = CppRuntimeProcessTransport(
            executable_path=[python_exe, str(spy_path)],
        )
        client = CppRuntimeClient(
            transport=transport,
            config_file_path=str(config_path),
        )
        config = RuntimeConfig(
            run_id="run_X",
            project_id="proj_X",
            spec_id="spec_X",
            backend="cpp_runtime",
        )
        status = client.start(config)

        assert status.state == "running"
        assert config_path.exists()
        written = json.loads(config_path.read_text(encoding="utf-8"))
        assert written["run_id"] == "run_X"
