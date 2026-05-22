"""Unified inference backend factory — selects and creates runners for .pt/.onnx/.engine artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from core.export_environment import detect_export_environment
from core.model_export import (
    create_export_artifact,
    get_export_artifact,
    list_export_artifacts,
    update_export_artifact,
)


class RuntimeBackend(str, Enum):
    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"


def create_runner_for_artifact(
    export_id: str,
    confidence: float = 0.5,
    iou: float = 0.45,
    image_size: int = 640,
) -> Any | None:
    """Create a duck-typed runner for a given export artifact.

    The runner must have:
      - predict_image(image_path: str) -> object (result with .detections attribute)
      - runner_name: str attribute

    Parameters
    ----------
    export_id : str
        The export artifact ID to look up.
    confidence : float
        Detection confidence threshold (default 0.5).
    iou : float
        NMS IoU threshold (default 0.45).
    image_size : int
        Input resize dimension in pixels (default 640).

    Returns
    -------
    Any | None
        A loaded runner instance, or None if artifact not found, status != "completed",
        or the requested backend cannot be used (e.g. TensorRT GPU mismatch).
    """
    artifact = get_export_artifact(export_id)
    if artifact is None or artifact.status != "completed":
        return None

    backend = artifact.backend
    model_path = artifact.artifact_path

    if backend == RuntimeBackend.PYTORCH:
        try:
            from model_runners.yolo_runner import YoloModelRunner
        except ImportError:
            return None

        runner = YoloModelRunner(
            model_path=model_path,
            config={
                "confidence": confidence,
                "iou": iou,
                "image_size": image_size,
            },
        )
        runner.load()
        return runner

    if backend == RuntimeBackend.ONNX:
        try:
            from model_runners.onnx_runner import OnnxModelRunner
        except ImportError:
            return None

        runner = OnnxModelRunner(
            model_path=model_path,
            config={
                "confidence": confidence,
                "iou": iou,
                "image_size": image_size,
            },
        )
        runner.load()
        return runner

    if backend == RuntimeBackend.TENSORRT:
        # Check GPU compatibility
        env = detect_export_environment()
        artifact_device = getattr(artifact, "device_name", "") or ""
        gpu_name = env.gpu_name or ""
        if artifact_device and gpu_name:
            art_lower = artifact_device.lower()
            gpu_lower = gpu_name.lower()
            if art_lower not in gpu_lower and gpu_lower not in art_lower:
                return None  # GPU mismatch — no silent fallback

        from model_runners.tensorrt_runner import TensorRTModelRunner

        runner = TensorRTModelRunner(
            engine_path=model_path,
            confidence=confidence,
            iou=iou,
            image_size=image_size,
        )
        runner.load()
        # Phase E: TensorRT inference pipeline is not yet implemented.
        # The engine loads correctly, but predict_image() raises NotImplementedError.
        # Return None so callers fall back to ONNX/PyTorch instead of crashing.
        if not getattr(runner, "can_predict", True):
            return None
        return runner

    return None


def _fallback_to_source_pt(
    source_model_id: str,
    artifacts: list[Any],
) -> tuple[str | None, str]:
    """Try to use the original .pt model when no export artifact exists."""
    from core.model_version import get_model_version
    import os as _os

    mv = get_model_version(source_model_id)
    if mv and mv.model_path and _os.path.isfile(mv.model_path):
        # Check if a PyTorch artifact already exists
        for a in artifacts:
            if a.backend == "pytorch":
                update_export_artifact(a.export_id, artifact_path=mv.model_path, status="completed")
                return (a.export_id, "Selected PyTorch (original .pt, existing artifact)")
        # Create a new PyTorch artifact pointing to the original .pt
        art = create_export_artifact(
            project_id=mv.project_id,
            source_model_id=source_model_id,
            backend="pytorch",
            precision="fp32",
            artifact_path=mv.model_path,
            status="completed",
        )
        return (art.export_id, "Selected PyTorch (original .pt fallback)")
    return (None, "No completed export artifacts and no source .pt model found")


def select_best_backend(
    source_model_id: str,
    preferred_backend: str = "auto",
) -> tuple[str | None, str]:
    """Select the best available backend for a source model.

    Parameters
    ----------
    source_model_id : str
        The source model to look up export artifacts for.
    preferred_backend : str
        One of "auto", "pytorch", "onnx", "tensorrt".

    Returns
    -------
    tuple[str | None, str]
        (export_id, reason_string).  export_id is None if no suitable backend found.
    """
    # Validate preferred_backend early (before query cost)
    valid_backends = {RuntimeBackend.PYTORCH, RuntimeBackend.ONNX, RuntimeBackend.TENSORRT}
    if preferred_backend != "auto" and preferred_backend not in valid_backends:
        return (None, f"Unknown backend: {preferred_backend}")

    artifacts = list_export_artifacts(source_model_id=source_model_id)
    completed = [a for a in artifacts if a.status == "completed"]

    if not completed:
        # Fallback: use the original .pt source model via PyTorch backend
        try:
            return _fallback_to_source_pt(source_model_id, artifacts)
        except Exception:
            return (None, "No completed export artifacts")

    # Detect environment once
    env_gpu = detect_export_environment().gpu_name or ""

    # Build lookup: backend -> [(export_id, artifact)]
    by_backend: dict[str, list[tuple[str, Any]]] = {}
    for a in completed:
        by_backend.setdefault(a.backend, []).append((a.export_id, a))

    def _gpu_matches(artifact: Any) -> bool:
        artifact_device = getattr(artifact, "device_name", "") or ""
        if not artifact_device or not env_gpu:
            return True  # No GPU info to compare — assume compatible
        art_lower = artifact_device.lower()
        gpu_lower = env_gpu.lower()
        return art_lower in gpu_lower or gpu_lower in art_lower

    if preferred_backend == "auto":
        # Priority: TensorRT FP16 > TensorRT FP32 > ONNX > PyTorch
        tensorrt_entries = by_backend.get(RuntimeBackend.TENSORRT, [])
        if tensorrt_entries:
            # Prefer FP16
            for export_id, art in tensorrt_entries:
                if getattr(art, "precision", "") == "fp16" and _gpu_matches(art):
                    return (export_id, "Selected TensorRT FP16")
            # Fallback to any TensorRT
            for export_id, art in tensorrt_entries:
                if _gpu_matches(art):
                    return (export_id, "Selected TensorRT FP32")

        onnx_entries = by_backend.get(RuntimeBackend.ONNX, [])
        if onnx_entries:
            return (onnx_entries[0][0], "Selected ONNX")

        pytorch_entries = by_backend.get(RuntimeBackend.PYTORCH, [])
        if pytorch_entries:
            return (pytorch_entries[0][0], "Selected PyTorch")

        return (None, "No suitable backend found")

    # Explicit preferred backend
    entries = by_backend.get(preferred_backend, [])
    if not entries:
        # Auto-fallback
        fallback_backends = [
            b for b in (RuntimeBackend.ONNX, RuntimeBackend.PYTORCH)
            if b != preferred_backend
        ]
        for fb in fallback_backends:
            fb_entries = by_backend.get(fb, [])
            if fb_entries:
                return (
                    fb_entries[0][0],
                    f"No {preferred_backend} artifact available, "
                    f"selected {fb} instead",
                )
        return (None, f"No {preferred_backend} artifact and no fallback available")

    for export_id, art in entries:
        if preferred_backend == RuntimeBackend.TENSORRT and not _gpu_matches(art):
            continue
        return (export_id, f"Selected {preferred_backend}")

    # All TensorRT entries had GPU mismatch
    if preferred_backend == RuntimeBackend.TENSORRT:
        # Try fallback
        onnx_entries = by_backend.get(RuntimeBackend.ONNX, [])
        if onnx_entries:
            return (
                onnx_entries[0][0],
                "TensorRT GPU mismatch, falling back to ONNX",
            )
        pytorch_entries = by_backend.get(RuntimeBackend.PYTORCH, [])
        if pytorch_entries:
            return (
                pytorch_entries[0][0],
                "TensorRT GPU mismatch, falling back to PyTorch",
            )

    return (None, "No compatible backend found")
