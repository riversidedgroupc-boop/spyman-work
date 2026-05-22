"""Synthetic model engines for benchmark mode."""
from __future__ import annotations

import numpy as np

from gpu_scheduler.model_pool import ModelEngine


class SyntheticModelEngine(ModelEngine):
    """Small deterministic model engine used when benchmark has no real model."""

    def __init__(self, model_type: str, vram_mb: float = 256.0) -> None:
        self._model_type = model_type
        self._vram_mb = vram_mb
        self._loaded = False

    @property
    def model_type(self) -> str:
        return self._model_type

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def vram_mb(self) -> float:
        return self._vram_mb

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        results = []
        for image in images:
            mean_value = float(np.mean(image))
            is_ng = mean_value > 105 or mean_value < 35
            results.append({
                "result_type": "NG" if is_ng else "OK",
                "confidence": 0.92 if is_ng else 0.88,
                "model_version": "synthetic_v1",
                "defect_type": "synthetic" if is_ng else "",
                "bbox": None,
            })
        return results
