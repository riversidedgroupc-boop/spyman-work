from __future__ import annotations

import json
import queue
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.runtime_contracts import RuntimeConfig, RuntimeStatus


@dataclass
class CppRuntimeStdioBackend:
    """Long-lived C++ runtime backend communicating over stdin/stdout.

    Launches ``cx_vision_runtime.exe serve`` as a child process.
    Commands are written as JSONL to stdin; events (status/error/log) are
    read as JSONL from stdout by a background reader thread and queued.

    ``start(config)`` writes the config to a temp file and passes its path
    to the C++ process via the JSONL ``config_path`` field.

    Current scope (Phase 5A): stub — no cameras, no models, no PLC.
    """

    executable_path: str
    startup_timeout: float = 10.0
    request_timeout: float = 5.0
    _process: subprocess.Popen | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _event_queue: queue.Queue = field(default_factory=queue.Queue, init=False)
    _reader_thread: threading.Thread | None = field(default=None, init=False)
    _reader_running: bool = field(default=False, init=False)
    _config_file: Path | None = field(default=None, init=False)

    # ── public API (RuntimeBackend protocol) ────────────────────────────

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        with self._lock:
            self._ensure_running()
            self._write_config_file(config)
            self._send_command("start", config_path=str(self._config_file or ""))
            return self._read_status()

    def stop(self) -> RuntimeStatus:
        with self._lock:
            self._ensure_running()
            self._send_command("stop")
            return self._read_status()

    def status(self) -> RuntimeStatus:
        with self._lock:
            self._ensure_running()
            self._send_command("status")
            return self._read_status()

    def shutdown(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._send_line(json.dumps({"command": "shutdown"}))
                    time.sleep(0.2)
                except Exception:
                    pass
            self._cleanup()

    # ── internals ───────────────────────────────────────────────────────

    def _write_config_file(self, config: RuntimeConfig) -> None:
        """Write RuntimeConfig as JSON to a temp file for the C++ process."""
        if self._config_file is None:
            tmp = Path(tempfile.mkdtemp(prefix="cx_runtime_config_"))
            self._config_file = tmp / "runtime_config.json"
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(mode="json"), f, ensure_ascii=False)

    def _ensure_running(self) -> None:
        if self._process is not None:
            if self._process.poll() is not None:
                self._cleanup()
            else:
                return
        self._launch()

    def _launch(self) -> None:
        self._process = subprocess.Popen(
            [self.executable_path, "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        self._event_queue = queue.Queue()
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

        t = threading.Thread(target=self._drain_stderr, daemon=True)
        t.start()

        try:
            event = self._event_queue.get(timeout=self.startup_timeout)
            if event.get("type") != "status":
                self._cleanup()
                raise RuntimeError(
                    f"Expected initial status, got {event.get('type')!r}"
                )
        except queue.Empty:
            self._cleanup()
            raise RuntimeError(
                f"serve process did not send initial status within "
                f"{self.startup_timeout:.1f}s"
            )

    def _reader_loop(self) -> None:
        """Background thread: read JSONL from stdout, push to queue."""
        assert self._process is not None
        stdout = self._process.stdout
        assert stdout is not None
        try:
            while self._reader_running:
                line_bytes = stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8").rstrip("\r\n")
                if line:
                    try:
                        event = json.loads(line)
                        self._event_queue.put(event)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    def _drain_stderr(self) -> None:
        """Prevent stderr buffer from blocking the child process."""
        assert self._process is not None
        stderr = self._process.stderr
        assert stderr is not None
        try:
            while True:
                chunk = stderr.read(4096)
                if not chunk:
                    break
        except Exception:
            pass

    def _send_command(self, command: str, **extra: object) -> None:
        msg: dict[str, object] = {"command": command}
        msg.update(extra)
        self._send_line(json.dumps(msg, ensure_ascii=False))

    def _send_line(self, line: str) -> None:
        assert self._process is not None
        stdin = self._process.stdin
        assert stdin is not None
        data = (line + "\n").encode("utf-8")
        stdin.write(data)
        stdin.flush()

    def _read_status(self) -> RuntimeStatus:
        """Read queued events until status or error response."""
        deadline = time.monotonic() + self.request_timeout
        while time.monotonic() < deadline:
            try:
                remaining = max(deadline - time.monotonic(), 0.1)
                event = self._event_queue.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(
                    f"No status response after {self.request_timeout:.1f}s"
                )

            etype = event.get("type")
            if etype == "status":
                return RuntimeStatus.model_validate(event["payload"])
            if etype == "error":
                payload = event["payload"]
                return RuntimeStatus(
                    state="error",
                    error_code=payload.get("code", "PIPE_ERROR"),
                    error_message=payload.get("message", ""),
                )
            if etype == "log":
                continue
            raise RuntimeError(f"Unexpected event type: {etype!r}")
        raise TimeoutError("No status response from serve process")

    def _cleanup(self) -> None:
        self._reader_running = False
        if self._config_file is not None:
            try:
                self._config_file.unlink(missing_ok=True)
            except Exception:
                pass
            self._config_file = None
        if self._process is not None:
            if self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            self._process = None

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception:
            pass
