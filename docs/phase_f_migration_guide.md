# Phase F Migration Guide — Workspace Split

> **Read-only by default.** The script copies data — it never deletes or moves
> original files. Verify the copy before cleaning up old locations manually.

## 1. What Changed

Phase F introduces a three-root workspace strategy:

```text
D:\work\copper-defect-eval-tool\              # source code repository
D:\work\copper-defect-eval-tool_external\     # SDKs, runtimes, wheels (unchanged)
D:\work\copper-defect-eval-tool_workspace\    # NEW — business/runtime assets
```

Business data that previously lived inside the repo now goes to the workspace:

| Old (repo) | New (workspace) |
|---|---|
| `<repo>/project_data/` | `<workspace>/projects/` |
| `<repo>/data/app.db` | `<workspace>/app_data/app.db` |
| `<repo>/data/benchmark/` | `<workspace>/benchmarks/` or `<workspace>/projects/.../benchmarks/` |
| `<repo>/outputs/reports/` | `<workspace>/reports/` |
| `<repo>/models/` | `<workspace>/model_registry/` |

## 2. Before You Start — Backup

```powershell
# PowerShell — back up the entire repo before any migration
Copy-Item -Recurse D:\work\copper-defect-eval-tool D:\work\copper-defect-eval-tool_backup_$(Get-Date -Format 'yyyyMMdd')
```

Verify the backup:

```powershell
Get-ChildItem D:\work\copper-defect-eval-tool_backup_* -Recurse | Measure-Object | Select-Object Count
```

## 3. Automatic Workspace Setup

The application auto-creates the workspace directory structure on first launch.
Run once to initialize:

```powershell
cd D:\work\copper-defect-eval-tool
python -c "from core.workspace_paths import ensure_workspace_dirs; ensure_workspace_dirs(); print('Workspace ready.')"
```

Verify:

```powershell
Get-ChildItem D:\work\copper-defect-eval-tool_workspace -Directory | Select-Object Name
# Expected: app_data, benchmarks, model_registry, projects, reports, sample_library, temp
```

## 4. Migrating Project Data

### 4.1 Copy projects (read-only copy — originals stay)

```powershell
$src = "D:\work\copper-defect-eval-tool\project_data"
$dst = "D:\work\copper-defect-eval-tool_workspace\projects"

if (Test-Path $src) {
    Copy-Item -Recurse "$src\*" $dst
    Write-Host "Projects copied. Original at $src is untouched."
} else {
    Write-Host "No legacy project_data directory — nothing to copy."
}
```

### 4.2 Copy database

```powershell
$src = "D:\work\copper-defect-eval-tool\data\app.db"
$dst = "D:\work\copper-defect-eval-tool_workspace\app_data\app.db"

if (Test-Path $src) {
    Copy-Item $src $dst
    Write-Host "Database copied."
}
```

### 4.3 Set environment variable (optional)

The application auto-discovers the workspace. To force a custom location:

```powershell
$env:COPPER_VISION_WORKSPACE_ROOT = "D:\work\copper-defect-eval-tool_workspace"
```

### 4.4 Copy existing models

```powershell
$src = "D:\work\copper-defect-eval-tool\models"
$dst = "D:\work\copper-defect-eval-tool_workspace\model_registry"

if (Test-Path $src) {
    Copy-Item -Recurse "$src\*" $dst
    Write-Host "Models copied."
}
```

## 5. Verification Checklist

After migration, verify:

- [ ] Workspace directories exist under `copper-defect-eval-tool_workspace/`
- [ ] `app_data/app.db` is present and accessible
- [ ] Projects appear in the desktop app Project Center
- [ ] New capture sessions save to workspace, not repo
- [ ] Benchmark output goes to workspace project folder or `benchmarks/`
- [ ] Reports export to workspace `reports/`
- [ ] Original repo data is intact (not deleted)

## 6. Cleanup (Manual Only)

Only after verifying everything works:

```powershell
# WARNING: manually review before running
# Remove-Item -Recurse D:\work\copper-defect-eval-tool\project_data
# Remove-Item D:\work\copper-defect-eval-tool\data\app.db
```

**Do not delete** without a verified backup. The application can still read from
legacy paths via `resolve_project_path()` as a fallback.

## 7. Path Resolution in Code

| Function | Returns |
|---|---|
| `get_repo_root()` | Source repo root |
| `get_workspace_root()` | Workspace root (env-overridable) |
| `get_project_dir(customer_id, project_id)` | Workspace project path |
| `get_benchmark_root()` | Shared benchmark output root |
| `get_reports_root()` | Shared reports output root |
| `get_db_path()` | Database path (env or workspace default) |
| `resolve_project_path(project_id)` | Workspace path if exists, else legacy fallback |

## 8. Smoke Test Checklist

Full workflow test after migration:

- [ ] New project creation
- [ ] Device configuration
- [ ] Baseline capture session
- [ ] Manual OK/NG/Uncertain triage
- [ ] Unsupervised (PatchCore) training
- [ ] Anomaly-assisted capture
- [ ] Historical sample import (if applicable)
- [ ] YOLO annotation / defect type definition
- [ ] YOLO training
- [ ] Hybrid runtime detection
- [ ] Benchmark run
- [ ] Report export
