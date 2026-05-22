"""Tests for RAMRingBuffer."""
import numpy as np
import pytest
from runtime.ring_buffer import RAMRingBuffer, RingBufferStats


def test_put_and_get_single():
    buf = RAMRingBuffer(max_slots=8, slot_shape=(3, 320, 320), dtype=np.uint8)
    data = np.ones((3, 320, 320), dtype=np.uint8) * 42
    assert buf.put(data) is True
    result = buf.get()
    assert result is not None
    assert result[0, 0, 0] == 42
    assert buf.size() == 0


def test_capacity_enforced():
    buf = RAMRingBuffer(max_slots=4, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(10):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    assert buf.size() == 4
    stats = buf.stats()
    assert stats.dropped >= 6


def test_get_returns_none_when_empty():
    buf = RAMRingBuffer(max_slots=8, slot_shape=(1, 10, 10), dtype=np.uint8)
    assert buf.get() is None


def test_usage_ratio():
    buf = RAMRingBuffer(max_slots=10, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(6):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    assert 0.5 < buf.usage_ratio() < 0.7


def test_drop_policy_oldest():
    buf = RAMRingBuffer(max_slots=3, slot_shape=(1, 10, 10), dtype=np.uint8, drop_policy="oldest")
    buf.put(np.full((1, 10, 10), 1, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 2, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 3, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 4, dtype=np.uint8))  # drops oldest (value=1)
    first = buf.get()
    assert first[0, 0, 0] == 2  # 1 was dropped


def test_stats_accurate():
    buf = RAMRingBuffer(max_slots=10, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(5):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    for _ in range(3):
        buf.get()
    stats = buf.stats()
    assert stats.total_puts == 5
    assert stats.total_gets == 3
    assert stats.current_size == 2
