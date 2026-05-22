"""Tests for TensorRT model runner."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── Helpers ────────────────────────────────────────────────────────────


def _make_fake_tensorrt_module() -> ModuleType:
    """Create a minimal fake tensorrt module for testing load()."""
    import logging as _logging

    mod = ModuleType("tensorrt")

    class FakeLogger:
        WARNING = _logging.WARNING

        def __init__(self, severity: int) -> None:
            self.severity = severity

    class FakeRuntime:
        def __init__(self, logger: FakeLogger) -> None:
            self._logger = logger

        def deserialize_cuda_engine(self, data: bytes) -> object:
            class FakeEngine:
                def create_execution_context(self) -> object:
                    class FakeContext:
                        pass
                    return FakeContext()
            return FakeEngine()

    class FakeTensorRT:
        Logger = FakeLogger
        Runtime = FakeRuntime

    mod.Logger = FakeLogger
    mod.Runtime = FakeRuntime

    return mod


def _install_fake_tensorrt(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Install a fake tensorrt module into sys.modules."""
    fake_mod = _make_fake_tensorrt_module()
    monkeypatch.setitem(sys.modules, "tensorrt", fake_mod)
    return fake_mod


# ── Tests ──────────────────────────────────────────────────────────────


def test_runner_has_runner_name():
    """TensorRTModelRunner instance has runner_name == 'tensorrt'."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    runner = TensorRTModelRunner(engine_path="dummy.engine")
    assert runner.runner_name == "tensorrt"


def test_load_raises_import_error_when_tensorrt_missing(monkeypatch):
    """When tensorrt is not importable, load() raises ImportError."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    # Ensure tensorrt is NOT in sys.modules
    monkeypatch.delitem(sys.modules, "tensorrt", raising=False)

    runner = TensorRTModelRunner(engine_path="dummy.engine")
    with pytest.raises(ImportError, match="TensorRT is not installed"):
        runner.load()


def test_load_raises_file_not_found_for_missing_engine(monkeypatch):
    """Non-existent .engine file raises FileNotFoundError."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    _install_fake_tensorrt(monkeypatch)

    runner = TensorRTModelRunner(
        engine_path="/nonexistent/path/model.engine"
    )
    with pytest.raises(FileNotFoundError, match="TensorRT engine not found"):
        runner.load()


def test_load_succeeds_with_valid_engine(monkeypatch):
    """load() succeeds when a valid .engine file exists and tensorrt is available."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    _install_fake_tensorrt(monkeypatch)

    # Create a temp .engine file
    with tempfile.NamedTemporaryFile(suffix=".engine", delete=False) as f:
        engine_path = f.name
        f.write(b"fake_engine_data")

    try:
        runner = TensorRTModelRunner(engine_path=engine_path)
        runner.load()
        assert runner._is_loaded is True
        assert runner._engine is not None
        assert runner._context is not None
    finally:
        Path(engine_path).unlink(missing_ok=True)


def test_load_raises_runtime_error_on_bad_engine_data(monkeypatch):
    """Corrupted engine data raises RuntimeError on load."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    _install_fake_tensorrt(monkeypatch)

    # Create a fake tensorrt Runtime that fails
    import tensorrt as trt_mod  # This is the fake we installed

    class BadRuntime:
        def __init__(self, logger: object) -> None:
            pass

        def deserialize_cuda_engine(self, data: bytes) -> object:
            raise Exception("Invalid engine data")

    monkeypatch.setattr(trt_mod, "Runtime", BadRuntime)

    with tempfile.NamedTemporaryFile(suffix=".engine", delete=False) as f:
        engine_path = f.name
        f.write(b"corrupt_data")

    try:
        runner = TensorRTModelRunner(engine_path=engine_path)
        with pytest.raises(RuntimeError, match="Failed to deserialize"):
            runner.load()
    finally:
        Path(engine_path).unlink(missing_ok=True)


def test_predict_raises_runtime_error_when_not_loaded():
    """Call predict_image before load raises RuntimeError."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    runner = TensorRTModelRunner(engine_path="dummy.engine")
    with pytest.raises(RuntimeError, match="not loaded"):
        runner.predict_image("test.png")


def test_predict_raises_not_implemented_when_loaded(monkeypatch):
    """predict_image raises NotImplementedError even when loaded (Phase E MVP)."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    _install_fake_tensorrt(monkeypatch)

    with tempfile.NamedTemporaryFile(suffix=".engine", delete=False) as f:
        engine_path = f.name
        f.write(b"fake_engine_data")

    try:
        runner = TensorRTModelRunner(engine_path=engine_path)
        runner.load()
        assert runner._is_loaded is True
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            runner.predict_image("test.png")
    finally:
        Path(engine_path).unlink(missing_ok=True)


def test_constructor_stores_parameters():
    """Constructor correctly stores all parameters."""
    from model_runners.tensorrt_runner import TensorRTModelRunner

    runner = TensorRTModelRunner(
        engine_path="model.engine",
        class_names={0: "scratch", 1: "pit"},
        confidence=0.7,
        iou=0.5,
        image_size=512,
        device_id=1,
    )
    assert runner._engine_path == "model.engine"
    assert runner._class_names == {0: "scratch", 1: "pit"}
    assert runner._confidence == 0.7
    assert runner._iou == 0.5
    assert runner._image_size == 512
    assert runner._device_id == 1
    assert runner._is_loaded is False
