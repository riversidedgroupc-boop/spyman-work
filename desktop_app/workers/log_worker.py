"""Background worker for tailing log file content."""
from __future__ import annotations

import os
import time

from desktop_app.workers.base_worker import BaseWorker


class LogTailWorker(BaseWorker):
    """Polls a log file periodically and emits new lines.

    Emits:
        message(str) — each new line appended to the log
        progress(int, int) — (file_size, 0) for polling updates
    """

    def __init__(
        self,
        log_path: str,
        poll_interval_ms: int = 500,
        parent=None,
    ):
        super().__init__(parent)
        self._log_path = log_path
        self._poll_interval = poll_interval_ms / 1000.0

    def _run_impl(self) -> None:
        if not os.path.isfile(self._log_path):
            self.message.emit(f"[Log file not found: {self._log_path}]")
            return

        last_size = 0
        while not self._cancelled:
            try:
                current_size = os.path.getsize(self._log_path)
                if current_size > last_size:
                    with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                        if last_size > 0:
                            f.seek(last_size)
                        new_content = f.read()
                        if new_content:
                            for line in new_content.strip().split("\n"):
                                if line.strip():
                                    self.message.emit(line.strip())
                    last_size = current_size
                elif current_size < last_size:
                    # File was rotated/truncated, re-read from start
                    last_size = 0
                self.progress.emit(current_size, 0)
            except Exception as e:
                self.message.emit(f"[Log read error: {e}]")
            time.sleep(self._poll_interval)
