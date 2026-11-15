"""DirModel — the single source of listing order, groups, counters and visibility.

The model is thread-agnostic: every method must run on one thread (the GTK
main loop in the app). The async wiring — a worker thread plus
``GLib.idle_add`` marshalling — belongs to the UI/controller layer.

Hidden entries are always enumerated and kept in memory; ``show_hidden`` is a
read policy over that list, not a scanner option (see design/view-panel.md
§2.5). ``entries()``/``groups()``/``counters()`` therefore describe only what the
current policy lets the user see, and flipping it is an in-memory operation.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .entry import Entry, Kind
from .order import BUCKET_ORDER, GroupBucket, SortKey, group_of, sort_entries
from .scanner import Batch, DirScanner, Phase
from .statpool import StatPool

STREAMING_THRESHOLD = 50_000


class ScanState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    READY = "ready"
    ERROR = "error"


class Event(Enum):
    ITEM_BATCH = "item-batch"
    ORDER_CHANGED = "order-changed"
    COUNTERS_CHANGED = "counters-changed"
    SCAN_STATE = "scan-state"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class Counters:
    folders: int = 0
    files: int = 0
    total_size: int = 0


@dataclass(slots=True, frozen=True)
class Group:
    bucket: GroupBucket
    entries: list[Entry]


class DirModel:
    """Holds one directory listing and publishes changes to subscribers."""

    def __init__(
        self,
        *,
        sort_key: SortKey = SortKey.MTIME,
        reverse: bool = True,
        folders_first: bool = True,
        show_hidden: bool = True,
        threshold: int = STREAMING_THRESHOLD,
        stat_pool: StatPool | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.sort_key = sort_key
        self.reverse = reverse
        self.folders_first = folders_first
        self.show_hidden = show_hidden
        self.threshold = threshold
        self._stat_pool = stat_pool
        self._now = now
        self._generation = 0
        self._state = ScanState.IDLE
        self._path = ""
        self._entries: list[Entry] = []
        self._counters = Counters()
        self._subscribers: dict[Event, list[Callable[..., None]]] = defaultdict(list)

    # -- subscriptions -------------------------------------------------

    def subscribe(self, event: Event, callback: Callable[..., None]) -> None:
        self._subscribers[event].append(callback)

    def _emit(self, event: Event, *args: object) -> None:
        for callback in self._subscribers[event]:
            callback(*args)

    # -- lifecycle -----------------------------------------------------

    def begin_scan(self, path: str) -> int:
        """Start a new listing: bump generation, reset state, return generation."""
        self._generation += 1
        self._state = ScanState.SCANNING
        self._path = path
        self._entries = []
        self._counters = Counters()
        self._emit(Event.SCAN_STATE, self._state, self._generation)
        return self._generation

    def finish_scan(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._flush_order()
        self._state = ScanState.READY
        self._emit(Event.SCAN_STATE, self._state, generation)

    def fail_scan(self, generation: int, error: BaseException) -> None:
        if generation != self._generation:
            return
        self._state = ScanState.ERROR
        self._emit(Event.ERROR, error, generation)
        self._emit(Event.SCAN_STATE, self._state, generation)

    # -- ingest --------------------------------------------------------

    def ingest(self, batch: Batch) -> None:
        """Apply one scanner batch; stale generations are ignored."""
        if batch.generation != self._generation:
            return

        if batch.phase is Phase.DIRENT:
            self._entries.extend(batch.entries)
            self._count_kinds(batch.entries)
        else:
            self._count_sizes(batch.entries)

        if len(self._entries) <= self.threshold:
            self._flush_order()

        self._emit(Event.ITEM_BATCH, batch, self._generation)
        self._emit(Event.COUNTERS_CHANGED, self._counters, self._generation)

    def _count_kinds(self, entries: list[Entry]) -> None:
        folders = self._counters.folders
        files = self._counters.files
        for entry in entries:
            if not self._visible(entry):
                continue
            if entry.kind is Kind.DIR:
                folders += 1
            else:
                files += 1
        self._counters = Counters(folders, files, self._counters.total_size)

    def _count_sizes(self, entries: list[Entry]) -> None:
        total = self._counters.total_size
        for entry in entries:
            if not self._visible(entry):
                continue
            if entry.kind is not Kind.DIR and entry.size is not None:
                total += entry.size
        self._counters = Counters(self._counters.folders, self._counters.files, total)

    def _flush_order(self) -> None:
        sort_entries(
            self._entries,
            key=self.sort_key,
            reverse=self.reverse,
            folders_first=self.folders_first,
        )
        self._emit(Event.ORDER_CHANGED, self._generation)

    # -- runtime order and visibility ----------------------------------

    def set_order(self, *, sort_key: SortKey, reverse: bool) -> bool:
        """Re-sort the loaded listing in memory; return whether it changed.

        This is a display change, not a scan: no I/O, no generation bump and
        ``ScanState`` keeps its current value. ``ORDER_CHANGED`` is emitted so
        subscribed views refresh through their usual idle batch.
        """
        if sort_key == self.sort_key and reverse == self.reverse:
            return False

        self.sort_key = sort_key
        self.reverse = reverse
        self._flush_order()

        return True

    def set_folders_first(self, folders_first: bool) -> bool:
        """Mix or group folders in the loaded listing; returns whether it changed.

        Display-only: re-sorts in memory and emits ``ORDER_CHANGED``; no I/O,
        no generation bump and ``ScanState`` is untouched.
        """
        if folders_first == self.folders_first:
            return False

        self.folders_first = folders_first
        self._flush_order()

        return True

    def set_show_hidden(self, show_hidden: bool) -> bool:
        """Apply the hidden-entry policy; return whether it changed.

        Hidden entries are already loaded, so nothing is scanned here: counters
        are rebuilt from the loaded list and both counters and order are
        announced so subscribed views refresh.
        """
        if show_hidden == self.show_hidden:
            return False

        self.show_hidden = show_hidden
        self._recount()
        self._emit(Event.COUNTERS_CHANGED, self._counters, self._generation)
        self._emit(Event.ORDER_CHANGED, self._generation)

        return True

    def _visible(self, entry: Entry) -> bool:
        return self.show_hidden or not entry.is_hidden

    def _recount(self) -> None:
        """Rebuild counters for the current visibility policy from loaded entries."""
        folders = 0
        files = 0
        total_size = 0
        for entry in self._entries:
            if not self._visible(entry):
                continue
            if entry.kind is Kind.DIR:
                folders += 1
                continue

            files += 1
            if entry.size is not None:
                total_size += entry.size

        self._counters = Counters(folders, files, total_size)

    # -- synchronous driver (tests, CLI) -------------------------------

    def scan(self, path: str) -> int:
        """Scan ``path`` synchronously on the calling thread."""
        generation = self.begin_scan(path)
        scanner = DirScanner(stat_pool=self._stat_pool)
        try:
            scanner.scan(path, generation, self.ingest)
        except Exception as exc:  # noqa: BLE001 — become scan state, not a crash
            self.fail_scan(generation, exc)
            return generation
        self.finish_scan(generation)
        return generation

    # -- queries -------------------------------------------------------

    def entries(self) -> list[Entry]:
        return [entry for entry in self._entries if self._visible(entry)]

    def counters(self) -> Counters:
        return self._counters

    def groups(self) -> list[Group]:
        now = self._now()
        buckets: dict[GroupBucket, list[Entry]] = defaultdict(list)
        for entry in self._entries:
            if not self._visible(entry):
                continue
            buckets[group_of(entry.mtime, now=now)].append(entry)

        return [
            Group(bucket, buckets[bucket])
            for bucket in BUCKET_ORDER
            if bucket in buckets
        ]

    @property
    def state(self) -> ScanState:
        return self._state

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def path(self) -> str:
        return self._path
