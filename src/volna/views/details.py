"""«Подробности» — a three-column table over the ordered listing."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk, Pango  # noqa: E402

from ..glyph import icon_path  # noqa: E402
from ..naming import content_icon, content_icon_label  # noqa: E402
from ..size import px  # noqa: E402


class Row(GObject.Object):
    """One listing row, bound by the column factories."""

    __gtype_name__ = "VolnaRow"

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


class _NameCell(Gtk.Box):
    """The name column cell: a type glyph followed by an ellipsized label."""

    __gtype_name__ = "VolnaNameCell"

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        self.set_hexpand(True)

        self.picture = Gtk.Image()
        self.picture.set_pixel_size(px(16))
        self.picture.set_halign(Gtk.Align.CENTER)
        self.picture.set_valign(Gtk.Align.CENTER)
        self.picture.add_css_class("volna-dt-icon")

        self.text = Gtk.Label(xalign=0)
        self.text.set_ellipsize(Pango.EllipsizeMode.END)
        self.text.set_hexpand(True)
        self.text.set_valign(Gtk.Align.CENTER)
        self.text.add_css_class("volna-dt-name")

        self.append(self.picture)
        self.append(self.text)


class DetailsView:
    """A three-column table; ``render`` replaces the visible rows."""

    def __init__(self, on_activate: Callable[[Row], None] | None = None) -> None:
        self._on_activate = on_activate
        self.store = Gio.ListStore.new(Row)
        selection = Gtk.NoSelection(model=self.store)
        self._column_view = Gtk.ColumnView(model=selection)
        self._column_view.set_show_column_separators(True)
        self._column_view.set_show_row_separators(False)
        self._column_view.connect("activate", self._activate_row)

        self._add_name_column("Имя")
        self._add_numeric_column("Размер", lambda row: row.size_text, width=px(96))
        self._add_numeric_column("Дата", lambda row: row.date_text, width=px(168))

        self.widget = Gtk.ScrolledWindow(vexpand=True)
        self.widget.set_child(self._column_view)

    def _add_name_column(self, title: str) -> None:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_name)
        factory.connect("bind", _bind_name)
        column = Gtk.ColumnViewColumn.new(title, factory)
        column.set_expand(True)
        self._column_view.append_column(column)

    def _add_numeric_column(
        self,
        title: str,
        getter: Callable[[Row], str],
        *,
        width: int,
    ) -> None:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_numeric)
        factory.connect("bind", _bind_text, getter)
        column = Gtk.ColumnViewColumn.new(title, factory)
        # Fixed widths from the design table: the automatic measure would clip
        # the date column as soon as the UI font grows.
        column.set_fixed_width(width)
        self._column_view.append_column(column)

    def render(self, rows: list[Row]) -> None:
        self.store.splice(0, self.store.get_n_items(), rows)

    def _activate_row(self, _view: Gtk.ColumnView, position: int) -> None:
        if self._on_activate is None:
            return
        row = self.store.get_item(position)
        if row is not None:
            self._on_activate(row)

    def reset_scroll(self) -> None:
        adjustment = self.widget.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)


def _setup_name(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    item.set_child(_NameCell())


def _bind_name(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    row: Row = item.get_item()
    cell = item.get_child()
    cell.picture.set_from_file(str(icon_path(row.icon_name, px(16))))
    # The icon is the only type cue in the table, so give it a name for AT.
    cell.picture.update_property(
        [Gtk.AccessibleProperty.LABEL], [content_icon_label(row.is_dir)]
    )
    cell.text.set_text(row.name)


def _setup_numeric(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    widget = Gtk.Label(xalign=1)
    widget.set_ellipsize(Pango.EllipsizeMode.END)
    widget.add_css_class("volna-dt-num")
    item.set_child(widget)


def _bind_text(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
    getter: Callable[[Row], str],
) -> None:
    item.get_child().set_text(getter(item.get_item()))
