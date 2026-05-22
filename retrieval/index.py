"""Build and search a defect retrieval index.

Stores embeddings under ``.cache/retrieval/``.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from retrieval.embeddings import (
    extract_crop,
    compute_basic_embedding,
    cosine_similarity,
    euclidean_distance,
)

DEFAULT_INDEX_DIR = Path(".cache/retrieval")


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
        "embeddings": np.array(embeddings) if embeddings else np.array([]).reshape(0, 80),
        "records": valid_records,
        "num_indexed": len(valid_records),
    }

    # Save to disk
    if index_path is None:
        index_path = DEFAULT_INDEX_DIR / "defect_index.pkl"
    else:
        index_path = Path(index_path)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "wb") as f:
        pickle.dump(index, f)

    # Also save records as JSON for human inspection
    json_path = index_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(valid_records, f, ensure_ascii=False, indent=2)

    return index


def load_retrieval_index(index_path: str | Path) -> dict:
    """Load a saved retrieval index."""
    index_path = Path(index_path)
    with open(index_path, "rb") as f:
        return pickle.load(f)


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
