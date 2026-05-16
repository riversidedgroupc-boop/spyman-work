"""Model runner registry — discovers and returns runners by type key."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model_runners.base import BaseModelRunner

_RUNNER_REGISTRY: dict[str, dict] = {}


def _ensure_registry() -> None:
    """Populate the registry lazily to avoid circular imports."""
    global _RUNNER_REGISTRY
    if _RUNNER_REGISTRY:
        return
    _RUNNER_REGISTRY = {
        "yolo": {
            "name": "YOLO .pt",
            "description": "Ultralytics YOLO object detection model",
            "extensions": (".pt",),
            "class_path": "model_runners.yolo_runner.YoloModelRunner",
        },
        "onnx": {
            "name": "ONNX .onnx",
            "description": "ONNX format object detection model",
            "extensions": (".onnx",),
            "class_path": "model_runners.onnx_runner.OnnxModelRunner",
        },
    }


def list_supported_runners() -> list[dict]:
    """Return metadata for all registered runner types."""
    _ensure_registry()
    return [
        {
            "type": key,
            "name": meta["name"],
            "description": meta["description"],
            "extensions": meta["extensions"],
        }
        for key, meta in _RUNNER_REGISTRY.items()
    ]


def get_runner(model_type: str) -> type[BaseModelRunner]:
    """Return the runner class for *model_type* (e.g. ``"yolo"``).

    Raises ``ValueError`` if the type is not registered.
    """
    _ensure_registry()
    if model_type not in _RUNNER_REGISTRY:
        valid = ", ".join(_RUNNER_REGISTRY.keys())
        raise ValueError(
            f"Unknown model type '{model_type}'. Valid types: {valid}"
        )
    entry = _RUNNER_REGISTRY[model_type]
    module_path, class_name = entry["class_path"].rsplit(".", 1)
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def register_runner(model_type: str, metadata: dict) -> None:
    """Register a custom runner type (for future extensibility)."""
    _ensure_registry()
    _RUNNER_REGISTRY[model_type] = metadata
