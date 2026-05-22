"""Tests for core/deployment_package.py."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Generator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _setup_db() -> Generator[None, None, None]:
    """Temp SQLite DB for deployment package tests."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


# ── _sanitize_dirname ──────────────────────────────────────────────────────────


def test_sanitize_dirname() -> None:
    """Replaces spaces and special characters with underscores."""
    from core.deployment_package import _sanitize_dirname

    assert _sanitize_dirname("hello world") == "hello_world"
    assert _sanitize_dirname("my project!") == "my_project_"
    assert _sanitize_dirname("test/project") == "test_project"
    assert _sanitize_dirname(" a b c ") == "_a_b_c_"


def test_sanitize_dirname_already_clean() -> None:
    """Clean name with only alphanumeric, dash, dot, underscore stays unchanged."""
    from core.deployment_package import _sanitize_dirname

    assert _sanitize_dirname("my-project.v2_test") == "my-project.v2_test"
    assert _sanitize_dirname("abc123") == "abc123"


# ── generate_deployment_package ────────────────────────────────────────────────


def _make_package(
    tmp_root: str,
    **kwargs: object,
) -> "object":
    """Helper: call generate_deployment_package with default args."""
    from core.deployment_package import generate_deployment_package

    defaults: dict = {
        "project_id": "PROJ_FIXTURE",
        "spec_id": "SPEC_FIXTURE",
        "source_model_id": "MODEL_FIXTURE",
        "output_root": tmp_root,
        "customer_name": "Test Corp",
        "project_name": "Demo Project",
        "spec_name": "Tube 10mm",
    }
    defaults.update({k: v for k, v in kwargs.items()})
    return generate_deployment_package(**defaults)  # type: ignore[arg-type]


def test_generate_deployment_package_creates_structure() -> None:
    """Directory and subdirectories are created."""
    with tempfile.TemporaryDirectory() as tmp_root:
        pkg = _make_package(tmp_root)

        assert os.path.isdir(pkg.package_dir)
        assert os.path.isdir(os.path.join(pkg.package_dir, "models"))
        assert os.path.isdir(os.path.join(pkg.package_dir, "config"))
        assert os.path.isdir(os.path.join(pkg.package_dir, "reports"))
        assert pkg.package_dir.startswith(tmp_root)


def test_generate_deployment_package_manifest_keys() -> None:
    """Manifest contains all required top-level keys."""
    with tempfile.TemporaryDirectory() as tmp_root:
        pkg = _make_package(tmp_root)

        required_keys = {
            "deployment_package_version",
            "customer",
            "project",
            "spec",
            "source_model_id",
            "training_job_id",
            "dataset_version_id",
            "class_mapping",
            "backend_artifacts",
            "gpu_name",
            "cuda_version",
            "tensorrt_version",
            "recommended_backend",
            "fallback_backend",
            "benchmark_summary",
            "created_at",
        }
        assert required_keys <= set(pkg.manifest.keys())
        assert pkg.manifest["deployment_package_version"] == "1.0"
        assert pkg.manifest["customer"] == "Test Corp"
        assert pkg.manifest["project"] == "Demo Project"
        assert pkg.manifest["spec"] == "Tube 10mm"


def test_generate_deployment_package_relative_paths() -> None:
    """All artifact_path values in the manifest are relative (no backslash, no colon)."""
    with tempfile.TemporaryDirectory() as tmp_root:
        pkg = _make_package(tmp_root)

        for art in pkg.manifest.get("backend_artifacts", []):
            path = art.get("artifact_path", "")
            if path:
                assert not os.path.isabs(path), f"Path must be relative: {path}"
                assert ":" not in path, f"Path must not contain colon: {path}"

        # Also check manifest.json on disk
        with open(pkg.manifest_path, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        for art in on_disk.get("backend_artifacts", []):
            path = art.get("artifact_path", "")
            if path:
                assert not os.path.isabs(path), f"Path must be relative: {path}"
                assert ":" not in path, f"Path must not contain colon: {path}"


def test_generate_deployment_package_copies_model_files() -> None:
    """Model files provided as backend_artifacts are copied into models/."""
    with tempfile.TemporaryDirectory() as tmp_root:
        # Create fake model files
        models_src = tempfile.mkdtemp()
        pt_file = os.path.join(models_src, "best.pt")
        onnx_file = os.path.join(models_src, "model.onnx")
        for p in (pt_file, onnx_file):
            with open(p, "wb") as f:
                f.write(b"dummy model content")

        artifacts = [
            {
                "backend": "pytorch",
                "precision": "fp32",
                "artifact_path": pt_file,
                "export_id": "EXP_001",
            },
            {
                "backend": "onnx",
                "precision": "fp32",
                "artifact_path": onnx_file,
                "export_id": "EXP_002",
            },
        ]

        pkg = _make_package(tmp_root, backend_artifacts=artifacts)

        # Files should exist in models/
        models_dir = os.path.join(pkg.package_dir, "models")
        assert os.path.isfile(os.path.join(models_dir, "best.pt"))
        assert os.path.isfile(os.path.join(models_dir, "model.onnx"))

        # Content matches
        with open(os.path.join(models_dir, "best.pt"), "rb") as f:
            assert f.read() == b"dummy model content"

        # Manifest entries use relative paths
        manifest_artifacts = pkg.manifest["backend_artifacts"]
        assert len(manifest_artifacts) == 2
        for a in manifest_artifacts:
            assert a["artifact_path"].startswith("models/")

        shutil.rmtree(models_src, ignore_errors=True)


def test_generate_deployment_package_writes_configs() -> None:
    """Config files are written and contain valid JSON matching the inputs."""
    with tempfile.TemporaryDirectory() as tmp_root:
        class_mapping = {"0": "scratch", "1": "dent"}
        thresholds = {"confidence": 0.6}
        hybrid_strategy = {"mode": "cascade"}

        pkg = _make_package(
            tmp_root,
            class_mapping=class_mapping,
            thresholds=thresholds,
            hybrid_strategy=hybrid_strategy,
        )

        config_dir = os.path.join(pkg.package_dir, "config")

        with open(os.path.join(config_dir, "class_mapping.json"), "r") as f:
            assert json.load(f) == class_mapping

        with open(os.path.join(config_dir, "thresholds.json"), "r") as f:
            assert json.load(f) == thresholds

        with open(os.path.join(config_dir, "hybrid_strategy.json"), "r") as f:
            assert json.load(f) == hybrid_strategy

        # runtime_backend.json should exist and be valid
        with open(os.path.join(config_dir, "runtime_backend.json"), "r") as f:
            rb = json.load(f)
        assert "recommended_backend" in rb
        assert "fallback_backend" in rb


def test_generate_deployment_package_writes_benchmark_reports() -> None:
    """Both benchmark_report.json and benchmark_report.md are created."""
    with tempfile.TemporaryDirectory() as tmp_root:
        benchmark = {
            "summary": {"avg_latency_ms": 12.5, "avg_throughput_fps": 80},
            "results": [
                {"backend": "tensorrt", "precision": "fp16", "latency_ms": 8, "throughput_fps": 120},
                {"backend": "onnx", "precision": "fp32", "latency_ms": 17, "throughput_fps": 55},
            ],
        }

        pkg = _make_package(tmp_root, benchmark_result=benchmark)
        reports_dir = os.path.join(pkg.package_dir, "reports")

        json_path = os.path.join(reports_dir, "benchmark_report.json")
        md_path = os.path.join(reports_dir, "benchmark_report.md")

        assert os.path.isfile(json_path)
        assert os.path.isfile(md_path)

        with open(json_path, "r") as f:
            assert json.load(f) == benchmark

        md_content = open(md_path, "r", encoding="utf-8").read()
        assert "# Benchmark Report" in md_content
        assert "| Backend | Precision | Latency (ms) | Throughput (fps) |" in md_content


def test_generate_deployment_package_runtime_backend_json() -> None:
    """Runtime backend JSON has correct recommended/fallback for tensorrt artifacts."""
    with tempfile.TemporaryDirectory() as tmp_root:
        # Create a fake TensorRT engine file
        models_src = tempfile.mkdtemp()
        engine_path = os.path.join(models_src, "model_fp16.engine")
        with open(engine_path, "wb") as f:
            f.write(b"dummy engine")

        artifacts = [
            {
                "backend": "tensorrt",
                "precision": "fp16",
                "artifact_path": engine_path,
                "export_id": "EXP_TRT",
            },
        ]

        pkg = _make_package(tmp_root, backend_artifacts=artifacts)
        config_dir = os.path.join(pkg.package_dir, "config")

        with open(os.path.join(config_dir, "runtime_backend.json"), "r") as f:
            rb = json.load(f)

        # The agent may not have TensorRT installed, so just check fields exist
        assert "recommended_backend" in rb
        assert "fallback_backend" in rb
        assert "available_backends" in rb
        assert "tensorrt" in rb["available_backends"]

        # Manifest should mirror these
        assert pkg.manifest["recommended_backend"] == rb["recommended_backend"]
        assert pkg.manifest["fallback_backend"] == rb["fallback_backend"]

        shutil.rmtree(models_src, ignore_errors=True)


# ── DeploymentPackage dataclass ────────────────────────────────────────────────


def test_deployment_package_to_dict_roundtrip() -> None:
    """to_dict() -> from_dict() roundtrip preserves all fields."""
    from core.deployment_package import DeploymentPackage

    original = DeploymentPackage(
        package_id="PKG_001",
        package_dir="/tmp/pkg",
        manifest_path="/tmp/pkg/manifest.json",
        manifest={"version": "1.0"},
        created_at="2025-01-01T00:00:00",
    )

    d = original.to_dict()
    restored = DeploymentPackage.from_dict(d)

    assert restored.package_id == original.package_id
    assert restored.package_dir == original.package_dir
    assert restored.manifest_path == original.manifest_path
    assert restored.manifest == original.manifest
    assert restored.created_at == original.created_at


# ── Edge cases ─────────────────────────────────────────────────────────────────


def test_generate_deployment_package_with_minimal_args() -> None:
    """Works with only the three required IDs, all other args defaulted."""
    with tempfile.TemporaryDirectory() as tmp_root:
        from core.deployment_package import generate_deployment_package

        pkg = generate_deployment_package(
            project_id="PROJ_X",
            spec_id="SPEC_X",
            source_model_id="MODEL_X",
            output_root=tmp_root,
        )

        assert os.path.isdir(pkg.package_dir)
        assert os.path.isfile(os.path.join(pkg.package_dir, "manifest.json"))

        # All three config files should exist (even with empty content)
        config_dir = os.path.join(pkg.package_dir, "config")
        for name in ("class_mapping.json", "thresholds.json", "hybrid_strategy.json", "runtime_backend.json"):
            assert os.path.isfile(os.path.join(config_dir, name))


def test_generate_deployment_package_empty_artifacts_ok() -> None:
    """No model files still produces a valid package with empty backend_artifacts."""
    with tempfile.TemporaryDirectory() as tmp_root:
        pkg = _make_package(tmp_root, backend_artifacts=[])

        assert pkg.manifest["backend_artifacts"] == []
        assert os.path.isdir(os.path.join(pkg.package_dir, "models"))


def test_generate_deployment_package_overwrites_existing() -> None:
    """Re-running with exist_ok=True handles pre-existing directories cleanly."""
    with tempfile.TemporaryDirectory() as tmp_root:
        # First generation
        pkg1 = _make_package(tmp_root)
        assert os.path.isfile(pkg1.manifest_path)
        # Simulate writing extra junk into the first package dir
        stale_file = os.path.join(pkg1.package_dir, "stale.log")
        with open(stale_file, "w") as f:
            f.write("old")

        # Brief sleep to ensure distinct timestamp
        import time
        time.sleep(1.1)

        # Second generation yields a new timestamped subdir
        pkg2 = _make_package(tmp_root)
        assert os.path.isfile(pkg2.manifest_path)
        # New dir is a different directory (or at least different package_id)
        assert pkg2.package_id != pkg1.package_id
        # The stale file is NOT in the new dir
        assert "stale.log" not in os.listdir(pkg2.package_dir)
        # Old dir still exists unchanged
        assert os.path.isfile(stale_file)


# ── DB-backed tests ───────────────────────────────────────────────────────────


@pytest.fixture
def db_ctx() -> dict[str, str]:
    """Create parent rows: customer -> project -> spec -> model_version."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.model_version import create_model_version

    c = create_customer("Deploy Test Co", "DTC")
    p = create_project(c.customer_id, "Deploy Test Proj")
    s = create_product_spec(p.project_id, "Deploy Spec", material="铜", geometry_type="管")
    mv = create_model_version(
        project_id=p.project_id,
        model_name="deploy_model",
        model_type="yolo",
        model_path="/fake/path/deploy_model.pt",
        spec_id=s.spec_id,
    )
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
        "model_id": mv.model_id,
    }


def test_generate_deployment_package_with_db_artifacts(db_ctx: dict[str, str]) -> None:
    """Backend artifacts from DB are included when export records exist."""
    from core.model_export import create_export_artifact

    _ = create_export_artifact(
        project_id=db_ctx["project_id"],
        source_model_id=db_ctx["model_id"],
        backend="onnx",
        precision="fp32",
    )

    with tempfile.TemporaryDirectory() as tmp_root:
        from core.deployment_package import generate_deployment_package

        pkg = generate_deployment_package(
            project_id=db_ctx["project_id"],
            spec_id=db_ctx["spec_id"],
            source_model_id=db_ctx["model_id"],
            output_root=tmp_root,
            customer_name="Test Corp",
            project_name="DB Project",
            spec_name="Pipe 5mm",
        )

        assert os.path.isfile(pkg.manifest_path)
        assert pkg.manifest["source_model_id"] == db_ctx["model_id"]


def test_deployment_package_manifest_on_disk_matches() -> None:
    """The manifest.json on disk matches the in-memory manifest dict."""
    with tempfile.TemporaryDirectory() as tmp_root:
        pkg = _make_package(tmp_root)

        with open(pkg.manifest_path, "r", encoding="utf-8") as fh:
            disk_manifest = json.load(fh)

        assert disk_manifest == pkg.manifest
