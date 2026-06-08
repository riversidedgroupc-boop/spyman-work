"""Build and search a defect retrieval index.

Stores embeddings under ``.cache/retrieval/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from retrieval.embeddings import (
    extract_crop,
    compute_basic_embedding,
    cosine_similarity,
    euclidean_distance,
)

DEFAULT_INDEX_DIR = Path(".cache/retrieval")
EMBEDDING_DIM = 80


def build_retrieval_index(
    records: list[dict],
    image_root: str | Path,
    index_path: str | Path | None = None,
) -> dict:
    """Build a retrieval index from defect records.

    Each record should have: image_name, bbox, class_name, confidence.

    Returns index dict with embeddings, records, and metadata.
    """
    image_root = Path(image_root)
    embeddings: list[np.ndarray] = []
    valid_records: list[dict] = []

    for rec in records:
        image_name = rec.get("image_name", "")
        bbox = rec.get("bbox", [])
        if not image_name or len(bbox) != 4:
            continue

        img_path = image_root / image_name
        if not img_path.exists():
            img_path = Path(image_name)
        if not img_path.exists():
            continue

        try:
            crop = extract_crop(str(img_path), bbox)
            crop_resized = crop.resize((64, 64))
            emb = compute_basic_embedding(crop_resized)
            embeddings.append(emb)
            valid_records.append(rec)
        except Exception:
            continue

    index: dict = {
        "embeddings": np.array(embeddings) if embeddings else np.array([]).reshape(0, EMBEDDING_DIM),
        "records": valid_records,
        "num_indexed": len(valid_records),
    }

    # Save to disk (numpy for embeddings, JSON for records/metadata)
    if index_path is None:
        index_path = DEFAULT_INDEX_DIR / "defect_index"
    else:
        index_path = Path(index_path)

    stem = index_path.with_suffix("")
    stem.parent.mkdir(parents=True, exist_ok=True)

    embeddings_path = stem.with_suffix(".npy")
    records_path = stem.with_suffix(".json")

    embeddings_arr: np.ndarray = np.array(embeddings) if embeddings else np.array([]).reshape(0, EMBEDDING_DIM)
    np.save(str(embeddings_path), embeddings_arr)
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump({"records": valid_records, "num_indexed": len(valid_records)}, f, ensure_ascii=False, indent=2)

    return index


def load_retrieval_index(index_path: str | Path) -> dict:
    """Load a saved retrieval index (JSON + numpy, with legacy pickle fallback)."""
    index_path = Path(index_path)
    stem = index_path.with_suffix("")

    embeddings_path = stem.with_suffix(".npy")
    records_path = stem.with_suffix(".json")

    # New format: separate .npy + .json
    if embeddings_path.exists() and records_path.exists():
        embeddings = np.load(str(embeddings_path))
        with open(records_path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "embeddings": embeddings,
            "records": data["records"],
            "num_indexed": data["num_indexed"],
        }

    # Legacy format: single .pkl file (backward compatibility)
    import pickle as _pickle_for_migration
    pkl_path = index_path.with_suffix(".pkl")
    if pkl_path.exists():
        with open(pkl_path, "rb") as f:
            legacy = _pickle_for_migration.load(f)
        return legacy

    raise FileNotFoundError(f"Index not found at {stem}.npy or {pkl_path}")


def search_similar_defects(
    query_image_path: str,
    query_bbox: list[float],
    index: dict,
    top_k: int = 10,
    metric: str = "cosine",
) -> list[dict]:
    """Search for similar defects in the index.

    Returns list of dicts with record data and similarity score.
    """
    embeddings = index.get("embeddings")
    records = index.get("records", [])

    if embeddings is None or len(embeddings) == 0:
        return []

    try:
        crop = extract_crop(query_image_path, query_bbox)
        crop_resized = crop.resize((64, 64))
        query_emb = compute_basic_embedding(crop_resized)
    except Exception:
        return []

    scores: list[tuple[int, float]] = []
    for i, emb in enumerate(embeddings):
        if metric == "cosine":
            score = cosine_similarity(query_emb, emb)
        elif metric == "euclidean":
            dist = euclidean_distance(query_emb, emb)
            score = 1.0 / (1.0 + dist)
        else:
            score = cosine_similarity(query_emb, emb)
        scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:top_k]

    results: list[dict] = []
    for idx, score in top:
        rec = records[idx].copy() if idx < len(records) else {}
        rec["similarity"] = float(score)
        results.append(rec)

    return results
