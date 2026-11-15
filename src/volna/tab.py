"""One directory tab: its own model, scanner and details view.

Tabs are independent so switching keeps that tab's listing and scroll position;
the window only shows the active tab and mirrors its status/counters.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib

from .controller import DirectoryController
from .core import DirModel, Entry, Event, ScanState
from .display import V1_CAPABILITIES, ViewCapabilities, ViewSettings
from .history import NavigationHistory
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
        on_navigate: Callable[[DirectoryTab], None],
        view_settings: ViewSettings | None = None,
        capabilities: ViewCapabilities = V1_CAPABILITIES,
    ) -> None:
        self.path = path
        self._history = NavigationHistory(path)
        self._capabilities = capabilities
        self._settings = (view_settings or ViewSettings()).normalized(capabilities)
        self.model = DirModel(
            sort_key=self._settings.sort_key,
            reverse=self._settings.reverse,
            folders_first=self._settings.folders_first,
            show_hidden=self._settings.show_hidden,
        )
        self._on_change = on_change
        self._on_navigate = on_navigate
        self._controller = DirectoryController(self.model, dispatch=GLib.idle_add)
        self._view = DetailsView(on_activate=self._on_row_activated)
        self.widget = self._view.widget
        self._loaded = False
        self._closed = False
        self._refresh_scheduled = False

        self.model.subscribe(Event.ITEM_BATCH, self._schedule_refresh)
        self.model.subscribe(Event.ORDER_CHANGED, self._schedule_refresh)
        self.model.subscribe(Event.SCAN_STATE, self._on_scan_state)
        self.model.subscribe(Event.COUNTERS_CHANGED, self._changed)
        self.model.subscribe(Event.ERROR, self._changed)

    @property
    def title(self) -> str:
        return tab_title(self.path)

    @property
    def icon_name(self) -> str:
        return tab_icon(self.path)

    @property
    def can_go_back(self) -> bool:
        return self._history.can_back

    @property
    def can_go_forward(self) -> bool:
        return self._history.can_forward

    @property
    def can_go_up(self) -> bool:
        return self._history.can_up

    @property
    def view_settings(self) -> ViewSettings:
        return self._settings

    def update_view_settings(self, **changes: object) -> bool:
        """Merge display changes into this tab and apply them in place.

        Returns ``False`` when the snapshot did not change. Never rescans:
        ordering and visibility are recomputed from the loaded entries.
        """
        settings = self._settings.merged(self._capabilities, **changes)
        if settings == self._settings:
            return False

        self._settings = settings
        self.model.set_folders_first(settings.folders_first)
        self.model.set_show_hidden(settings.show_hidden)
        self.model.set_order(sort_key=settings.sort_key, reverse=settings.reverse)
        self._schedule_refresh()
        return True

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

    def navigate(self, path: Path) -> bool:
        """Record ``path`` in the tab history and open it; False if unchanged."""
        if self._closed or path == self.path:
            return False
        self._history.visit(path)
        self._load(path)
        return True

    def go_back(self) -> bool:
        return self._go(self._history.back())

    def go_forward(self) -> bool:
        return self._go(self._history.forward())

    def go_up(self) -> bool:
        return self._go(self._history.up())

    def close(self) -> None:
        self._closed = True
        self._controller.close()

    def _go(self, target: Path | None) -> bool:
        """Open a history target; False when that direction is unavailable."""
        if self._closed or target is None:
            return False
        self._load(target)
        return True

    def _load(self, path: Path) -> None:
        self.path = path
        self.reload()
        self._view.reset_scroll()
        self._on_navigate(self)

    def _on_row_activated(self, row: Row) -> None:
        if self._closed or not row.is_dir:
            return
        path = Path(row.path)
        # A row from the previous listing must not navigate the new directory.
        if path.parent != self.path:
            return
        self.navigate(path)

    def _on_scan_state(self, state: ScanState, _generation: int) -> None:
        if self._closed:
            return
        if state is ScanState.SCANNING:
            self._view.render([])
        self._on_change(self)

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
            path=entry.path,
            size_text="—" if entry.is_dir else format_size(entry.size),
            date_text=format_date(entry.mtime),
            is_dir=entry.is_dir,
        )
