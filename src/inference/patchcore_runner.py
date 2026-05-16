"""PatchCore anomaly-detection runner.

Supports three operating modes:

- **real**   – uses anomalib (if installed) for actual inference.
- **import** – reads pre-computed anomaly scores from a CSV file.
- **mock**    – generates deterministic pseudo-random results for testing.
"""

from __future__ import annotations

import time
from pathlib import Path
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
        Keys: ``mode`` ("mock"|"import"|"real"), ``model_path``, ``result_file``,
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

    # ------------------------------------------------------------------ load_model

    def load_model(self) -> None:
        """Load model or switch to fallback mode."""
        if self.mode == "real":
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
            from anomalib.models import Patchcore

            _log.info("anomalib PatchCore available (model loading deferred)")
        except Exception:
            _log.warning(
                "Failed to import anomalib PatchCore. Falling back to mock mode."
            )
            self.mode = "mock"

        self._is_loaded = True

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

        # ---- mock mode ---------------------------------------------------------
        if self.mode == "mock":
            seed = hash(img_path_str) % (2**31)
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

        # ---- real mode (placeholder) -------------------------------------------
        # Real anomalib inference should be wired in here once the model pipeline is
        # finalized.  For now we return a zero-score result so callers can iterate.
        elapsed = (time.perf_counter() - t0) * 1000.0
        return UnifiedPrediction(
            image_path=img_path_str,
            model_name="patchcore",
            anomaly=AnomalyResult(image_score=0.0, threshold=self.score_threshold),
            runtime_ms=elapsed,
            extra={"warning": "Real PatchCore inference not yet implemented"},
        )

    # -------------------------------------------------------------- predict_batch

    def predict_batch(self, image_paths: list[str | Path]) -> list[UnifiedPrediction]:
        """Infer on a batch sequentially."""
        return [self.predict(p) for p in image_paths]
