"""Sorting — pure functions, no GTK imports."""

from __future__ import annotations

from enum import Enum

from .entry import Entry, Kind


class SortKey(Enum):
    NAME = "name"
    SIZE = "size"
    MTIME = "mtime"


def sort_entries(
    entries: list[Entry],
    *,
    key: SortKey,
    reverse: bool = False,
    folders_first: bool = True,
) -> None:
    """Sort in place: by key, optionally folders first, missing/zero last.

    ``folders_first=False`` mixes folders and files in one order; the value key
    decides their positions. Missing values still go last in both directions.
    """
    if key is SortKey.NAME:
        entries.sort(key=lambda entry: entry.name_key, reverse=reverse)
        if folders_first:
            entries.sort(key=_folder_rank)
        return

    def numeric_key(entry: Entry) -> tuple[int, int, float]:
        present, value = _present_value(entry, key)
        if reverse:
            value = -value
        # One shape for both modes: with ``folders_first`` off every entry gets
        # the same rank, so the key decides and missing values still go last.
        folder_rank = _folder_rank(entry) if folders_first else 0

        return (folder_rank, 0 if present else 1, value)

    entries.sort(key=numeric_key)


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
