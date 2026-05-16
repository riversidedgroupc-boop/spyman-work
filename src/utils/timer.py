"""Execution timer utilities."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager


class Timer:
    """Record execution times with named checkpoints."""

    def __init__(self) -> None:
        self.records: dict[str, float] = {}
        self._starts: dict[str, float] = {}

    def start(self, name: str) -> None:
        self._starts[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        elapsed = time.perf_counter() - self._starts.pop(name, time.perf_counter())
        self.records[name] = elapsed
        return elapsed

    @contextmanager
    def measure(self, name: str):
        self.start(name)
        try:
            yield
        finally:
            self.stop(name)

    def summary(self) -> dict[str, float]:
        return dict(self.records)


class BatchTimer:
    """Aggregate timing over multiple runs."""

    def __init__(self) -> None:
        self._totals: dict[str, float] = defaultdict(float)
        self._counts: dict[str, int] = defaultdict(int)

    def record(self, name: str, elapsed_ms: float) -> None:
        self._totals[name] += elapsed_ms
        self._counts[name] += 1

    def avg(self, name: str) -> float:
        count = self._counts.get(name, 0)
        if count == 0:
            return 0.0
        return self._totals[name] / count

    def total(self, name: str) -> float:
        return self._totals.get(name, 0.0)

    def summary(self) -> dict[str, dict[str, float]]:
        return {
            name: {
                "total_ms": self._totals[name],
                "avg_ms": self.avg(name),
                "count": self._counts[name],
            }
            for name in self._totals
        }
