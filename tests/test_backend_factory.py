"""Tests for model_runners/backend_factory.py."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from model_runners.backend_factory import (
    RuntimeBackend,
    create_runner_for_artifact,
    select_best_backend,
)


@dataclass
class FakeExportArtifact:
    export_id: str = ""
    project_id: str = ""
    source_model_id: str = ""
    backend: str = "pytorch"
    precision: str = "fp32"
    artifact_path: str = ""
    status: str = "completed"
    device_name: str = ""
    cuda_version: str = ""
    tensorrt_version: str = ""
    metrics_json: str = ""


# ── Helpers ────────────────────────────────────────────────────────────


def _make_artifact(**overrides: object) -> FakeExportArtifact:
    """Create a FakeExportArtifact with sensible defaults."""
    defaults: dict[str, object] = {
        "export_id": "exp-001",
        "project_id": "proj-001",
        "source_model_id": "model-001",
        "backend": "pytorch",
        "precision": "fp32",
        "artifact_path": "/tmp/model.pt",
        "status": "completed",
        "device_name": "",
           }
    defaults.update(overrides)
    return FakeExportArtifact(**defaults)  # type: ignore[arg-type]


def _setup_artifact_getter(monkeypatch, artifact):
    """Mock get_export_artifact on backend_factory module to return the given artifact.

    We must patch ``model_runners.backend_factory`` directly because the module
    has already imported the function by name at module level.
    """
    monkeypatch.setattr(
        "model_runners.backend_factory.get_export_artifact",
        lambda export_id, artifact=artifact: artifact,
    )


def _setup_artifact_list(monkeypatch, artifacts):
    """Mock list_export_artifacts on backend_factory module to return the given list.

    We must patch ``model_runners.backend_factory`` directly because the module
    has already imported the function by name at module level.
    """
    monkeypatch.setattr(
        "model_runners.backend_factory.list_export_artifacts",
        lambda source_model_id, artifacts=artifacts: artifacts,
    )


def _setup_env_gpu(monkeypatch, gpu_name: str):
    """Mock detect_export_environment to return the given GPU name."""
    monkeypatch.setattr(
        "model_runners.backend_factory.detect_export_environment",
        lambda: _fake_env(gpu_name),
    )


def _fake_env(gpu_name: str):
    """Return a minimal ExportEnvironment-like namespace."""
    from core.export_environment import ExportEnvironment

    return ExportEnvironment(gpu_name=gpu_name)


def _create_temp_pt_file() -> str:
    """Create a temporary .pt file on disk and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=".pt", delete=False)
    f.write(b"fake_model")
    f.close()
    return f.name


# ═══════════════════════════════════════════════════════════════════════
# RuntimeBackend enum
# ═══════════════════════════════════════════════════════════════════════


def test_runtime_backend_enum_values():
    """Verify RuntimeBackend enum has correct string values."""
    assert RuntimeBackend.PYTORCH == "pytorch"
    assert RuntimeBackend.ONNX == "onnx"
    assert RuntimeBackend.TENSORRT == "tensorrt"


def test_runtime_backend_from_string():
    """RuntimeBackend can be constructed from string values."""
    assert RuntimeBackend("pytorch") == RuntimeBackend.PYTORCH
    assert RuntimeBackend("onnx") == RuntimeBackend.ONNX
    with pytest.raises(ValueError):
        RuntimeBackend("unknown")


# ═══════════════════════════════════════════════════════════════════════
# create_runner_for_artifact
# ═══════════════════════════════════════════════════════════════════════


def test_create_runner_returns_none_for_nonexistent_artifact(monkeypatch):
    """Non-existent export_id returns None."""
    monkeypatch.setattr(
        "model_runners.backend_factory.get_export_artifact",
        lambda export_id: None,
    )
    result = create_runner_for_artifact("nonexistent")
    assert result is None


def test_create_runner_returns_none_for_failed_artifact(monkeypatch):
    """Artifact with status='failed' returns None."""
    artifact = _make_artifact(status="failed", backend="pytorch")
    _setup_artifact_getter(monkeypatch, artifact)
    result = create_runner_for_artifact("exp-001")
    assert result is None


def test_create_runner_returns_none_for_unknown_backend(monkeypatch):
    """Artifact with an unrecognized backend returns None."""
    artifact = _make_artifact(backend="unknown_backend")
    _setup_artifact_getter(monkeypatch, artifact)
    result = create_runner_for_artifact("exp-001")
    assert result is None


def test_create_runner_pytorch_artifact(monkeypatch):
    """Completed pytorch artifact with valid .pt path creates YoloModelRunner."""
    import model_runners.yolo_runner as yr

    load_calls: list[bool] = []

    class FakeYoloRunner:
        runner_name = "yolo"

        def __init__(self, model_path, class_names=None, config=None):
            self.model_path = model_path
            self.config = config

        def load(self):
            load_calls.append(True)

    monkeypatch.setattr(yr, "YoloModelRunner", FakeYoloRunner)

    pt_path = _create_temp_pt_file()
    try:
        artifact = _make_artifact(backend="pytorch", artifact_path=pt_path)
        _setup_artifact_getter(monkeypatch, artifact)

        result = create_runner_for_artifact(
            "exp-001", confidence=0.6, iou=0.4, image_size=512
        )
        assert result is not None
        assert result.runner_name == "yolo"
        assert load_calls == [True]
        assert result.config["confidence"] == 0.6
        assert result.config["iou"] == 0.4
        assert result.config["image_size"] == 512
    finally:
        Path(pt_path).unlink(missing_ok=True)


def test_create_runner_onnx_artifact(monkeypatch):
    """Completed onnx artifact creates OnnxModelRunner."""
    import model_runners.onnx_runner as onnxr

    load_calls: list[bool] = []

    class FakeOnnxRunner:
        runner_name = "onnx"

        def __init__(self, model_path, class_names=None, config=None):
            self.model_path = model_path
            self.config = config

        def load(self):
            load_calls.append(True)

    monkeypatch.setattr(onnxr, "OnnxModelRunner", FakeOnnxRunner)

    artifact = _make_artifact(backend="onnx", artifact_path="/tmp/model.onnx")
    _setup_artifact_getter(monkeypatch, artifact)

    result = create_runner_for_artifact("exp-001")
    assert result is not None
    assert result.runner_name == "onnx"
    assert load_calls == [True]


def test_create_runner_tensorrt_gpu_mismatch_returns_none(monkeypatch):
    """TensorRT artifact with mismatched device_name returns None."""
    import model_runners.tensorrt_runner as trt_mod

    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")
    artifact = _make_artifact(
        backend="tensorrt",
        artifact_path="/tmp/model.engine",
        device_name="NVIDIA RTX 4090",
    )
    _setup_artifact_getter(monkeypatch, artifact)

    # Ensure TensorRT runner import would succeed (to test GPU mismatch specifically)
    class FakeTRTRunner:
        runner_name = "tensorrt"

        def __init__(self, **kwargs):
            pass

        def load(self):
            pass

    monkeypatch.setattr(trt_mod, "TensorRTModelRunner", FakeTRTRunner)

    result = create_runner_for_artifact("exp-001")
    assert result is None  # GPU mismatch


def test_create_runner_tensorrt_gpu_match_succeeds(monkeypatch):
    """TensorRT artifact with matching device_name creates TensorRTModelRunner."""
    import model_runners.tensorrt_runner as trt_mod

    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")
    artifact = _make_artifact(
        backend="tensorrt",
        artifact_path="/tmp/model.engine",
        device_name="RTX 3060",  # substring matches "NVIDIA GeForce RTX 3060"
    )
    _setup_artifact_getter(monkeypatch, artifact)

    load_calls: list[bool] = []

    class FakeTRTRunner:
        runner_name = "tensorrt"

        def __init__(self, **kwargs):
            pass

        def load(self):
            load_calls.append(True)

    monkeypatch.setattr(trt_mod, "TensorRTModelRunner", FakeTRTRunner)

    result = create_runner_for_artifact("exp-001")
    assert result is not None
    assert result.runner_name == "tensorrt"
    assert load_calls == [True]


# ═══════════════════════════════════════════════════════════════════════
# select_best_backend
# ═══════════════════════════════════════════════════════════════════════


def test_select_best_backend_none_available(monkeypatch):
    """No completed artifacts returns (None, reason)."""
    _setup_artifact_list(monkeypatch, [])
    export_id, reason = select_best_backend("model-001")
    assert export_id is None
    assert "No completed" in reason


def test_select_best_backend_auto_prefers_tensorrt_fp16(monkeypatch):
    """Auto mode prefers TensorRT FP16 over other backends."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
        _make_artifact(export_id="exp-onnx", backend="onnx"),
        _make_artifact(
            export_id="exp-tr-fp32", backend="tensorrt", precision="fp32",
            device_name="RTX 3060",
        ),
        _make_artifact(
            export_id="exp-tr-fp16", backend="tensorrt", precision="fp16",
            device_name="RTX 3060",
        ),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")

    export_id, reason = select_best_backend("model-001", preferred_backend="auto")
    assert export_id == "exp-tr-fp16"
    assert "FP16" in reason


def test_select_best_backend_auto_falls_back_to_onnx(monkeypatch):
    """Only onnx + pytorch completed, auto picks onnx."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
        _make_artifact(export_id="exp-onnx", backend="onnx"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")

    export_id, reason = select_best_backend("model-001", preferred_backend="auto")
    assert export_id == "exp-onnx"
    assert "ONNX" in reason


def test_select_best_backend_auto_falls_back_to_pytorch(monkeypatch):
    """Only pytorch completed, auto picks pytorch."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "")

    export_id, reason = select_best_backend("model-001", preferred_backend="auto")
    assert export_id == "exp-pt"
    assert "PyTorch" in reason


def test_select_best_backend_explicit_onnx(monkeypatch):
    """Explicit preferred_backend='onnx' with completed onnx artifact picks it."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
        _make_artifact(export_id="exp-onnx", backend="onnx"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)

    export_id, reason = select_best_backend("model-001", preferred_backend="onnx")
    assert export_id == "exp-onnx"
    assert "onnx" in reason.lower()


def test_select_best_backend_explicit_pytorch(monkeypatch):
    """Explicit preferred_backend='pytorch' picks the pytorch artifact."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)

    export_id, reason = select_best_backend("model-001", preferred_backend="pytorch")
    assert export_id == "exp-pt"


def test_select_best_backend_explicit_tensorrt_not_found_falls_back(monkeypatch):
    """Explicit tensorrt with no tensorrt artifacts falls back to onnx."""
    artifacts = [
        _make_artifact(export_id="exp-onnx", backend="onnx"),
        _make_artifact(export_id="exp-pt", backend="pytorch"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)

    export_id, reason = select_best_backend("model-001", preferred_backend="tensorrt")
    assert export_id == "exp-onnx"

    assert "onnx" in reason.lower() or "ONNX" in reason


def test_select_best_backend_tensorrt_gpu_mismatch_falls_back(monkeypatch):
    """TensorRT artifact with GPU mismatch falls back to ONNX."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
        _make_artifact(export_id="exp-onnx", backend="onnx"),
        _make_artifact(
            export_id="exp-tr", backend="tensorrt",
            device_name="NVIDIA RTX 4090",
        ),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")

    # Explicit tensorrt with GPU mismatch
    export_id, reason = select_best_backend("model-001", preferred_backend="tensorrt")
    assert export_id == "exp-onnx"
    assert "mismatch" in reason or "ONNX" in reason


def test_select_best_backend_auto_tensorrt_gpu_mismatch_skips_tensorrt(monkeypatch):
    """Auto mode skips tensorrt with GPU mismatch and picks ONNX."""
    artifacts = [
        _make_artifact(export_id="exp-pt", backend="pytorch"),
        _make_artifact(export_id="exp-onnx", backend="onnx"),
        _make_artifact(
            export_id="exp-tr", backend="tensorrt",
            device_name="NVIDIA RTX 4090",
        ),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "NVIDIA GeForce RTX 3060")

    export_id, reason = select_best_backend("model-001", preferred_backend="auto")
    assert export_id == "exp-onnx"
    assert "ONNX" in reason


def test_select_best_backend_rejects_non_completed_artifacts(monkeypatch):
    """Only completed artifacts are considered."""
    artifacts = [
        _make_artifact(export_id="exp-fail", status="failed", backend="onnx"),
        _make_artifact(export_id="exp-running", status="running", backend="onnx"),
    ]
    _setup_artifact_list(monkeypatch, artifacts)

    export_id, reason = select_best_backend("model-001")
    assert export_id is None
    assert "No completed" in reason


def test_select_best_backend_unknown_explicit_backend(monkeypatch):
    """Unknown preferred_backend returns (None, reason)."""
    _setup_artifact_list(monkeypatch, [])
    export_id, reason = select_best_backend("model-001", preferred_backend="caffe")
    assert export_id is None
    assert "Unknown" in reason


def test_select_best_backend_empty_gpu_assumes_compatible_for_tensorrt(monkeypatch):
    """When GPU name is empty, TensorRT artifacts are treated as compatible."""
    artifacts = [
        _make_artifact(
            export_id="exp-tr", backend="tensorrt",
            device_name="Some GPU",
        ),
    ]
    _setup_artifact_list(monkeypatch, artifacts)
    _setup_env_gpu(monkeypatch, "")  # Empty GPU name

    export_id, reason = select_best_backend("model-001", preferred_backend="auto")
    assert export_id == "exp-tr"
