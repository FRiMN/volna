"""«Подробности» — a three-column table over the ordered listing."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk, Pango  # noqa: E402

from ..display import ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .group_header import count_label, title_label  # noqa: E402
from .item import ListingItem  # noqa: E402

# One cell of a group strip; every column cell carries it so the 28 px row
# reads as a single full-width band (theme.css, design/grouping.md D9).
_GROUP_CELL = "volna-dt-group"


class GroupRow(GObject.Object):
    """A date group caption in the row store (design/grouping.md D5).

    Group rows share the heterogeneous model with :class:`ListingItem` rows:
    one ColumnView keeps its sticky column header and shared column widths.
    ``count`` is the number of items rendered under the caption.
    """

    __gtype_name__ = "VolnaGroupRow"

    def __init__(self, label: str, count: int) -> None:
        super().__init__()
        self.label = label
        self.count = count


class _NameCell(Gtk.Box):
    """The name column cell: an entry row or a full-width group strip.

    The column view recycles cells between row kinds, so the cell keeps both
    layouts and ``bind`` shows one of them. The hidden branch is cleared too:
    a recycled cell must never expose a stale name (tests, accessibility).
    """

    __gtype_name__ = "VolnaNameCell"

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_hexpand(True)

        self._entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        self._entry.set_hexpand(True)

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

        self._entry.append(self.picture)
        self._entry.append(self.text)

        self._group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        self._group.add_css_class("volna-dt-group-content")
        self._group.set_halign(Gtk.Align.START)
        self._group.set_valign(Gtk.Align.CENTER)

        self._title = title_label("")
        self._count = count_label(0)

        self._group.append(self._title)
        self._group.append(self._count)
        self._group.set_visible(False)

        self.append(self._entry)
        self.append(self._group)

    def bind(self, row: ListingItem | GroupRow) -> None:
        """Fill the cell for ``row``, switching between the two layouts."""
        if isinstance(row, GroupRow):
            self._show_group(row)
            return

        self._show_entry(row)

    def _show_group(self, row: GroupRow) -> None:
        self.add_css_class(_GROUP_CELL)
        self._title.set_text(row.label)
        self._count.set_text(str(row.count))
        # Recycle safety: the hidden entry branch must not keep its old text.
        self.text.set_text("")

        self._group.set_visible(True)
        self._entry.set_visible(False)

    def _show_entry(self, row: ListingItem) -> None:
        self.remove_css_class(_GROUP_CELL)
        self.picture.set_from_file(str(icon_path(row.icon_name, px(16))))
        # The icon is the only type cue in the table, so give it a name for AT.
        self.picture.update_property([Gtk.AccessibleProperty.LABEL], [row.icon_label])
        self.text.set_text(row.name)
        # Recycle safety: the hidden group branch must not keep its old caption.
        self._title.set_text("")
        self._count.set_text("")

        self._entry.set_visible(True)
        self._group.set_visible(False)


class DetailsView(ListingView):
    """A three-column table; ``render`` replaces the visible rows."""

    mode = ViewMode.DETAILS

    def __init__(self, *, on_activate: Callable[[ListingItem], None]) -> None:
        super().__init__(on_activate=on_activate)
        self.store = Gio.ListStore.new(GObject.Object)
        selection = Gtk.NoSelection(model=self.store)
        self._column_view = Gtk.ColumnView(model=selection)
        self._column_view.set_show_column_separators(True)
        self._column_view.set_show_row_separators(False)
        self._column_view.connect("activate", self._activate_row)

        self._add_name_column("Имя")
        self._add_numeric_column("Размер", lambda row: row.size_text, width=px(96))
        self._add_numeric_column("Дата", lambda row: row.date_text, width=px(168))

        self._scroller = Gtk.ScrolledWindow(vexpand=True)
        self._scroller.set_child(self._column_view)

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        rows: list[ListingItem | GroupRow] = []
        for section in sections:
            if section.header is not None:
                rows.append(GroupRow(section.header, len(section.items)))
            rows.extend(section.items)

        self.store.splice(0, self.store.get_n_items(), rows)

    def reset_scroll(self) -> None:
        adjustment = self._scroller.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)

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
        getter: Callable[[ListingItem], str],
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

    def _activate_row(self, _view: Gtk.ColumnView, position: int) -> None:
        row = self.store.get_item(position)
        if not isinstance(row, ListingItem):
            return

        self._on_activate(row)


def _setup_name(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    item.set_child(_NameCell())


def _bind_name(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    item.get_child().bind(item.get_item())


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
    getter: Callable[[ListingItem], str],
) -> None:
    row = item.get_item()
    label: Gtk.Label = item.get_child()
    if isinstance(row, GroupRow):
        # An empty cell that still joins the strip: same background and height.
        label.add_css_class(_GROUP_CELL)
        label.set_text("")
        return

    label.remove_css_class(_GROUP_CELL)
    label.set_text(getter(row))
