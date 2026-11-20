"""Pure tests for the grouping strategies (design/grouping.md V5).

A strategy is policy over an already ordered and filtered entry list: these
tests pass plain ``Entry`` lists and pin captions, keys, group order and the
one property every strategy must keep — item order inside a group is the order
the model produced.
"""

from __future__ import annotations

import time

import pytest

from volna.core import Entry, Kind
from volna.display.grouping import (
    BUCKET_ORDER,
    GROUPING_ORDER,
    GROUPING_STRATEGIES,
    SIZE_BANDS,
    DateGrouping,
    FlatGrouping,
    GroupBucket,
    Grouping,
    SizeGrouping,
    day_start,
    group_of,
    strategy_for,
)

_WEEKDAYS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_NOW = 1_700_000_000.0
_TODAY = day_start(_NOW)
_DAY = 86_400.0
_KIB = 1024
_MIB = 1024 * 1024
_GIB = 1024 * 1024 * 1024


def make(
    name: str,
    *,
    kind: Kind = Kind.FILE,
    size: int | None = None,
    mtime: float | None = None,
) -> Entry:
    return Entry(name, f"/d/{name}", kind, size=size, mtime=mtime)


def local_day(year: int, month: int, day: int) -> float:
    return time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))


def week_key(timestamp: float) -> str:
    return f"week:{time.strftime('%Y-%m-%d', time.localtime(timestamp))}"


def weekday(timestamp: float) -> str:
    return _WEEKDAYS[time.localtime(timestamp).tm_wday]


# -- registry -----------------------------------------------------------------


def test_the_registry_covers_every_grouping_and_is_the_panel_order() -> None:
    kinds = [strategy.kind for strategy in GROUPING_STRATEGIES]

    assert kinds == [Grouping.DATE, Grouping.SIZE, Grouping.NONE]
    assert GROUPING_ORDER == (Grouping.DATE, Grouping.SIZE, Grouping.NONE)
    assert set(kinds) == set(Grouping)
    assert strategy_for(Grouping.DATE).__class__ is DateGrouping
    assert strategy_for(Grouping.SIZE).__class__ is SizeGrouping
    assert strategy_for(Grouping.NONE).__class__ is FlatGrouping


@pytest.mark.parametrize(
    ("grouping", "expected"),
    [
        (Grouping.DATE, "По дате изменения"),
        (Grouping.SIZE, "По размеру"),
        (Grouping.NONE, "Без группировки"),
    ],
)
def test_grouping_has_a_panel_label(grouping: Grouping, expected: str) -> None:
    assert grouping.label == expected


# -- date grouping ------------------------------------------------------------


@pytest.mark.parametrize(
    ("mtime", "expected"),
    [
        (None, GroupBucket.UNKNOWN),
        (_TODAY + 10, GroupBucket.TODAY),
        (_TODAY - 10, GroupBucket.YESTERDAY),
        (_TODAY - 2 * _DAY, GroupBucket.THIS_WEEK),
        (_TODAY - 8 * _DAY, GroupBucket.OLDER),
    ],
)
def test_group_of_buckets_by_local_calendar_days(
    mtime: float | None, expected: GroupBucket
) -> None:
    assert group_of(mtime, now=_NOW) is expected


def test_date_groups_are_ordered_oldest_bucket_last_and_days_newest_first() -> None:
    two_days = day_start(_TODAY - 2 * _DAY)
    three_days = day_start(_TODAY - 3 * _DAY)
    entries = [
        make("today", mtime=_TODAY + 10),
        make("yesterday", mtime=_TODAY - 10),
        make("two-days", mtime=two_days + 60),
        make("three-days", mtime=three_days + 60),
        make("old", mtime=_TODAY - 8 * _DAY),
        make("unknown"),
    ]

    groups = DateGrouping().groups(entries, now=_NOW)

    assert [group.key for group in groups] == [
        "today",
        "yesterday",
        week_key(two_days),
        week_key(three_days),
        "older",
        "unknown",
    ]
    assert [group.header for group in groups] == [
        "Сегодня",
        "Вчера",
        weekday(two_days),
        weekday(three_days),
        "Неделю назад",
        "Без даты",
    ]
    assert [[entry.name for entry in group.entries] for group in groups] == [
        ["today"],
        ["yesterday"],
        ["two-days"],
        ["three-days"],
        ["old"],
        ["unknown"],
    ]


def test_date_group_keys_are_stable_and_week_keys_name_the_day() -> None:
    now = time.mktime((2026, 11, 14, 12, 0, 0, 0, 0, -1))
    day = local_day(2026, 11, 11)
    entries = [make("a", mtime=day + 60)]

    first = DateGrouping().groups(entries, now=now)
    second = DateGrouping().groups(entries, now=now + 60)

    assert first[0].key == "week:2026-11-11"
    assert first[0].key == second[0].key
    assert first[0].header == "Среда"


def test_date_group_order_inside_a_bucket_is_the_model_order() -> None:
    entries = [
        make("b", mtime=day_start(_TODAY - 2 * _DAY) + 120),
        make("a", mtime=day_start(_TODAY - 2 * _DAY) + 60),
        make("c", mtime=day_start(_TODAY - 3 * _DAY) + 60),
    ]

    groups = DateGrouping().groups(entries, now=_NOW)

    assert [[entry.name for entry in group.entries] for group in groups] == [
        ["b", "a"],
        ["c"],
    ]


def test_date_grouping_of_an_empty_listing_has_no_groups() -> None:
    assert DateGrouping().groups([], now=_NOW) == []


def test_bucket_order_lists_every_bucket_once() -> None:
    assert list(BUCKET_ORDER) == list(GroupBucket)
    assert len(set(BUCKET_ORDER)) == len(BUCKET_ORDER)


# -- size grouping ------------------------------------------------------------


def test_size_bands_are_a_contiguous_ascending_table() -> None:
    assert SIZE_BANDS
    assert SIZE_BANDS[0].lower == 0
    assert SIZE_BANDS[-1].upper is None

    for previous, band in zip(SIZE_BANDS, SIZE_BANDS[1:], strict=False):
        assert band.lower == previous.upper

    headers = [band.header for band in SIZE_BANDS]
    assert len(headers) == len(set(headers))


@pytest.mark.parametrize(
    ("size", "key"),
    [
        (0, "empty"),
        (1, "tiny"),
        (10 * _KIB - 1, "tiny"),
        (10 * _KIB, "small"),
        (100 * _KIB - 1, "small"),
        (100 * _KIB, "medium"),
        (_MIB - 1, "medium"),
        (_MIB, "large"),
        (10 * _MIB - 1, "large"),
        (10 * _MIB, "huge"),
        (100 * _MIB - 1, "huge"),
        (100 * _MIB, "giant"),
        (_GIB - 1, "giant"),
        (_GIB, "colossal"),
        (10 * _GIB, "colossal"),
    ],
)
def test_a_file_falls_into_the_band_its_size_belongs_to(size: int, key: str) -> None:
    groups = SizeGrouping().groups([make("file", size=size)], now=_NOW)

    assert [group.key for group in groups] == [f"size:{key}"]


def test_size_groups_run_from_folders_to_the_largest_file_then_no_size() -> None:
    entries = [
        make("huge", size=10 * _MIB),
        make("folder", kind=Kind.DIR, size=4096),
        make("empty", size=0),
        make("tiny", size=5),
        make("unknown", size=None),
    ]

    groups = SizeGrouping().groups(entries, now=_NOW)

    assert [group.header for group in groups] == [
        "Папки",
        "0 Б",
        "до 10 КиБ",
        "10–100 МиБ",
        "Без размера",
    ]
    assert [group.key for group in groups] == [
        "size:folders",
        "size:empty",
        "size:tiny",
        "size:huge",
        "size:unknown",
    ]
    assert [entry.name for group in groups for entry in group.entries] == [
        "folder",
        "empty",
        "tiny",
        "huge",
        "unknown",
    ]


def test_a_folder_never_lands_in_a_size_band() -> None:
    folder = make("folder", kind=Kind.DIR, size=5)

    groups = SizeGrouping().groups([folder], now=_NOW)

    assert [group.key for group in groups] == ["size:folders"]


def test_size_group_order_inside_a_band_is_the_model_order() -> None:
    entries = [
        make("b", size=2),
        make("a", size=1),
    ]

    groups = SizeGrouping().groups(entries, now=_NOW)

    assert [group.key for group in groups] == ["size:tiny"]
    assert [entry.name for entry in groups[0].entries] == ["b", "a"]


def test_size_grouping_of_an_empty_listing_has_no_groups() -> None:
    assert SizeGrouping().groups([], now=_NOW) == []


# -- flat listing -------------------------------------------------------------


def test_the_ungrouped_strategy_returns_one_captionless_block() -> None:
    entries = [make("a", size=1), make("b", size=2)]

    groups = FlatGrouping().groups(entries, now=_NOW)

    assert len(groups) == 1
    assert groups[0].key is None
    assert groups[0].header is None
    assert [entry.name for entry in groups[0].entries] == ["a", "b"]


def test_the_ungrouped_strategy_returns_an_empty_block_for_an_empty_listing() -> None:
    groups = FlatGrouping().groups([], now=_NOW)

    assert len(groups) == 1
    assert groups[0].entries == []
