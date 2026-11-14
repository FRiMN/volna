"""Sorting and date grouping — pure functions, no GTK imports."""

from __future__ import annotations

import time
from enum import Enum

from .entry import Entry, Kind


class SortKey(Enum):
    NAME = "name"
    SIZE = "size"
    MTIME = "mtime"


class GroupBucket(Enum):
    """Coarse date bucket; the UI renders weekday labels inside THIS_WEEK."""

    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    OLDER = "older"
    UNKNOWN = "unknown"


BUCKET_ORDER = (
    GroupBucket.TODAY,
    GroupBucket.YESTERDAY,
    GroupBucket.THIS_WEEK,
    GroupBucket.OLDER,
    GroupBucket.UNKNOWN,
)

_DAY = 86_400.0


def sort_entries(entries: list[Entry], *, key: SortKey, reverse: bool = False) -> None:
    """Sort in place: folders first, direction on the value, missing/zero last."""
    if key is SortKey.NAME:
        entries.sort(key=lambda entry: entry.name_key, reverse=reverse)
        entries.sort(key=_folder_rank)
        return

    def numeric_key(entry: Entry) -> tuple[int, int, float]:
        present, value = _present_value(entry, key)
        if reverse:
            value = -value
        return (_folder_rank(entry), 0 if present else 1, value)

    entries.sort(key=numeric_key)


def group_of(mtime: float | None, *, now: float) -> GroupBucket:
    """Bucket a modification time relative to ``now`` using local calendar days."""
    if mtime is None:
        return GroupBucket.UNKNOWN

    today = day_start(now)
    if mtime >= today:
        return GroupBucket.TODAY
    if mtime >= today - _DAY:
        return GroupBucket.YESTERDAY
    if mtime >= today - 7 * _DAY:
        return GroupBucket.THIS_WEEK
    return GroupBucket.OLDER


def day_start(timestamp: float) -> float:
    """Local midnight for the day containing ``timestamp``."""
    local = time.localtime(timestamp)
    return time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))


def _folder_rank(entry: Entry) -> int:
    return 0 if entry.kind is Kind.DIR else 1


def _present_value(entry: Entry, key: SortKey) -> tuple[bool, float]:
    if key is SortKey.SIZE:
        size = entry.size
        if size is None or size <= 0:
            return False, 0.0
        return True, float(size)

    mtime = entry.mtime
    if mtime is None:
        return False, 0.0
    return True, mtime
