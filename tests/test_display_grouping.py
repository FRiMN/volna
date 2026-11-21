"""Pure tests for the grouping strategies (design/grouping.md V5).

A strategy is policy over an already ordered and filtered entry list: these
tests pass plain ``Entry`` lists and pin captions, keys, group order, bucket
boundaries and the one property the base class must keep — item order inside a
group is the order the model produced.
"""

from __future__ import annotations

import time

import pytest

from volna.core import Entry, Kind
from volna.display.grouping import (
    GROUPING_STRATEGIES,
    DateGrouping,
    FlatGrouping,
    Grouping,
    SizeGrouping,
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


def local_midnight(timestamp: float) -> float:
    local = time.localtime(timestamp)
    return time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))


def week_key(timestamp: float) -> str:
    return f"week:{time.strftime('%Y-%m-%d', time.localtime(timestamp))}"


def weekday(timestamp: float) -> str:
    return _WEEKDAYS[time.localtime(timestamp).tm_wday]


_TODAY = local_midnight(_NOW)


# -- registry -----------------------------------------------------------------


def test_the_registry_covers_every_grouping_and_is_the_panel_order() -> None:
    kinds = [kind for kind, _strategy in GROUPING_STRATEGIES]

    assert kinds == [Grouping.DATE, Grouping.SIZE, Grouping.NONE]
    assert set(kinds) == set(Grouping)
    assert [strategy.label for _kind, strategy in GROUPING_STRATEGIES] == [
        "По дате изменения",
        "По размеру",
        "Без группировки",
    ]
    assert strategy_for(Grouping.DATE).__class__ is DateGrouping
    assert strategy_for(Grouping.SIZE).__class__ is SizeGrouping
    assert strategy_for(Grouping.NONE).__class__ is FlatGrouping


# -- date grouping ------------------------------------------------------------


@pytest.mark.parametrize(
    ("mtime", "expected"),
    [
        (_TODAY + 10, "today"),
        (_TODAY, "today"),
        (_TODAY - 10, "yesterday"),
        (_TODAY - _DAY, "yesterday"),
        (_TODAY - 2 * _DAY, week_key(_TODAY - 2 * _DAY)),
        (_TODAY - 7 * _DAY + 1, week_key(_TODAY - 7 * _DAY + 1)),
        (_TODAY - 7 * _DAY - 1, "older"),
        (None, "unknown"),
    ],
)
def test_a_date_falls_into_the_bucket_of_its_local_calendar_day(
    mtime: float | None, expected: str
) -> None:
    groups = DateGrouping().groups([make("x", mtime=mtime)], now=_NOW)

    assert [group.key for group in groups] == [expected]


def test_date_groups_are_ordered_oldest_bucket_last_and_days_newest_first() -> None:
    two_days = local_midnight(_TODAY - 2 * _DAY)
    three_days = local_midnight(_TODAY - 3 * _DAY)
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
    day = time.mktime((2026, 11, 11, 0, 0, 0, 0, 0, -1))
    entries = [make("a", mtime=day + 60)]

    first = DateGrouping().groups(entries, now=now)
    second = DateGrouping().groups(entries, now=now + 60)

    assert first[0].key == "week:2026-11-11"
    assert first[0].key == second[0].key
    assert first[0].header == "Среда"


def test_date_group_order_inside_a_bucket_is_the_model_order() -> None:
    entries = [
        make("b", mtime=local_midnight(_TODAY - 2 * _DAY) + 120),
        make("a", mtime=local_midnight(_TODAY - 2 * _DAY) + 60),
        make("c", mtime=local_midnight(_TODAY - 3 * _DAY) + 60),
    ]

    groups = DateGrouping().groups(entries, now=_NOW)

    assert [[entry.name for entry in group.entries] for group in groups] == [
        ["b", "a"],
        ["c"],
    ]


def test_date_grouping_of_an_empty_listing_has_no_groups() -> None:
    assert DateGrouping().groups([], now=_NOW) == []


# -- size grouping ------------------------------------------------------------


def test_size_bands_are_a_contiguous_ascending_table() -> None:
    bands = SizeGrouping.BANDS

    assert bands
    assert bands[0].lower == 0
    assert bands[-1].upper is None

    for previous, band in zip(bands, bands[1:], strict=False):
        assert band.lower == previous.upper

    headers = [band.header for band in bands]
    assert len(headers) == len(set(headers))
    assert [band.order for band in bands] == sorted(band.order for band in bands)


@pytest.mark.parametrize(
    ("size", "key"),
    [
        (0, "size:empty"),
        (1, "size:tiny"),
        (10 * _KIB - 1, "size:tiny"),
        (10 * _KIB, "size:small"),
        (100 * _KIB - 1, "size:small"),
        (100 * _KIB, "size:medium"),
        (_MIB - 1, "size:medium"),
        (_MIB, "size:large"),
        (10 * _MIB - 1, "size:large"),
        (10 * _MIB, "size:huge"),
        (100 * _MIB - 1, "size:huge"),
        (100 * _MIB, "size:giant"),
        (_GIB - 1, "size:giant"),
        (_GIB, "size:colossal"),
        (10 * _GIB, "size:colossal"),
    ],
)
def test_a_file_falls_into_the_band_its_size_belongs_to(size: int, key: str) -> None:
    groups = SizeGrouping().groups([make("file", size=size)], now=_NOW)

    assert [group.key for group in groups] == [key]


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


def test_the_ungrouped_strategy_has_no_groups_for_an_empty_listing() -> None:
    assert FlatGrouping().groups([], now=_NOW) == []
