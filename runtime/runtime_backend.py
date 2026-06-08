from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from core.runtime_contracts import RuntimeConfig, RuntimeStatus
from runtime.cpp_runtime_client import CppRuntimeClient, CppRuntimeProcessTransport
from runtime.fake_cpp_runtime import FakeCppRuntime


@runtime_checkable
class RuntimeBackend(Protocol):
    def start(self, config: RuntimeConfig) -> RuntimeStatus: ...
    def stop(self) -> RuntimeStatus: ...
    def status(self) -> RuntimeStatus: ...


@dataclass
class PythonRuntimeBackend:
    """Wraps the existing Python acquisition/inference runtime.

    This backend delegates to the current Python pipeline modules.
    During Phase 2 migration it provides the reference implementation.

    Currently uses a lightweight simulation until the full pipeline is
    wired in -- the contract tests pass and UI can select the backend.
    """

    _config: RuntimeConfig | None = None
    _started_at: float | None = None
    _running: bool = False

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        self._config = config
        self._started_at = time.monotonic()
        self._running = True
        return self.status()

    def stop(self) -> RuntimeStatus:
        self._running = False
        self._config = None
        self._started_at = None
        return self.status()

    def status(self) -> RuntimeStatus:
        if not self._running or self._config is None or self._started_at is None:
            return RuntimeStatus(state="stopped")
        uptime_ms = int((time.monotonic() - self._started_at) * 1000)
        return RuntimeStatus(
            state="running",
            uptime_ms=uptime_ms,
        )


@dataclass
class FakeCppRuntimeBackend:
    """Development-only backend wrapping FakeCppRuntime for contract testing.

    Does NOT connect to a real C++ process. Use when no C++ runtime binary
    is available, or in unit tests that need a deterministic fake.
    """

    _fake: FakeCppRuntime = field(default_factory=FakeCppRuntime)

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        return self._fake.start(config)

    def stop(self) -> RuntimeStatus:
        return self._fake.stop()

    def status(self) -> RuntimeStatus:
        return self._fake.status()


@dataclass
class CppRuntimeProcessBackend:
    """Real C++ runtime backend via process transport.

    Each start/stop/status call invokes the ``cx_vision_runtime.exe``
    subprocess.  This is the production backend for C++ platform
    integration.

    Args:
        executable_path: Path to ``cx_vision_runtime.exe``.
        state_file_path: If provided, the transport passes
            ``--state-file <path>`` to the runtime so state persists
            across one-shot invocations.
    """

    _client: CppRuntimeClient

    def __init__(
        self,
        executable_path: str,
        state_file_path: str | None = None,
        config_file_path: str | None = None,
    ) -> None:
        extra_args: list[str] | None = None
        if state_file_path is not None:
            extra_args = ["--state-file", state_file_path]
        self._client = CppRuntimeClient(
            transport=CppRuntimeProcessTransport(
                executable_path=executable_path,
                extra_args=extra_args,
                config_file_path=config_file_path,
            ),
            config_file_path=config_file_path,
        )

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        return self._client.start(config)

    def stop(self) -> RuntimeStatus:
        return self._client.stop()

    def status(self) -> RuntimeStatus:
        return self._client.status()


def create_backend(
    backend: str | RuntimeBackend,
    *,
    executable_path: str | None = None,
    state_file_path: str | None = None,
    config_file_path: str | None = None,
) -> RuntimeBackend:
    """Factory: create a runtime backend by name or pass through an instance.

    Args:
        backend: ``"python_runtime"``, ``"fake_cpp_runtime"``,
            ``"cpp_runtime"``, or a RuntimeBackend instance.
        executable_path: Required when ``backend="cpp_runtime"`` --
            path to ``cx_vision_runtime.exe``.
        state_file_path: Optional path for state-file persistence
            (only meaningful with ``backend="cpp_runtime"``).
        config_file_path: Optional path for runtime config JSON file
            (only meaningful with ``backend="cpp_runtime"``).

    Returns:
        Configured RuntimeBackend.

    Raises:
        ValueError: Unknown backend name, or ``"cpp_runtime"`` without
            ``executable_path``.
    """
    if isinstance(backend, RuntimeBackend):
        return backend
    if backend == "python_runtime":
        return PythonRuntimeBackend()
    if backend == "fake_cpp_runtime":
        return FakeCppRuntimeBackend()
    if backend == "cpp_runtime":
        if executable_path is None:
            raise ValueError(
                "backend='cpp_runtime' requires executable_path=... "
                "(path to cx_vision_runtime.exe)"
            )
        return CppRuntimeProcessBackend(
            executable_path=executable_path,
            state_file_path=state_file_path,
            config_file_path=config_file_path,
        )
    raise ValueError(f"Unknown backend: {backend!r}")
