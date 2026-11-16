"""One listing item, shared by every view mode.

Pure presentation data derived from ``core.Entry`` by the tab: the views never
import ``core`` (see design/view-modes.md §3). A GObject because the mode
stores are typed ``Gio.ListStore`` instances.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject  # noqa: E402

from ..naming import content_icon, content_icon_label  # noqa: E402


class ListingItem(GObject.Object):
    """One entry as the views render it: name, path and formatted values."""

    __gtype_name__ = "VolnaListingItem"

    def __init__(
        self,
        name: str,
        path: str,
        size_text: str,
        date_text: str,
        is_dir: bool,
    ) -> None:
        super().__init__()
        self.name = name
        self.path = path
        self.size_text = size_text
        self.date_text = date_text
        self.is_dir = is_dir

    @property
    def icon_name(self) -> str:
        return content_icon(self.is_dir)

    @property
    def icon_label(self) -> str:
        return content_icon_label(self.is_dir)
