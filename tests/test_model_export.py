"""Tests for core/model_export.py — Phase E."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Generator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _setup_db() -> Generator[None, None, None]:
    """Temp SQLite DB with Phase E tables (schema v8)."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def ctx() -> dict[str, str]:
    """Create parent rows: customer → project → spec → model_version."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.model_version import create_model_version

    c = create_customer("Export Test Co", "ETC")
    p = create_project(c.customer_id, "Export Test Proj")
    s = create_product_spec(p.project_id, "Export Spec", material="铜", geometry_type="管")
    mv = create_model_version(
        project_id=p.project_id,
        model_name="test_model",
        model_type="yolo",
        model_path="/fake/path/model.pt",
        spec_id=s.spec_id,
    )
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
        "model_id": mv.model_id,
    }


# ── Artifact CRUD ─────────────────────────────────────────────────────────────


def test_create_artifact(ctx: dict[str, str]):
    """create_export_artifact persists to DB with correct fields."""
    from core.model_export import create_export_artifact, get_export_artifact

    m = create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
        precision="fp32",
    )
    assert m.export_id.startswith("EXP_")
    assert m.backend == "onnx"
    assert m.precision == "fp32"
    assert m.status == "created"

    retrieved = get_export_artifact(m.export_id)
    assert retrieved is not None
    assert retrieved.export_id == m.export_id
    assert retrieved.project_id == ctx["project_id"]


def test_list_artifacts_by_project(ctx: dict[str, str]):
    """list_export_artifacts filters by project_id."""
    from core.model_export import create_export_artifact, list_export_artifacts

    create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
    )
    create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="tensorrt",
    )
    results = list_export_artifacts(project_id=ctx["project_id"])
    assert len(results) == 2


def test_list_artifacts_by_source_model(ctx: dict[str, str]):
    """list_export_artifacts filters by source_model_id."""
    from core.model_export import create_export_artifact, list_export_artifacts

    create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
    )
    # Create another model version + artifact with different source
    from core.model_version import create_model_version

    mv2 = create_model_version(
        project_id=ctx["project_id"],
        model_name="other_model",
        model_type="yolo",
        model_path="/fake/path/other.pt",
        spec_id=ctx["spec_id"],
    )
    create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=mv2.model_id,
        backend="tensorrt",
    )

    results = list_export_artifacts(source_model_id=ctx["model_id"])
    assert len(results) == 1
    assert results[0].source_model_id == ctx["model_id"]


def test_update_artifact_status(ctx: dict[str, str]):
    """update_export_artifact updates status correctly."""
    from core.model_export import (
        create_export_artifact,
        get_export_artifact,
        update_export_artifact,
    )

    m = create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
    )
    assert m.status == "created"

    updated = update_export_artifact(m.export_id, status="completed")
    assert updated is not None
    assert updated.status == "completed"

    retrieved = get_export_artifact(m.export_id)
    assert retrieved is not None
    assert retrieved.status == "completed"


def test_update_nonexistent_returns_none():
    """update_export_artifact returns None for nonexistent ID."""
    from core.model_export import update_export_artifact

    result = update_export_artifact("EXP_nonexistent", status="completed")
    assert result is None


def test_delete_artifact(ctx: dict[str, str]):
    """delete_export_artifact removes the record."""
    from core.model_export import (
        create_export_artifact,
        delete_export_artifact,
        get_export_artifact,
    )

    m = create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
    )
    assert get_export_artifact(m.export_id) is not None

    delete_export_artifact(m.export_id)
    assert get_export_artifact(m.export_id) is None


def test_artifact_to_dict_roundtrip(ctx: dict[str, str]):
    """ModelExportArtifact → to_dict → from_dict produces an equal object."""
    from core.model_export import ModelExportArtifact

    original = ModelExportArtifact(
        export_id="EXP_test_001",
        project_id="P1",
        spec_id="S1",
        source_model_id="M1",
        backend="tensorrt",
        precision="fp16",
        artifact_path="/outputs/model.engine",
        status="completed",
        device_name="NVIDIA RTX 4090",
        cuda_version="12.1",
        tensorrt_version="10.0",
        input_shape="[1,3,640,640]",
        export_config_json='{"imgsz": 640}',
        metrics_json='{"latency_ms": 2.3}',
        error_message="",
        created_at="2025-01-01 12:00:00",
        updated_at="2025-01-01 12:01:00",
    )
    d = original.to_dict()
    restored = ModelExportArtifact.from_dict(d)
    assert restored.export_id == original.export_id
    assert restored.project_id == original.project_id
    assert restored.spec_id == original.spec_id
    assert restored.source_model_id == original.source_model_id
    assert restored.backend == original.backend
    assert restored.precision == original.precision
    assert restored.artifact_path == original.artifact_path
    assert restored.status == original.status
    assert restored.device_name == original.device_name
    assert restored.cuda_version == original.cuda_version
    assert restored.tensorrt_version == original.tensorrt_version
    assert restored.input_shape == original.input_shape
    assert restored.export_config_json == original.export_config_json
    assert restored.metrics_json == original.metrics_json
    assert restored.error_message == original.error_message


def test_create_artifact_with_extra_kwargs(ctx: dict[str, str]):
    """create_export_artifact applies extra kwargs that match dataclass fields."""
    from core.model_export import create_export_artifact, get_export_artifact

    m = create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=ctx["model_id"],
        backend="onnx",
        spec_id="S_EXTRA",
        device_name="Test GPU",
        input_shape="[1,3,640,640]",
    )
    retrieved = get_export_artifact(m.export_id)
    assert retrieved is not None
    assert retrieved.spec_id == "S_EXTRA"
    assert retrieved.device_name == "Test GPU"
    assert retrieved.input_shape == "[1,3,640,640]"


# ── Export ONNX ───────────────────────────────────────────────────────────────


def test_export_onnx_missing_model_file_raises(ctx: dict[str, str], monkeypatch):
    """export_yolo_to_onnx raises FileNotFoundError when model file is missing."""
    from core.model_export import export_yolo_to_onnx
    from core.model_version import create_model_version

    mv = create_model_version(
        project_id=ctx["project_id"],
        model_name="missing_file_model",
        model_type="yolo",
        model_path="/nonexistent/path/model.pt",
        spec_id=ctx["spec_id"],
    )

    with pytest.raises(FileNotFoundError, match="Model file not found"):
        export_yolo_to_onnx(mv.model_id, "/tmp/output")


def test_export_onnx_missing_model_version_raises():
    """export_yolo_to_onnx raises ValueError for nonexistent model_id."""
    from core.model_export import export_yolo_to_onnx

    with pytest.raises(ValueError, match="Model version not found"):
        export_yolo_to_onnx("MODEL_nonexistent", "/tmp/output")


def test_export_onnx_success(ctx: dict[str, str], monkeypatch):
    """export_yolo_to_onnx completes successfully with mocked ultralytics."""
    from core.model_export import export_yolo_to_onnx, get_export_artifact
    from core.model_version import update_model_version

    tmp = tempfile.mkdtemp()
    try:
        model_file = os.path.join(tmp, "model.pt")
        with open(model_file, "wb") as f:
            f.write(b"fake_yolo_model")
        output_dir = os.path.join(tmp, "exports")
        os.makedirs(output_dir, exist_ok=True)

        update_model_version(ctx["model_id"], model_path=model_file)

        class _MockModel:
            def __init__(self, model_path: str) -> None:
                self.model_path = model_path

            def export(self, **kwargs) -> None:
                onnx_path = self.model_path.replace(".pt", ".onnx")
                with open(onnx_path, "w") as f:
                    f.write("fake_onnx")

        monkeypatch.setattr("ultralytics.YOLO", _MockModel)

        from core import export_environment

        monkeypatch.setattr(
            "core.model_export._detect_cached",
            lambda: export_environment.ExportEnvironment(),
        )

        result = export_yolo_to_onnx(ctx["model_id"], output_dir)
        assert result.status == "completed"
        assert result.backend == "onnx"
        assert result.artifact_path.endswith(".onnx")

        db_record = get_export_artifact(result.export_id)
        assert db_record is not None
        assert db_record.status == "completed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_onnx_failure_updates_status(ctx: dict[str, str], monkeypatch):
    """export_yolo_to_onnx sets status=failed on exception."""
    from core.model_export import export_yolo_to_onnx, list_export_artifacts
    from core.model_version import update_model_version

    tmp = tempfile.mkdtemp()
    try:
        model_file = os.path.join(tmp, "model.pt")
        with open(model_file, "wb") as f:
            f.write(b"fake_yolo_model")
        output_dir = os.path.join(tmp, "exports")
        os.makedirs(output_dir, exist_ok=True)

        update_model_version(ctx["model_id"], model_path=model_file)

        class _FailingModel:
            def __init__(self, model_path: str) -> None:
                pass

            def export(self, **kwargs) -> None:
                raise RuntimeError("Export failed: out of memory")

        monkeypatch.setattr("ultralytics.YOLO", _FailingModel)

        from core import export_environment

        monkeypatch.setattr(
            "core.model_export._detect_cached",
            lambda: export_environment.ExportEnvironment(),
        )

        with pytest.raises(RuntimeError, match="out of memory"):
            export_yolo_to_onnx(ctx["model_id"], output_dir)

        artifacts = list_export_artifacts(project_id=ctx["project_id"])
        assert len(artifacts) >= 1
        failed = artifacts[0]
        assert failed.status == "failed"
        assert "out of memory" in failed.error_message
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Export TensorRT ───────────────────────────────────────────────────────────


def test_export_tensorrt_int8_without_calibration_raises(ctx: dict[str, str], monkeypatch):
    """export_yolo_to_tensorrt with int8 and no calibration_dir raises ValueError."""
    from core.model_export import export_yolo_to_tensorrt
    from core import export_environment

    monkeypatch.setattr(
        "core.model_export._detect_cached",
        lambda: export_environment.ExportEnvironment(tensorrt_available=True),
    )

    with pytest.raises(ValueError, match="INT8 precision requires calibration_dir"):
        export_yolo_to_tensorrt(
            ctx["model_id"],
            "/tmp/output",
            precision="int8",
            calibration_dir="",
        )


def test_export_tensorrt_not_available_creates_failed_artifact(
    ctx: dict[str, str], monkeypatch
):
    """When TensorRT is not available, create artifact with status=failed."""
    from core.model_export import export_yolo_to_tensorrt, get_export_artifact
    from core import export_environment

    monkeypatch.setattr(
        "core.model_export._detect_cached",
        lambda: export_environment.ExportEnvironment(tensorrt_available=False),
    )

    result = export_yolo_to_tensorrt(ctx["model_id"], "/tmp/output")
    assert result.status == "failed"
    assert "TensorRT not available" in result.error_message

    db_record = get_export_artifact(result.export_id)
    assert db_record is not None
    assert db_record.status == "failed"


def test_export_tensorrt_success(ctx: dict[str, str], monkeypatch):
    """export_yolo_to_tensorrt completes with mocked dependencies."""
    from core.model_export import export_yolo_to_tensorrt, get_export_artifact
    from core.model_version import update_model_version
    from core import export_environment

    tmp = tempfile.mkdtemp()
    try:
        model_file = os.path.join(tmp, "model.pt")
        with open(model_file, "wb") as f:
            f.write(b"fake_yolo_model")
        output_dir = os.path.join(tmp, "engine_exports")
        os.makedirs(output_dir, exist_ok=True)

        update_model_version(ctx["model_id"], model_path=model_file)

        monkeypatch.setattr(
            "core.model_export._detect_cached",
            lambda: export_environment.ExportEnvironment(
                tensorrt_available=True,
                tensorrt_version="10.0.1",
                gpu_name="NVIDIA RTX 4090",
                cuda_version="12.1",
            ),
        )

        class _MockModel:
            def __init__(self, model_path: str) -> None:
                self.model_path = model_path

            def export(self, **kwargs) -> None:
                engine_path = self.model_path.replace(".pt", ".engine")
                with open(engine_path, "w") as f:
                    f.write("fake_engine")

        monkeypatch.setattr("ultralytics.YOLO", _MockModel)

        result = export_yolo_to_tensorrt(
            ctx["model_id"],
            output_dir,
            precision="fp16",
        )
        assert result.status == "completed"
        assert result.backend == "tensorrt"
        assert result.precision == "fp16"
        assert result.artifact_path.endswith(".engine")

        db_record = get_export_artifact(result.export_id)
        assert db_record is not None
        assert db_record.status == "completed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_tensorrt_missing_model_version_raises():
    """export_yolo_to_tensorrt raises ValueError for nonexistent model_id."""
    from core.model_export import export_yolo_to_tensorrt

    with pytest.raises(ValueError, match="Model version not found"):
        export_yolo_to_tensorrt("MODEL_nonexistent", "/tmp/output")
