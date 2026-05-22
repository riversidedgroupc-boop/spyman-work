"""Model export — artifact model, CRUD, and export services for ONNX and TensorRT."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update

if TYPE_CHECKING:
    from core.export_environment import ExportEnvironment

_EXPORT_STATUSES = ["created", "running", "completed", "failed", "invalid"]
_BACKENDS = ["pytorch", "onnx", "tensorrt"]
_PRECISIONS = ["fp32", "fp16", "int8"]


@dataclass
class ModelExportArtifact:
    """Record of a model export operation (ONNX or TensorRT)."""

    export_id: str
    project_id: str
    spec_id: str = ""
    source_model_id: str = ""
    backend: str = "pytorch"
    precision: str = "fp32"
    artifact_path: str = ""
    status: str = "created"
    device_name: str = ""
    cuda_version: str = ""
    tensorrt_version: str = ""
    input_shape: str = ""
    export_config_json: str = "{}"
    metrics_json: str = "{}"
    error_message: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "export_id": self.export_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "source_model_id": self.source_model_id,
            "backend": self.backend,
            "precision": self.precision,
            "artifact_path": self.artifact_path,
            "status": self.status,
            "device_name": self.device_name,
            "cuda_version": self.cuda_version,
            "tensorrt_version": self.tensorrt_version,
            "input_shape": self.input_shape,
            "export_config_json": self.export_config_json,
            "metrics_json": self.metrics_json,
            "error_message": self.error_message,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModelExportArtifact:
        return cls(
            export_id=d["export_id"],
            project_id=d["project_id"],
            spec_id=d.get("spec_id", ""),
            source_model_id=d.get("source_model_id", ""),
            backend=d.get("backend", "pytorch"),
            precision=d.get("precision", "fp32"),
            artifact_path=d.get("artifact_path", ""),
            status=d.get("status", "created"),
            device_name=d.get("device_name", ""),
            cuda_version=d.get("cuda_version", ""),
            tensorrt_version=d.get("tensorrt_version", ""),
            input_shape=d.get("input_shape", ""),
            export_config_json=d.get("export_config_json", "{}"),
            metrics_json=d.get("metrics_json", "{}"),
            error_message=d.get("error_message", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("EXP")


# ── CRUD ──────────────────────────────────────────────────────────────────────


def create_export_artifact(
    project_id: str,
    source_model_id: str,
    backend: str,
    precision: str = "fp32",
    **kwargs: object,
) -> ModelExportArtifact:
    """Create a new export artifact record and persist it to the database."""
    m = ModelExportArtifact(
        export_id=_gen_id(),
        project_id=project_id,
        source_model_id=source_model_id,
        backend=backend,
        precision=precision,
        **{k: v for k, v in kwargs.items() if hasattr(ModelExportArtifact, k)},
    )
    insert("model_export_artifacts", m.to_dict())
    return m


def get_export_artifact(export_id: str) -> ModelExportArtifact | None:
    """Retrieve a single export artifact by its ID."""
    row = fetch_one("model_export_artifacts", export_id, "export_id")
    return ModelExportArtifact.from_dict(row) if row else None


def list_export_artifacts(
    project_id: str | None = None,
    source_model_id: str | None = None,
) -> list[ModelExportArtifact]:
    """List export artifacts, optionally filtered by project or source model."""
    if project_id is not None and source_model_id is not None:
        rows = fetch_all(
            "model_export_artifacts",
            where="project_id = ? AND source_model_id = ? ORDER BY created_at DESC",
            params=(project_id, source_model_id),
        )
    elif project_id is not None:
        rows = fetch_all(
            "model_export_artifacts",
            where="project_id = ? ORDER BY created_at DESC",
            params=(project_id,),
        )
    elif source_model_id is not None:
        rows = fetch_all(
            "model_export_artifacts",
            where="source_model_id = ? ORDER BY created_at DESC",
            params=(source_model_id,),
        )
    else:
        rows = fetch_all(
            "model_export_artifacts",
            where="1 ORDER BY created_at DESC",
        )
    return [ModelExportArtifact.from_dict(r) for r in rows]


def update_export_artifact(export_id: str, **kwargs: object) -> ModelExportArtifact | None:
    """Update fields on an existing export artifact."""
    existing = get_export_artifact(export_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("model_export_artifacts", export_id, existing.to_dict(), "export_id")
    return existing


def delete_export_artifact(export_id: str) -> None:
    """Remove an export artifact record from the database."""
    delete("model_export_artifacts", export_id, "export_id")


# ── Export services ───────────────────────────────────────────────────────────


def export_yolo_to_onnx(
    model_id: str,
    output_dir: str,
    imgsz: int = 640,
    opset: int = 12,
    simplify: bool = True,
) -> ModelExportArtifact:
    """Export a YOLO .pt model to ONNX format.

    1. Look up ModelVersion by model_id → get model_path (.pt file)
    2. Verify model_path exists on disk (raise FileNotFoundError if not)
    3. Create an export artifact record with status="running"
    4. Use ultralytics YOLO model.export(format="onnx", ...)
    5. On success: update artifact status="completed", set artifact_path
    6. On failure: update artifact status="failed", set error_message, re-raise
    """
    from core.model_version import get_model_version

    mv = get_model_version(model_id)
    if mv is None:
        raise ValueError(f"Model version not found: {model_id}")

    model_path = mv.model_path
    if not model_path or not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    env = _detect_cached()
    artifact = create_export_artifact(
        project_id=mv.project_id,
        source_model_id=model_id,
        backend="onnx",
        precision="fp32",
        spec_id=mv.spec_id or "",
        device_name=env.gpu_name,
        cuda_version=env.cuda_version,
        tensorrt_version=env.tensorrt_version,
        export_config_json=_json_dumps({"imgsz": imgsz, "opset": opset, "simplify": simplify}),
        status="running",
    )

    model_name = mv.model_name or os.path.splitext(os.path.basename(model_path))[0]
    output_path = os.path.join(output_dir, f"{model_name}_onnx_fp32.onnx")

    try:
        from ultralytics import YOLO

        model = YOLO(model_path)
        exported_path: str = model.export(format="onnx", imgsz=imgsz, opset=opset, simplify=simplify)

        # Use ultralytics return value to confirm actual output location
        actual_onnx = exported_path if exported_path and os.path.isfile(exported_path) else ""
        if not actual_onnx:
            # Fallback: check default location next to .pt
            default_onnx = model_path.replace(".pt", ".onnx")
            if os.path.isfile(default_onnx):
                actual_onnx = default_onnx

        if actual_onnx and os.path.abspath(actual_onnx) != os.path.abspath(output_path):
            os.makedirs(output_dir, exist_ok=True)
            if os.path.isfile(output_path):
                os.remove(output_path)
            os.rename(actual_onnx, output_path)

        if not os.path.isfile(output_path):
            raise FileNotFoundError(
                f"ONNX export succeeded but output file not found at {output_path}. "
                f"ultralytics returned: {exported_path}"
            )

        update_export_artifact(
            artifact.export_id,
            status="completed",
            artifact_path=output_path,
        )
        artifact = get_export_artifact(artifact.export_id)  # type: ignore[assignment]
    except Exception as exc:
        update_export_artifact(
            artifact.export_id,
            status="failed",
            error_message=str(exc),
        )
        raise

    return artifact  # type: ignore[return-value]


def export_yolo_to_tensorrt(
    model_id: str,
    output_dir: str,
    imgsz: int = 640,
    precision: str = "fp16",
    workspace_gb: int = 4,
    calibration_dir: str = "",
) -> ModelExportArtifact:
    """Export a YOLO .pt model to TensorRT .engine format.

    1. Check TensorRT availability — if not available, create failed artifact and return
    2. INT8 precision requires calibration_dir — raise ValueError if missing
    3. Look up ModelVersion → get model_path
    4. Verify file exists
    5. Create artifact with status="running"
    6. Use ultralytics YOLO model.export(format="engine", ...)
    7. On success: update artifact status="completed", set artifact_path
    8. On failure: update artifact status="failed", set error_message
    """
    from core.model_version import get_model_version

    mv = get_model_version(model_id)
    if mv is None:
        raise ValueError(f"Model version not found: {model_id}")

    env = _detect_cached()
    if not env.tensorrt_available:
        artifact = create_export_artifact(
            project_id=mv.project_id,
            source_model_id=model_id,
            backend="tensorrt",
            precision=precision,
            spec_id=mv.spec_id or "",
            device_name=env.gpu_name,
            cuda_version=env.cuda_version,
            tensorrt_version=env.tensorrt_version,
            export_config_json=_json_dumps(
                {"imgsz": imgsz, "precision": precision, "workspace_gb": workspace_gb}
            ),
            status="failed",
            error_message="TensorRT not available on this machine",
        )
        return artifact

    if precision == "int8" and not calibration_dir:
        raise ValueError("INT8 precision requires calibration_dir")

    model_path = mv.model_path
    if not model_path or not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    artifact = create_export_artifact(
        project_id=mv.project_id,
        source_model_id=model_id,
        backend="tensorrt",
        precision=precision,
        spec_id=mv.spec_id or "",
        device_name=env.gpu_name,
        cuda_version=env.cuda_version,
        tensorrt_version=env.tensorrt_version,
        export_config_json=_json_dumps(
            {"imgsz": imgsz, "precision": precision, "workspace_gb": workspace_gb}
        ),
        status="running",
    )

    model_name = mv.model_name or os.path.splitext(os.path.basename(model_path))[0]
    output_path = os.path.join(output_dir, f"{model_name}_tensorrt_{precision}.engine")

    try:
        from ultralytics import YOLO

        model = YOLO(model_path)
        export_kwargs: dict = {
            "format": "engine",
            "imgsz": imgsz,
            "half": precision == "fp16",
            "int8": precision == "int8",
            "workspace": workspace_gb,
        }
        if precision == "int8" and calibration_dir:
            export_kwargs["data"] = calibration_dir

        exported_path: str = model.export(**export_kwargs)

        # Use ultralytics return value to confirm actual output location
        actual_engine = exported_path if exported_path and os.path.isfile(exported_path) else ""
        if not actual_engine:
            # Fallback: check default location next to .pt
            default_engine = model_path.replace(".pt", ".engine")
            if os.path.isfile(default_engine):
                actual_engine = default_engine

        if actual_engine and os.path.abspath(actual_engine) != os.path.abspath(output_path):
            os.makedirs(output_dir, exist_ok=True)
            if os.path.isfile(output_path):
                os.remove(output_path)
            os.rename(actual_engine, output_path)

        if not os.path.isfile(output_path):
            raise FileNotFoundError(
                f"TensorRT export succeeded but output file not found at {output_path}. "
                f"ultralytics returned: {exported_path}"
            )

        update_export_artifact(
            artifact.export_id,
            status="completed",
            artifact_path=output_path,
        )
        artifact = get_export_artifact(artifact.export_id)  # type: ignore[assignment]
    except Exception as exc:
        update_export_artifact(
            artifact.export_id,
            status="failed",
            error_message=str(exc),
        )
        raise

    return artifact  # type: ignore[return-value]


# ── Internal helpers ──────────────────────────────────────────────────────────


def _detect_cached() -> ExportEnvironment:
    """Detect environment once per process, cache result."""
    from core.export_environment import detect_export_environment

    cache_key = "_copper_export_env_cache"
    if not hasattr(_detect_cached, cache_key):
        setattr(_detect_cached, cache_key, detect_export_environment())
    return getattr(_detect_cached, cache_key)


def _json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
