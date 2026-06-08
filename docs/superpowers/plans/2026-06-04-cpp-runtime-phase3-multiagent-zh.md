# C++ Runtime Phase 3 Multiagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `cpp_runtime` / `fake_cpp_runtime` 成为真正可选择的运行 backend，而不是 Python production pipeline 的旁路通知。

**Architecture:** `ProductionRunPage` 根据 backend 模式选择互斥启动路径：`python_runtime` 使用现有 Python acquisition/inference/timer；`fake_cpp_runtime` 和 `cpp_runtime` 只通过 `RuntimeBackend` 启停，并用 `RuntimeConfig` 文件把运行配置交给 C++。C++ runtime 继续保持 one-shot CLI，但 config 校验要覆盖关键结构字段。

**Tech Stack:** Python 3.12, PySide6, Pydantic v2, pytest, ruff, C++20, CMake.

---

## 多 Agent 分工

- Agent A: `ProductionRunPage` backend 互斥启动/停止。
- Agent B: `RuntimeConfig` 构建器和 Python contract 测试。
- Agent C: C++ config parser 增强，校验 `cameras` / `model_artifacts` 基本结构。
- Agent D: UI/backend 行为测试补全。
- Agent E: 文档更新。
- Agent F: 最终验证和工作区清单。

并行建议：
- Agent A 和 Agent B 会同时改 `desktop_app/pages/production_run_page.py`，不要并行改同一文件。建议 A 先做启动路径，B 再做 config 构建。
- Agent C 可与 A/B 并行。
- Agent D 等 A/B 完成后执行。
- Agent E 可与 C/D 并行。
- Agent F 最后执行。

不要 git commit，不要 git push。

---

## File Structure

### Python UI/runtime

- Modify: `desktop_app/pages/production_run_page.py`
  - backend 模式判断。
  - external runtime 启动/停止。
  - `RuntimeConfig` 构建。

- Modify: `core/runtime_contracts.py`
  - 原则上不改字段；只有确认必要时才改。

- Modify: `runtime/runtime_backend.py`
  - 原则上不改；已有 `config_file_path` / `state_file_path` 支持。

### C++ runtime

- Modify: `cpp_runtime/src/runtime_contracts.cpp`
  - 严格 JSON parser 基础上增加顶层字段结构校验。

- Modify: `cpp_runtime/include/cx_vision/runtime_contracts.hpp`
  - 如需暴露新 summary 字段才改。

### Tests

- Modify: `tests/test_production_runtime_modes.py`
- Modify: `tests/test_cpp_runtime_config_cli.py`
- Optional Modify: `tests/test_runtime_backend.py`

### Docs

- Modify: `docs/cpp_runtime_contract.md`
- Modify: `docs/cpp_platform_integration.md`

---

## Agent A: ProductionRunPage Backend Mutually Exclusive Startup

**Owner:** UI runtime control flow only.

**Files:**
- Modify: `desktop_app/pages/production_run_page.py`
- Do not touch C++.

### Task A1: Add backend mode helper

- [ ] Add helper method to `ProductionRunPage`:

```python
def _uses_external_runtime_backend(self) -> bool:
    return self._runtime_backend_name != "python_runtime"
```

Meaning:
- `python_runtime`: current Python acquisition/inference path.
- `fake_cpp_runtime`: external backend path.
- `cpp_runtime`: external backend path.

- [ ] No behavior change yet.

### Task A2: Split start path after setup succeeds

Current behavior still does camera setup/model setup and then starts Python pipeline. Change only the final start section.

Required behavior:

```python
if self._runtime_backend is not None:
    status = self._runtime_backend.start(cfg)
    if status.error_code:
        QMessageBox.warning(...)
        self._runtime_backend = None
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        return

if self._uses_external_runtime_backend():
    self._timer.start(500)
else:
    self._acq.start()
    if yolo_runner is not None or anomaly_runner is not None:
        self._inference.start()
    self._timer.start(200)

self._start_btn.setEnabled(False)
self._stop_btn.setEnabled(True)
```

Rules:
- external backend success must not call `_acq.start()`.
- external backend success must not call `_inference.start()`.
- external backend may start UI timer for status refresh.
- backend error must not enter running UI state.

### Task A3: Split stop path

Current `_stop()` always stops Python `_timer/_inference/_acq` first. Change to:

```python
if self._uses_external_runtime_backend():
    self._timer.stop()
    if self._runtime_backend is not None:
        status = self._runtime_backend.stop()
        ...
else:
    self._timer.stop()
    self._inference.stop()
    self._acq.stop()
```

Rules:
- external backend mode must not call `_acq.stop()` or `_inference.stop()`.
- always disable sampling controller after stop.
- always reset buttons after stop.

### Task A4: Run focused UI behavior tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected after Agent D tests exist: pass.

---

## Agent B: RuntimeConfig Builder From Real Page State

**Owner:** config construction only.

**Files:**
- Modify: `desktop_app/pages/production_run_page.py`
- Modify: `tests/test_production_runtime_modes.py`

### Task B1: Add `_build_runtime_config`

Add method:

```python
def _build_runtime_config(
    self,
    *,
    run_id: str,
    project_id: str,
    spec_id: str,
    camera_configs: dict[str, CameraConfig],
    yolo_model_id: str,
    anomaly_model_id: str,
    output_dir: str,
) -> RuntimeConfig:
    ...
```

Expected:
- returns `core.runtime_contracts.RuntimeConfig`.
- backend = `self._runtime_backend_name`.
- confidence = `0.5`.
- iou = `0.45`.
- output_dir = `output_dir`.

Camera mapping:

```python
CameraRuntimeConfig(
    camera_id=camera_id,
    camera_type="line_scan" if cfg.adapter_type in ("line_scan", "hikrobot_line_scan") else "area_scan",
    serial_number=cfg.serial_number or "",
    ip_address=cfg.ip_address or "",
    width=cfg.resolution_width or 0,
    height=cfg.resolution_height or 0,
    block_height=cfg.image_block_height or 1024,
    pixel_format=cfg.pixel_format or "Mono8",
    exposure_us=cfg.exposure_us,
    gain_db=cfg.gain_db,
    line_rate=cfg.line_rate,
)
```

Important:
- `CameraRuntimeConfig.width` requires `gt=0`. If `cfg.resolution_width` is missing, use a safe default:
  - line scan: `2048`
  - area scan/folder watcher: `1920`
- height may be `0`.

Model artifacts:
- if `yolo_model_id`, lookup `get_model_version(yolo_model_id)` and set `model_artifacts["yolo"] = model.model_path`.
- if `anomaly_model_id`, lookup and set `model_artifacts["anomaly"] = model.model_path`.
- if model lookup returns None, omit that artifact.

### Task B2: Use builder in `_start`

Replace inline:

```python
RuntimeConfig(run_id=run_id, project_id=project_id, spec_id=spec_id, backend=...)
```

with `_build_runtime_config(...)`.

Pass:
- `camera_configs=self._configured_adapters`
- selected `yolo_model_id`
- selected `anomaly_model_id`
- `output_dir=self._run_output_root`

### Task B3: Add config builder tests

In `tests/test_production_runtime_modes.py`, add tests:

```python
def test_build_runtime_config_maps_camera_configs(qapp):
    ...
```

Assertions:
- `config.run_id == "run_001"`
- `config.backend == "fake_cpp_runtime"`
- `len(config.cameras) == 2`
- line-scan camera has `camera_type == "line_scan"` and `block_height == 2048` if provided.
- area-scan camera has `camera_type == "area_scan"`.
- `config.output_dir` matches.

Add model artifact test:

```python
def test_build_runtime_config_includes_model_artifacts(qapp, monkeypatch):
    ...
```

Monkeypatch `desktop_app.pages.production_run_page.get_model_version` to return objects with `model_path`.

### Task B4: Run tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected: pass.

---

## Agent C: C++ Config Structure Validation

**Owner:** C++ parser and CLI tests only.

**Files:**
- Modify: `cpp_runtime/src/runtime_contracts.cpp`
- Modify: `tests/test_cpp_runtime_config_cli.py`

### Task C1: Add failing tests for config structure

Add to `tests/test_cpp_runtime_config_cli.py`:

```python
def test_start_with_cameras_object_returns_error(real_exe_path, tmp_path):
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":{}}',
        encoding="utf-8",
    )
    ...
    assert proc.returncode == 2
    assert payload["error_code"] == "CONFIG_FILE_INVALID"
```

```python
def test_start_with_model_artifacts_array_returns_error(real_exe_path, tmp_path):
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","model_artifacts":[]}',
        encoding="utf-8",
    )
    ...
    assert proc.returncode == 2
    assert payload["error_code"] == "CONFIG_FILE_INVALID"
```

```python
def test_start_with_cameras_array_and_model_artifacts_object_returns_running(real_exe_path, tmp_path):
    config_file.write_text(
        '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":[],"model_artifacts":{}}',
        encoding="utf-8",
    )
    ...
    assert proc.returncode == 0
    assert payload["state"] == "running"
```

### Task C2: Implement top-level type lookup

In `cpp_runtime/src/runtime_contracts.cpp`, add helper:

```cpp
char FindTopLevelValueFirstChar(const std::string& content, const std::string& target_key);
```

Behavior:
- parse only top-level object members.
- when key matches, skip whitespace after `:` and return first value char.
- if key missing, return `'\0'`.

Use it in `ReadRuntimeConfigFile`:

```cpp
char cameras_type = FindTopLevelValueFirstChar(content, "cameras");
if (cameras_type != '\0' && cameras_type != '[') return summary;

char artifacts_type = FindTopLevelValueFirstChar(content, "model_artifacts");
if (artifacts_type != '\0' && artifacts_type != '{') return summary;
```

Rules:
- `cameras` missing is allowed.
- `model_artifacts` missing is allowed.
- wrong type returns `CONFIG_FILE_INVALID`.

### Task C3: Run C++ tests

Build:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_config_cli.py -q -ra --tb=short
```

Expected: pass.

---

## Agent D: UI Backend Behavior Tests

**Owner:** tests only, unless tests reveal missing tiny helper.

**Files:**
- Modify: `tests/test_production_runtime_modes.py`

### Task D1: Add spies

Create small local classes inside tests:

```python
class SpyBackend:
    def __init__(self, start_status):
        self.start_status = start_status
        self.start_called = False
        self.stop_called = False
        self.started_config = None

    def start(self, config):
        self.start_called = True
        self.started_config = config
        return self.start_status

    def stop(self):
        self.stop_called = True
        return RuntimeStatus(state="stopped")

    def status(self):
        return RuntimeStatus(state="running")
```

```python
class SpyAcquisition:
    def __init__(self):
        self.start_called = False
        self.stop_called = False

    def start(self):
        self.start_called = True

    def stop(self):
        self.stop_called = True

    def set_encoder(self, encoder): ...
    def set_sampling_controller(self, sampling_controller): ...
    def get_status(self): return []
```

### Task D2: Add tests

Add tests:

- `test_python_runtime_start_uses_python_pipeline`
  - env default.
  - `_start()` calls `_acq.start()`.

- `test_external_runtime_start_does_not_start_python_pipeline`
  - env `CX_RUNTIME_BACKEND=fake_cpp_runtime`.
  - monkeypatch `create_backend` to return `SpyBackend(RuntimeStatus(state="running"))`.
  - `_start()` calls backend.start.
  - `_acq.start()` is not called.

- `test_external_runtime_start_error_blocks_pipeline`
  - already exists or update existing.
  - backend returns `RuntimeStatus(state="error", error_code="E_BACKEND")`.
  - `_acq.start()` not called.
  - `_stop_btn.isEnabled()` false.
  - `_start_btn.isEnabled()` true.

- `test_external_runtime_stop_does_not_stop_python_pipeline`
  - set page `_runtime_backend_name = "fake_cpp_runtime"`.
  - set `_runtime_backend = SpyBackend(...)`.
  - call `_stop()`.
  - backend.stop called.
  - `_acq.stop()` not called.

### Task D3: Run UI tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected: pass.

---

## Agent E: Documentation Update

**Owner:** docs only.

**Files:**
- Modify: `docs/cpp_runtime_contract.md`
- Modify: `docs/cpp_platform_integration.md`

### Task E1: Update backend mode semantics

Document:

- `python_runtime`: Python UI owns acquisition/inference.
- `fake_cpp_runtime`: test/development backend, no real C++ process.
- `cpp_runtime`: C++ runtime owns execution.

Production page behavior:
- external backend start happens before Python pipelines.
- external backend success does not start Python acquisition/inference.
- backend error blocks startup.

### Task E2: Update config schema

Document current required fields:

```json
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
  "output_dir": "D:/..."
}
```

Validation:
- required fields must be top-level strings.
- `cameras`, if present, must be array.
- `model_artifacts`, if present, must be object.
- extra fields ignored.

### Task E3: Docs scan

Run:

```powershell
rg -n "sidecar|旁路|JSON Lines|stdin|stdout stream|cameras|model_artifacts" docs\cpp_runtime_contract.md docs\cpp_platform_integration.md
```

Expected:
- no wording implying current `cpp_runtime` is only sidecar.
- JSON Lines only appears under future mode.

---

## Agent F: Final Verification

**Owner:** final build/test/lint report only.

### Task F1: Build C++

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Expected:

```text
[100%] Built target cx_vision_runtime
```

### Task F2: Run focused tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected:
- all pass.

### Task F3: Run source encoding test

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_source_encoding.py -q
```

Expected:
- pass.

### Task F4: Run ruff

```powershell
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core\runtime_contracts.py core\runtime_mode.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py runtime\runtime_backend.py desktop_app\pages\production_run_page.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py
```

Expected:

```text
All checks passed!
```

### Task F5: Manual CLI smoke

Run:

```powershell
$state='D:\work\copper-defect-eval-tool\cx_phase3_smoke_state.json'
$config='D:\work\copper-defect-eval-tool\cx_phase3_smoke_config.json'
Set-Content -LiteralPath $config -Value '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":[],"model_artifacts":{}}'
cpp_runtime\build\cx_vision_runtime.exe start --state-file $state --config-file $config
cpp_runtime\build\cx_vision_runtime.exe status --state-file $state
```

Expected:
- both return `state=running`.

Invalid smoke:

```powershell
$bad='D:\work\copper-defect-eval-tool\cx_phase3_bad_config.json'
Set-Content -LiteralPath $bad -Value '{"run_id":"r1","project_id":"p1","spec_id":"s1","backend":"cpp_runtime","cameras":{}}'
cpp_runtime\build\cx_vision_runtime.exe start --state-file $state --config-file $bad
```

Expected:
- `state=error`
- `error_code=CONFIG_FILE_INVALID`

### Task F6: Report git status

```powershell
git status --short -- core\runtime_contracts.py core\runtime_mode.py runtime\cpp_runtime_client.py runtime\runtime_backend.py desktop_app\pages\production_run_page.py cpp_runtime tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py tests\test_runtime_backend.py docs\cpp_runtime_contract.md docs\cpp_platform_integration.md
```

Report:
- modified files.
- new files.
- generated/temp files that should not be committed.

Do not delete files.
Do not commit.
Do not push.

---

## Acceptance Criteria

- `python_runtime` still starts the Python production pipeline.
- `fake_cpp_runtime` / `cpp_runtime` start through `RuntimeBackend` only.
- external backend success does not start Python acquisition/inference.
- external backend error blocks startup.
- external backend stop does not stop Python acquisition/inference.
- `RuntimeConfig` contains real cameras, model artifacts, output dir, and backend.
- C++ config parser rejects malformed JSON and wrong top-level structure.
- C++ config parser accepts valid config with `cameras: []` and `model_artifacts: {}`.
- Focused pytest, source encoding test, CMake build, and ruff all pass.

