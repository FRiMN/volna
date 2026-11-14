"""DirectoryController — async glue between DirScanner and DirModel.

No GTK imports here: the UI passes ``dispatch`` (``GLib.idle_add``) so scanner
batches land on the main loop; tests pass a queue-based dispatcher.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .core import DirModel, DirScanner, StatPool

Dispatch = Callable[..., Any]


class DirectoryController:
    """Runs one scan at a time, feeding batches into a ``DirModel``."""

    def __init__(
        self,
        model: DirModel,
        *,
        dispatch: Dispatch,
        stat_pool: StatPool | None = None,
    ) -> None:
        self._model = model
        self._dispatch = dispatch
        self._stat_pool = stat_pool or StatPool()
        self._scanner: DirScanner | None = None

    def open(self, path: str) -> int:
        if self._scanner is not None:
            self._scanner.cancel()

        generation = self._model.begin_scan(path)
        scanner = DirScanner(stat_pool=self._stat_pool)
        self._scanner = scanner
        scanner.start(
            path,
            generation,
            emit=lambda batch: self._dispatch(self._model.ingest, batch),
            on_done=lambda: self._dispatch(self._model.finish_scan, generation),
            on_error=lambda exc: self._dispatch(self._model.fail_scan, generation, exc),
        )
        return generation

    def join(self, timeout: float | None = None) -> None:
        if self._scanner is not None:
            self._scanner.join(timeout)

    def close(self) -> None:
        if self._scanner is not None:
            self._scanner.cancel()
            self._scanner.join(1.0)
            self._scanner = None
        self._stat_pool.close()
