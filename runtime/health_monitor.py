"""Health monitor — tracks system health metrics."""
from __future__ import annotations

import os
import time
import platform


class HealthMonitor:
    """Tracks disk, memory, and process health."""

    def __init__(self):
        self._start_time = time.time()

    def get_health(self) -> dict:
        uptime = time.time() - self._start_time
        disk_usage = self._get_disk_usage()
        return {
            "uptime_seconds": round(uptime, 0),
            "disk_free_gb": round(disk_usage.get("free_gb", 0), 1),
            "disk_total_gb": round(disk_usage.get("total_gb", 0), 1),
            "disk_percent": disk_usage.get("percent", 0),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        }

    @staticmethod
    def _get_disk_usage() -> dict:
        try:
            import shutil
            usage = shutil.disk_usage(os.getcwd())
            return {
                "free_gb": usage.free / (1024**3),
                "total_gb": usage.total / (1024**3),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            return {"free_gb": 0, "total_gb": 0, "percent": 0}
