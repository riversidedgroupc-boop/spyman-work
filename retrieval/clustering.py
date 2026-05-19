"""Unknown defect clustering scaffold.

Groups unknown or unclassified defects to help create new defect categories.
"""

from __future__ import annotations

import numpy as np


def cluster_embeddings(
    embeddings: np.ndarray,
    method: str = "kmeans",
    n_clusters: int = 5,
    random_state: int = 42,
) -> list[int]:
    """Cluster embeddings and return cluster labels.

    Parameters
    ----------
    embeddings:
        2D array of shape (n_samples, n_features).
    method:
        Clustering method: "kmeans" (requires scikit-learn) or "fallback".
    n_clusters:
        Number of clusters for kmeans.

    Returns
    -------
    list[int]
        Cluster labels for each sample.
    """
    n_samples = len(embeddings)
    if n_samples == 0:
        return []

    actual_clusters = min(n_clusters, n_samples)

    if method == "kmeans":
        try:
            from sklearn.cluster import KMeans

            kmeans = KMeans(
                n_clusters=actual_clusters,
                random_state=random_state,
                n_init="auto",
            )
            labels = kmeans.fit_predict(embeddings)
            return labels.tolist()
        except ImportError:
            # Fall through to fallback
            pass

    # Fallback: simple equal-interval grouping by first PCA-like dimension
    if embeddings.ndim == 2 and embeddings.shape[1] > 0:
        # Use the first feature dimension as a simple proxy
        values = embeddings[:, 0]
        min_val, max_val = values.min(), values.max()
        if max_val > min_val:
            bins = np.linspace(min_val, max_val, actual_clusters + 1)
            labels = np.digitize(values, bins[1:-1])
            return labels.tolist()

    return [0] * n_samples


def summarize_clusters(
    records: list[dict],
    cluster_labels: list[int],
) -> dict:
    """Summarize each cluster with counts and top class names.

    Returns dict with per-cluster info.
    """
    if not records or not cluster_labels:
        return {"n_clusters": 0, "clusters": {}}

    unique_labels = sorted(set(cluster_labels))
    summary: dict[int, dict] = {}

    for label in unique_labels:
        indices = [i for i, l in enumerate(cluster_labels) if l == label]
        cluster_records = [records[i] for i in indices if i < len(records)]

        class_counts: dict[str, int] = {}
        for r in cluster_records:
            cn = r.get("class_name", "unknown")
            class_counts[cn] = class_counts.get(cn, 0) + 1

        top_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)

        avg_conf = 0.0
        confs = [r.get("confidence", 0) for r in cluster_records if r.get("confidence") is not None]
        if confs:
            avg_conf = sum(confs) / len(confs)

        summary[label] = {
            "count": len(cluster_records),
            "top_classes": top_classes[:5],
            "avg_confidence": avg_conf,
        }

    return {"n_clusters": len(unique_labels), "clusters": summary}


def select_cluster_representatives(
    records: list[dict],
    embeddings: np.ndarray,
    cluster_labels: list[int],
    top_k: int = 5,
) -> dict:
    """Select representative samples from each cluster (closest to centroid).

    Returns dict mapping cluster_label -> list of record indices.
    """
    if not records or embeddings.size == 0:
        return {}

    unique_labels = sorted(set(cluster_labels))
    representatives: dict[int, list[int]] = {}

    for label in unique_labels:
        indices = [i for i, l in enumerate(cluster_labels) if l == label]
        if not indices:
            representatives[label] = []
            continue

        cluster_embs = embeddings[indices]
        centroid = cluster_embs.mean(axis=0)

        # Compute distances to centroid
        dists = np.linalg.norm(cluster_embs - centroid, axis=1)
        sorted_idx = np.argsort(dists)

        top_indices = [indices[i] for i in sorted_idx[:top_k].tolist()]
        representatives[label] = top_indices

    return representatives
