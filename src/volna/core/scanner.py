"""Directory enumeration: readdir batches, then lazy stat batches."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Generator
from contextlib import closing
from dataclasses import dataclass
from enum import Enum

from .entry import Entry, Kind
from .statpool import StatPool

DIRENT_BATCH = 1024
STAT_CHUNK = 256


class Phase(Enum):
    DIRENT = "dirent"
    STATS = "stats"


@dataclass(slots=True, frozen=True)
class Batch:
    generation: int
    phase: Phase
    entries: list[Entry]


class ScanError(RuntimeError):
    """Fatal error while enumerating a directory."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


def iter_dirents(
    path: str,
    generation: int,
    *,
    batch_size: int = DIRENT_BATCH,
    cancel: threading.Event | None = None,
) -> Generator[Batch, None, None]:
    """Phase 1: yield DIRENT batches straight from ``readdir``.

    Entries carry ``name``/``path``/``kind`` only; ``size``/``mtime`` stay empty
    until a STATS pass. Raises ``ScanError`` when the directory cannot be opened.
    """
    try:
        scandir = os.scandir(path)
    except OSError as exc:
        raise ScanError(path, str(exc)) from exc

    with scandir:
        batch: list[Entry] = []
        for dirent in scandir:
            if cancel is not None and cancel.is_set():
                return

            batch.append(Entry(name=dirent.name, path=dirent.path, kind=_kind(dirent)))
            if len(batch) >= batch_size:
                yield Batch(generation, Phase.DIRENT, batch)
                batch = []

        if batch:
            yield Batch(generation, Phase.DIRENT, batch)


def iter_stats(
    entries: list[Entry],
    generation: int,
    *,
    stat_pool: StatPool | None = None,
    chunk_size: int = STAT_CHUNK,
    cancel: threading.Event | None = None,
) -> Generator[Batch, None, None]:
    """Phase 2: fill ``size``/``mtime`` on ``entries`` and yield STATS batches.

    ``entries`` are mutated in place, ``chunk_size`` at a time. Without a
    ``stat_pool`` a private one is created and closed when the iterator ends;
    a caller-provided pool is left open.
    """
    pool = stat_pool
    owns_pool = pool is None
    if pool is None:
        pool = StatPool()
    try:
        for start in range(0, len(entries), chunk_size):
            if cancel is not None and cancel.is_set():
                return

            chunk = entries[start : start + chunk_size]
            results = pool.stat_batch([entry.path for entry in chunk])
            for entry, result in zip(chunk, results, strict=True):
                if result.ok:
                    entry.size = result.size
                    entry.mtime = result.mtime
            yield Batch(generation, Phase.STATS, chunk)
    finally:
        if owns_pool:
            pool.close()


def iter_batches(
    path: str,
    generation: int,
    *,
    stat_pool: StatPool | None = None,
    batch_size: int = DIRENT_BATCH,
    need_stats: bool = True,
    cancel: threading.Event | None = None,
) -> Generator[Batch, None, None]:
    """Yield DIRENT batches, then (optionally) STATS batches that fill sizes."""
    dirents = iter_dirents(
        path,
        generation,
        batch_size=batch_size,
        cancel=cancel,
    )
    entries: list[Entry] = []
    with closing(dirents):
        for batch in dirents:
            if need_stats:
                entries.extend(batch.entries)
            yield batch

    if not need_stats:
        return

    if cancel is not None and cancel.is_set():
        return

    yield from iter_stats(
        entries,
        generation,
        stat_pool=stat_pool,
        cancel=cancel,
    )


class DirScanner:
    """Run enumeration synchronously (``scan``) or on a worker (``start``)."""

    def __init__(
        self,
        *,
        stat_pool: StatPool | None = None,
        batch_size: int = DIRENT_BATCH,
        need_stats: bool = True,
    ) -> None:
        self._stat_pool = stat_pool
        self._batch_size = batch_size
        self._need_stats = need_stats
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def scan(self, path: str, generation: int, emit: Callable[[Batch], None]) -> None:
        """Synchronous: call ``emit`` for every batch on the current thread."""
        self._cancel.clear()
        batches = iter_batches(
            path,
            generation,
            stat_pool=self._stat_pool,
            batch_size=self._batch_size,
            need_stats=self._need_stats,
            cancel=self._cancel,
        )
        try:
            for batch in batches:
                if self._cancel.is_set():
                    return
                emit(batch)
        finally:
            batches.close()

    def start(
        self,
        path: str,
        generation: int,
        emit: Callable[[Batch], None],
        *,
        on_done: Callable[[], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> threading.Thread:
        """Run ``scan`` on a daemon thread; callbacks fire from that thread.

        The caller owns thread-safety of ``emit``: the UI layer must marshal
        into the GTK main loop (``GLib.idle_add``) before touching the model.
        """
        thread = threading.Thread(
            target=self._run,
            args=(path, generation, emit, on_done, on_error),
            name=f"volna-scan-{generation}",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return thread

    def _run(
        self,
        path: str,
        generation: int,
        emit: Callable[[Batch], None],
        on_done: Callable[[], None] | None,
        on_error: Callable[[BaseException], None] | None,
    ) -> None:
        try:
            self.scan(path, generation, emit)
        except Exception as exc:  # noqa: BLE001 — surfaced through on_error
            if on_error is not None:
                on_error(exc)
            return

        if on_done is not None:
            on_done()

    def cancel(self) -> None:
        self._cancel.set()

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()


def _kind(dirent: os.DirEntry[str]) -> Kind:
    try:
        if dirent.is_symlink():
            return Kind.SYMLINK
        if dirent.is_dir(follow_symlinks=False):
            return Kind.DIR
        if dirent.is_file(follow_symlinks=False):
            return Kind.FILE
    except OSError:
        return Kind.OTHER

    return Kind.OTHER
