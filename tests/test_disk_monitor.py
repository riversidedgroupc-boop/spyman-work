"""Tests for DiskMonitor."""
import os
import tempfile

import pytest
from storage_v8.disk_monitor import DiskMonitor, DiskLevel, DiskStatus


def test_normal_disk():
    base = os.path.dirname(__file__)
    monitor = DiskMonitor(base)
    status = monitor.check()
    assert isinstance(status, DiskStatus)
    assert status.total_bytes > 0
    assert status.free_bytes > 0
    assert status.free_pct >= 0
    assert status.level in (DiskLevel.NORMAL, DiskLevel.WARNING, DiskLevel.CRITICAL)


def test_level_property():
    monitor = DiskMonitor(os.path.dirname(__file__))
    monitor.check()
    assert monitor.level in (DiskLevel.NORMAL, DiskLevel.WARNING, DiskLevel.CRITICAL)


def test_status_property():
    monitor = DiskMonitor(os.path.dirname(__file__))
    monitor.check()
    assert monitor.status.free_bytes > 0
