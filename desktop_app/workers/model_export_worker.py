"""Model export worker — runs export/benchmark/deploy on a background QThread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class ModelExportWorker(QThread):
    """Background worker for model export, benchmark, and deployment operations.

    task_type: "export_onnx", "export_tensorrt", "benchmark", "deploy"
    config: dict with model_id, output_dir, imgsz, precision, etc.
    """

    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        task_type: str,
        config: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._task_type = task_type
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._task_type == "export_onnx":
                self._run_export_onnx()
            elif self._task_type == "export_tensorrt":
                self._run_export_tensorrt()
            elif self._task_type == "benchmark":
                self._run_benchmark()
            elif self._task_type == "deploy":
                self._run_deploy()
            else:
                self.error.emit(f"Unknown task type: {self._task_type}")
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _run_export_onnx(self) -> None:
        from core.model_export import export_yolo_to_onnx

        model_id: str = self._config["model_id"]
        output_dir: str = self._config["output_dir"]
        imgsz: int = self._config.get("imgsz", 640)

        self.progress.emit("Starting ONNX export...")

        result = export_yolo_to_onnx(
            model_id=model_id,
            output_dir=output_dir,
            imgsz=imgsz,
        )
        if self._cancelled:
            return
        self.finished.emit(result)

    def _run_export_tensorrt(self) -> None:
        from core.model_export import export_yolo_to_tensorrt

        model_id: str = self._config["model_id"]
        output_dir: str = self._config["output_dir"]
        imgsz: int = self._config.get("imgsz", 640)
        precision: str = self._config.get("precision", "fp16")
        workspace_gb: int = self._config.get("workspace_gb", 4)
        calibration_dir: str = self._config.get("calibration_dir", "")

        self.progress.emit(f"Starting TensorRT {precision.upper()} export...")

        result = export_yolo_to_tensorrt(
            model_id=model_id,
            output_dir=output_dir,
            imgsz=imgsz,
            precision=precision,
            workspace_gb=workspace_gb,
            calibration_dir=calibration_dir,
        )
        if self._cancelled:
            return
        self.finished.emit(result)

    def _run_benchmark(self) -> None:
        """Placeholder: benchmark not yet implemented."""
        self.progress.emit("Benchmark not yet implemented")
        self.finished.emit(None)

    def _run_deploy(self) -> None:
        """Placeholder: deploy not yet implemented."""
        self.progress.emit("Deploy not yet implemented")
        self.finished.emit(None)
