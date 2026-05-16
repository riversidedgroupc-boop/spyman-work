"""Abstract base class for external model runners.

Every runner converts framework-specific outputs into the unified
``ImagePrediction`` schema from ``core.schema``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from core.schema import ImagePrediction


class BaseModelRunner(ABC):
    """Stable interface for external object-detection models.

    Subclasses implement model-specific loading, inference, and normalize
    results to ``ImagePrediction``.
    """

    runner_name: str = "base"
    supported_extensions: tuple[str, ...] = ()

    def __init__(
        self,
        model_path: str,
        class_names: dict[int, str] | None = None,
        config: dict | None = None,
    ) -> None:
        self.model_path: str = model_path
        self.class_names: dict[int, str] = class_names or {}
        self.config: dict = config or {}
        self._is_loaded: bool = False

    @abstractmethod
    def load(self) -> None:
        """Load model weights / resources.  Sets ``_is_loaded = True``."""
        ...

    @abstractmethod
    def predict_image(self, image_path: str | Path) -> ImagePrediction:
        """Run inference on a single image."""
        ...

    def predict_batch(
        self,
        image_paths: list[str | Path],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ImagePrediction]:
        """Run inference on a batch (default: sequential with optional progress)."""
        results: list[ImagePrediction] = []
        total = len(image_paths)
        for i, p in enumerate(image_paths):
            results.append(self.predict_image(p))
            if progress_callback:
                progress_callback(i + 1, total)
        return results

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded
