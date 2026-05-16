"""YOLO .pt model runner for external model evaluation."""

from __future__ import annotations

import time
import os
from pathlib import Path
from typing import Callable

from core.schema import DetectionBox, ImagePrediction
from model_runners.base import BaseModelRunner


class YoloModelRunner(BaseModelRunner):
    """Load a YOLO .pt model via ultralytics and produce ``ImagePrediction``."""

    runner_name = "yolo"
    supported_extensions = (".pt",)

    def __init__(
        self,
        model_path: str,
        class_names: dict[int, str] | None = None,
        config: dict | None = None,
    ) -> None:
        super().__init__(model_path, class_names, config)
        self._model: object = None
        self.confidence: float = float(self.config.get("confidence", 0.25))
        self.iou: float = float(self.config.get("iou", 0.45))
        self.image_size: int = int(self.config.get("image_size", 640))
        self.device: str = str(self.config.get("device", self._detect_device()))

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def load(self) -> None:
        config_dir = Path("outputs/ultralytics").resolve()
        config_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(config_dir))

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError(
                "ultralytics is not installed. Run: pip install ultralytics"
            ) from exc

        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"YOLO model not found: {model_file}")

        try:
            self._model = YOLO(self.model_path)
        except Exception as exc:
            raise ValueError(
                f"Failed to load YOLO model from {self.model_path}: {exc}"
            ) from exc

        # Use model's built-in names if class_names not provided
        if not self.class_names and hasattr(self._model, "names"):
            self.class_names = {
                int(k): str(v) for k, v in self._model.names.items()
            }

        self._is_loaded = True

    def predict_image(self, image_path: str | Path) -> ImagePrediction:
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        t0 = time.perf_counter()
        try:
            results = self._model.predict(
                source=str(image_path),
                conf=self.confidence,
                iou=self.iou,
                imgsz=self.image_size,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            raise RuntimeError(
                f"YOLO inference failed for {image_path}: {exc}"
            ) from exc

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        img_name = Path(image_path).name
        detections: list[DetectionBox] = []

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0].item())
                cls_name = self.class_names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    DetectionBox(
                        image_name=img_name,
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                        bbox=xyxy,
                    )
                )

        _ = elapsed_ms  # kept for potential logging
        return ImagePrediction(image_name=img_name, detections=detections)

    def predict_batch(
        self,
        image_paths: list[str | Path],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ImagePrediction]:
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        results: list[ImagePrediction] = []
        total = len(image_paths)

        for i, p in enumerate(image_paths):
            results.append(self.predict_image(p))
            if progress_callback:
                progress_callback(i + 1, total)

        return results
