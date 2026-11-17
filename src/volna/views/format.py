"""Display formatting for listing rows — pure functions, no GTK."""

from __future__ import annotations

import time

from ..core import Counters

_UNITS = ("Б", "КиБ", "МиБ", "ГиБ", "ТиБ")
_EMPTY = "—"


def format_size(size: int | None) -> str:
    if size is None:
        return _EMPTY

    value = float(size)
    for unit in _UNITS:
        if value < 1024 or unit == _UNITS[-1]:
            if unit == "Б":
                return f"{int(value)} Б"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024

    return f"{size} Б"


def format_counters(counters: Counters) -> str:
    """The listing summary: the editor header and every group caption share it."""
    return (
        f"{counters.folders} папок · {counters.files} файлов "
        f"({format_size(counters.total_size)})"
    )


def format_date(mtime: float | None) -> str:
    if mtime is None:
        return _EMPTY
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(mtime))
