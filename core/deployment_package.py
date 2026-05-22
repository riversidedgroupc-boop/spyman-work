"""Deployment package generator — creates self-contained, field-deliverable directory.

Produces a directory tree with models, configs, benchmark reports, and a single
manifest.json entry point.  All file paths in the manifest are relative.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

from core.export_environment import ExportEnvironment, detect_export_environment
from core.id_utils import generate_id


@dataclass
class DeploymentPackage:
    """Result of a deployment package generation."""

    package_id: str
    package_dir: str
    manifest_path: str
    manifest: dict
    created_at: str

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "package_dir": self.package_dir,
            "manifest_path": self.manifest_path,
            "manifest": self.manifest,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DeploymentPackage:
        return cls(
            package_id=d["package_id"],
            package_dir=d["package_dir"],
            manifest_path=d["manifest_path"],
            manifest=d["manifest"],
            created_at=d["created_at"],
        )


def generate_deployment_package(
    project_id: str,
    spec_id: str,
    source_model_id: str,
    output_root: str = "deployment_packages",
    customer_name: str = "",
    project_name: str = "",
    spec_name: str = "",
    training_job_id: str = "",
    dataset_version_id: str = "",
    class_mapping: dict | None = None,
    thresholds: dict | None = None,
    hybrid_strategy: dict | None = None,
    benchmark_result: dict | None = None,
    backend_artifacts: list[dict] | None = None,
) -> DeploymentPackage:
    """Generate a self-contained deployment package directory.

    1. Create timestamped package directory.
    2. Create subdirectories: models/, config/, reports/.
    3. Copy model files (.pt, .onnx, .engine) into models/.
    4. Write config files into config/.
    5. Write benchmark report files into reports/.
    6. Generate manifest.json as the single entry point.
    7. All paths in manifest are RELATIVE paths.
    """
    # ── Sanitize names and build dirname ────────────────────────────────────
    cust = _sanitize_dirname(customer_name) if customer_name else "unknown"
    proj = _sanitize_dirname(project_name) if project_name else "unknown"
    spc = _sanitize_dirname(spec_name) if spec_name else "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dirname = f"{cust}_{proj}_{spc}_{timestamp}"

    package_dir = os.path.join(output_root, dirname)
    models_dir = os.path.join(package_dir, "models")
    config_dir = os.path.join(package_dir, "config")
    reports_dir = os.path.join(package_dir, "reports")

    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # ── Environment detection ───────────────────────────────────────────────
    env = detect_export_environment()

    # ── Package ID ──────────────────────────────────────────────────────────
    package_id = generate_id("PKG")

    # ── Model files ─────────────────────────────────────────────────────────
    final_artifacts = _copy_model_files(backend_artifacts or [], models_dir)

    # ── Config files ────────────────────────────────────────────────────────
    _write_config_json("class_mapping.json", class_mapping or {}, config_dir)
    _write_config_json("thresholds.json", thresholds or {}, config_dir)
    _write_config_json("hybrid_strategy.json", hybrid_strategy or {}, config_dir)

    runtime_backend = _generate_runtime_backend_json(
        final_artifacts, source_model_id, env, benchmark_result
    )
    _write_config_json("runtime_backend.json", runtime_backend, config_dir)

    # ── Benchmark reports ───────────────────────────────────────────────────
    _write_benchmark_report(benchmark_result or {}, reports_dir)

    # ── Manifest ────────────────────────────────────────────────────────────
    manifest = _generate_manifest(
        customer_name=customer_name,
        project_name=project_name,
        spec_name=spec_name,
        source_model_id=source_model_id,
        training_job_id=training_job_id,
        dataset_version_id=dataset_version_id,
        class_mapping=class_mapping,
        backend_artifacts=final_artifacts,
        env=env,
        benchmark_result=benchmark_result,
        runtime_backend=runtime_backend,
    )

    manifest_path = os.path.join(package_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return DeploymentPackage(
        package_id=package_id,
        package_dir=package_dir,
        manifest_path=manifest_path,
        manifest=manifest,
        created_at=created_at,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _sanitize_dirname(name: str) -> str:
    """Replace spaces and special characters with underscores."""
    result: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in "-_.":
            result.append(ch)
        else:
            result.append("_")
    return "".join(result)


def _copy_model_files(artifacts: list[dict], dest_dir: str) -> list[dict]:
    """Copy model files into *dest_dir* and return metadata with relative paths.

    Each artifact dict is expected to have keys:
      - ``artifact_path`` (absolute path to the source file)
      - ``backend``, ``precision``, ``export_id``
    An optional ``filename`` key overrides the basename of ``artifact_path``.

    Files that do not exist on disk are still recorded in the output list
    with their expected relative path so the manifest stays complete.
    """
    result: list[dict] = []
    for art in artifacts:
        src = art.get("artifact_path", "")
        filename = art.get("filename") or (os.path.basename(src) if src else "")
        rel_path = os.path.join("models", filename).replace("\\", "/") if filename else ""

        if src and os.path.isfile(src):
            dest = os.path.join(dest_dir, filename)
            if os.path.abspath(src) != os.path.abspath(dest):
                shutil.copy2(src, dest)

        result.append({
            "backend": art.get("backend", ""),
            "precision": art.get("precision", ""),
            "artifact_path": rel_path,
            "export_id": art.get("export_id", ""),
        })
    return result


def _write_config_json(filename: str, data: dict, dest_dir: str) -> None:
    """Write a JSON config file into *dest_dir*."""
    filepath = os.path.join(dest_dir, filename)
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _write_benchmark_report(benchmark_result: dict, dest_dir: str) -> None:
    """Write ``benchmark_report.json`` and ``benchmark_report.md`` into *dest_dir*."""
    # JSON
    json_path = os.path.join(dest_dir, "benchmark_report.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(benchmark_result, fh, ensure_ascii=False, indent=2)

    # Markdown
    md_path = os.path.join(dest_dir, "benchmark_report.md")
    lines: list[str] = [
        "# Benchmark Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if benchmark_result:
        summary = benchmark_result.get("summary", {})
        if summary:
            lines.append("## Summary")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("| ------ | ----- |")
            for k, v in summary.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        results = benchmark_result.get("results", [])
        if results:
            lines.append("## Per-Backend Results")
            lines.append("")
            lines.append("| Backend | Precision | Latency (ms) | Throughput (fps) |")
            lines.append("| ------- | --------- | ------------ | ---------------- |")
            for r in results:
                backend = r.get("backend", "")
                precision = r.get("precision", "")
                latency = r.get("latency_ms", "")
                throughput = r.get("throughput_fps", "")
                lines.append(
                    f"| {backend} | {precision} | {latency} | {throughput} |"
                )
            lines.append("")
    else:
        lines.append("No benchmark data available.")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def _generate_manifest(
    customer_name: str,
    project_name: str,
    spec_name: str,
    source_model_id: str,
    training_job_id: str,
    dataset_version_id: str,
    class_mapping: dict | None,
    backend_artifacts: list[dict],
    env: ExportEnvironment,
    benchmark_result: dict | None,
    runtime_backend: dict,
) -> dict:
    """Assemble the full manifest dictionary."""
    return {
        "deployment_package_version": "1.0",
        "customer": customer_name,
        "project": project_name,
        "spec": spec_name,
        "source_model_id": source_model_id,
        "training_job_id": training_job_id,
        "dataset_version_id": dataset_version_id,
        "class_mapping": class_mapping or {},
        "backend_artifacts": backend_artifacts,
        "gpu_name": env.gpu_name,
        "cuda_version": env.cuda_version,
        "tensorrt_version": env.tensorrt_version,
        "recommended_backend": runtime_backend.get("recommended_backend", "pytorch"),
        "fallback_backend": runtime_backend.get("fallback_backend", "onnx"),
        "benchmark_summary": benchmark_result.get("summary", {}) if benchmark_result else {},
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _generate_runtime_backend_json(
    artifacts: list[dict],
    source_model_id: str,
    env: ExportEnvironment,
    benchmark_result: dict | None,
) -> dict:
    """Generate runtime_backend.json with recommended and fallback backends.

    Uses ``select_best_backend`` from the backend factory when the source model
    has export artifact records; otherwise infers backends from the provided
    artifact dicts and environment capabilities.
    """
    backends = list({a.get("backend", "") for a in artifacts if a.get("backend")})

    recommended_backend = "pytorch"
    fallback_backend = "onnx"

    # Try the backend factory first (uses DB records)
    try:
        from model_runners.backend_factory import select_best_backend

        best_id, reason = select_best_backend(source_model_id, preferred_backend="auto")
        if best_id is not None:
            from core.model_export import get_export_artifact

            best_artifact = get_export_artifact(best_id)
            if best_artifact is not None:
                recommended_backend = best_artifact.backend
    except Exception:
        pass

    # Fallback inference from the passed-in artifact dicts
    if not backends:
        pass  # keep defaults
    elif "tensorrt" in backends and env.tensorrt_available:
        recommended_backend = "tensorrt"
        fallback_backend = "onnx" if "onnx" in backends else "pytorch"
    elif "onnx" in backends:
        recommended_backend = "onnx"
        fallback_backend = "pytorch" if "pytorch" in backends else "onnx"
    elif "pytorch" in backends:
        recommended_backend = "pytorch"
        fallback_backend = "onnx"

    # Benchmark results can override recommendation
    if benchmark_result and benchmark_result.get("results"):
        results = benchmark_result["results"]
        # Prefer the backend with highest throughput_fps
        best = max(results, key=lambda r: r.get("throughput_fps", 0))
        if best.get("backend"):
            recommended_backend = best["backend"]

    return {
        "recommended_backend": recommended_backend,
        "fallback_backend": fallback_backend,
        "gpu_name": env.gpu_name,
        "cuda_version": env.cuda_version,
        "tensorrt_version": env.tensorrt_version,
        "available_backends": backends,
    }
