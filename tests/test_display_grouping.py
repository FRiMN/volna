"""Pure tests for the date-group captions (design/grouping.md D1–D2)."""

from __future__ import annotations

import time

import pytest

from volna.core import Group, GroupBucket
from volna.display import group_label


def group(bucket: GroupBucket, day: float | None = None) -> Group:
    return Group(bucket, [], day)


def local_day(year: int, month: int, day: int) -> float:
    return time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))


@pytest.mark.parametrize(
    ("bucket", "expected"),
    [
        (GroupBucket.TODAY, "Сегодня"),
        (GroupBucket.YESTERDAY, "Вчера"),
        (GroupBucket.OLDER, "Неделю назад"),
        (GroupBucket.UNKNOWN, "Без даты"),
    ],
)
def test_coarse_buckets_have_design_captions(
    bucket: GroupBucket, expected: str
) -> None:
    assert group_label(group(bucket)) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (local_day(2026, 11, 13), "Пятница"),
        (local_day(2026, 11, 11), "Среда"),
        (local_day(2026, 11, 10), "Вторник"),
        (local_day(2026, 11, 9), "Понедельник"),
        (local_day(2026, 11, 15), "Воскресенье"),
    ],
)
def test_this_week_groups_are_named_after_their_weekday(
    day: float, expected: str
) -> None:
    assert group_label(group(GroupBucket.THIS_WEEK, day)) == expected


def test_this_week_group_without_a_day_keeps_a_caption() -> None:
    assert group_label(group(GroupBucket.THIS_WEEK)) == "На этой неделе"
