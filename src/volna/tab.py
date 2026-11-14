"""One directory tab: its own model, scanner and details view.

Tabs are independent so switching keeps that tab's listing and scroll position;
the window only shows the active tab and mirrors its status/counters.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib

from .controller import DirectoryController
from .core import DirModel, Entry, Event
from .naming import tab_icon, tab_title
from .views.details import DetailsView, Row
from .views.format import format_date, format_size


class DirectoryTab:
    """Owns one listing: ``model`` + controller + view + scroll."""

    def __init__(
        self,
        path: Path,
        *,
        on_change: Callable[[DirectoryTab], None],
    ) -> None:
        self.path = path
        self.model = DirModel()
        self._on_change = on_change
        self._controller = DirectoryController(self.model, dispatch=GLib.idle_add)
        self._view = DetailsView()
        self.widget = self._view.widget
        self._loaded = False
        self._closed = False
        self._refresh_scheduled = False

        self.model.subscribe(Event.ITEM_BATCH, self._schedule_refresh)
        self.model.subscribe(Event.ORDER_CHANGED, self._schedule_refresh)
        self.model.subscribe(Event.SCAN_STATE, self._changed)
        self.model.subscribe(Event.COUNTERS_CHANGED, self._changed)
        self.model.subscribe(Event.ERROR, self._changed)

    @property
    def title(self) -> str:
        return tab_title(self.path)

    @property
    def icon_name(self) -> str:
        return tab_icon(self.path)

    def ensure_loaded(self) -> None:
        if self._closed or self._loaded:
            return
        self._loaded = True
        self._controller.open(str(self.path))

    def reload(self) -> None:
        if self._closed:
            return
        self._loaded = True
        self._controller.open(str(self.path))

    def navigate(self, path: Path) -> None:
        if self._closed or path == self.path:
            return
        self.path = path
        self.reload()
        self._view.reset_scroll()

    def close(self) -> None:
        self._closed = True
        self._controller.close()

    def _changed(self, *_args: object) -> None:
        if self._closed:
            return
        self._on_change(self)

    def _schedule_refresh(self, *_args: object) -> None:
        if self._closed or self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        GLib.idle_add(self._refresh)

    def _refresh(self) -> bool:
        self._refresh_scheduled = False
        if self._closed:
            return False
        self._view.render([self._row(entry) for entry in self.model.entries()])
        return False

    @staticmethod
    def _row(entry: Entry) -> Row:
        return Row(
            name=entry.name,
            size_text="—" if entry.is_dir else format_size(entry.size),
            date_text=format_date(entry.mtime),
            is_dir=entry.is_dir,
        )
