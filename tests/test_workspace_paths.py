"""Tests for workspace path resolution."""
from __future__ import annotations

import os
import tempfile

from core import workspace_paths


class TestDefaults:
    """Test default path resolution (no env var overrides)."""

    def test_repo_root_is_absolute(self) -> None:
        root = workspace_paths.get_repo_root()
        assert os.path.isabs(root)
        assert os.path.isdir(root)

    def test_external_root_exists(self) -> None:
        root = workspace_paths.get_external_root()
        assert os.path.isabs(root)
        assert os.path.isdir(root)

    def test_workspace_root_default(self, monkeypatch) -> None:
        monkeypatch.delenv("COPPER_VISION_WORKSPACE_ROOT", raising=False)
        root = workspace_paths.get_workspace_root()
        assert "_workspace" in root

    def test_project_data_root(self) -> None:
        d = workspace_paths.get_project_data_root()
        assert d.endswith("projects")

    def test_sample_library_root(self) -> None:
        d = workspace_paths.get_sample_library_root()
        assert "sample_library" in d

    def test_model_registry_root(self) -> None:
        d = workspace_paths.get_model_registry_root()
        assert "model_registry" in d

    def test_benchmark_root(self) -> None:
        d = workspace_paths.get_benchmark_root()
        assert "benchmarks" in d

    def test_reports_root(self) -> None:
        d = workspace_paths.get_reports_root()
        assert "reports" in d

    def test_project_dir_structure(self) -> None:
        d = workspace_paths.get_project_dir("cust1", "proj1")
        assert "customer_cust1" in d
        assert "project_proj1" in d


class TestEnvOverrides:
    """Test env var overrides for workspace root and DB path."""

    def test_workspace_root_from_env(self, monkeypatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("COPPER_VISION_WORKSPACE_ROOT", td)
            assert workspace_paths.get_workspace_root() == td

    def test_db_path_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("COPPER_VISION_DB_PATH", "/custom/path/app.db")
        assert workspace_paths.get_db_path() == "/custom/path/app.db"

    def test_db_path_defaults_to_workspace(self, monkeypatch) -> None:
        monkeypatch.delenv("COPPER_VISION_DB_PATH", raising=False)
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("COPPER_VISION_WORKSPACE_ROOT", td)
            db_path = workspace_paths.get_db_path()
            assert db_path.startswith(td)
            assert db_path.endswith("app.db")

    def test_storage_db_path_creates_workspace_app_data(self, monkeypatch) -> None:
        monkeypatch.delenv("COPPER_VISION_DB_PATH", raising=False)
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("COPPER_VISION_WORKSPACE_ROOT", td)
            from core import storage

            db_path = storage._db_path()
            assert db_path == os.path.join(td, "app_data", "app.db")
            assert os.path.isdir(os.path.join(td, "app_data"))


class TestEnsureDir:
    """Test directory creation utilities."""

    def test_ensure_dir_creates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "a", "b", "c")
            result = workspace_paths.ensure_dir(target)
            assert result == target
            assert os.path.isdir(target)

    def test_ensure_dir_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "x")
            workspace_paths.ensure_dir(target)
            workspace_paths.ensure_dir(target)  # no error
            assert os.path.isdir(target)


class TestEnsureWorkspaceDirs:
    """Test full workspace layout creation."""

    def test_creates_all_standard_dirs(self, monkeypatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("COPPER_VISION_WORKSPACE_ROOT", td)
            workspace_paths.ensure_workspace_dirs()
            assert os.path.isdir(os.path.join(td, "app_data"))
            assert os.path.isdir(os.path.join(td, "projects"))
            assert os.path.isdir(os.path.join(td, "sample_library", "manifests"))
            assert os.path.isdir(os.path.join(td, "sample_library", "assets"))
            assert os.path.isdir(os.path.join(td, "model_registry", "unsupervised"))
            assert os.path.isdir(os.path.join(td, "model_registry", "yolo"))
            assert os.path.isdir(os.path.join(td, "model_registry", "exported", "onnx"))
            assert os.path.isdir(os.path.join(td, "model_registry", "exported", "tensorrt"))
            assert os.path.isdir(os.path.join(td, "benchmarks"))
            assert os.path.isdir(os.path.join(td, "reports"))
            assert os.path.isdir(os.path.join(td, "temp"))


class TestLegacyCompatibility:
    """Test fallback to legacy repo project_data."""

    def test_legacy_root_points_to_repo(self) -> None:
        legacy = workspace_paths.get_legacy_project_data_root()
        assert "copper-defect-eval-tool" in legacy
        assert "project_data" in legacy
        # Legacy dir exists (current default)
        assert os.path.isdir(legacy)
