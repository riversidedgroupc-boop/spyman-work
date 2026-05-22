"""PatchCore-style trainer — anomaly detection via nominal feature memory bank."""
from __future__ import annotations

import json
import os
from pathlib import Path

from core.training_job import TrainingJob
from core.training_result import TrainingResult
from trainers.base import BaseTrainer
from trainers.registry import register


@register("patchcore")
class PatchCoreTrainer(BaseTrainer):
    """Lightweight PatchCore-style anomaly trainer.

    The full deep-feature PatchCore backend can replace this later, but this
    implementation is intentionally real: it scans ``train/good`` images,
    extracts deterministic image/patch statistics, builds a sampled nominal
    memory bank, and saves it as a model artifact for anomaly scoring.
    """

    trainer_name = "patchcore"
    supported_tasks = ("anomaly_patchcore",)

    def __init__(self, job: TrainingJob):
        super().__init__(job)
        self._result: TrainingResult | None = None
        self._cfg: dict = {}
        self._image_paths: list[Path] = []
        self.output_path = ""

    def prepare(self) -> None:
        """Validate dataset and prepare output paths."""
        cfg_raw = self.job.training_config or "{}"
        self._cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})

        dataset_path = self.job.dataset_path
        train_good = Path(dataset_path) / "train" / "good"
        if not dataset_path or not train_good.is_dir():
            raise FileNotFoundError(
                f"PatchCore requires a valid dataset_path. "
                f"Expected structure: {dataset_path}/train/good/"
            )

        extensions = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        self._image_paths = sorted(
            p for p in train_good.iterdir()
            if p.is_file() and p.suffix.lower() in extensions
        )
        if len(self._image_paths) < 10:
            raise ValueError(
                f"PatchCore requires at least 10 OK training images. Found {len(self._image_paths)}."
            )

        output_dir = self.job.output_dir or os.path.join("outputs", "train_anomaly", self.job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        self.output_path = os.path.join(output_dir, "patchcore_model.json")

    def train(self, progress_callback=None) -> None:
        """Build and persist a sampled nominal feature memory bank."""
        import cv2
        import numpy as np

        features: list[list[float]] = []
        total = len(self._image_paths)
        image_size = int(self._cfg.get("image_size", 256))
        for index, image_path in enumerate(self._image_paths, start=1):
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            resized = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
            features.append(_extract_feature_vector(resized))
            if progress_callback:
                progress_callback(index / total, f"Extracted features {index}/{total}")

        if not features:
            raise ValueError("No readable OK images found for anomaly training")

        feature_array = np.asarray(features, dtype=np.float32)
        ratio = float(self._cfg.get("coreset_sampling_ratio", 0.1))
        ratio = max(0.01, min(1.0, ratio))
        coreset_size = max(1, int(len(feature_array) * ratio))
        indices = _farthest_point_sample(feature_array, coreset_size)
        coreset = feature_array[indices]

        centroid = feature_array.mean(axis=0)
        distances = np.linalg.norm(feature_array - centroid, axis=1)
        threshold = float(distances.mean() + 3.0 * distances.std())

        model = {
            "model_type": "patchcore",
            "feature_backend": "statistical_patch_features",
            "backbone": self._cfg.get("backbone", "statistical"),
            "image_size": image_size,
            "coreset_sampling_ratio": ratio,
            "train_image_count": len(features),
            "feature_dim": int(feature_array.shape[1]),
            "coreset_size": int(len(coreset)),
            "threshold": threshold,
            "centroid": centroid.astype(float).tolist(),
            "coreset": coreset.astype(float).tolist(),
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(model, f, ensure_ascii=False)

        self._result = TrainingResult(
            job_id=self.job.job_id,
            best_model_path=self.output_path,
            last_model_path=self.output_path,
            output_dir=os.path.dirname(self.output_path),
            metrics={
                "train_image_count": len(features),
                "feature_dim": int(feature_array.shape[1]),
                "coreset_size": int(len(coreset)),
                "threshold": threshold,
            },
        )

    def collect_results(self) -> TrainingResult:
        """Return generated model metadata and metrics."""
        if self._result:
            return self._result
        return TrainingResult.empty(self.job.job_id)


def _extract_feature_vector(image) -> list[float]:
    """Extract deterministic image and patch statistics for anomaly training."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0
    edges = cv2.Canny((gray * 255).astype("uint8"), 50, 150).astype(np.float32) / 255.0

    values: list[float] = [
        float(gray.mean()),
        float(gray.std()),
        float(np.percentile(gray, 5)),
        float(np.percentile(gray, 50)),
        float(np.percentile(gray, 95)),
        float(edges.mean()),
    ]
    for channel in range(3):
        ch = hsv[:, :, channel]
        values.extend([float(ch.mean()), float(ch.std())])

    h, w = gray.shape
    grid = 4
    for gy in range(grid):
        for gx in range(grid):
            patch = gray[
                int(gy * h / grid):int((gy + 1) * h / grid),
                int(gx * w / grid):int((gx + 1) * w / grid),
            ]
            values.extend([float(patch.mean()), float(patch.std())])
    return values


def _farthest_point_sample(features, count: int) -> list[int]:
    """Small deterministic farthest-point sampler for the coreset."""
    import numpy as np

    if count >= len(features):
        return list(range(len(features)))
    centroid = features.mean(axis=0)
    first = int(np.argmax(np.linalg.norm(features - centroid, axis=1)))
    selected = [first]
    min_dist = np.linalg.norm(features - features[first], axis=1)
    while len(selected) < count:
        idx = int(np.argmax(min_dist))
        selected.append(idx)
        dist = np.linalg.norm(features - features[idx], axis=1)
        min_dist = np.minimum(min_dist, dist)
    return selected
