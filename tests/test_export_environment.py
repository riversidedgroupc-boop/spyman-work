"""Tests for core/export_environment.py."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_detect_environment_does_not_crash():
    """detect_export_environment() must never crash, even when optional deps are missing."""
    from core.export_environment import ExportEnvironment, detect_export_environment

    result = detect_export_environment()
    assert isinstance(result, ExportEnvironment)


def test_environment_has_expected_fields():
    """All ExportEnvironment fields are present on the returned object."""
    from core.export_environment import detect_export_environment

    result = detect_export_environment()
    for field in [
        "gpu_name",
        "cuda_available",
        "cuda_version",
        "torch_version",
        "ultralytics_version",
        "tensorrt_available",
        "tensorrt_version",
        "device_capability",
    ]:
        assert hasattr(result, field)


def test_environment_to_dict_roundtrip():
    """ExportEnvironment → to_dict → from_dict produces an equal object."""
    from core.export_environment import ExportEnvironment

    original = ExportEnvironment(
        gpu_name="NVIDIA RTX 4090",
        cuda_available=True,
        cuda_version="12.1",
        torch_version="2.2.0",
        ultralytics_version="8.1.0",
        tensorrt_available=True,
        tensorrt_version="10.0.1",
        device_capability="8.9",
    )
    d = original.to_dict()
    restored = ExportEnvironment.from_dict(d)
    assert restored.gpu_name == original.gpu_name
    assert restored.cuda_available == original.cuda_available
    assert restored.cuda_version == original.cuda_version
    assert restored.torch_version == original.torch_version
    assert restored.ultralytics_version == original.ultralytics_version
    assert restored.tensorrt_available == original.tensorrt_available
    assert restored.tensorrt_version == original.tensorrt_version
    assert restored.device_capability == original.device_capability


def test_environment_defaults():
    """ExportEnvironment default values are all falsy/empty."""
    from core.export_environment import ExportEnvironment

    e = ExportEnvironment()
    assert e.gpu_name == ""
    assert e.cuda_available is False
    assert e.cuda_version == ""
    assert e.torch_version == ""
    assert e.ultralytics_version == ""
    assert e.tensorrt_available is False
    assert e.tensorrt_version == ""
    assert e.device_capability == ""


def test_from_dict_missing_keys():
    """from_dict handles missing keys gracefully (treats as defaults)."""
    from core.export_environment import ExportEnvironment

    e = ExportEnvironment.from_dict({"gpu_name": "Test"})
    assert e.gpu_name == "Test"
    assert e.cuda_available is False
    assert e.torch_version == ""


def test_detect_environment_handles_missing_deps(monkeypatch):
    """detect_export_environment sets *_available=False when imports fail."""
    import builtins

    _original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name in ("torch", "tensorrt", "ultralytics"):
            raise ImportError(f"No module named '{name}'")
        return _original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    from core.export_environment import detect_export_environment

    result = detect_export_environment()
    assert result.torch_version == ""
    assert result.ultralytics_version == ""
    assert result.tensorrt_available is False
    assert result.tensorrt_version == ""
    assert result.cuda_available is False
