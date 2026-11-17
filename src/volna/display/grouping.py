"""Date-group captions for the UI: pure label mapping, no GTK imports.

The calendar arithmetic (which bucket an entry belongs to, which day a
``THIS_WEEK`` group covers) stays in ``core``; this module only turns a
:class:`core.Group` into the Russian caption shown in the listing. Labels are
data, not logic (the same split as ``ViewMode.label`` in ``display.settings``):
see design/grouping.md D1–D2.
"""

from __future__ import annotations

import time
from enum import StrEnum

from ..core import Group, GroupBucket

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
_BUCKET_LABELS: dict[GroupBucket, str] = {
    GroupBucket.TODAY: "Сегодня",
    GroupBucket.YESTERDAY: "Вчера",
    GroupBucket.THIS_WEEK: "На этой неделе",
    GroupBucket.OLDER: "Неделю назад",
    GroupBucket.UNKNOWN: "Без даты",
}


def group_label(group: Group) -> str:
    """Caption for one date group: «Сегодня», «Среда», «Неделю назад», …"""
    if group.bucket is GroupBucket.THIS_WEEK and group.day is not None:
        return _WEEKDAYS[time.localtime(group.day).tm_wday]

    return _BUCKET_LABELS[group.bucket]


class GroupAction(StrEnum):
    """What a group header interaction asks the tab to do (design/grouping.md D13)."""

    TOGGLE = "toggle"
    COLLAPSE_OTHERS = "collapse-others"
    COLLAPSE_ALL = "collapse-all"
    EXPAND_ALL = "expand-all"


def group_key(group: Group) -> str:
    """Stable identity of a date group within a session (design/grouping.md D12).

    Weekday groups key by their local date, so a collapsed «Среда» stays
    collapsed while the session runs; the coarse buckets key by themselves.
    """
    if group.bucket is GroupBucket.THIS_WEEK and group.day is not None:
        return f"week:{time.strftime('%Y-%m-%d', time.localtime(group.day))}"

    return group.bucket.value
