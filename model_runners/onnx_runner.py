"""ONNX .onnx model runner scaffold.

First version supports YOLO-style ONNX exports only.  Falls back gracefully
when ``onnxruntime`` is not installed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from core.schema import DetectionBox, ImagePrediction
from model_runners.base import BaseModelRunner

_ONNXRUNTIME_AVAILABLE = False
try:
    import onnxruntime as ort  # noqa: F401

    _ONNXRUNTIME_AVAILABLE = True
except ImportError:
    pass


class OnnxModelRunner(BaseModelRunner):
    """ONNX object-detection runner (YOLO-export style).

    Config keys
    -----------
    confidence : float (default 0.25)
        Detection confidence threshold.
    iou : float (default 0.45)
        NMS IoU threshold.
    image_size : int (default 640)
        Input resize dimension (square).
    device : str (default "cpu")
        ``"cpu"`` or ``"cuda"``.
    output_format : str (default "yolo_nx")
        ONNX output format.  Currently only ``"yolo_nx"`` is supported.
    """

    runner_name = "onnx"
    supported_extensions = (".onnx",)

    def __init__(
        self,
        model_path: str,
        class_names: dict[int, str] | None = None,
        config: dict | None = None,
    ) -> None:
        super().__init__(model_path, class_names, config)
        self.confidence: float = float(self.config.get("confidence", 0.25))
        self.iou: float = float(self.config.get("iou", 0.45))
        self.image_size: int = int(self.config.get("image_size", 640))
        self.device: str = str(self.config.get("device", self._detect_device()))
        self.output_format: str = str(self.config.get("output_format", "yolo_nx"))
        self._session: Any = None
        self._input_name: str = ""
        self._input_shape: tuple[int, ...] = ()

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
        if not _ONNXRUNTIME_AVAILABLE:
            raise ImportError(
                "onnxruntime is not installed. Run: pip install onnxruntime"
            )

        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_file}")

        if self.output_format not in ("yolo_nx",):
            raise ValueError(
                f"Unsupported ONNX output format: '{self.output_format}'. "
                f"Currently supported: yolo_nx"
            )

        providers = ["CPUExecutionProvider"]
        if self.device.lower() in ("cuda", "gpu"):
            try:
                providers.insert(0, "CUDAExecutionProvider")
            except Exception:
                pass

        self._session = ort.InferenceSession(
            str(model_file), providers=providers
        )
        self._input_name = self._session.get_inputs()[0].name
        self._input_shape = tuple(self._session.get_inputs()[0].shape)
        self._is_loaded = True

    def _preprocess(self, image_path: str | Path) -> np.ndarray:
        """Load image, resize/letterbox, normalize, convert to NCHW."""
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        img = img.resize((self.image_size, self.image_size), Image.Resampling.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0  # RGB 0..1
        arr = np.transpose(arr, (2, 0, 1))  # HWC → CHW
        arr = np.expand_dims(arr, axis=0)  # NCHW
        return arr

    def _parse_yolo_output(self, output: np.ndarray, img_w: int, img_h: int) -> list[DetectionBox]:
        """Parse YOLO-format ONNX output: [1, N, 6] where last dim is
        [x_center, y_center, width, height, confidence, class_probs...] or
        [1, num_boxes, 5+num_classes]."""
        if output.ndim != 3:
            raise ValueError(
                f"Unsupported YOLO ONNX output rank {output.ndim}; expected [1, N, 5+C]"
            )
        if output.shape[0] != 1:
            raise ValueError(
                f"Unsupported YOLO ONNX batch dimension {output.shape[0]}; expected 1"
            )
        if output.shape[1] < output.shape[2] and output.shape[1] >= 5:
            raise ValueError(
                "Unsupported YOLO ONNX layout [1, C, N]. Export or transpose to [1, N, 5+C]."
            )
        boxes = output[0]  # shape (N, 6) or (N, 5+num_classes)

        if boxes.shape[1] < 6:
            return []

        num_classes = boxes.shape[1] - 4  # after cx, cy, w, h
        detections: list[DetectionBox] = []

        for row in boxes:
            cx, cy, bw, bh = row[0], row[1], row[2], row[3]
            obj_conf = float(row[4])

            if num_classes > 1:
                class_probs = row[5:]
                cls_id = int(np.argmax(class_probs))
                cls_conf = obj_conf * float(class_probs[cls_id])
            else:
                cls_id = 0
                cls_conf = obj_conf

            if cls_conf < self.confidence:
                continue

            # Convert center-format to corner-format, scaled to image size
            x1 = (cx - bw / 2) * img_w
            y1 = (cy - bh / 2) * img_h
            x2 = (cx + bw / 2) * img_w
            y2 = (cy + bh / 2) * img_h

            cls_name = self.class_names.get(cls_id, f"class_{cls_id}")
            detections.append(
                DetectionBox(
                    image_name="",
                    class_id=cls_id,
                    class_name=cls_name,
                    confidence=float(cls_conf),
                    bbox=[float(x1), float(y1), float(x2), float(y2)],
                )
            )

        return self._nms(detections)

    def _nms(self, detections: list[DetectionBox]) -> list[DetectionBox]:
        """Apply class-aware NMS."""
        if not detections:
            return []

        # Group by class
        by_class: dict[int, list[DetectionBox]] = {}
        for d in detections:
            by_class.setdefault(d.class_id, []).append(d)

        kept: list[DetectionBox] = []
        for boxes in by_class.values():
            boxes.sort(key=lambda b: b.confidence, reverse=True)
            while boxes:
                best = boxes.pop(0)
                kept.append(best)
                boxes = [
                    b
                    for b in boxes
                    if self._iou_boxes(best.bbox, b.bbox) < self.iou
                ]
        return kept

    @staticmethod
    def _iou_boxes(a: list[float], b: list[float]) -> float:
        x_left = max(a[0], b[0])
        y_top = max(a[1], b[1])
        x_right = min(a[2], b[2])
        y_bottom = min(a[3], b[3])
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        inter = (x_right - x_left) * (y_bottom - y_top)
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def predict_image(self, image_path: str | Path) -> ImagePrediction:
        if not self._is_loaded:
            raise RuntimeError("ONNX model not loaded. Call load() first.")

        from PIL import Image

        img = Image.open(image_path)
        img_w, img_h = img.size

        t0 = time.perf_counter()
        try:
            tensor = self._preprocess(image_path)
            outputs = self._session.run(None, {self._input_name: tensor})
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
        except Exception as exc:
            raise RuntimeError(
                f"ONNX inference failed for {image_path}: {exc}"
            ) from exc

        img_name = Path(image_path).name
        detections = self._parse_yolo_output(outputs[0], img_w, img_h)
        for d in detections:
            d.image_name = img_name

        _ = elapsed_ms
        return ImagePrediction(image_name=img_name, detections=detections)
