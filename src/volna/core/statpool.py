"""Parallel metadata lookup over a thread pool — no GTK imports."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

CHUNK = 256


@dataclass(slots=True, frozen=True)
class StatResult:
    path: str
    ok: bool
    size: int = 0
    mtime: float = 0.0


def _stat_one(path: str) -> StatResult:
    try:
        info = os.stat(path)
    except OSError:
        return StatResult(path=path, ok=False)

    return StatResult(path=path, ok=True, size=info.st_size, mtime=info.st_mtime)


class StatPool:
    """Thread pool for the stat phase; ``os.stat`` releases the GIL."""

    def __init__(self, *, max_workers: int = 8, chunk: int = CHUNK) -> None:
        self._chunk = chunk
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="volna-stat",
        )

    def stat_batch(self, paths: list[str]) -> list[StatResult]:
        """Stat ``paths`` in parallel; results keep the input order."""
        if not paths:
            return []

        results: list[StatResult] = []
        for start in range(0, len(paths), self._chunk):
            results.extend(
                self._executor.map(_stat_one, paths[start : start + self._chunk])
            )
        return results

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
