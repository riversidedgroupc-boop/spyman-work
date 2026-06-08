"""Hybrid retest worker — runs fusion on a background QThread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from core.hybrid_retest import (
    HybridRetestConfig,
    _build_anomaly_runner,
    _build_yolo_runner,
    run_hybrid_retest,
)


class HybridRetestWorker(QThread):
    """Background worker for hybrid retest (YOLO + anomaly fusion)."""

    progress = Signal(int, int, str)
    item_done = Signal(dict)
    finished = Signal(object)  # HybridRetestResult
    error = Signal(str)

    def __init__(
        self,
        config: HybridRetestConfig,
        yolo_runner: object | None = None,
        anomaly_runner: object | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._yolo_runner = yolo_runner
        self._anomaly_runner = anomaly_runner
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation (checked between images)."""
        self._cancelled = True

    def run(self) -> None:
        try:
            # Build YOLO runner from model_id if not explicitly provided
            yolo_runner = self._yolo_runner
            if yolo_runner is None and self._config.yolo_model_id:
                yolo_runner = _build_yolo_runner(
                    self._config.yolo_model_id,
                    confidence=self._config.yolo_conf_threshold,
                )
            anomaly_runner = self._anomaly_runner
            if anomaly_runner is None and self._config.anomaly_model_id:
                anomaly_runner = _build_anomaly_runner(
                    self._config.anomaly_model_id,
                    score_threshold=self._config.anomaly_score_threshold,
                )

            result = run_hybrid_retest(
                config=self._config,
                yolo_runner=yolo_runner,
                anomaly_runner=anomaly_runner,
                progress_callback=self._on_progress,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, image_path: str) -> None:
        if self._cancelled:
            raise InterruptedError("Retest cancelled by user")
        self.progress.emit(current, total, image_path)
