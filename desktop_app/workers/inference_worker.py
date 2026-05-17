"""Inference worker — runs model inference in background."""
from __future__ import annotations

from PySide6.QtCore import Signal

from desktop_app.i18n import tr
from desktop_app.workers.base_worker import BaseWorker


class InferenceWorker(BaseWorker):
    """Runs batch inference using model_runners."""
    result_ready = Signal(str, object)  # image_path, ImagePrediction

    def __init__(
        self,
        model_path: str,
        image_paths: list[str],
        model_type: str = "yolo",
        confidence: float = 0.25,
        iou: float = 0.45,
        image_size: int = 640,
        device: str = "cpu",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._model_path = model_path
        self._image_paths = image_paths
        self._model_type = model_type
        self._confidence = confidence
        self._iou = iou
        self._image_size = image_size
        self._device = device
        self._predictions: list[tuple[str, object]] = []

    def _run_impl(self) -> None:
        total = len(self._image_paths)

        if self._model_type == "yolo":
            from model_runners.yolo_runner import YoloModelRunner

            runner = YoloModelRunner(
                model_path=self._model_path,
                config={
                    "confidence": self._confidence,
                    "iou": self._iou,
                    "image_size": self._image_size,
                    "device": self._device,
                },
            )
            runner.load()

            for i, img_path in enumerate(self._image_paths):
                if self.is_cancelled():
                    break
                try:
                    pred = runner.predict_image(img_path)
                    self._predictions.append((img_path, pred))
                    self.result_ready.emit(img_path, pred)
                except Exception as e:
                    self.message.emit(tr("inference.failed", path=img_path, error=str(e)))
                self.progress.emit(i + 1, total)
        else:
            self.error.emit(tr("inference.unsupported_model", type=self._model_type))

    def get_predictions(self) -> list[tuple[str, object]]:
        return self._predictions
