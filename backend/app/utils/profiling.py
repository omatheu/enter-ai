"""Helpers to capture per-step execution timing."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from time import perf_counter
from typing import Dict


class ProfileCollector:
    """Collects execution timings (in milliseconds) for named sections."""

    def __init__(self) -> None:
        self._metrics = defaultdict(float)

    @contextmanager
    def track(self, name: str):
        """Context manager to time a code block."""

        start = perf_counter()
        try:
            yield
        finally:
            duration_ms = (perf_counter() - start) * 1000.0
            self._metrics[name] += duration_ms

    def record(self, name: str, duration_ms: float | int) -> None:
        """Record an explicit duration."""

        if duration_ms is None:
            return
        try:
            value = float(duration_ms)
        except (TypeError, ValueError):
            return
        self._metrics[name] += value

    def snapshot(self) -> Dict[str, int]:
        """Return timings rounded to millisecond integers."""

        return {key: int(value) for key, value in self._metrics.items()}
