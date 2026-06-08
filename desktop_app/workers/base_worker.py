"""Base worker with standardized signals for background tasks."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    started = Signal()
    progress = Signal(int, int)  # current, total
    message = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            self.started.emit()
            self._run_impl()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def _run_impl(self) -> None:
        raise NotImplementedError
