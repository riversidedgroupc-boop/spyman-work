# C++ Runtime Phase 2 Multiagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 one-shot C++ runtime 从“可 start/stop/status”推进到“能接收 `RuntimeConfig`、固化 JSON 协议、具备平台集成入口、可被 Python UI 稳定选择”的下一阶段。

**Architecture:** Python UI 仍保留，runtime contract 作为 Python/C++ 的唯一边界。C++ runtime 先保持 one-shot CLI 模式，通过 `--config-file` 和 `--state-file` 传递配置与状态；后续再升级为 long-running service/JSON Lines。

**Tech Stack:** Python 3.12, Pydantic v2, pytest, ruff, C++17, CMake, Windows process integration.

---

## 多 Agent 分工原则

- Agent A 只做 Python contract/config 序列化。
- Agent B 只做 C++ config 读取和状态响应。
- Agent C 只做 backend factory/runtime mode 接入。
- Agent D 只做文档和测试矩阵。
- Agent E 只做构建、验证、清理和提交前复核。

不要让多个 agent 同时改同一个文件。每个 agent 完成后先运行自己的聚焦测试，再交给主 agent 汇总。

---

## File Structure

### Python contract/runtime

- Modify: `core/runtime_contracts.py`
  - 保持 `RuntimeConfig` / `CameraRuntimeConfig` / `RuntimeStatus` 为唯一协议模型。
  - 不新增 UI 字段；只新增协议必要字段。

- Modify: `runtime/cpp_runtime_client.py`
  - 负责把 `RuntimeCommand` 传给 C++ runtime。
  - 下一步增加 start config 的文件传递能力。

- Modify: `runtime/runtime_backend.py`
  - 负责 backend 创建、`state_file_path`、`config_file_path` 的连接。

### C++ runtime

- Modify: `cpp_runtime/include/cx_vision/runtime_contracts.hpp`
  - 增加 C++ 侧 config structs 或最小配置读取函数声明。

- Modify: `cpp_runtime/src/runtime_contracts.cpp`
  - 增加 config JSON 读取。
  - 保持状态 JSON 输出稳定。

- Modify: `cpp_runtime/src/main.cpp`
  - 增加 `--config-file <path>`。
  - `start` 时读取 config 并在 state file 里记录关键字段。

### Tests

- Modify: `tests/test_cpp_runtime_client.py`
- Modify: `tests/test_runtime_backend.py`
- Create or Modify: `tests/test_cpp_runtime_config_cli.py`

### Docs

- Modify: `docs/cpp_runtime_contract.md`
- Modify: `docs/cpp_platform_integration.md`

---

## Agent A: Python RuntimeConfig To C++ CLI Contract

**Owner:** Python protocol side only.

**Files:**
- Modify: `runtime/cpp_runtime_client.py`
- Modify: `runtime/runtime_backend.py`
- Modify: `tests/test_cpp_runtime_client.py`
- Modify: `tests/test_runtime_backend.py`

### Task A1: Add config file argument support to process transport

- [ ] Add a focused failing test in `tests/test_cpp_runtime_client.py`.

Expected test intent:

```python
def test_start_with_config_file_passes_config_file_arg(
    self, python_exe, tmp_path
) -> None:
    out_path = tmp_path / "argv.json"
    config_path = tmp_path / "runtime_config.json"
    spy_path = tmp_path / "spy.py"
    spy_path.write_text(
        "import json, sys\n"
        "with open(" + repr(str(out_path)) + ", 'w') as f:\n"
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
    assert captured[captured.index("--config-file") + 1] == str(config_path)
```

- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_client.py::TestCppRuntimeProcessTransport::test_start_with_config_file_passes_config_file_arg -q
```

Expected: fail because `config_file_path` is not implemented.

- [ ] Implement `config_file_path: str | None = None` in `CppRuntimeProcessTransport`.

Rules:
- append `--config-file <path>` only when `command.command == "start"` and `config_file_path` is not `None`.
- keep `status` and `stop` unchanged.
- do not serialize config here yet; Agent A2 handles writing JSON.

- [ ] Run the same test again.

Expected: pass.

### Task A2: Serialize RuntimeConfig before start

- [ ] Add test in `tests/test_cpp_runtime_client.py` proving start writes JSON.

Expected behavior:
- `CppRuntimeClient.start(config)` writes config JSON to `config_file_path`.
- JSON uses `RuntimeConfig.model_dump(mode="json")`.
- transport then calls C++ with `--config-file`.

Implementation approach:
- Keep `CppRuntimeProcessTransport` responsible for process argv only.
- Let `CppRuntimeClient` accept optional `config_file_path`.
- In `CppRuntimeClient.start`, if path is provided:
  - create parent directory if needed.
  - write UTF-8 JSON.
  - then call transport.

Suggested method signature:

```python
class CppRuntimeClient:
    def __init__(
        self,
        transport: RuntimeTransport,
        config_file_path: str | None = None,
    ) -> None:
        self._transport = transport
        self._config_file_path = config_file_path
```

Suggested write logic:

```python
if self._config_file_path is not None:
    path = Path(self._config_file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
```

- [ ] Add imports:

```python
from pathlib import Path
```

- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_client.py -q
```

Expected: pass.

### Task A3: Wire config_file_path through backend factory

- [ ] Add tests in `tests/test_runtime_backend.py`.

Expected assertions:

```python
backend = create_backend(
    "cpp_runtime",
    executable_path="/fake/exe",
    state_file_path="/tmp/state.json",
    config_file_path="/tmp/config.json",
)
assert isinstance(backend, CppRuntimeProcessBackend)
assert backend._client._config_file_path == "/tmp/config.json"
assert backend._client._transport.config_file_path == "/tmp/config.json"
```

- [ ] Modify `CppRuntimeProcessBackend.__init__` to accept `config_file_path`.
- [ ] Modify `create_backend(...)` to accept and forward `config_file_path`.
- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_backend.py tests\test_cpp_runtime_client.py -q
```

Expected: pass.

---

## Agent B: C++ RuntimeConfig Reader And CLI Behavior

**Owner:** C++ runtime only.

**Files:**
- Modify: `cpp_runtime/include/cx_vision/runtime_contracts.hpp`
- Modify: `cpp_runtime/src/runtime_contracts.cpp`
- Modify: `cpp_runtime/src/main.cpp`
- Modify: `tests/test_runtime_backend.py`
- Create: `tests/test_cpp_runtime_config_cli.py`

### Task B1: Add C++ config-file CLI parsing

- [ ] Update `Args` in `cpp_runtime/src/main.cpp`.

Expected:

```cpp
struct Args {
    std::string command;
    std::string state_file;
    std::string config_file;
};
```

- [ ] Update `ParseArgs` to support:

```text
--state-file <path>
--config-file <path>
```

Rules:
- unknown flags may be ignored for now, but missing value must not crash.
- `--config-file` is only meaningful for `start`.

- [ ] Build:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Expected: build succeeds.

### Task B2: Add minimal RuntimeConfig parsing in C++

Keep it minimal. Do not introduce external JSON dependency unless already vendored.

- [ ] Add struct in `runtime_contracts.hpp`:

```cpp
struct RuntimeConfigSummary {
    std::string run_id{};
    std::string project_id{};
    std::string spec_id{};
    std::string backend{};
    bool valid{false};
    std::string error_code{};
    std::string error_message{};
};

RuntimeConfigSummary ReadRuntimeConfigFile(const std::string& path);
```

- [ ] Implement `ReadRuntimeConfigFile` in `runtime_contracts.cpp`.

Minimum behavior:
- missing file -> `CONFIG_FILE_MISSING`
- malformed file or missing required key -> `CONFIG_FILE_INVALID`
- valid file -> extract `run_id`, `project_id`, `spec_id`, `backend`, `valid=true`

Required keys:
- `run_id`
- `project_id`
- `spec_id`
- `backend`

- [ ] Add tests through CLI rather than direct C++ unit framework.

Create `tests/test_cpp_runtime_config_cli.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def real_exe_path(tmp_path_factory):
    path = (
        Path(__file__).resolve().parents[1]
        / "cpp_runtime"
        / "build"
        / "cx_vision_runtime.exe"
    )
    if not path.exists():
        pytest.skip("cpp_runtime/build/cx_vision_runtime.exe is not built")
    try:
        probe = subprocess.run(
            [str(path), "status"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except OSError as exc:
        pytest.skip(f"cx_vision_runtime.exe cannot start: {exc}")
    if probe.returncode != 0:
        pytest.fail((probe.stdout or probe.stderr).strip())
    return str(path)


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
```

- [ ] Run expected failing tests first:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_config_cli.py -q
```

Expected: fail before implementation, pass after implementation.

### Task B3: Start requires config only when `--config-file` is passed

Rules:
- `start` without `--config-file` remains allowed for old tests.
- `start --config-file missing.json` returns `CONFIG_FILE_MISSING`.
- `start --config-file invalid.json` returns `CONFIG_FILE_INVALID`.
- valid config returns running.

- [ ] Implement in `main.cpp` before setting `status.state = "running"`.

Expected pseudocode:

```cpp
if (args.command == "start" && !args.config_file.empty()) {
    auto config = cx_vision::ReadRuntimeConfigFile(args.config_file);
    if (!config.valid) {
        status.state = "error";
        status.error_code = config.error_code;
        status.error_message = config.error_message;
    } else {
        status.state = "running";
    }
}
```

- [ ] Build C++.
- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_config_cli.py tests\test_runtime_backend.py -q
```

Expected: pass.

---

## Agent C: Runtime Mode Integration In Python App

**Owner:** backend selection only. Do not modify UI layout.

**Files to inspect first:**
- `core/runtime_mode.py`
- `tests/test_production_runtime_modes.py`
- `desktop_app/pages/production_run_page.py`
- `desktop_app/pages/inference_page.py`
- `desktop_app/pages/monitor_page.py`
- `runtime/runtime_backend.py`

### Task C1: Locate existing runtime selection path

- [ ] Run:

```powershell
rg -n "create_backend|cpp_runtime|fake_cpp_runtime|python_runtime|RuntimeBackend|runtime_mode" core runtime desktop_app tests
```

- [ ] Document in agent response:
  - where UI/runtime decides backend.
  - whether `create_backend("cpp_runtime")` is reachable.
  - which path currently provides `executable_path`.

No code changes in C1.

### Task C2: Add config/state path resolver for cpp runtime

Expected behavior:
- state/config files should live under project/workspace runtime directory, not random temp path.
- paths must be deterministic per run.

Suggested helper:
- Create or modify `core/runtime_mode.py`.

Expected function:

```python
from pathlib import Path


def cpp_runtime_paths(base_dir: Path, run_id: str) -> tuple[Path, Path]:
    runtime_dir = base_dir / "runtime" / run_id
    return runtime_dir / "state.json", runtime_dir / "config.json"
```

Add tests in `tests/test_production_runtime_modes.py`:

```python
def test_cpp_runtime_paths_are_run_scoped(tmp_path):
    state_path, config_path = cpp_runtime_paths(tmp_path, "run_001")

    assert state_path == tmp_path / "runtime" / "run_001" / "state.json"
    assert config_path == tmp_path / "runtime" / "run_001" / "config.json"
```

- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py -q
```

Expected: pass.

### Task C3: Wire cpp runtime backend with both files

- [ ] Find the runtime start call.
- [ ] When backend is `cpp_runtime`, pass:
  - `executable_path`
  - `state_file_path`
  - `config_file_path`

Do not hardcode `cpp_runtime/build/cx_vision_runtime.exe` in UI code unless there is already a dev-mode convention. Prefer config/env/settings.

Acceptance:
- `python_runtime` still works.
- `fake_cpp_runtime` still works.
- `cpp_runtime` errors clearly when executable is missing.

- [ ] Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py tests\test_runtime_backend.py -q
```

Expected: pass.

---

## Agent D: Protocol Docs And Platform Handoff

**Owner:** documentation only.

**Files:**
- Modify: `docs/cpp_runtime_contract.md`
- Modify: `docs/cpp_platform_integration.md`

### Task D1: Update current protocol contract

`docs/cpp_runtime_contract.md` must state current mode exactly:

- CLI mode: one process per command.
- Commands:
  - `cx_vision_runtime.exe status --state-file <path>`
  - `cx_vision_runtime.exe start --state-file <path> --config-file <path>`
  - `cx_vision_runtime.exe stop --state-file <path>`
- stdout: exactly one JSON object.
- non-zero exit may still emit valid JSON error status.
- Python parses stdout JSON first, then checks process error only if stdout is invalid.

Add error codes:

```text
UNKNOWN_COMMAND
STATE_FILE_MISSING
STATE_FILE_INVALID
STATE_FILE_WRITE_FAILED
CONFIG_FILE_MISSING
CONFIG_FILE_INVALID
```

### Task D2: Add platform integration checklist

`docs/cpp_platform_integration.md` must include:

- C++ platform team only needs to implement the contract.
- Python UI can remain as operator console during migration.
- State/config path ownership.
- How to build:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

- How to smoke test:

```powershell
cpp_runtime\build\cx_vision_runtime.exe status
cpp_runtime\build\cx_vision_runtime.exe start --state-file D:\work\cx_state.json --config-file D:\work\runtime_config.json
cpp_runtime\build\cx_vision_runtime.exe stop --state-file D:\work\cx_state.json
```

### Task D3: Run docs sanity check

- [ ] Run:

```powershell
rg -n "JSON Lines|stdin|stdout stream|future" docs\cpp_runtime_contract.md docs\cpp_platform_integration.md
```

Expected:
- Current one-shot CLI is not incorrectly described as JSON Lines.
- JSON Lines may be mentioned only under future long-running service section.

---

## Agent E: Final Verification And Merge Readiness

**Owner:** verification only. Do not implement feature logic unless a previous agent left a failing test.

### Task E1: Build C++

Run:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Expected:

```text
[100%] Built target cx_vision_runtime
```

### Task E2: Run focused tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected:
- all selected tests pass.
- if Windows application control blocks the C++ exe, only the real-exe integration tests may skip; pure Python tests must pass.

### Task E3: Run lint

Preferred:

```powershell
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core\runtime_contracts.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py runtime\runtime_backend.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py
```

Fallback if that Python is blocked:

```powershell
.\.venv\Scripts\python.exe -m ruff check core\runtime_contracts.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py runtime\runtime_backend.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py
```

Expected: `All checks passed!`

### Task E4: Encoding scan for touched files

Run:

```powershell
rg -n -P "[^\x00-\x7F]" cpp_runtime\src cpp_runtime\include runtime\cpp_runtime_client.py runtime\runtime_backend.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py
```

Expected:
- no output, unless Chinese text exists only in markdown docs.

### Task E5: Git status summary

Run:

```powershell
git status --short -- core\runtime_contracts.py runtime\cpp_runtime_client.py runtime\runtime_backend.py cpp_runtime tests docs\cpp_runtime_contract.md docs\cpp_platform_integration.md
```

Report:
- new files.
- modified files.
- any generated artifacts that should stay ignored, especially `cpp_runtime/build/`.

Do not run `git commit` or `git push`.

---

## Recommended Agent Execution Order

1. Agent A: Python config-file plumbing.
2. Agent B: C++ config-file reader and CLI behavior.
3. Agent C: runtime mode integration.
4. Agent D: docs update.
5. Agent E: final verification.

Agents A and B can start in parallel only if Agent A does not touch C++ and Agent B does not touch Python transport. Agent C must wait for Agent A. Agent E must run last.

---

## Acceptance Criteria

- `start` can send `RuntimeConfig` to C++ through `--config-file`.
- C++ runtime returns clear JSON errors for missing/invalid config files.
- State file read/write behavior remains stable.
- Python backend factory supports `executable_path`, `state_file_path`, and `config_file_path`.
- Existing fake/runtime tests still pass.
- C++ build passes.
- Docs describe current one-shot CLI contract, not future JSON Lines mode.
- No new generated build artifacts are tracked.

