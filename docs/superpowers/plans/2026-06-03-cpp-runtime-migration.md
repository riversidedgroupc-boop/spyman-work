# C++ Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a C++ production runtime path for CX-vision so the existing C++ platform can host real-time camera acquisition, line-scan tiling, inference, and defect event output while Python remains the training, evaluation, and engineering toolchain.

**Architecture:** Do not translate the whole Python application. First define stable runtime contracts, then add a small Python-side adapter and fake runtime for contract tests, then implement a C++ runtime skeleton with the same protocol. Only after the interface is proven should camera capture, tile generation, TensorRT inference, and postprocessing be moved into C++.

**Tech Stack:** Python 3.12, pytest, Pydantic v2, JSON Lines contract fixtures, C++20, CMake, optional GoogleTest, optional Protobuf/gRPC in later phases.

---

## Non-Goals

- Do not rewrite `desktop_app/`, `core/`, `trainers/`, reports, dataset builders, or field review workflows in C++.
- Do not remove existing Python runtime modules.
- Do not change `.env`, secrets, CI/CD, or deployment publishing.
- Do not introduce live camera SDK requirements into unit tests.
- Do not require TensorRT or CUDA for local unit tests.

## Target Boundary

The first C++ runtime boundary is a process or library named `cx_vision_runtime`.

Input:
- runtime session config
- camera config
- model artifact config
- product/spec metadata
- start/stop/status commands

Output:
- health status
- per-camera status
- defect events
- optional preview frame path or encoded preview payload
- runtime errors with stable codes

The Python application remains the operator tool during migration. It should be able to run either:
- `python_runtime`: current Python pipeline
- `cpp_runtime`: external C++ runtime adapter

---

## File Structure

Create:
- `core/runtime_contracts.py` - Pydantic models for runtime commands, status, and defect events.
- `tests/test_runtime_contracts.py` - contract serialization and validation tests.
- `runtime/cpp_runtime_client.py` - Python adapter for an external C++ runtime process.
- `tests/test_cpp_runtime_client.py` - adapter tests using a fake local server or fake transport.
- `runtime/fake_cpp_runtime.py` - deterministic fake runtime used by tests and UI smoke checks.
- `tests/test_fake_cpp_runtime.py` - fake runtime behavior tests.
- `cpp_runtime/CMakeLists.txt` - C++ runtime build root.
- `cpp_runtime/include/cx_vision/runtime_contracts.hpp` - C++ contract structs.
- `cpp_runtime/src/runtime_contracts.cpp` - JSON parsing/serialization helpers.
- `cpp_runtime/src/main.cpp` - CLI skeleton for start/status/stop test commands.
- `cpp_runtime/tests/test_runtime_contracts.cpp` - C++ contract tests if GoogleTest is available.
- `docs/cpp_runtime_contract.md` - human-readable contract for the C++ platform team.

Modify:
- `runtime/inference_pipeline.py` only if needed to expose a numpy/batch-friendly runner path later.
- `desktop_app/pages/production_run_page.py` only after the runtime client is tested.
- `pyproject.toml` only if adding test dependencies is unavoidable; prefer stdlib + existing Pydantic.

Do not modify:
- `core/storage.py` in the first phase.
- `model_runners/tensorrt_runner.py` until the contract and fake runtime pass.
- `camera_adapters/` until the C++ boundary is proven.

---

## Phase 1: Python Runtime Contract

### Task 1: Add Runtime Contract Models

**Files:**
- Create: `core/runtime_contracts.py`
- Test: `tests/test_runtime_contracts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_runtime_contracts.py`:

```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_runtime_contracts.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.runtime_contracts'`.

- [ ] **Step 3: Implement contract models**

Create `core/runtime_contracts.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RuntimeBackend = Literal["python_runtime", "cpp_runtime"]
CameraType = Literal["area_scan", "line_scan", "folder_watcher"]
RuntimeState = Literal["stopped", "starting", "running", "stopping", "error"]
CommandName = Literal["start", "stop", "status"]


class CameraRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: str = Field(min_length=1)
    camera_type: CameraType
    serial_number: str = ""
    ip_address: str = ""
    width: int = Field(gt=0)
    height: int = Field(default=0, ge=0)
    block_height: int = Field(default=1024, gt=0)
    pixel_format: str = "Mono8"
    exposure_us: float | None = Field(default=None, gt=0)
    gain_db: float | None = None
    line_rate: int | None = Field(default=None, gt=0)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    backend: RuntimeBackend = "python_runtime"
    cameras: list[CameraRuntimeConfig] = Field(default_factory=list)
    model_artifacts: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    iou: float = Field(default=0.45, ge=0.0, le=1.0)
    save_policy: str = "save_ng_only"
    output_dir: str = ""


class RuntimeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: CommandName
    config: RuntimeConfig | None = None


class RuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RuntimeState
    uptime_ms: int = Field(default=0, ge=0)
    fps_by_camera: dict[str, float] = Field(default_factory=dict)
    queue_size: int = Field(default=0, ge=0)
    dropped_frames: int = Field(default=0, ge=0)
    ng_count: int = Field(default=0, ge=0)
    error_code: str = ""
    error_message: str = ""


class DefectEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp_ms: int = Field(ge=0)
    meter_position: float
    defect_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_xyxy: list[float] = Field(min_length=4, max_length=4)
    image_path: str = ""
    model_version: str = ""
```

- [ ] **Step 4: Run test to verify pass**

Run the same pytest command.

Expected: PASS.

---

### Task 2: Add Contract Documentation

**Files:**
- Create: `docs/cpp_runtime_contract.md`

- [ ] **Step 1: Create contract document**

Create `docs/cpp_runtime_contract.md`:

```markdown
# CX-vision C++ Runtime Contract

## Purpose

The C++ runtime owns real-time production execution. Python owns training,
evaluation, dataset management, reports, and engineering UI during migration.

## Runtime Commands

All command payloads are JSON encoded using the schema in `core/runtime_contracts.py`.

### start

Starts a production run.

Required payload:
- `command`: `"start"`
- `config`: `RuntimeConfig`

### stop

Stops the current production run.

Required payload:
- `command`: `"stop"`

### status

Returns current runtime status.

Required payload:
- `command`: `"status"`

## RuntimeStatus

States:
- `stopped`
- `starting`
- `running`
- `stopping`
- `error`

`error_code` must be stable. Human-readable text belongs in `error_message`.

## DefectEvent

Each NG event must include:
- `event_id`
- `run_id`
- `camera_id`
- `timestamp_ms`
- `meter_position`
- `defect_type`
- `confidence`
- `bbox_xyxy`
- `image_path`
- `model_version`

## Migration Rule

Do not add Python-only fields to the runtime contract unless the C++ platform
can ignore them safely or validate them explicitly.
```

- [ ] **Step 2: No test needed**

This is a documentation-only task. Run contract tests from Task 1 to keep the schema honest.

---

## Phase 2: Fake Runtime and Python Adapter

### Task 3: Add Fake C++ Runtime

**Files:**
- Create: `runtime/fake_cpp_runtime.py`
- Test: `tests/test_fake_cpp_runtime.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fake_cpp_runtime.py`:

```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_fake_cpp_runtime.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement fake runtime**

Create `runtime/fake_cpp_runtime.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass

from core.runtime_contracts import DefectEvent, RuntimeConfig, RuntimeStatus


@dataclass
class FakeCppRuntime:
    _config: RuntimeConfig | None = None
    _started_at: float | None = None
    _ng_count: int = 0

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        self._config = config
        self._started_at = time.monotonic()
        return self.status()

    def stop(self) -> RuntimeStatus:
        self._config = None
        self._started_at = None
        return self.status()

    def status(self) -> RuntimeStatus:
        if self._config is None or self._started_at is None:
            return RuntimeStatus(state="stopped")
        uptime_ms = int((time.monotonic() - self._started_at) * 1000)
        return RuntimeStatus(
            state="running",
            uptime_ms=uptime_ms,
            fps_by_camera={c.camera_id: 30.0 for c in self._config.cameras},
            ng_count=self._ng_count,
        )

    def emit_test_defect(self, camera_id: str) -> DefectEvent:
        if self._config is None:
            raise RuntimeError("Fake runtime is not running")
        self._ng_count += 1
        return DefectEvent(
            event_id=f"fake_evt_{self._ng_count:06d}",
            run_id=self._config.run_id,
            camera_id=camera_id,
            timestamp_ms=int(time.time() * 1000),
            meter_position=1.23,
            defect_type="test_defect",
            confidence=0.9,
            bbox_xyxy=[10.0, 20.0, 110.0, 220.0],
            image_path="",
            model_version="fake_model",
        )
```

- [ ] **Step 4: Run test to verify pass**

Run the same pytest command.

Expected: PASS.

---

### Task 4: Add Python Client Interface

**Files:**
- Create: `runtime/cpp_runtime_client.py`
- Test: `tests/test_cpp_runtime_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cpp_runtime_client.py`:

```python
from __future__ import annotations

from core.runtime_contracts import RuntimeCommand, RuntimeConfig, RuntimeStatus
from runtime.cpp_runtime_client import CppRuntimeClient, InMemoryRuntimeTransport


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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_cpp_runtime_client.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement client and in-memory transport**

Create `runtime/cpp_runtime_client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
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


class CppRuntimeClient:
    def __init__(self, transport: RuntimeTransport) -> None:
        self._transport = transport

    def start(self, config: RuntimeConfig) -> RuntimeStatus:
        return self._transport.request(RuntimeCommand(command="start", config=config))

    def stop(self) -> RuntimeStatus:
        return self._transport.request(RuntimeCommand(command="stop"))

    def status(self) -> RuntimeStatus:
        return self._transport.request(RuntimeCommand(command="status"))
```

- [ ] **Step 4: Run test to verify pass**

Run the same pytest command.

Expected: PASS.

---

## Phase 3: C++ Runtime Skeleton

### Task 5: Add C++ Runtime Build Skeleton

**Files:**
- Create: `cpp_runtime/CMakeLists.txt`
- Create: `cpp_runtime/include/cx_vision/runtime_contracts.hpp`
- Create: `cpp_runtime/src/runtime_contracts.cpp`
- Create: `cpp_runtime/src/main.cpp`

- [ ] **Step 1: Create CMake project**

Create `cpp_runtime/CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.24)
project(cx_vision_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(cx_vision_runtime
    src/main.cpp
    src/runtime_contracts.cpp
)

target_include_directories(cx_vision_runtime PRIVATE include)
```

- [ ] **Step 2: Create header**

Create `cpp_runtime/include/cx_vision/runtime_contracts.hpp`:

```cpp
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace cx_vision {

struct RuntimeStatus {
    std::string state{"stopped"};
    std::int64_t uptime_ms{0};
    int queue_size{0};
    int dropped_frames{0};
    int ng_count{0};
    std::string error_code{};
    std::string error_message{};
};

struct DefectEvent {
    std::string event_id{};
    std::string run_id{};
    std::string camera_id{};
    std::int64_t timestamp_ms{0};
    double meter_position{0.0};
    std::string defect_type{};
    double confidence{0.0};
    std::vector<double> bbox_xyxy{};
    std::string image_path{};
    std::string model_version{};
};

std::string ToJsonLine(const RuntimeStatus& status);
std::string ToJsonLine(const DefectEvent& event);

}  // namespace cx_vision
```

- [ ] **Step 3: Create JSON-line implementation**

Create `cpp_runtime/src/runtime_contracts.cpp`:

```cpp
#include "cx_vision/runtime_contracts.hpp"

#include <sstream>

namespace cx_vision {

std::string ToJsonLine(const RuntimeStatus& status) {
    std::ostringstream out;
    out << "{\"state\":\"" << status.state << "\""
        << ",\"uptime_ms\":" << status.uptime_ms
        << ",\"queue_size\":" << status.queue_size
        << ",\"dropped_frames\":" << status.dropped_frames
        << ",\"ng_count\":" << status.ng_count
        << ",\"error_code\":\"" << status.error_code << "\""
        << ",\"error_message\":\"" << status.error_message << "\""
        << "}";
    return out.str();
}

std::string ToJsonLine(const DefectEvent& event) {
    std::ostringstream out;
    out << "{\"event_id\":\"" << event.event_id << "\""
        << ",\"run_id\":\"" << event.run_id << "\""
        << ",\"camera_id\":\"" << event.camera_id << "\""
        << ",\"timestamp_ms\":" << event.timestamp_ms
        << ",\"meter_position\":" << event.meter_position
        << ",\"defect_type\":\"" << event.defect_type << "\""
        << ",\"confidence\":" << event.confidence
        << ",\"bbox_xyxy\":[";
    for (std::size_t i = 0; i < event.bbox_xyxy.size(); ++i) {
        if (i != 0) {
            out << ",";
        }
        out << event.bbox_xyxy[i];
    }
    out << "]"
        << ",\"image_path\":\"" << event.image_path << "\""
        << ",\"model_version\":\"" << event.model_version << "\""
        << "}";
    return out.str();
}

}  // namespace cx_vision
```

- [ ] **Step 4: Create CLI skeleton**

Create `cpp_runtime/src/main.cpp`:

```cpp
#include "cx_vision/runtime_contracts.hpp"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    const std::string command = argc > 1 ? argv[1] : "status";

    cx_vision::RuntimeStatus status;
    if (command == "start") {
        status.state = "running";
    } else if (command == "stop") {
        status.state = "stopped";
    } else if (command == "status") {
        status.state = "stopped";
    } else {
        status.state = "error";
        status.error_code = "UNKNOWN_COMMAND";
        status.error_message = "Supported commands: start, stop, status";
    }

    std::cout << cx_vision::ToJsonLine(status) << '\n';
    return status.state == "error" ? 2 : 0;
}
```

- [ ] **Step 5: Build if CMake is installed**

Run:

```powershell
cmake -S cpp_runtime -B cpp_runtime\build
cmake --build cpp_runtime\build --config Release
```

Expected: `cx_vision_runtime.exe` is produced under `cpp_runtime\build`.

If CMake is not installed, record that as an environment gap and continue with Python tests.

---

## Phase 4: Real-Time Hot Path Migration

### Task 6: Replace Temporary-File Inference Boundary

**Files:**
- Modify: `model_runners/base.py`
- Modify: `model_runners/onnx_runner.py`
- Modify: `model_runners/yolo_runner.py`
- Modify: `runtime/inference_pipeline.py`
- Test: `tests/test_inference_pipeline.py` or a new focused test

Plan:
- Add optional `predict_array(image: np.ndarray) -> ImagePrediction` to runner protocol.
- Keep `predict_image(path)` for compatibility.
- Update `InferencePipeline` to call `predict_array()` when available.
- Fall back to current temp-file path only for old runners.

Acceptance:
- Existing tests pass.
- A new test verifies no temp file is written when a runner implements `predict_array`.

Do this before implementing C++ TensorRT. It removes a known Python-side bottleneck and gives the C++ runtime a cleaner input model.

---

### Task 7: Move Line-Scan Block and Tile Logic Behind a Runtime Interface

**Files:**
- Create: `runtime/runtime_backend.py`
- Modify: `runtime/acquisition_pipeline.py`
- Modify: `runtime/unified_image_pool.py` only if required
- Test: new focused runtime backend tests

Plan:
- Define `RuntimeBackend` protocol with `start(config)`, `stop()`, `status()`.
- Add `PythonRuntimeBackend` that wraps existing acquisition and scheduler modules.
- Add `CppRuntimeBackend` that wraps `CppRuntimeClient`.
- Keep `FakeCppRuntime` for tests.

Acceptance:
- UI or tests can choose backend by string: `python_runtime` or `cpp_runtime`.
- Current Python runtime still works.
- Fake C++ runtime can be selected without camera hardware.

---

### Task 8: Implement C++ TensorRT Runtime After Contract Stabilizes

**Files:**
- Modify/add under `cpp_runtime/`
- Modify: `docs/cpp_runtime_contract.md`
- Add tests with fake engine outputs

Plan:
- Add C++ modules in this order:
  1. `TensorRTEngine` with engine load and metadata validation.
  2. `ImagePreprocessor` for resize/normalize/HWC-to-CHW.
  3. `YoloPostProcessor` for output parsing and NMS.
  4. `RuntimeLoop` for input tile batch and event output.
  5. `HealthMonitor` for FPS, queue, errors.

Acceptance:
- TensorRT unavailable returns a stable error code, not a crash.
- Fake engine path can run tests without GPU.
- Real engine path is tested only on the target machine.

---

## Phase 5: C++ Platform Integration

### Task 9: Produce Platform Adapter Package

**Files:**
- Create: `docs/cpp_platform_integration.md`
- Create: `packaging/cpp_runtime_package.ps1` if packaging is needed

Plan:
- Document plugin ABI or process protocol used by the existing C++ platform.
- List required runtime files:
  - `cx_vision_runtime.exe`
  - model artifact `.engine` or `.onnx`
  - runtime config JSON
  - class mapping JSON
  - calibration metadata if used
- Include version compatibility:
  - runtime version
  - contract version
  - CUDA version
  - TensorRT version
  - GPU name

Acceptance:
- Platform team can launch runtime, call status, start/stop a run, and receive one fake defect event.

---

## Verification Commands

Run after each Python phase:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py -q
```

Run broader smoke tests before handing off:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests -q -x --tb=short
```

Run lint on changed Python files:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core\runtime_contracts.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py
```

Build C++ runtime if CMake is installed:

```powershell
cmake -S cpp_runtime -B cpp_runtime\build
cmake --build cpp_runtime\build --config Release
cpp_runtime\build\Release\cx_vision_runtime.exe status
```

---

## Recommended Claude Code Execution Order

1. Implement Phase 1 only.
2. Run the three focused tests.
3. Review the contract with the C++ platform team.
4. Implement Phase 2 fake runtime and client.
5. Add C++ skeleton in Phase 3.
6. Do not touch production camera or TensorRT code until the fake runtime path works.
7. Then migrate hot paths one at a time, starting with temp-file-free inference.

## Commit Guidance

Do not auto-commit unless the user asks.

If committing manually later, use small commits:

```text
feat: add runtime contract models
feat: add fake cpp runtime adapter
feat: scaffold cpp vision runtime
refactor: add array inference runner path
```

## Self-Review

- The plan keeps Python training and engineering workflows intact.
- The plan creates a testable C++ boundary before runtime rewrites.
- The plan avoids requiring camera hardware, CUDA, or TensorRT for unit tests.
- The plan does not remove or rewrite existing modules.
- The plan gives the existing C++ platform a stable contract to integrate against.
