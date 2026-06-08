# C++ Runtime Phase 5A — Serve 模式与 stdin/stdout Long-Lived Backend

**日期**: 2026-06-08
**状态**: 实现完成，测试通过（53 passed）

---

## 1. 概述

Phase 5A 将 C++ runtime 从 one-shot CLI stub 升级为可长驻运行的 serve 模式，Python UI 通过 `CppRuntimeStdioBackend` 基于 stdin/stdout 与 C++ 进程通信。

**当前不是 Named Pipe**。因沙箱环境 Windows Named Pipe 创建失败，Phase 5A 采用 subprocess stdin/stdout 的 fallback 方案，协议和生命周期逻辑一致。如需多客户端支持，后续可迁移到 Named Pipe 或 TCP。

当前仍是 stub — 不连接相机、不加载模型、不接入 PLC。Phase 5B+ 逐步添加真实硬件。

---

## 2. 架构

```
[Python UI]                              [cx_vision_runtime.exe]
     |                                           |
     |  CppRuntimeStdioBackend                    |
     |  ├── _launch()                             |
     |  │   └── subprocess.Popen("serve") ───────→ 启动 serve 进程
     |  │                                          │
     |  │   stdout.readline() ←───────────────────→ 输出初始 status (idle)
     |  │                                          │
     |  ├── status()                               |
     |  │   └── stdin.write({"command":"status"})─→ receive command
     |  │   ← stdout.readline() ──────────────────→ 输出 {"type":"status",...}
     |  │                                          │
     |  ├── start(config)                          |
     |  │   ├── _write_config_file(config)         |
     |  │   │   └── writetemp runtime_config.json  |
     |  │   └── stdin.write({"command":"start",    |
     |  │         "config_path":"..."})───────────→ state = "running"
     |  │   ← stdout.readline() ──────────────────→ 输出 {"type":"status","payload":{"state":"running"}}
     |  │                                          │
     |  ├── stop()                                 |
     |  │   └── stdin.write({"command":"stop"})───→ state = "idle"
     |  │   ← stdout.readline() ──────────────────→ 输出 {"type":"status","payload":{"state":"idle"}}
     |  │                                          │
     |  └── shutdown()                             |
     |      └── stdin.write({"command":"shutdown"})→ 进程退出 (exit 0)
     |      └── terminate() (timeout fallback)
```

---

## 3. JSONL 协议

### 3.1 Python → C++ (commands)

每行一个 JSON object，通过 stdin 发送：

```jsonl
{"command":"status"}
{"command":"start","config_path":"C:\\tmp\\cx_runtime_config_...\\runtime_config.json"}
{"command":"stop"}
{"command":"shutdown"}
```

malformed JSON 会触发错误响应。JSON 验证使用与 `ReadRuntimeConfigFile()` 相同的 C++20 递归下降解析器。

### 3.2 C++ → Python (events)

每行一个 JSON object，通过 stdout 发送：

```jsonl
{"type":"status","payload":{"state":"idle","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}}
{"type":"error","payload":{"code":"MALFORMED_JSON","message":"input is not valid JSON"}}
{"type":"error","payload":{"code":"BAD_REQUEST","message":"missing 'command' field"}}
{"type":"log","payload":{"level":"info","message":"start accepted, config_path=..."}}
```

---

## 4. C++ 实现

### 4.1 文件

| 文件 | 说明 |
|------|------|
| `cpp_runtime/src/main.cpp` | 解析 `serve` 命令，路由到 `ServeMode()` |
| `cpp_runtime/src/runtime_serve.cpp` | serve 模式主循环：读取 stdin JSONL，JSON 验证，处理 command，写 stdout JSONL event |
| `cpp_runtime/include/cx_vision/runtime_contracts.hpp` | `ServeMode()` 声明；`ValidateMinimalJsonObject()` 导出供 serve 模式复用 |
| `cpp_runtime/CMakeLists.txt` | 新增 `runtime_serve.cpp` 编译 |

### 4.2 支持的命令

| 命令 | 行为 | 响应 |
|------|------|------|
| `status` | 返回当前状态 | `{"type":"status",...}` |
| `start` | 切换到 running（如非 running） | `{"type":"status","payload":{"state":"running"}}` |
| `start` (已 running) | 拒绝 | `{"type":"error","payload":{"code":"ALREADY_RUNNING"}}` |
| `stop` | 切换到 idle（如 running） | `{"type":"status","payload":{"state":"idle"}}` |
| `stop` (非 running) | 拒绝 | `{"type":"error","payload":{"code":"NOT_RUNNING"}}` |
| `shutdown` | 退出进程 | `{"type":"log","payload":{"level":"info","message":"shutdown acknowledged"}}` |
| malformed JSON | 拒绝并返回错误 | `{"type":"error","payload":{"code":"MALFORMED_JSON"}}` |

---

## 5. Python 实现

### 5.1 文件

| 文件 | 说明 |
|------|------|
| `runtime/cpp_runtime_stdio.py` | `CppRuntimeStdioBackend`：子进程生命周期管理、JSONL 通信、后台 reader 线程、config file 写入 |
| `runtime/runtime_backend.py` | `create_backend("cpp_runtime_stdio")` 工厂支持 |
| `core/runtime_contracts.py` | `RuntimeBackend` Literal 新增 `"cpp_runtime_stdio"`；`RuntimeState` 新增 `"idle"` |

### 5.2 CppRuntimeStdioBackend

- `start(config)` → 写 runtime_config.json 到临时文件 → 发送 `start` + `config_path` → 返回 status
- `stop()` → 发送 `stop` 命令，返回 status
- `status()` → 发送 `status` 命令，返回 status
- `shutdown()` → 发送 `shutdown`，等待进程退出

后台 reader 线程持续从 stdout 读取 JSONL，推入 `queue.Queue`。`_read_status()` 从队列取出事件直到收到 `status` 或 `error` 响应。

---

## 6. 测试覆盖

### 6.1 tests/test_cpp_runtime_stdio_backend.py（13 tests）

| 测试 | 覆盖 |
|------|------|
| `test_backend_is_runtime_backend` | Protocol 检查 |
| `test_serve_starts_and_returns_idle_status` | 进程启动 → 初始 idle |
| `test_start_transitions_to_running` | start → running |
| `test_start_writes_config_file` | start() 写 runtime_config.json，验证字段完整性 |
| `test_stop_transitions_to_idle` | start → stop → idle |
| `test_start_stop_start_cycle` | 重启周期 |
| `test_shutdown_exits_process` | shutdown 后 cleanup |
| `test_stop_when_idle_returns_error` | 非法 stop |
| `test_start_when_already_running_returns_error` | 重复 start |
| `test_uptime_increases_while_running` | uptime_ms 增长 |
| `test_create_via_factory` | create_backend("cpp_runtime_stdio") |
| `test_malformed_json_input_returns_error` | malformed JSON → MALFORMED_JSON error |
| `test_missing_command_field_returns_error` | 无 command 字段 → BAD_REQUEST error |

### 6.2 tests/test_runtime_backend.py（+2 tests）

| 测试 | 覆盖 |
|------|------|
| `test_create_cpp_stdio_backend_by_name` | 工厂创建 |
| `test_create_cpp_stdio_backend_without_executable_raises` | 缺少 executable_path 报错 |

### 6.3 tests/test_cpp_runtime_config_cli.py（15 tests）

现有 one-shot CLI 测试全部保持通过。

---

## 7. 与 Phase 4 的向后兼容

- 现有 `CppRuntimeProcessBackend`（one-shot CLI）未改动
- `create_backend("cpp_runtime")` 仍创建 `CppRuntimeProcessBackend`
- `create_backend("fake_cpp_runtime")` / `create_backend("python_runtime")` 未改动
- 现有 `test_cpp_runtime_config_cli.py` 全部通过

---

## 8. 当前限制

| 限制 | 说明 |
|------|------|
| stdin/stdout 而非 Named Pipe | 沙箱环境 Named Pipe 创建失败。当前 subprocess stdin/stdout 通信正常，功能等效。后续如需多客户端再迁移到 Named Pipe 或 TCP。 |
| 无相机/模型/PLC | Phase 5B+ 逐步添加 |
| 单客户端 | stdin/stdout 天然单客户端 |
| config_path 传递但不加载 | C++ start 命令收到 config_path 并记录日志，但尚未加载和解析配置内容（Phase 5B 添加） |

---

## 9. 验收命令

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'
python -m pytest tests/test_cpp_runtime_stdio_backend.py tests/test_runtime_backend.py tests/test_cpp_runtime_config_cli.py -q -ra --tb=short
```

要求：所有 53 tests 通过。
