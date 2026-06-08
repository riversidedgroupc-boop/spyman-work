# C++ Runtime Phase 4 Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先恢复全量测试绿色，再把 C++ runtime 从“可启动”推进到“可被 UI 监控、契约更严格、可交付打包”的下一阶段。

**Architecture:** Python UI 继续负责操作界面、训练、评估、数据管理；外部 runtime 模式下 Python 不连接相机、不加载模型，只写 `RuntimeConfig`、调用 C++ backend、轮询状态。C++ runtime 保持 one-shot CLI 协议，但配置校验要与 Python `RuntimeConfig` 合同更一致。

**Tech Stack:** Python 3.12, PySide6, Pydantic v2, pytest, ruff, C++20, CMake, Windows PowerShell.

---

## 执行规则

- 不要执行 `git commit`、`git push`、`git reset --hard`、`git rebase`。
- 不要删除文件。临时文件优先写到 `D:\work\...` 或 pytest 的 `tmp_path`。
- 每个 agent 完成后必须贴出：改动文件、验证命令、验证结果。
- 如果某一步发现已有未关联变更，不要回滚；只说明并继续处理本任务相关文件。
- 任务可并行，但建议先完成 Agent A，因为全量测试目前被它阻塞。

## 当前已知状态

- Runtime focused tests 已通过：`85 passed`。
- C++ build 已通过：`[100%] Built target cx_vision_runtime`。
- ruff focused check 已通过：`All checks passed!`
- C++ CLI smoke 已通过：
  - 合法 `cameras: []`, `model_artifacts: {}` 返回 `running`。
  - 非法 `cameras: {}` 返回 `CONFIG_FILE_INVALID`。
- 全量回归仍有已知失败：
  - `tests/test_config_backup.py::test_restore_backup`
  - 原因：测试调用 `restore_backup()` 默认恢复到项目根目录，尝试覆盖 `D:\work\copper-defect-eval-tool\config\ui_state.json`，在当前环境报 `PermissionError`。

## File Structure

- Modify: `core/config_backup.py`
  - 增加测试可控的 restore root，不让单测恢复到真实项目目录。
- Modify: `tests/test_config_backup.py`
  - 把 restore 测试改为恢复到 `tmp_path / "restore_root"`。
- Modify: `desktop_app/pages/production_run_page.py`
  - 外部 runtime 模式下增加 backend status 轮询显示，避免继续展示 Python acquisition/inference 的空状态。
- Modify: `tests/test_production_runtime_modes.py`
  - 增加外部 runtime 刷新 UI 时调用 backend.status、不调用 Python pipeline status 的测试。
- Modify: `core/runtime_contracts.py`
  - 如有必要，补齐 Python 合同字段约束，确保 C++ 校验目标明确。
- Modify: `cpp_runtime/src/runtime_contracts.cpp`
  - 加强 `model_artifacts` 与 `cameras` 的结构校验。
- Modify: `tests/test_cpp_runtime_config_cli.py`
  - 增加 C++ CLI 的非法结构测试。
- Create: `packaging/cpp_runtime_package.ps1`
  - 打包 C++ runtime exe、docs、示例 config。
- Create: `tests/test_cpp_runtime_package.py`
  - 测试打包脚本存在、可调用、输出目录结构正确。
- Modify: `docs/cpp_runtime_contract.md`
  - 同步外部 runtime UI 状态轮询、严格配置校验、打包说明。
- Modify: `docs/cpp_platform_integration.md`
  - 增加部署包结构和 smoke 测试步骤。

---

### Agent A: 修复 backup restore 红测试

**Files:**
- Modify: `core/config_backup.py`
- Modify: `tests/test_config_backup.py`

- [ ] **Step 1: 写失败测试，证明 restore 可以定向到临时目录**

在 `tests/test_config_backup.py` 中把 `test_restore_backup` 改为：

```python
def test_restore_backup(tmp_path):
    meta = create_backup(name="restore_test", backup_dir=str(tmp_path))
    restore_root = tmp_path / "restore_root"

    restored = restore_backup(
        meta.backup_id,
        backup_dir=str(tmp_path),
        restore_root=str(restore_root),
    )

    assert "data/app.db" in restored or any("data" in r for r in restored)
    assert restore_root.exists()
```

- [ ] **Step 2: 运行单测确认当前会失败**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_config_backup.py::test_restore_backup -q --tb=short
```

Expected before implementation: `TypeError: restore_backup() got an unexpected keyword argument 'restore_root'`

- [ ] **Step 3: 实现 `restore_root` 参数**

在 `core/config_backup.py` 中把函数签名和 root 选择改为：

```python
def restore_backup(
    backup_id: str,
    backup_dir: str | None = None,
    restore_root: str | None = None,
) -> list[str]:
    dest_dir = backup_dir or _default_backup_dir()
    zip_path = os.path.join(dest_dir, f"{backup_id}.zip")
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Backup not found: {zip_path}")

    root = restore_root or _project_root()
    root_abs = os.path.abspath(root)
    restored: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            target = _safe_restore_target(root_abs, member)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            zf.extract(member, root_abs)
            restored.append(member)
    return restored
```

- [ ] **Step 4: 验证 backup tests**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_config_backup.py -q -ra --tb=short
```

Expected: all tests in `tests/test_config_backup.py` pass.

- [ ] **Step 5: 验证不会破坏路径穿越保护**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_config_backup.py::test_restore_backup_rejects_path_traversal -q --tb=short
```

Expected: pass.

---

### Agent B: 外部 runtime 状态轮询接入 UI

**Files:**
- Modify: `desktop_app/pages/production_run_page.py`
- Modify: `tests/test_production_runtime_modes.py`

- [ ] **Step 1: 写测试，外部刷新必须调用 backend.status**

在 `tests/test_production_runtime_modes.py` 中新增测试。测试目标：外部 runtime 模式下 `_refresh_display()` 不调用 `_acq.get_status()`，而是调用 `_runtime_backend.status()` 并把 `fps_by_camera` 显示到 label。

```python
def test_external_runtime_refresh_uses_backend_status(qapp, monkeypatch):
    from core.runtime_contracts import RuntimeStatus
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    class StatusBackend:
        def __init__(self):
            self.status_called = False

        def start(self, config):
            return RuntimeStatus(state="running")

        def stop(self):
            return RuntimeStatus(state="stopped")

        def status(self):
            self.status_called = True
            return RuntimeStatus(
                state="running",
                uptime_ms=1234,
                fps_by_camera={"cam1": 25.5},
                queue_size=2,
                dropped_frames=1,
                ng_count=3,
            )

    class RaisingAcq:
        def get_status(self):
            raise AssertionError("external runtime must not read Python acquisition status")

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.BASELINE_CAPTURE)
        backend = StatusBackend()
        page._runtime_backend = backend
        page._acq = RaisingAcq()
        page._cam_status_labels["cam1"].setText("")

        page._refresh_display()

        assert backend.status_called
        assert "cam1" in page._cam_status_labels["cam1"].text()
        assert "25.5" in page._cam_status_labels["cam1"].text()
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)
```

- [ ] **Step 2: 运行测试确认当前失败**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py::test_external_runtime_refresh_uses_backend_status -q --tb=short
```

Expected before implementation: fail because `_refresh_display()` still reads `_acq.get_status()`.

- [ ] **Step 3: 增加外部状态刷新方法**

在 `desktop_app/pages/production_run_page.py` 的 `_refresh_display()` 开头加入外部模式分支，并新增 helper：

```python
    def _refresh_external_runtime_display(self) -> None:
        if self._runtime_backend is None:
            return
        try:
            status = self._runtime_backend.status()
        except Exception as exc:
            self._encoder_label.setText(f"Runtime status error: {exc}")
            return

        self._encoder_label.setText(
            f"Runtime: {status.state}  "
            f"uptime:{status.uptime_ms}ms  "
            f"queue:{status.queue_size}  "
            f"dropped:{status.dropped_frames}  "
            f"NG:{status.ng_count}"
        )
        for camera_id, fps in status.fps_by_camera.items():
            lbl = self._cam_status_labels.get(camera_id)
            if lbl is not None:
                lbl.setText(f"{camera_id}  FPS:{fps:.1f}  Runtime:{status.state}")
```

把 `_refresh_display()` 开头改为：

```python
    def _refresh_display(self):
        if self._uses_external_runtime_backend():
            self._refresh_external_runtime_display()
            return
```

- [ ] **Step 4: 验证外部刷新测试**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py::test_external_runtime_refresh_uses_backend_status -q --tb=short
```

Expected: pass.

- [ ] **Step 5: 验证生产 runtime tests**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_production_runtime_modes.py -q -ra --tb=short
```

Expected: pass.

---

### Agent C: 加强 C++ RuntimeConfig 结构校验

**Files:**
- Modify: `cpp_runtime/src/runtime_contracts.cpp`
- Modify: `tests/test_cpp_runtime_config_cli.py`
- Optional Modify: `docs/cpp_runtime_contract.md`

- [ ] **Step 1: 增加 C++ CLI 反例测试**

在 `tests/test_cpp_runtime_config_cli.py` 中新增两个测试：

```python
def test_start_with_model_artifacts_number_value_returns_error(real_exe_path, tmp_path):
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
        check=False,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 2
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"


def test_start_with_cameras_string_entry_returns_error(real_exe_path, tmp_path):
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
        check=False,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 2
    assert payload["state"] == "error"
    assert payload["error_code"] == "CONFIG_FILE_INVALID"
```

- [ ] **Step 2: 运行新增测试确认当前失败**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_config_cli.py::test_start_with_model_artifacts_number_value_returns_error tests\test_cpp_runtime_config_cli.py::test_start_with_cameras_string_entry_returns_error -q --tb=short
```

Expected before implementation: at least one test fails because C++ currently only checks top-level value type.

- [ ] **Step 3: 在 C++ 中实现最小结构检查**

在 `cpp_runtime/src/runtime_contracts.cpp` 中增加 helpers：

```cpp
bool TopLevelObjectStringValuesOnly(const std::string& content, const std::string& target_key);
bool TopLevelArrayObjectsOnly(const std::string& content, const std::string& target_key);
```

要求：
- `model_artifacts` 不存在时返回 true。
- `model_artifacts` 存在且为空对象 `{}` 返回 true。
- `model_artifacts` 每个 value 必须以 `"` 开头，否则 false。
- `cameras` 不存在时返回 true。
- `cameras` 存在且为空数组 `[]` 返回 true。
- `cameras` 每个 entry 必须以 `{` 开头，否则 false。
- 使用已有 `SkipJsonValueAt`, `ReadQuotedStringAt`, `SkipWhitespaceAt`，不要引入第三方 JSON 库。

在 `ReadRuntimeConfigFile()` 中加入：

```cpp
    if (!TopLevelArrayObjectsOnly(content, "cameras")) {
        return summary;
    }
    if (!TopLevelObjectStringValuesOnly(content, "model_artifacts")) {
        return summary;
    }
```

- [ ] **Step 4: 重新 build C++ runtime**

Run:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Expected: `[100%] Built target cx_vision_runtime`

- [ ] **Step 5: 验证 C++ config CLI tests**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_config_cli.py -q -ra --tb=short
```

Expected: pass.

---

### Agent D: C++ runtime 打包脚本

**Files:**
- Create: `packaging/cpp_runtime_package.ps1`
- Create: `tests/test_cpp_runtime_package.py`
- Modify: `docs/cpp_platform_integration.md`

- [ ] **Step 1: 写打包脚本测试**

新增 `tests/test_cpp_runtime_package.py`：

```python
from __future__ import annotations

from pathlib import Path


def test_cpp_runtime_package_script_exists() -> None:
    script = Path("packaging/cpp_runtime_package.ps1")
    assert script.is_file()
    content = script.read_text(encoding="utf-8")
    assert "cx_vision_runtime.exe" in content
    assert "cpp_runtime_contract.md" in content
    assert "runtime_config.example.json" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_package.py -q --tb=short
```

Expected before implementation: fail because script does not exist.

- [ ] **Step 3: 新增 PowerShell 打包脚本**

创建 `packaging/cpp_runtime_package.ps1`：

```powershell
param(
    [string]$Configuration = "Release",
    [string]$OutputDir = "dist\cpp_runtime_package"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ExePath = Join-Path $RepoRoot "cpp_runtime\build\cx_vision_runtime.exe"
$ContractDoc = Join-Path $RepoRoot "docs\cpp_runtime_contract.md"
$IntegrationDoc = Join-Path $RepoRoot "docs\cpp_platform_integration.md"

if (-not (Test-Path $ExePath)) {
    throw "Missing runtime executable: $ExePath"
}

$Out = Join-Path $RepoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $Out | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out "docs") | Out-Null

Copy-Item -LiteralPath $ExePath -Destination (Join-Path $Out "cx_vision_runtime.exe") -Force
Copy-Item -LiteralPath $ContractDoc -Destination (Join-Path $Out "docs\cpp_runtime_contract.md") -Force
Copy-Item -LiteralPath $IntegrationDoc -Destination (Join-Path $Out "docs\cpp_platform_integration.md") -Force

$ExampleConfig = @'
{
  "run_id": "smoke_001",
  "project_id": "project_001",
  "spec_id": "spec_001",
  "backend": "cpp_runtime",
  "cameras": [],
  "model_artifacts": {},
  "confidence": 0.5,
  "iou": 0.45,
  "save_policy": "save_ng_only",
  "output_dir": "D:/data/cx_runtime/output"
}
'@

Set-Content -LiteralPath (Join-Path $Out "config\runtime_config.example.json") -Value $ExampleConfig -Encoding UTF8
Write-Output "C++ runtime package written to: $Out"
```

- [ ] **Step 4: 运行测试**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_cpp_runtime_package.py -q --tb=short
```

Expected: pass.

- [ ] **Step 5: 运行打包脚本 smoke**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\cpp_runtime_package.ps1 -OutputDir "dist\cpp_runtime_package_smoke"
```

Expected: output contains `C++ runtime package written to:` and directory includes:
- `dist\cpp_runtime_package_smoke\cx_vision_runtime.exe`
- `dist\cpp_runtime_package_smoke\config\runtime_config.example.json`
- `dist\cpp_runtime_package_smoke\docs\cpp_runtime_contract.md`

---

### Agent E: 文档与最终验证

**Files:**
- Modify: `docs/cpp_runtime_contract.md`
- Modify: `docs/cpp_platform_integration.md`

- [ ] **Step 1: 更新 contract 文档**

在 `docs/cpp_runtime_contract.md` 中同步三点：

```markdown
### External Runtime UI Status

When `CX_RUNTIME_BACKEND` is `fake_cpp_runtime` or `cpp_runtime`, the UI must not
read Python acquisition or inference status. The production page polls
`RuntimeBackend.status()` and displays `RuntimeStatus` fields such as state,
uptime, queue size, dropped frames, NG count, and `fps_by_camera`.

### Strict Config Structure

The C++ runtime rejects invalid runtime config structures:

- `cameras` must be an array. If entries are present, each entry must be an object.
- `model_artifacts` must be an object. If entries are present, each value must be a string path.
```

- [ ] **Step 2: 更新 integration 文档**

在 `docs/cpp_platform_integration.md` 增加打包和 smoke 说明：

```markdown
## Packaging

Build first:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Package:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\cpp_runtime_package.ps1 -OutputDir "dist\cpp_runtime_package"
```

Smoke:

```powershell
dist\cpp_runtime_package\cx_vision_runtime.exe start --state-file dist\cpp_runtime_package\state.json --config-file dist\cpp_runtime_package\config\runtime_config.example.json
dist\cpp_runtime_package\cx_vision_runtime.exe status --state-file dist\cpp_runtime_package\state.json
dist\cpp_runtime_package\cx_vision_runtime.exe stop --state-file dist\cpp_runtime_package\state.json
```
```

- [ ] **Step 3: 运行 focused 验证**

Run:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests\test_config_backup.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py tests\test_cpp_runtime_package.py -q -ra --tb=short
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core\config_backup.py core\runtime_contracts.py core\runtime_mode.py runtime\fake_cpp_runtime.py runtime\cpp_runtime_client.py runtime\runtime_backend.py desktop_app\pages\production_run_page.py tests\test_config_backup.py tests\test_runtime_contracts.py tests\test_fake_cpp_runtime.py tests\test_cpp_runtime_client.py tests\test_runtime_backend.py tests\test_cpp_runtime_config_cli.py tests\test_production_runtime_modes.py tests\test_cpp_runtime_package.py
```

Expected:
- C++ build succeeds.
- pytest focused suite passes.
- ruff reports `All checks passed!`.

- [ ] **Step 4: 运行全量测试**

Run:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'; .\.venv\Scripts\python.exe -m pytest tests -q -ra --tb=short
```

Expected:
- If pass: report full test count.
- If fail: paste first failing test name, traceback summary, and explain whether it is related to this plan.

---

## Multi-Agent Dispatch 建议

- Agent A 先跑，优先恢复全量回归入口。
- Agent B 和 Agent C 可以并行。
- Agent D 可以与 Agent B/C 并行，但最终 smoke 依赖 C++ build。
- Agent E 最后跑，做文档收口和最终验证。

## 最终交付清单

- `tests/test_config_backup.py::test_restore_backup` 不再写真实项目根目录。
- 外部 runtime UI status 刷新来自 `RuntimeBackend.status()`。
- C++ runtime 拒绝 `model_artifacts` 非字符串值和 `cameras` 非对象 entry。
- C++ runtime 有 Windows 打包脚本和基础包结构测试。
- CMake build、focused pytest、ruff 通过。
- 全量 pytest 至少重新执行一次，并报告结果。
