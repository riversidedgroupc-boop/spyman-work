"""Disk space monitor with degradation level support."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum


class DiskLevel(str, Enum):
    NORMAL = "normal"       # > 10% free and > 2GB — write all
    WARNING = "warning"     # 5-10% free or 1-2GB — log warning, still write
    CRITICAL = "critical"   # < 5% free or < 1GB — drop OK images, only save NG/UNKNOWN


@dataclass
class DiskStatus:
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    free_pct: float = 0.0
    level: DiskLevel = DiskLevel.NORMAL


class DiskMonitor:
    """Monitors free disk space and returns a degradation level.

    Thresholds:
      CRITICAL: free < 5% or free < 1 GB
      WARNING:  free < 10% or free < 2 GB
      NORMAL:   otherwise
    """

    CRITICAL_FREE_PCT = 5.0
    CRITICAL_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB
    WARNING_FREE_PCT = 10.0
    WARNING_FREE_BYTES = 2 * 1024 * 1024 * 1024   # 2 GB

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._status = DiskStatus()

    def check(self) -> DiskStatus:
        usage = shutil.disk_usage(self._base_dir)
        free_pct = usage.free / max(usage.total, 1) * 100.0

        if free_pct < self.CRITICAL_FREE_PCT or usage.free < self.CRITICAL_FREE_BYTES:
            level = DiskLevel.CRITICAL
        elif free_pct < self.WARNING_FREE_PCT or usage.free < self.WARNING_FREE_BYTES:
            level = DiskLevel.WARNING
        else:
            level = DiskLevel.NORMAL

        self._status = DiskStatus(
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            free_pct=round(free_pct, 1),
            level=level,
        )
        return self._status

    @property
    def status(self) -> DiskStatus:
        return self._status

    @property
    def level(self) -> DiskLevel:
        return self._status.level
