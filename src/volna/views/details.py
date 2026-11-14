"""«Подробности» — a three-column table over the ordered listing."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk, Pango  # noqa: E402


class Row(GObject.Object):
    """One listing row, bound by the column factories."""

    __gtype_name__ = "VolnaRow"

    def __init__(self, name: str, size_text: str, date_text: str, is_dir: bool) -> None:
        super().__init__()
        self.name = name
        self.size_text = size_text
        self.date_text = date_text
        self.is_dir = is_dir


class DetailsView:
    """A three-column table; ``render`` replaces the visible rows."""

    def __init__(self) -> None:
        self.store = Gio.ListStore.new(Row)
        selection = Gtk.NoSelection(model=self.store)
        self._column_view = Gtk.ColumnView(model=selection)
        self._column_view.set_show_column_separators(True)
        self._column_view.set_show_row_separators(False)

        self._add_column("Имя", lambda row: row.name, expand=True)
        self._add_column("Размер", lambda row: row.size_text, width=96, numeric=True)
        self._add_column("Дата", lambda row: row.date_text, width=168, numeric=True)

        self.widget = Gtk.ScrolledWindow(vexpand=True)
        self.widget.set_child(self._column_view)

    def _add_column(
        self,
        title: str,
        getter: Callable[[Row], str],
        *,
        expand: bool = False,
        width: int | None = None,
        numeric: bool = False,
    ) -> None:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_label, numeric)
        factory.connect("bind", _bind_label, getter)
        column = Gtk.ColumnViewColumn.new(title, factory)
        column.set_expand(expand)
        if width is not None:
            # Fixed widths from the design table: the automatic measure would
            # clip the date column as soon as the UI font grows.
            column.set_fixed_width(width)
        self._column_view.append_column(column)

    def render(self, rows: list[Row]) -> None:
        self.store.splice(0, self.store.get_n_items(), rows)


def _setup_label(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
    numeric: bool,
) -> None:
    widget = Gtk.Label(xalign=1 if numeric else 0)
    widget.set_ellipsize(Pango.EllipsizeMode.END)
    widget.add_css_class("volna-dt-num" if numeric else "volna-dt-name")
    item.set_child(widget)


def _bind_label(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
    getter: Callable[[Row], str],
) -> None:
    item.get_child().set_text(getter(item.get_item()))
