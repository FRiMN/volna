"""Grouping policy: split an ordered listing into captioned groups.

Grouping is a display policy over the loaded model (design/grouping.md V5):
the model keeps entries and their sort order, a strategy decides where the
captions go and what they say. One strategy = one class, one registry row and
one radio in the View panel, so a new criterion never becomes a new ``if`` in
the tab or the views.

Buckets are data tables at the top of each strategy (calendar rules, size
bands): changing them is a data edit, not a new branch.
"""

from __future__ import annotations

import abc
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import ClassVar

from ..core import Entry


class Grouping(StrEnum):
    """How a listing is split (the View panel radio group)."""

    DATE = "date"
    SIZE = "size"
    NONE = "none"

    @property
    def label(self) -> str:
        """Display name for controls."""
        return _GROUPING_LABELS[self]


_GROUPING_LABELS: dict[Grouping, str] = {
    Grouping.DATE: "По дате изменения",
    Grouping.SIZE: "По размеру",
    Grouping.NONE: "Без группировки",
}


class GroupAction(StrEnum):
    """What a group header interaction asks the tab to do (design/grouping.md D13)."""

    TOGGLE = "toggle"
    COLLAPSE_OTHERS = "collapse-others"
    COLLAPSE_ALL = "collapse-all"
    EXPAND_ALL = "expand-all"


@dataclass(frozen=True, slots=True)
class Group:
    """One non-empty block of a grouped listing.

    ``key`` is the group's stable identity inside its strategy (the tab keys
    collapse state by it) and ``header`` is the caption. Both stay ``None`` for
    the single block of an ungrouped listing.
    """

    entries: list[Entry]
    key: str | None = None
    header: str | None = None


class GroupingStrategy(abc.ABC):
    """One way to split a listing into groups."""

    kind: ClassVar[Grouping]

    @abc.abstractmethod
    def groups(self, entries: Sequence[Entry], *, now: float) -> list[Group]:
        """Split already ordered, visible ``entries`` into non-empty groups."""


# -- date grouping -----------------------------------------------------------


class GroupBucket(Enum):
    """Coarse date bucket; ``THIS_WEEK`` is split per day by the strategy."""

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

# Calendar weekday names; index matches ``time.localtime(...).tm_wday``.
_WEEKDAYS: tuple[str, ...] = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

# One caption per coarse bucket. ``THIS_WEEK`` normally renders as a weekday
# name; the fallback only guards a malformed group (a week group without a day)
# so the UI never shows an empty caption.
_BUCKET_HEADERS: dict[GroupBucket, str] = {
    GroupBucket.TODAY: "Сегодня",
    GroupBucket.YESTERDAY: "Вчера",
    GroupBucket.THIS_WEEK: "На этой неделе",
    GroupBucket.OLDER: "Неделю назад",
    GroupBucket.UNKNOWN: "Без даты",
}


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


class DateGrouping(GroupingStrategy):
    """Groups by modification time: today, yesterday, one group per day of the
    last seven days, the older rest, and entries without a date last.

    Sorting stays global (the model sorts once): bucketing preserves the loaded
    order, so the current sort key and ``folders_first`` apply inside every
    group without a second sort (design/grouping.md D3).
    """

    kind = Grouping.DATE

    def groups(self, entries: Sequence[Entry], *, now: float) -> list[Group]:
        buckets: dict[tuple[GroupBucket, float | None], list[Entry]] = defaultdict(list)
        for entry in entries:
            mtime = entry.mtime
            bucket = group_of(mtime, now=now)
            day = (
                day_start(mtime)
                if bucket is GroupBucket.THIS_WEEK and mtime is not None
                else None
            )
            buckets[(bucket, day)].append(entry)

        return [
            Group(
                items,
                key=_date_key(bucket, day),
                header=_date_header(bucket, day),
            )
            for (bucket, day), items in sorted(buckets.items(), key=_date_order)
        ]


def _date_order(
    item: tuple[tuple[GroupBucket, float | None], list[Entry]],
) -> tuple[int, float]:
    """Bucket order, then newest day first inside ``THIS_WEEK``."""
    (bucket, day), _entries = item
    return BUCKET_ORDER.index(bucket), -(day or 0.0)


def _date_key(bucket: GroupBucket, day: float | None) -> str:
    """Stable identity of a date group (design/grouping.md D12).

    Weekday groups key by their local date, so a collapsed «Среда» stays
    collapsed while the session runs; the coarse buckets key by themselves.
    """
    if bucket is GroupBucket.THIS_WEEK and day is not None:
        return f"week:{time.strftime('%Y-%m-%d', time.localtime(day))}"

    return bucket.value


def _date_header(bucket: GroupBucket, day: float | None) -> str:
    if bucket is GroupBucket.THIS_WEEK and day is not None:
        return _WEEKDAYS[time.localtime(day).tm_wday]

    return _BUCKET_HEADERS[bucket]


# -- size grouping -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SizeBand:
    """A half-open byte range ``[lower, upper)`` and its caption.

    ``upper=None`` is the open-ended last band. The table below is contiguous
    and ordered from small to large; tests pin that property.
    """

    key: str
    header: str
    lower: int
    upper: int | None


# Geometric, tenfold bands: each range is the previous one ×10, from an empty
# file up to anything above a gibibyte. Bytes are the scanner's ``st_size``,
# the same number the Size column shows.
SIZE_BANDS: tuple[SizeBand, ...] = (
    SizeBand("empty", "0 Б", 0, 1),
    SizeBand("tiny", "до 10 КиБ", 1, 10 * 1024),
    SizeBand("small", "10–100 КиБ", 10 * 1024, 100 * 1024),
    SizeBand("medium", "100 КиБ–1 МиБ", 100 * 1024, 1024 * 1024),
    SizeBand("large", "1–10 МиБ", 1024 * 1024, 10 * 1024 * 1024),
    SizeBand("huge", "10–100 МиБ", 10 * 1024 * 1024, 100 * 1024 * 1024),
    SizeBand("giant", "100 МиБ–1 ГиБ", 100 * 1024 * 1024, 1024 * 1024 * 1024),
    SizeBand("colossal", "больше 1 ГиБ", 1024 * 1024 * 1024, None),
)

_FOLDERS_KEY = "folders"
_NO_SIZE_KEY = "unknown"

# Group order: folders first (their size is the directory inode's, not the
# contents'), then the size bands from small to large, and files whose size the
# scan could not read last.
_SIZE_GROUPS: tuple[tuple[str, str], ...] = (
    (_FOLDERS_KEY, "Папки"),
    *((band.key, band.header) for band in SIZE_BANDS),
    (_NO_SIZE_KEY, "Без размера"),
)


class SizeGrouping(GroupingStrategy):
    """Groups files by their reported byte size; folders get their own group.

    A folder's ``st_size`` is the directory inode, not the size of its
    contents, so it would be misleading in a size band: folders are always one
    «Папки» group at the top. Entries whose stat failed have no size and go to
    «Без размера» at the bottom.
    """

    kind = Grouping.SIZE

    def groups(self, entries: Sequence[Entry], *, now: float) -> list[Group]:
        del now
        buckets: dict[str, list[Entry]] = defaultdict(list)
        for entry in entries:
            buckets[_size_key(entry)].append(entry)

        return [
            Group(items, key=f"size:{key}", header=header)
            for key, header in _SIZE_GROUPS
            if (items := buckets.get(key))
        ]


def _size_key(entry: Entry) -> str:
    if entry.is_dir:
        return _FOLDERS_KEY

    size = entry.size
    if size is None:
        return _NO_SIZE_KEY

    for band in SIZE_BANDS:
        if band.lower <= size and (band.upper is None or size < band.upper):
            return band.key

    return _NO_SIZE_KEY  # unreachable: the last band is open-ended


# -- flat listing ------------------------------------------------------------


class FlatGrouping(GroupingStrategy):
    """No grouping: the whole listing is one caption-less block."""

    kind = Grouping.NONE

    def groups(self, entries: Sequence[Entry], *, now: float) -> list[Group]:
        del now
        return [Group(list(entries))]


# -- registry ----------------------------------------------------------------

# The order is the panel's radio order and the coverage of ``Grouping``; a new
# strategy is one row here and one class above.
GROUPING_STRATEGIES: tuple[GroupingStrategy, ...] = (
    DateGrouping(),
    SizeGrouping(),
    FlatGrouping(),
)

GROUPING_ORDER: tuple[Grouping, ...] = tuple(
    strategy.kind for strategy in GROUPING_STRATEGIES
)

_STRATEGIES_BY_KIND: dict[Grouping, GroupingStrategy] = {
    strategy.kind: strategy for strategy in GROUPING_STRATEGIES
}


def strategy_for(kind: Grouping) -> GroupingStrategy:
    """The registered strategy for ``kind``; tests pin that every kind has one."""
    return _STRATEGIES_BY_KIND[kind]
