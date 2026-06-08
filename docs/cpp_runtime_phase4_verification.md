# C++ Runtime Phase 4 — 交付验证报告

**日期**: 2026-06-05
**范围**: Phase 3（外部 backend 真正可切换）+ Phase 4（全量测试恢复、UI 状态轮询、C++ 配置验证、打包）
**复核日期**: 2026-06-05（修正 C++ exe 执行结论、ruff 命令、pytest 状态）

---

## 1. C++ Exe CLI Smoke

**命令**:
```powershell
.\cpp_runtime\build\cx_vision_runtime.exe status
```

**输出**:
```json
{"state":"stopped","uptime_ms":0,"queue_size":0,"dropped_frames":0,"ng_count":0,"error_code":"","error_message":""}
```

**结果**: `cx_vision_runtime.exe` 可正常执行，`status` 命令返回合法 JSON。之前的"被 Windows Application Control Policy 阻止"结论已不再适用。

---

## 2. C++ CLI 测试 + Runtime Backend 测试

**命令**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cpp_runtime_config_cli.py tests/test_runtime_backend.py -q -ra --tb=short
```

**结果**: **37 passed** in 7.03s

分解:
- `test_cpp_runtime_config_cli.py`: 15 tests — 有效/无效 JSON、缺失字段、嵌套必需字段、结构类型验证（cameras 为对象、model_artifacts 为数组、字段值类型）、边界格式（缺失逗号、尾随逗号、不平衡括号）
- `test_runtime_backend.py`: `create_backend()` 工厂三种模式、backend.start/stop/status 协议

---

## 3. ruff linting（Phase 3/4 变更文件）

**命令**:
```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'
C:\Users\43714\AppData\Local\Programs\Python\Python312\python.exe -m ruff check core/runtime_contracts.py core/runtime_mode.py runtime/runtime_backend.py runtime/cpp_runtime_client.py runtime/fake_cpp_runtime.py core/config_backup.py desktop_app/pages/production_run_page.py tests/test_production_runtime_modes.py tests/test_cpp_runtime_config_cli.py tests/test_cpp_runtime_client.py tests/test_runtime_backend.py tests/test_runtime_contracts.py tests/test_fake_cpp_runtime.py tests/test_cpp_runtime_package.py tests/test_config_backup.py tests/test_config_backup_full.py tests/test_defect_trace_upgrade.py tests/test_v6_integration.py
```

**结果**: **All checks passed**（0 errors, 0 warnings）。

> 注：ruff 不在项目 `.venv` 中；裸 `ruff` 不在当前 shell PATH。当前可用形式是系统 Python `python.exe -m ruff`。在 Codex 沙箱内直接执行系统 Python 可能被拒绝访问，需提升权限运行。全局 `ruff check` 会报告 17 个历史文件的预存问题（`scripts/`、`src/device/camera/hikrobot/`、`ui/`、`retrieval/clustering.py`），均不在 Phase 3/4 变更范围内。

---

## 4. CMake 构建

```powershell
cd cpp_runtime/build
cmake .. -G "MinGW Makefiles" -DCMAKE_CXX_COMPILER=g++
cmake --build .
```

**结果**: **BUILD SUCCESSFUL**，生成 `cx_vision_runtime.exe`（~1.5 MB，静态链接）。

C++ 源码文件:
- `cpp_runtime/CMakeLists.txt`
- `cpp_runtime/src/main.cpp`
- `cpp_runtime/src/runtime_contracts.cpp`
- `cpp_runtime/include/cx_vision/runtime_contracts.hpp`

---

## 5. Python 测试覆盖（Phase 3/4 相关）

### 5.1 Runtime Contract 模型

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_runtime_contracts.py` | ~6 | Pydantic 模型序列化/反序列化、RuntimeConfig 字段验证 |
| `test_runtime_backend.py` | ~6 | `create_backend()` 工厂三种模式、backend.start/stop/status 协议 |
| `test_fake_cpp_runtime.py` | ~4 | FakeCppRuntimeBackend 行为正确性 |

### 5.2 Production Run 外部模式隔离

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_production_runtime_modes.py` | 28 | 外部模式不启动 Python pipeline（spy 断言 4 条件）、Python 模式正常启动、stop 正确跳过、status 轮询使用 backend、`_build_runtime_config()` 映射 camera configs + model artifacts |

### 5.3 C++ CLI 配置验证（真实 exe）

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_cpp_runtime_config_cli.py` | 15 | 有效/无效 JSON、缺失字段、嵌套必需字段、类型验证、边界格式 |

### 5.4 Config Backup 修复

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_config_backup.py` | ~8 | `restore_backup()` 含 `restore_root` 参数、`_safe_restore_target` 路径隔离 |
| `test_config_backup_full.py` | ~8 | 备份创建/恢复/删除、export_project_config_package、audit monkeypatch 隔离 |

### 5.5 Defect Trace 隔离

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_defect_trace_upgrade.py` | 6 | NG 事件记录使用 `output_root=tmp_output`，不写真实 `outputs/` |

### 5.6 C++ Packaging

| 测试文件 | 测试数 | 关键覆盖 |
|----------|--------|----------|
| `test_cpp_runtime_package.py` | ~2 | 打包脚本存在、引用预期产物 |

---

## 6. 全量 pytest（本次复核状态）

**命令**:
```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'
.\.venv\Scripts\python.exe -m pytest tests -q -ra --tb=short
```

**结果**: **1137 passed** in 804.54s（0 failed，2026-06-05 本次复核）

---

## 7. 已知限制

| 限制 | 影响 | 缓解 |
|------|------|------|
| 无实际相机/GPU 环境 | 外部 runtime 模式仅验证协议层 | Phase 5 需真实平台集成测试 |
| C++ exe 未签名 | 可能在启用了 Device Guard 的机器被阻止 | 开发机当前可正常执行；Phase 5 规划签名方案 |
| 全量 pytest 耗时较长 | 本次完整运行约 13 分钟 | 后续回归需预留足够超时时间 |

---

## 8. 结论

Phase 3 + Phase 4 核心交付物:

- ✅ `cx_vision_runtime.exe status` 可正常执行，返回合法 JSON
- ✅ C++ CLI + Runtime Backend 测试: **37 passed**（7s）
- ✅ ruff: Phase 3/4 变更文件零告警
- ✅ CMake build 通过
- ✅ 外部 runtime 模式真正隔离（spy 断言验证）
- ✅ UI 状态轮询使用 `RuntimeBackend.status()`
- ✅ C++ config 结构验证（JSON 解析 + 类型检查）
- ✅ 打包脚本
- ✅ 全量 pytest: **1137 passed**（耗时约 13 分钟）
