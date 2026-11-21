"""Grouping policy: split an ordered listing into captioned groups.

Grouping is a display policy over the loaded model (design/grouping.md V5):
the model keeps entries and their sort order, a strategy decides where the
captions go and what they say. Each strategy is a self-contained class with its
own bucket table, caption and ordering; the shared parent only runs the single
pass and preserves the model's order inside every bucket.

Buckets are data on the class that owns them: changing calendar rules or size
bands is a data edit inside one strategy, not a new branch elsewhere.
"""

from __future__ import annotations

import abc
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ..core import Entry


# The stored setting value, deliberately not a strategy object: this enum is
# the stable JSON/preset token and the closed set `ViewSettings.from_mapping`
# validates, while a strategy is behavior. Storing a strategy in ViewSettings
# would make the settings snapshot depend on policy-object equality; the
# registry below keeps the mapping explicit instead (same split as ViewMode).
class Grouping(StrEnum):
    """How a listing is split (the stored value and the panel radio group)."""

    DATE = "date"
    SIZE = "size"
    NONE = "none"


class GroupAction(StrEnum):
    """What a group header interaction asks the tab to do (design/grouping.md D13)."""

    TOGGLE = "toggle"
    COLLAPSE_OTHERS = "collapse-others"
    COLLAPSE_ALL = "collapse-all"
    EXPAND_ALL = "expand-all"


@dataclass(frozen=True, slots=True)
class Bucket:
    """One group's identity, caption and position, as a strategy decides it.

    ``key`` is stable for the session (the tab keys collapse state by it);
    ``header`` is the caption; ``order`` is where the bucket goes in the
    listing. ``None`` in both identity fields is the single block of an
    ungrouped listing.
    """

    key: str | None
    header: str | None
    order: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Group:
    """One non-empty block of a grouped listing: a bucket and its entries."""

    entries: list[Entry]
    bucket: Bucket

    @property
    def key(self) -> str | None:
        return self.bucket.key

    @property
    def header(self) -> str | None:
        return self.bucket.header


class GroupingStrategy(abc.ABC):
    """One way to split a listing into groups.

    A strategy is behavior, not the stored value: `Grouping` is the token in
    settings and presets, and `GROUPING_STRATEGIES` maps the two explicitly.
    A subclass builds an entry → bucket resolver for the pass; the base runs
    the linear pass and returns the buckets in their declared order, preserving
    the model's order inside each (design/grouping.md D3).
    """

    label: ClassVar[str]

    @abc.abstractmethod
    def bucket_resolver(self, *, now: float) -> Callable[[Entry], Bucket]:
        """Build the entry → bucket mapping for one grouping pass."""

    def groups(self, entries: Sequence[Entry], *, now: float) -> list[Group]:
        bucket_for = self.bucket_resolver(now=now)
        found: dict[str | None, tuple[Bucket, list[Entry]]] = {}
        for entry in entries:
            bucket = bucket_for(entry)
            pair = found.get(bucket.key)
            if pair is None:
                found[bucket.key] = (bucket, [entry])
                continue
            pair[1].append(entry)

        return [
            Group(items, bucket)
            for bucket, items in sorted(found.values(), key=lambda pair: pair[0].order)
        ]


class DateGrouping(GroupingStrategy):
    """Modification time: today, yesterday, a day per group inside the last
    seven days, the older rest, and entries without a date last.

    The week is split per local calendar day because the design labels those
    groups with weekday names (design/grouping.md D2). Sorting stays global:
    bucketing preserves the loaded order, so the current sort key and
    ``folders_first`` apply inside every group without a second sort (D3).
    """

    label = "По дате изменения"

    _DAY = 86_400.0
    _TODAY = Bucket("today", "Сегодня", (0.0,))
    _YESTERDAY = Bucket("yesterday", "Вчера", (1.0,))
    _OLDER = Bucket("older", "Неделю назад", (3.0,))
    _UNKNOWN = Bucket("unknown", "Без даты", (4.0,))

    # Calendar weekday names; index matches ``time.localtime(...).tm_wday``.
    _WEEKDAYS: ClassVar[tuple[str, ...]] = (
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    )

    def bucket_resolver(self, *, now: float) -> Callable[[Entry], Bucket]:
        today = self._local_midnight(now)

        def bucket_for(entry: Entry) -> Bucket:
            mtime = entry.mtime
            if mtime is None:
                return self._UNKNOWN

            if mtime >= today:
                return self._TODAY
            if mtime >= today - self._DAY:
                return self._YESTERDAY
            if mtime < today - 7 * self._DAY:
                return self._OLDER

            day = self._local_midnight(mtime)
            local = time.localtime(day)
            return Bucket(
                key=f"week:{time.strftime('%Y-%m-%d', local)}",
                header=self._WEEKDAYS[local.tm_wday],
                order=(2.0, -day),
            )

        return bucket_for

    @staticmethod
    def _local_midnight(timestamp: float) -> float:
        local = time.localtime(timestamp)
        return time.mktime(
            (local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1)
        )


class SizeGrouping(GroupingStrategy):
    """Reported byte size; folders have their own leading group.

    A folder's ``st_size`` is the directory inode, not the size of its
    contents, so it would be misleading in a size band: folders are always one
    «Папки» group at the top. Entries whose stat failed have no size and go to
    «Без размера» at the bottom.
    """

    label = "По размеру"

    @dataclass(frozen=True, slots=True)
    class Band(Bucket):
        """A half-open byte range ``[lower, upper)`` and its group position."""

        lower: int
        upper: int | None

        def holds(self, size: int) -> bool:
            return self.lower <= size and (self.upper is None or size < self.upper)

    # Geometric, tenfold bands: each range is the previous one ×10, from an
    # empty file up to anything above a gibibyte. Bytes are the scanner's
    # ``st_size``, the same number the Size column shows.
    BANDS: ClassVar[tuple[Band, ...]] = (
        Band("size:empty", "0 Б", (1.0,), 0, 1),
        Band("size:tiny", "до 10 КиБ", (2.0,), 1, 10 * 1024),
        Band("size:small", "10–100 КиБ", (3.0,), 10 * 1024, 100 * 1024),
        Band("size:medium", "100 КиБ–1 МиБ", (4.0,), 100 * 1024, 1024 * 1024),
        Band("size:large", "1–10 МиБ", (5.0,), 1024 * 1024, 10 * 1024 * 1024),
        Band("size:huge", "10–100 МиБ", (6.0,), 10 * 1024 * 1024, 100 * 1024 * 1024),
        Band(
            "size:giant",
            "100 МиБ–1 ГиБ",
            (7.0,),
            100 * 1024 * 1024,
            1024 * 1024 * 1024,
        ),
        Band("size:colossal", "больше 1 ГиБ", (8.0,), 1024 * 1024 * 1024, None),
    )

    _FOLDERS = Bucket("size:folders", "Папки", (0.0,))
    _NO_SIZE = Bucket("size:unknown", "Без размера", (float(len(BANDS) + 1),))

    def bucket_resolver(self, *, now: float) -> Callable[[Entry], Bucket]:
        return self._bucket_for

    def _bucket_for(self, entry: Entry) -> Bucket:
        if entry.is_dir:
            return self._FOLDERS

        size = entry.size
        if size is None:
            return self._NO_SIZE

        for band in self.BANDS:
            if band.holds(size):
                return band

        return self._NO_SIZE  # unreachable: the last band is open-ended


class FlatGrouping(GroupingStrategy):
    """No grouping: the whole listing is one caption-less block."""

    label = "Без группировки"

    _ONE = Bucket(None, None, ())

    def bucket_resolver(self, *, now: float) -> Callable[[Entry], Bucket]:
        return self._bucket_for

    def _bucket_for(self, entry: Entry) -> Bucket:
        return self._ONE


# Explicit (kind, strategy) pairs: the registry is the single place that
# associates a stored value with a policy and fixes the panel order. A new
# criterion is one row here and one class above; the strategy itself carries
# only its label and buckets, not a copy of its registry key.
GROUPING_STRATEGIES: tuple[tuple[Grouping, GroupingStrategy], ...] = (
    (Grouping.DATE, DateGrouping()),
    (Grouping.SIZE, SizeGrouping()),
    (Grouping.NONE, FlatGrouping()),
)

_STRATEGIES_BY_KIND: dict[Grouping, GroupingStrategy] = dict(GROUPING_STRATEGIES)


def strategy_for(kind: Grouping) -> GroupingStrategy:
    """The registered strategy for ``kind``; tests pin that every kind has one."""
    return _STRATEGIES_BY_KIND[kind]
