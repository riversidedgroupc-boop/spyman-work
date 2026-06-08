# C++ Platform Integration Guide

## Overview

The C++ runtime (`cx_vision_runtime.exe`) owns real-time production execution.
Python remains the operator tooling: training, evaluation, dataset management,
reports, and the engineering UI.

## Required Runtime Files

Deploy the following to the target production machine:

| File | Purpose |
|------|---------|
| `cx_vision_runtime.exe` | C++ runtime executable |
| `model_artifacts/*.engine` | TensorRT engine files |
| `model_artifacts/class_mapping.json` | Class label mapping |
| `config/runtime_config.json` | Runtime session config (see below) |
| `calibration/*.json` | Camera calibration metadata (if used) |

## Runtime Protocol

The C++ runtime communicates via **one-shot CLI** invocations:

```
cx_vision_runtime.exe <command> [--state-file <path>] [--config-file <path>]
```

Each invocation is a separate process: the executable prints a single line of
JSON to stdout and exits. There is no persistent process, no stdin/stdout stream,
and no daemon lifecycle.

### Commands

#### status

```
cx_vision_runtime.exe status [--state-file <path>]
```

Returns current runtime state. Without `--state-file`, reports `stopped` (struct
defaults). See state-file semantics below for detailed behavior.

#### start

```
cx_vision_runtime.exe start --state-file <path> [--config-file <path>]
```

Starts a production run with an optional config file. The state file is persisted
on success. When `--config-file` is provided, the file is validated before the
state transition.

#### stop

```
cx_vision_runtime.exe stop --state-file <path>
```

Stops the current production run and persists `state=stopped`.

### stdout Protocol

Exactly one JSON object per invocation, following the `RuntimeStatus` schema:

```json
{"state":"running","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | `stopped`, `starting`, `running`, `stopping`, `error` |
| `uptime_ms` | int | Milliseconds since run started |
| `queue_size` | int | Pending frame count |
| `dropped_frames` | int | Frames dropped during run |
| `ng_count` | int | Non-good (defect) count |
| `error_code` | string | Machine-readable error code (empty on success) |
| `error_message` | string | Human-readable error message (empty on success) |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — `state` is `running`, `stopped`, `starting`, or `stopping` |
| 2 | Error — `state` is `error`. stdout is still valid JSON. |

### Error Codes

| Code | Trigger | Command |
|------|---------|---------|
| `UNKNOWN_COMMAND` | argv[1] is not `start`, `stop`, or `status` | any |
| `STATE_FILE_MISSING` | `--state-file` path does not exist (read-only commands) | status |
| `STATE_FILE_INVALID` | `--state-file` exists but cannot be parsed | any |
| `STATE_FILE_WRITE_FAILED` | `--state-file` path cannot be written | start, stop |
| `CONFIG_FILE_MISSING` | `--config-file` path does not exist | start |
| `CONFIG_FILE_INVALID` | `--config-file` exists but is unparseable or missing required fields | start |

### State File Semantics

- `--state-file` is optional. Without it, `status` always returns `stopped`
  (no persistence), and `start`/`stop` have no persistent effect.
- When provided, `status --state-file <nonexistent>` returns `state=stopped`
  (not an error). `start` creates the file on first run.
- A corrupted or unreadable state file returns `state=error` with
  `error_code=STATE_FILE_INVALID`.
- `start` and `stop` write or overwrite the state file on success.

### Config File Semantics

- `--config-file` is only meaningful with `start`.
- `start` without `--config-file` is allowed for backward compatibility.
- Required fields: `run_id`, `project_id`, `spec_id`, `backend`.
- Missing file -> `CONFIG_FILE_MISSING` (exit 2).
- Unparseable or missing required fields -> `CONFIG_FILE_INVALID` (exit 2).
- Additional fields beyond the required four are silently ignored.

### State File Format

Single-line JSON, same schema as the status output:

```json
{"state":"running","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}
```

### States

`stopped`, `starting`, `running`, `stopping`, `error`.

## State/Config Path Ownership

The **Python UI owns path management** for both state and config files. The C++
runtime only reads and writes files at the paths it receives via `argv`; it does
not create directories or resolve relative locations.

Recommended directory layout (managed by Python):

```
runtime/
  <run_id>/
    state.json         # C++ state file
    config.json        # C++ config file (written by Python before start)
```

The Python UI is responsible for:
1. Creating the `runtime/<run_id>/` directory before invoking `start`.
2. Writing `config.json` with the required four fields before invoking `start --config-file`.
3. Deleting or cleaning up state/config files when a run is finalized.

## Defect Events

Defect events are **not emitted** in the current one-shot CLI mode. This section
describes the schema reserved for a future long-running mode:

```json
{"event_id": "evt_000001", "run_id": "run_001", "camera_id": "cam_1", "timestamp_ms": 1717000000000, "meter_position": 12.34, "defect_type": "scratch", "confidence": 0.92, "bbox_xyxy": [10.0, 20.0, 110.0, 220.0], "image_path": "D:/data/ng/evt_000001.png", "model_version": "model_001"}
```

All string fields are JSON-escaped (quotes, backslashes, control characters).

## Future Upgrade Path

Long-running service mode (planned for a later phase) may replace the one-shot
CLI with a persistent process that accepts commands and emits events over
stdin/stdout (JSON Lines) or a named pipe. The `DefectEvent` schema above is
designed for that mode. Until then, all interaction is one-shot CLI only.

## Contract Version Compatibility

| Component | Version |
|-----------|---------|
| Runtime contract | 1.0.0 |
| CUDA | 11.8+ |
| TensorRT | 8.6+ |
| C++ standard | C++20 |

## Build

```powershell
# From the repository root
& 'C:\Program Files\CMake\bin\cmake.exe' -S cpp_runtime -B cpp_runtime\build
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

The built executable is at `cpp_runtime\build\cx_vision_runtime.exe`.

## Packaging

Build the C++ runtime first:

```powershell
& 'C:\Program Files\CMake\bin\cmake.exe' --build cpp_runtime\build --config Release
```

Package everything:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\cpp_runtime_package.ps1 -OutputDir "dist\cpp_runtime_package"
```

Output structure:

```
dist/cpp_runtime_package/
  cx_vision_runtime.exe
  config/
    runtime_config.example.json
  docs/
    cpp_runtime_contract.md
    cpp_platform_integration.md
```

Smoke test:

```powershell
dist\cpp_runtime_package\cx_vision_runtime.exe start --state-file dist\cpp_runtime_package\state.json --config-file dist\cpp_runtime_package\config\runtime_config.example.json
dist\cpp_runtime_package\cx_vision_runtime.exe status --state-file dist\cpp_runtime_package\state.json
dist\cpp_runtime_package\cx_vision_runtime.exe stop --state-file dist\cpp_runtime_package\state.json
```

## Integration Smoke Test

After deploying to the target machine:

```bash
# 1. Quick detection: check status without persistence
cx_vision_runtime.exe status

# 2. Create a minimal config file
echo {"run_id":"smoke_001","project_id":"p1","spec_id":"s1","backend":"cpp_runtime"} > runtime_config.json

# 3. Start a run with state-file and config-file persistence
cx_vision_runtime.exe start --state-file cx_state.json --config-file runtime_config.json

# 4. Verify running state persists
cx_vision_runtime.exe status --state-file cx_state.json

# 5. Stop gracefully
cx_vision_runtime.exe stop --state-file cx_state.json

# 6. Verify stopped
cx_vision_runtime.exe status --state-file cx_state.json
```

Expected: all commands return valid JSON. Exit code 0 for success, 2 for errors.
On error, stdout still contains valid JSON with `error_code` set.

## Migration Rule

Do not add Python-only fields to the runtime contract unless the C++ platform
can ignore them safely (extra="ignore" in the C++ parser) or validate them
explicitly. The contract must remain symmetrical between Python and C++.
