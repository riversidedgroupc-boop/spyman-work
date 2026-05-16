"""Abstract base class for all model runners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.fusion.decision_types import UnifiedPrediction


class BaseRunner(ABC):
    """Abstract base class for all inference runners.

    Each runner wraps a specific model (YOLO, PatchCore, EfficientAD, FastFlow,
    OpenCV) and provides a uniform predict / predict_batch interface returning
    ``UnifiedPrediction`` objects.
    """

    def __init__(self, model_name: str, config: dict[str, Any] | None = None) -> None:
        self.model_name: str = model_name
        self.config: dict[str, Any] = config or {}
        self._model: Any = None
        self._is_loaded: bool = False

    @abstractmethod
    def load_model(self) -> None:
        """Load model weights / resources.  Must set ``self._is_loaded = True``."""
        ...

    @abstractmethod
    def predict(self, image_path: str | Path) -> UnifiedPrediction:
        """Run inference on a single image."""
        ...

    def predict_batch(self, image_paths: list[str | Path]) -> list[UnifiedPrediction]:
        """Run inference on a batch of images (default: sequential)."""
        return [self.predict(p) for p in image_paths]

    def warmup(self) -> None:
        """Optional warmup run — override to run a dummy inference pass."""

    def get_model_info(self) -> dict[str, Any]:
        """Return metadata about this runner."""
        return {
            "model_name": self.model_name,
            "is_loaded": self._is_loaded,
        }

    @property
    def is_loaded(self) -> bool:
        """Whether the model has been successfully loaded."""
        return self._is_loaded

    @property
    def device(self) -> str:
        """Get the compute device string ('cuda' or 'cpu')."""
        import torch

        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
