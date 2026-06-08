"""Central workspace path resolution.

Three-root strategy:
    <repo>/           — source code (D:\\work\\copper-defect-eval-tool)
    <repo>_external/  — SDKs, runtimes, wheels, downloaded dependencies
    <repo>_workspace/ — projects, samples, datasets, models, reports, benchmarks

Override via env vars:
    COPPER_VISION_WORKSPACE_ROOT  — custom workspace root
    COPPER_VISION_DB_PATH         — custom DB path (existing behaviour preserved)
"""

from __future__ import annotations

import os


def _default_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_repo_root() -> str:
    """Source code repository root."""
    return _default_repo_root()


def get_external_root() -> str:
    """External dependencies root (SDKs, wheels, runtimes)."""
    return os.path.join(os.path.dirname(_default_repo_root()), "copper-defect-eval-tool_external")


def get_workspace_root() -> str:
    """Business/runtime data workspace root.

    Default: <parent>/copper-defect-eval-tool_workspace
    Override: COPPER_VISION_WORKSPACE_ROOT
    """
    env = os.environ.get("COPPER_VISION_WORKSPACE_ROOT", "")
    if env:
        return env
    return os.path.join(os.path.dirname(_default_repo_root()), "copper-defect-eval-tool_workspace")


def get_db_path() -> str:
    """Database path. Respects existing COPPER_VISION_DB_PATH, else workspace default."""
    env = os.environ.get("COPPER_VISION_DB_PATH", "")
    if env:
        return env
    return os.path.join(get_app_data_dir(), "app.db")


def get_app_data_dir() -> str:
    return os.path.join(get_workspace_root(), "app_data")


def get_config_path() -> str:
    return os.path.join(get_app_data_dir(), "config.json")


def get_project_data_root() -> str:
    """Root for project business data (new projects default here)."""
    return os.path.join(get_workspace_root(), "projects")


def get_legacy_project_data_root() -> str:
    """Old repo-local project_data dir (read-only compatibility)."""
    return os.path.join(get_repo_root(), "project_data")


def get_sample_library_root() -> str:
    return os.path.join(get_workspace_root(), "sample_library")


def get_model_registry_root() -> str:
    return os.path.join(get_workspace_root(), "model_registry")


def get_benchmark_root() -> str:
    return os.path.join(get_workspace_root(), "benchmarks")


def get_temp_dir() -> str:
    return os.path.join(get_workspace_root(), "temp")


def get_reports_root() -> str:
    return os.path.join(get_workspace_root(), "reports")


def get_project_dir(customer_id: str, project_id: str) -> str:
    """Workspace path for a specific project."""
    return os.path.join(
        get_project_data_root(),
        f"customer_{customer_id}",
        f"project_{project_id}",
    )


def get_project_subdir(customer_id: str, project_id: str, subdir: str) -> str:
    """Workspace path for a project sub-directory (e.g. 'datasets', 'models')."""
    return os.path.join(get_project_dir(customer_id, project_id), subdir)


def ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist; return path for chaining."""
    os.makedirs(path, exist_ok=True)
    return path


def ensure_workspace_dirs() -> None:
    """Create the standard workspace directory layout if missing."""
    dirs = [
        get_app_data_dir(),
        get_project_data_root(),
        get_sample_library_root(),
        os.path.join(get_sample_library_root(), "manifests"),
        os.path.join(get_sample_library_root(), "assets"),
        get_model_registry_root(),
        os.path.join(get_model_registry_root(), "unsupervised"),
        os.path.join(get_model_registry_root(), "yolo"),
        os.path.join(get_model_registry_root(), "exported", "onnx"),
        os.path.join(get_model_registry_root(), "exported", "tensorrt"),
        get_benchmark_root(),
        get_reports_root(),
        get_temp_dir(),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def resolve_project_path(project_id: str) -> str:
    """Resolve project directory preferring workspace, falling back to legacy repo path.

    Returns the workspace path if it exists; otherwise returns the legacy path.
    This ensures old projects remain readable without physical migration.
    """
    from core.project import get_project as _get_project

    p = _get_project(project_id)
    if p is None:
        return ""

    ws_path = get_project_dir(p.customer_id, project_id)
    if os.path.isdir(ws_path):
        return ws_path

    legacy = os.path.join(get_legacy_project_data_root(), f"customer_{p.customer_id}", f"project_{project_id}")
    if os.path.isdir(legacy):
        return legacy

    return ws_path  # default to workspace for new
