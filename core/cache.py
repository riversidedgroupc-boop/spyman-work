"""Prediction result cache — avoids re-running inference on unchanged inputs.

Cache key encodes model identity, image source, and inference parameters.
Results are stored as JSON under ``.cache/predictions/``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from core.schema import DetectionBox, ImagePrediction

DEFAULT_CACHE_DIR = Path(".cache/predictions")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def _image_manifest(image_folder: str) -> list[dict[str, Any]]:
    """Return a deterministic manifest for images under a folder."""
    folder = Path(image_folder)
    if not folder.exists() or not folder.is_dir():
        return []

    manifest: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        stat = path.stat()
        manifest.append({
            "path": str(path.relative_to(folder)).replace("\\", "/"),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        })
    return manifest


def build_prediction_cache_key(
    model_path: str,
    image_folder: str,
    config: dict | None = None,
    class_names: dict[int, str] | None = None,
) -> str:
    """Build a deterministic cache key from model + image source + parameters."""
    components: list[str] = []

    # Model path + mtime
    model_p = Path(model_path)
    components.append(str(model_p.resolve()))
    if model_p.exists():
        components.append(str(int(os.path.getmtime(model_p))))

    # Image folder
    img_p = Path(image_folder)
    components.append(str(img_p.resolve()))
    components.append(json.dumps(_image_manifest(image_folder), sort_keys=True))

    # Config sorted by key for determinism
    if config:
        config_str = json.dumps(config, sort_keys=True, default=str)
        components.append(config_str)

    # Class names
    if class_names:
        names_str = json.dumps(class_names, sort_keys=True, default=str)
        components.append(names_str)

    raw = "|".join(components)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_path(cache_key: str, cache_dir: Path | None = None) -> Path:
    cd = cache_dir or DEFAULT_CACHE_DIR
    cd.mkdir(parents=True, exist_ok=True)
    return cd / f"{cache_key}.json"


def has_prediction_cache(cache_key: str, cache_dir: Path | None = None) -> bool:
    return _cache_path(cache_key, cache_dir).exists()


def save_predictions(
    cache_key: str,
    predictions: list[ImagePrediction],
    cache_dir: Path | None = None,
) -> None:
    """Serialize predictions to a JSON cache file."""
    data: list[dict[str, Any]] = []
    for pred in predictions:
        dets = []
        for d in pred.detections:
            dets.append({
                "image_name": d.image_name,
                "class_id": d.class_id,
                "class_name": d.class_name,
                "confidence": d.confidence,
                "bbox": d.bbox,
            })
        data.append({
            "image_name": pred.image_name,
            "detections": dets,
        })

    path = _cache_path(cache_key, cache_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_predictions(
    cache_key: str, cache_dir: Path | None = None
) -> list[ImagePrediction]:
    """Load cached predictions from JSON."""
    path = _cache_path(cache_key, cache_dir)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results: list[ImagePrediction] = []
    for item in data:
        dets = [
            DetectionBox(
                image_name=d["image_name"],
                class_id=d["class_id"],
                class_name=d["class_name"],
                confidence=d["confidence"],
                bbox=d["bbox"],
            )
            for d in item["detections"]
        ]
        results.append(ImagePrediction(image_name=item["image_name"], detections=dets))
    return results


def clear_cache(cache_key: str, cache_dir: Path | None = None) -> None:
    """Delete a specific cache file."""
    path = _cache_path(cache_key, cache_dir)
    if path.exists():
        path.unlink()


def clear_all_cache(cache_dir: Path | None = None) -> int:
    """Delete all cache files, return count of deleted files."""
    cd = cache_dir or DEFAULT_CACHE_DIR
    if not cd.exists():
        return 0
    count = 0
    for f in cd.glob("*.json"):
        f.unlink()
        count += 1
    return count
