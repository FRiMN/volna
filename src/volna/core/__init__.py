"""Volna core: directory enumeration, ordering and the listing model.

No GTK imports here, so the whole package is testable without a display.
"""

from .entry import Entry, Kind
from .model import Counters, DirModel, Event, ScanState, counters_of
from .order import SortKey, sort_entries
from .scanner import (
    Batch,
    DirScanner,
    Phase,
    ScanError,
    iter_batches,
    iter_dirents,
    iter_stats,
)
from .statpool import StatPool, StatResult

__all__ = [
    "Batch",
    "Counters",
    "DirModel",
    "DirScanner",
    "Entry",
    "Event",
    "Kind",
    "Phase",
    "ScanError",
    "ScanState",
    "SortKey",
    "StatPool",
    "StatResult",
    "counters_of",
    "iter_batches",
    "iter_dirents",
    "iter_stats",
    "sort_entries",
]
