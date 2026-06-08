from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from core.runtime_contracts import RuntimeCommand, RuntimeConfig, RuntimeStatus


class RuntimeTransport(Protocol):
    def request(self, command: RuntimeCommand) -> RuntimeStatus:
        """Send a runtime command and return the parsed status."""


@dataclass
class InMemoryRuntimeTransport:
    status: RuntimeStatus = field(default_factory=lambda: RuntimeStatus(state="stopped"))
    commands: list[RuntimeCommand] = field(default_factory=list)

    def request(self, command: RuntimeCommand) -> RuntimeStatus:
        self.commands.append(command)
        if command.command == "start":
            self.status = RuntimeStatus(state="running")
        elif command.command == "stop":
            self.status = RuntimeStatus(state="stopped")
        return self.status


@dataclass
class CppRuntimeProcessTransport:
    """Transport that invokes a C++ runtime executable for each command.

    Spawns a subprocess: ``executable_path <command>``, reads stdout as JSON,
    and parses it into a RuntimeStatus.

    Args:
        executable_path: Path (or list of args) to invoke.  A list is useful
            for ``["python", "script.py"]`` in tests.
        timeout_seconds: Max wait time for each subprocess call.
    """

    executable_path: str | list[str]
    extra_args: list[str] | None = None
    config_file_path: str | None = None
    timeout_seconds: float = 5.0

    def request(self, command: RuntimeCommand) -> RuntimeStatus:
        cmd = (
            list(self.executable_path)
            if isinstance(self.executable_path, list)
            else [str(self.executable_path)]
        )
        cmd.append(command.command)
        if self.extra_args:
            cmd.extend(self.extra_args)
        if command.command == "start" and self.config_file_path is not None:
            cmd.extend(["--config-file", self.config_file_path])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Runtime executable not found: {cmd[0]!r}"
            ) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Runtime process timed out after "
                f"{self.timeout_seconds:.1f}s: {cmd!r}"
            ) from None
        except OSError as exc:
            raise RuntimeError(
                f"Runtime process failed to start: {cmd[0]!r}: {exc}"
            ) from None

        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""

        # Try to parse stdout as RuntimeStatus regardless of exit code.
        # The C++ runtime returns valid JSON even on error (e.g. UNKNOWN_COMMAND).
        try:
            data = json.loads(stdout)
            return RuntimeStatus.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

        # If parsing failed and process exited non-zero, surface the error.
        if proc.returncode != 0:
            detail = stdout or stderr or "(no output)"
            raise RuntimeError(
                f"Runtime process exited with code {proc.returncode}: "
                f"{detail[:500]}"
            )

        raise RuntimeError(
            f"Runtime process returned unparseable output: {stdout[:200]!r}"
        )


class CppRuntimeClient:
    def __init__(
        self,
        transport: RuntimeTransport,
        config_file_path: str | None = None,
    ) -> None:
        self._transport = transport
        self._config_file_path = config_file_path

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        if self._config_file_path is not None:
            p = Path(self._config_file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(config.model_dump(mode="json"), ensure_ascii=False),
                encoding="utf-8",
            )
        return self._transport.request(RuntimeCommand(command="start", config=config))

    def stop(self) -> RuntimeStatus:
        return self._transport.request(RuntimeCommand(command="stop"))

    def status(self) -> RuntimeStatus:
        return self._transport.request(RuntimeCommand(command="status"))
