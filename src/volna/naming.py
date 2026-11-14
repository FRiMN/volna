"""Display names and icons for directory tabs and listing rows.

Pure path/kind → presentation policy, no GTK: tests cover it without a display
and the views only wire the results into widgets.
"""

from __future__ import annotations

from pathlib import Path

_HOME_TITLE = "Домашняя папка"
_DOWNLOAD_NAMES = ("Загрузки", "Downloads")

_FOLDER_GLYPH = "folder-filled"
_FILE_GLYPH = "file"


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


def content_icon(is_dir: bool) -> str:
    """Glyph for a listing row: the blue folder or the neutral document.

    Only the listing rows use the saturated folder: the design keeps it the one
    coloured glyph of the interface, files differ by shape (see design spec §6).
    """
    return _FOLDER_GLYPH if is_dir else _FILE_GLYPH


def content_icon_label(is_dir: bool) -> str:
    """Accessible name for the row glyph (the table has no «Тип» column yet)."""
    return "Папка" if is_dir else "Файл"
