"""System monitor — CPU, memory, GPU status."""
from __future__ import annotations

import os
import threading


class SystemMonitor:
    """Monitors CPU and memory usage."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cpu_percent = 0.0
        self._memory_percent = 0.0

    def update(self) -> None:
        try:
            import psutil
            with self._lock:
                self._cpu_percent = psutil.cpu_percent(interval=0.1)
                self._memory_percent = psutil.virtual_memory().percent
        except ImportError:
            # psutil not installed, use fallback
            try:
                import subprocess
                # Windows: use wmic
                result = subprocess.run(
                    ["wmic", "cpu", "get", "loadpercentage"],
                    capture_output=True, text=True, timeout=5,
                )
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    self._cpu_percent = float(lines[1].strip() or 0)
            except Exception:
                self._cpu_percent = -1

    def get_status(self) -> dict:
        with self._lock:
            return {
                "cpu_percent": self._cpu_percent,
                "memory_percent": self._memory_percent,
            }
