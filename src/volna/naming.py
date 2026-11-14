"""Display names and icons for directory-tab locations.

Pure path → presentation policy, no GTK: tests cover it without a display and
the window only wires the results into widgets.
"""

from __future__ import annotations

from pathlib import Path

_HOME_TITLE = "Домашняя папка"
_DOWNLOAD_NAMES = ("Загрузки", "Downloads")


def tab_title(path: Path) -> str:
    """Tab label for a directory: friendly for known locations, basename otherwise."""
    if path == Path.home():
        return _HOME_TITLE
    if path == Path("/"):
        return "/"
    return path.name or str(path)


def tab_icon(path: Path) -> str:
    """Icon name (from ``volna/icons``) representing the directory."""
    if path == Path.home():
        return "home"
    if path.parent == Path.home() and path.name in _DOWNLOAD_NAMES:
        return "down"
    return "folder"
