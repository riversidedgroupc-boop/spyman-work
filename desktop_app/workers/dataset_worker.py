"""QThread worker for dataset building + quality checking."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class DatasetBuildWorker(QThread):
    """Background worker that builds a dataset from a capture session.

    Emits:
        progress(msg: str, pct: float) — progress update
        finished(result: object)        — build completed successfully
        error(message: str)             — build failed
    """

    progress = Signal(str, float)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        builder_fn,
        builder_kwargs: dict,
        parent=None,
    ):
        super().__init__(parent)
        self._builder_fn = builder_fn
        self._kwargs = builder_kwargs

    def run(self) -> None:
        try:
            # Inject progress callback
            self._kwargs["progress_callback"] = lambda msg, pct: self.progress.emit(msg, pct)
            result = self._builder_fn(**self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
