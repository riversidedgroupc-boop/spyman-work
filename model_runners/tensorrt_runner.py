"""TensorRT .engine model runner — duck-typed compatible with hybrid_retest flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TensorRTModelRunner:
    """Load a TensorRT .engine file and produce ImagePrediction-compatible results.

    Duck-typed: has predict_image(path) returning object with .detections attribute.

    Attributes
    ----------
    runner_name : str
        Constant "tensorrt" identifier for duck-typing by backend_factory.
    """

    runner_name: str = "tensorrt"

    def __init__(
        self,
        engine_path: str,
        class_names: dict[int, str] | None = None,
        confidence: float = 0.5,
        iou: float = 0.45,
        image_size: int = 640,
        device_id: int = 0,
    ) -> None:
        self._engine_path = engine_path
        self._class_names = class_names or {}
        self._confidence = confidence
        self._iou = iou
        self._image_size = image_size
        self._device_id = device_id
        self._is_loaded = False
        self._context: Any = None
        self._engine: Any = None

    def load(self) -> None:
        """Load TensorRT engine and create execution context.

        Raises
        ------
        ImportError
            If tensorrt module is not importable.
        FileNotFoundError
            If engine file does not exist at engine_path.
        RuntimeError
            If engine deserialization fails.
        """
        try:
            import tensorrt as trt
        except ImportError:
            raise ImportError(
                "TensorRT is not installed. Install with: pip install tensorrt"
            ) from None

        engine_file = Path(self._engine_path)
        if not engine_file.exists():
            raise FileNotFoundError(
                f"TensorRT engine not found: {self._engine_path}"
            )

        logger = trt.Logger(trt.Logger.WARNING)
        with open(self._engine_path, "rb") as f:
            engine_data = f.read()

        runtime = trt.Runtime(logger)
        try:
            self._engine = runtime.deserialize_cuda_engine(engine_data)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to deserialize TensorRT engine: {self._engine_path}"
            ) from exc

        if self._engine is None:
            raise RuntimeError(
                f"Failed to deserialize TensorRT engine: {self._engine_path}"
            )

        self._context = self._engine.create_execution_context()
        self._is_loaded = True

    def predict_image(self, image_path: str | Path) -> Any:
        """Run inference on a single image.

        Returns an object with .detections attribute (list of DetectionBox-like objects).

        Raises
        ------
        RuntimeError
            If engine is not loaded yet.
        NotImplementedError
            Full TensorRT inference pipeline is not yet implemented (Phase E MVP).
            Use ONNX runner for accelerated inference, or PyTorch runner for development.
        """
        if not self._is_loaded:
            raise RuntimeError("TensorRT engine not loaded. Call load() first.")

        # NOTE: Full TensorRT inference implementation requires:
        # - Preprocessing: load image, resize to self._image_size, normalize, HWC->CHW
        # - GPU memory allocation for input/output bindings via CUDA
        # - Execute context with CUDA stream
        # - Postprocessing: parse output tensors, apply NMS, convert to DetectionBox list
        #
        # For Phase E MVP, this raises NotImplementedError with a clear message.
        # The backend_factory will handle this gracefully.
        raise NotImplementedError(
            "Full TensorRT inference not yet implemented. "
            "Use ONNX runner for accelerated inference, or PyTorch runner for development."
        )
