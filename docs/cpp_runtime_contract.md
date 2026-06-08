# CX-vision C++ Runtime Contract

## Purpose

The C++ runtime (`cx_vision_runtime.exe`) owns real-time production execution.
Python owns training, evaluation, dataset management, reports, and the engineering
UI during migration.

## Backend Modes

The system supports three backend modes, selected via `backend` in the config file:

| Mode | Meaning |
|------|---------|
| `python_runtime` | Python UI owns the acquisition and inference pipeline. Default mode. |
| `fake_cpp_runtime` | Test/development backend; no real C++ process is spawned. Used for contract testing. |
| `cpp_runtime` | C++ runtime owns execution via one-shot CLI (`cx_vision_runtime.exe`). |

### Production Page Behavior

When the backend is external (`fake_cpp_runtime` or `cpp_runtime`):

1. **External backend start** happens before Python pipelines are started.
2. **External backend success** does NOT start Python acquisition/inference pipelines.
3. **Backend error** blocks startup entirely — no pipelines (Python or external) are started.
4. **External backend stop** does NOT stop Python acquisition/inference (they were never started).
5. **UI timer** runs for status refresh in all modes (Python and external).

### External Runtime UI Status

When `CX_RUNTIME_BACKEND` is `fake_cpp_runtime` or `cpp_runtime`, the production
page does NOT read Python acquisition or inference status. Instead it polls
`RuntimeBackend.status()` and displays `RuntimeStatus` fields: state, uptime,
queue size, dropped frames, NG count, and per-camera FPS from `fps_by_camera`.

The UI refresh cycle (`_refresh_display()`) delegates to
`_refresh_external_runtime_display()` which calls `backend.status()` and renders
the data into the encoder label and camera status labels.

## Protocol Overview

The runtime uses a **one-shot CLI** protocol: each invocation spawns a new process,
takes arguments via `argv`, prints exactly one JSON object to stdout, and exits.
There is no persistent daemon and no ongoing stdin/stdout stream.

## Commands

### status

```
cx_vision_runtime.exe status [--state-file <path>]
```

Returns current runtime status. Without `--state-file`, always reports `stopped`.

### start

```
cx_vision_runtime.exe start --state-file <path> [--config-file <path>]
```

Starts a production run. Requires a state file for persistence. A config file is
optional for backward compatibility.

### stop

```
cx_vision_runtime.exe stop --state-file <path>
```

Stops the current production run.

## stdout Protocol

Every invocation produces **exactly one** JSON object on stdout, representing a
`RuntimeStatus`. The format is always the same regardless of success or error:

```json
{"state":"running","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}
```

Fields:

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | `stopped`, `starting`, `running`, `stopping`, `error` |
| `uptime_ms` | int | Milliseconds since run started |
| `queue_size` | int | Pending frame count |
| `dropped_frames` | int | Frames dropped during run |
| `ng_count` | int | Non-good (defect) count |
| `error_code` | string | Machine-readable error identifier (empty on success) |
| `error_message` | string | Human-readable error detail (empty on success) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — `state` is `running`, `stopped`, or `starting` / `stopping` |
| 2 | Error — `state` is `error`. stdout still contains valid JSON with `error_code` set. |

## Error Codes

| Code | Trigger | Command |
|------|---------|---------|
| `UNKNOWN_COMMAND` | argv[1] is not `start`, `stop`, or `status` | any |
| `STATE_FILE_MISSING` | `--state-file` path does not exist (read-only commands) | status |
| `STATE_FILE_INVALID` | `--state-file` exists but cannot be parsed as valid JSON | any |
| `STATE_FILE_WRITE_FAILED` | `--state-file` path cannot be written | start, stop |
| `CONFIG_FILE_MISSING` | `--config-file` path does not exist | start |
| `CONFIG_FILE_INVALID` | `--config-file` exists but is unparseable or missing required fields | start |

## State File Semantics

- `--state-file` is **optional**. When omitted, the runtime operates in memory-only
  mode: `status` always reports `stopped` (struct defaults), and `start`/`stop`
  return the correct JSON but have no persistent effect.
- When `--state-file` is provided, `status` reads the file to determine runtime
  state. If the file does not exist, status reports `stopped` (not an error).
- If the file exists but is corrupted or unparseable, status returns `error`
  with `error_code=STATE_FILE_INVALID`.
- `start` and `stop` write or overwrite the state file on success.
- State file format: single-line JSON, same schema as the RuntimeStatus stdout output.

## Config File (RuntimeConfig JSON schema)

The config file is passed via `--config-file <path>` and must conform to the
`RuntimeConfig` JSON schema below.

### Schema

```json
{
  "run_id": "run_001",
  "project_id": "project_001",
  "spec_id": "spec_001",
  "backend": "cpp_runtime",
  "cameras": [
    {
      "camera_id": "cam1",
      "camera_type": "line_scan",
      "serial_number": "SN001",
      "ip_address": "",
      "width": 2048,
      "height": 1,
      "block_height": 2048,
      "pixel_format": "Mono8",
      "exposure_us": 100,
      "gain_db": 0.0,
      "line_rate": 20000
    }
  ],
  "model_artifacts": {
    "yolo": "/path/to/yolo.pt",
    "anomaly": "/path/to/patchcore.pt"
  },
  "confidence": 0.5,
  "iou": 0.45,
  "save_policy": "save_ng_only",
  "output_dir": "D:/data/output"
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | string | **yes** | Unique run identifier |
| `project_id` | string | **yes** | Project identifier |
| `spec_id` | string | **yes** | Spec/product identifier |
| `backend` | string | **yes** | Backend mode: `python_runtime`, `fake_cpp_runtime`, or `cpp_runtime` |
| `cameras` | array[object] | no | Camera config objects (see Camera Config below) |
| `model_artifacts` | object | no | String-to-string map of model names to file paths |
| `confidence` | number | no | Detection confidence threshold |
| `iou` | number | no | Detection IoU threshold |
| `save_policy` | string | no | Image save policy |
| `output_dir` | string | no | Output directory path |

#### Camera Config Object

| Field | Type | Description |
|-------|------|-------------|
| `camera_id` | string | Camera identifier |
| `camera_type` | string | Camera type (e.g., `line_scan`, `area_scan`) |
| `serial_number` | string | Camera serial number |
| `ip_address` | string | Camera IP address (empty if not network) |
| `width` | int | Sensor width in pixels |
| `height` | int | Sensor height in pixels |
| `block_height` | int | Line-scan block height |
| `pixel_format` | string | Pixel format (e.g., `Mono8`) |
| `exposure_us` | int | Exposure time in microseconds |
| `gain_db` | number | Gain in dB |
| `line_rate` | int | Line rate for line-scan cameras |

### Command Semantics

- `--config-file` is **only** meaningful with the `start` command.
- `start` without `--config-file` is allowed for backward compatibility.
- When provided, the config file must exist and be parseable as JSON.
- Missing file triggers `CONFIG_FILE_MISSING` (exit code 2).
- Parse failure or missing required fields triggers `CONFIG_FILE_INVALID` (exit code 2).
  In both cases the state file (if provided) is written with `state=error`.

### Validation Rules

1. `run_id`, `project_id`, `spec_id`, `backend` are **REQUIRED** top-level strings
   (all four must be present and non-empty).
2. `cameras`, if present, **MUST** be an array of camera config objects.
   It may be absent (backward compatible).
3. `model_artifacts`, if present, **MUST** be an object with string keys and
   string values. It may be absent (backward compatible).
4. Extra fields beyond those listed above are **silently ignored**.
5. The following all produce `CONFIG_FILE_INVALID`:
   - Malformed JSON (unbalanced braces, unquoted keys, trailing commas, missing commas).
   - Wrong type for `cameras` (e.g., a string or object instead of an array).
   - Wrong type for `model_artifacts` (e.g., an array or string instead of an object).

### Strict Config Structure

The C++ runtime rejects invalid runtime config structures beyond basic JSON
validation:

- `cameras` must be an array. If entries are present, each must be a JSON object (`{...}`).
- `model_artifacts` must be an object. If entries are present, each value must be a string.
- Violations return `CONFIG_FILE_INVALID`.

See `tests/test_cpp_runtime_config_cli.py` for the full set of config validation
tests.

## RuntimeStatus State Machine

- `stopped` --start--> `running`
- `running` --stop--> `stopped`
- any state --error--> `error`

`starting` and `stopping` are reserved for future long-running mode.

## DefectEvent

Defect events are **not** emitted in the current one-shot CLI mode. The
`DefectEvent` structure is defined for a future long-running mode (see
integration guide for details).

Required fields when used:

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | Unique event identifier |
| `run_id` | string | Active run ID |
| `camera_id` | string | Camera source identifier |
| `timestamp_ms` | int | Event timestamp (epoch ms) |
| `meter_position` | double | Meter position at time of event |
| `defect_type` | string | Defect classification label |
| `confidence` | double | Model confidence score |
| `bbox_xyxy` | double[] | Bounding box [x1, y1, x2, y2] |
| `image_path` | string | Path to saved NG image |
| `model_version` | string | Model version identifier |

## Migration Rule

Do not add Python-only fields to the runtime contract unless the C++ platform
can ignore them safely or validate them explicitly.
