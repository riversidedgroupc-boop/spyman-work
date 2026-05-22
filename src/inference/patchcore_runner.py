"""PatchCore anomaly-detection runner.

Supports three operating modes:

- **real**   – uses anomalib (if installed) for actual inference.
- **import** – reads pre-computed anomaly scores from a CSV file.
- **mock**    – generates deterministic pseudo-random results for testing.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.fusion.decision_types import AnomalyResult, UnifiedPrediction
from src.inference.base_runner import BaseRunner
from src.utils.logger import get_logger

_log = get_logger()


class PatchCoreRunner(BaseRunner):
    """PatchCore anomaly runner.

    Parameters
    ----------
    config : dict | None
        Keys: ``mode`` ("mock"|"import"|"real"|"statistical"), ``model_path``, ``result_file``,
        ``score_threshold`` (default 0.65), ``input_size`` (default [256, 256]).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("patchcore", config)
        self.mode: str = str(self.config.get("mode", "mock"))
        self.model_path: str = str(self.config.get("model_path", ""))
        self.result_file: str = str(self.config.get("result_file", ""))
        self.score_threshold: float = float(self.config.get("score_threshold", 0.65))
        self.input_size: list[int] = list(self.config.get("input_size", [256, 256]))
        self._imported_results: dict[str, dict[str, Any]] = {}
        self._real_model: Any = None
        self._statistical_model: dict[str, Any] = {}

    # ------------------------------------------------------------------ load_model

    def load_model(self) -> None:
        """Load model or switch to fallback mode."""
        if self.mode == "statistical":
            self._load_statistical_model()
        elif self.mode == "real":
            self._load_real_model()
        elif self.mode == "import":
            self._load_imported_results()
        elif self.mode == "mock":
            self._is_loaded = True
            _log.info("PatchCore mock mode enabled")
        else:
            _log.warning(
                "Unknown PatchCore mode '%s', falling back to mock", self.mode
            )
            self.mode = "mock"
            self._is_loaded = True

    def _load_statistical_model(self) -> None:
        """Load the JSON model produced by the lightweight PatchCore trainer."""
        model_file = Path(self.model_path) if self.model_path else None
        if not model_file or not model_file.exists():
            raise FileNotFoundError(f"PatchCore statistical model file not found: {self.model_path}")
        with open(model_file, encoding="utf-8") as f:
            model = json.load(f)
        if model.get("feature_backend") != "statistical_patch_features":
            raise ValueError(
                "Unsupported PatchCore model artifact. "
                "Expected feature_backend=statistical_patch_features."
            )
        if not model.get("coreset"):
            raise ValueError("PatchCore statistical model has empty coreset")
        self._statistical_model = model
        self._is_loaded = True

    def _load_real_model(self) -> None:
        """Attempt to load the PatchCore model via anomalib."""
        try:
            import anomalib  # noqa: F401
        except ImportError:
            _log.warning(
                "anomalib not installed. PatchCore real mode requires anomalib. "
                "Falling back to mock mode."
            )
            self.mode = "mock"
            self._is_loaded = True
            return

        model_file = Path(self.model_path) if self.model_path else None
        if model_file and not model_file.exists():
            _log.warning(
                "PatchCore model file not found: %s. Falling back to mock mode.",
                model_file,
            )
            self.mode = "mock"
            self._is_loaded = True
            return

        try:
            from anomalib.models import Patchcore  # noqa: F401
        except Exception:
            _log.warning(
                "Failed to import anomalib PatchCore. Falling back to mock mode."
            )
            self.mode = "mock"
            self._is_loaded = True
            return

        raise NotImplementedError(
            "Real PatchCore inference is not implemented yet. Use import or mock mode."
        )

    def _load_imported_results(self) -> None:
        """Parse pre-computed anomaly scores from a CSV file."""
        import csv

        result_path = Path(self.result_file)
        if not result_path.exists():
            _log.warning(
                "PatchCore result file not found: %s. Using mock mode.",
                self.result_file,
            )
            self.mode = "mock"
            self._is_loaded = True
            return

        with open(result_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                img_path = row.get("image_path", "")
                if not img_path:
                    continue
                self._imported_results[img_path] = {
                    "anomaly_score": float(row.get("anomaly_score", 0.0)),
                    "heatmap_path": row.get("heatmap_path", ""),
                    "mask_path": row.get("mask_path", ""),
                }

        _log.info("PatchCore imported %d results", len(self._imported_results))
        self._is_loaded = True

    # ------------------------------------------------------------------ predict

    def predict(self, image_path: str | Path) -> UnifiedPrediction:
        """Run PatchCore inference (or mock / import)."""
        import random as _random_mod

        t0 = time.perf_counter()
        img_path_str = str(image_path)

        # ---- import mode -------------------------------------------------------
        if self.mode == "import" and img_path_str in self._imported_results:
            data = self._imported_results[img_path_str]
            elapsed = (time.perf_counter() - t0) * 1000.0
            return UnifiedPrediction(
                image_path=img_path_str,
                model_name="patchcore",
                anomaly=AnomalyResult(
                    image_score=data["anomaly_score"],
                    threshold=self.score_threshold,
                    heatmap_path=str(data.get("heatmap_path"))
                    if data.get("heatmap_path")
                    else None,
                    mask_path=str(data.get("mask_path"))
                    if data.get("mask_path")
                    else None,
                ),
                runtime_ms=elapsed,
            )

        if self.mode == "statistical":
            anomaly_score, raw_distance = self._predict_statistical(img_path_str)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return UnifiedPrediction(
                image_path=img_path_str,
                model_name="patchcore",
                anomaly=AnomalyResult(
                    image_score=anomaly_score,
                    threshold=self.score_threshold,
                ),
                runtime_ms=elapsed,
                extra={"raw_anomaly_distance": raw_distance},
            )

        # ---- mock mode ---------------------------------------------------------
        if self.mode == "mock":
            digest = hashlib.sha256(img_path_str.encode("utf-8")).hexdigest()
            seed = int(digest[:16], 16)
            rng = _random_mod.Random(seed)
            anomaly_score = round(rng.uniform(0.1, 0.95), 4)
            elapsed = (time.perf_counter() - t0) * 1000.0 + rng.uniform(10.0, 50.0)
            return UnifiedPrediction(
                image_path=img_path_str,
                model_name="patchcore",
                anomaly=AnomalyResult(
                    image_score=anomaly_score,
                    threshold=self.score_threshold,
                ),
                runtime_ms=elapsed,
            )

        raise NotImplementedError(
            "Real PatchCore inference is not implemented yet. Use import or mock mode."
        )

    def _predict_statistical(self, image_path: str) -> tuple[float, float]:
        """Score an image against the saved statistical coreset."""
        import cv2
        import numpy as np

        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Unable to read image for PatchCore inference: {image_path}")
        image_size = int(self._statistical_model.get("image_size", self.input_size[0]))
        resized = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
        feature = np.asarray(_extract_statistical_feature_vector(resized), dtype=np.float32)
        coreset = np.asarray(self._statistical_model["coreset"], dtype=np.float32)
        if coreset.ndim != 2 or coreset.shape[1] != feature.shape[0]:
            raise ValueError(
                f"PatchCore feature dimension mismatch: model={coreset.shape}, "
                f"image={feature.shape[0]}"
            )
        distances = np.linalg.norm(coreset - feature, axis=1)
        raw_distance = float(distances.min())
        threshold = float(self._statistical_model.get("threshold") or self.score_threshold or 1.0)
        normalized = raw_distance / max(threshold, 1e-6)
        return float(max(0.0, min(1.0, normalized))), raw_distance

    def predict_image(self, image_path: str | Path) -> object:
        """Compatibility adapter for hybrid retest workers."""
        prediction = self.predict(image_path)
        return SimpleNamespace(
            image_score=prediction.anomaly.image_score,
            heatmap_path=prediction.anomaly.heatmap_path,
        )

    # -------------------------------------------------------------- predict_batch

    def predict_batch(self, image_paths: list[str | Path]) -> list[UnifiedPrediction]:
        """Infer on a batch sequentially."""
        return [self.predict(p) for p in image_paths]


def _extract_statistical_feature_vector(image) -> list[float]:
    """Extract the same deterministic features used by the lightweight trainer."""
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
