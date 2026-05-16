"""YOLO object-detection runner backed by ultralytics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.fusion.decision_types import BBoxPrediction, UnifiedPrediction
from src.inference.base_runner import BaseRunner
from src.utils.logger import get_logger

_log = get_logger()


class YoloRunner(BaseRunner):
    """YOLO-based bounding-box detector for surface defects.

    Parameters
    ----------
    config : dict | None
        Expected keys: ``conf_threshold`` (default 0.6), ``iou_threshold`` (default
        0.5), ``device`` (default "auto"), ``model_path`` (default "models/yolo/
        best.pt"), ``task`` (default "detect").
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("yolo", config)
        self.conf_threshold: float = float(self.config.get("conf_threshold", 0.6))
        self.iou_threshold: float = float(self.config.get("iou_threshold", 0.5))
        self.device_str: str = str(self.config.get("device", "auto"))
        self.model_path: str = str(self.config.get("model_path", "models/yolo/best.pt"))
        self.task: str = str(self.config.get("task", "detect"))
        self._class_names: dict[int, str] = {}

    # ------------------------------------------------------------------ load_model

    def load_model(self) -> None:
        """Load the YOLO model from disk."""
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError(
                "ultralytics is not installed. Run: pip install ultralytics"
            ) from exc

        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"YOLO model not found: {model_file}")

        self._model = YOLO(self.model_path)
        self._is_loaded = True

        if hasattr(self._model, "names"):
            self._class_names = self._model.names
            _log.info("YOLO model loaded — %d classes", len(self._class_names))
        else:
            _log.info("YOLO model loaded (no class names exposed)")

    # ------------------------------------------------------------------ predict

    def predict(self, image_path: str | Path) -> UnifiedPrediction:
        """Run YOLO on a single image."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        t0 = time.perf_counter()
        results = self._model.predict(
            source=str(image_path),
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            device=self.device_str,
            verbose=False,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0

        predictions: list[BBoxPrediction] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0].item())
                cls_name = self._class_names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].tolist()

                mask: Any = None
                if hasattr(r, "masks") and r.masks is not None:
                    try:
                        mask = r.masks.xy[0].tolist() if len(r.masks.xy) > 0 else None
                    except Exception:
                        mask = None

                predictions.append(
                    BBoxPrediction(
                        type="bbox",
                        class_name=cls_name,
                        confidence=conf,
                        bbox_xyxy=xyxy,
                        mask=mask,
                        score=conf,
                    )
                )

        return UnifiedPrediction(
            image_path=str(image_path),
            model_name="yolo",
            predictions=predictions,
            runtime_ms=elapsed,
        )

    # -------------------------------------------------------------- predict_batch

    def predict_batch(self, image_paths: list[str | Path]) -> list[UnifiedPrediction]:
        """Batch-predict in a single ultralytics call for efficiency."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        t0 = time.perf_counter()
        results = self._model.predict(
            source=[str(p) for p in image_paths],
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            device=self.device_str,
            verbose=False,
        )
        total_elapsed = (time.perf_counter() - t0) * 1000.0

        output: list[UnifiedPrediction] = []
        per_image = total_elapsed / max(len(image_paths), 1)

        for i, r in enumerate(results):
            predictions: list[BBoxPrediction] = []
            if r.boxes is not None:
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = self._class_names.get(cls_id, f"class_{cls_id}")
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()
                    predictions.append(
                        BBoxPrediction(
                            type="bbox",
                            class_name=cls_name,
                            confidence=conf,
                            bbox_xyxy=xyxy,
                            score=conf,
                        )
                    )

            output.append(
                UnifiedPrediction(
                    image_path=str(image_paths[i]),
                    model_name="yolo",
                    predictions=predictions,
                    runtime_ms=per_image,
                )
            )

        return output

    # ------------------------------------------------------------ get_model_info

    def get_model_info(self) -> dict[str, Any]:
        """Return runner metadata including thresholds."""
        info = super().get_model_info()
        info.update(
            {
                "model_path": self.model_path,
                "conf_threshold": self.conf_threshold,
                "iou_threshold": self.iou_threshold,
                "device": self.device_str,
                "task": self.task,
                "num_classes": len(self._class_names),
            }
        )
        return info
