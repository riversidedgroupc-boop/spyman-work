"""Model engine pool — manages model lifecycle, loading, and inference dispatch."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class ModelEngine(ABC):
    """Abstract engine for a single model type."""

    @property
    @abstractmethod
    def model_type(self) -> str: ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def load(self, model_path: str, device_id: int = 0) -> bool: ...

    @abstractmethod
    def unload(self) -> None: ...

    @abstractmethod
    def infer_batch(self, images: list[np.ndarray]) -> list[dict]: ...

    @property
    @abstractmethod
    def vram_mb(self) -> float: ...


class ModelEnginePool:
    """Manages multiple model engines sharing a single GPU device."""

    def __init__(self, device_id: int = 0):
        self._device_id = device_id
        self._engines: dict[str, ModelEngine] = {}
        self._vram_limit_mb: float = 0.0

    def register(self, model_type: str, engine: ModelEngine) -> None:
        self._engines[model_type] = engine

    def load(self, model_type: str, model_path: str) -> bool:
        engine = self._engines.get(model_type)
        if engine is None:
            raise ValueError(f"Model type '{model_type}' not registered")
        if engine.is_loaded:
            return True
        success = engine.load(model_path, self._device_id)
        if success:
            logger.info("Loaded %s -> %s (VRAM: %.0f MB)", model_type, model_path, engine.vram_mb)
        return success

    def unload(self, model_type: str) -> None:
        engine = self._engines.get(model_type)
        if engine and engine.is_loaded:
            engine.unload()

    def unload_all(self) -> None:
        for engine in self._engines.values():
            if engine.is_loaded:
                engine.unload()

    def is_loaded(self, model_type: str) -> bool:
        engine = self._engines.get(model_type)
        return engine is not None and engine.is_loaded

    def infer(self, model_type: str, images: list[np.ndarray]) -> list[dict]:
        engine = self._engines.get(model_type)
        if engine is None:
            raise ValueError(f"Model type '{model_type}' not registered")
        if not engine.is_loaded:
            raise RuntimeError(f"Model '{model_type}' is not loaded")
        return engine.infer_batch(images)

    def list_loaded(self) -> list[str]:
        return [t for t, e in self._engines.items() if e.is_loaded]

    @property
    def total_vram_mb(self) -> float:
        return sum(e.vram_mb for e in self._engines.values() if e.is_loaded)

    @property
    def device_id(self) -> int:
        return self._device_id
