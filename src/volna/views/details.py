"""«Подробности» — a three-column table over the ordered listing."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk, Pango  # noqa: E402

from ..display import GroupAction, ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .group_header import GroupHeader  # noqa: E402
from .item import ListingItem  # noqa: E402

# One cell of a group strip; every column cell carries it so the 28 px row
# reads as a single full-width band (theme.css, design/grouping.md D9).
_GROUP_CELL = "volna-dt-group"


class GroupRow(GObject.Object):
    """A date group caption in the row store (design/grouping.md D5).

    Group rows share the heterogeneous model with :class:`ListingItem` rows:
    one ColumnView keeps its sticky column header and shared column widths.
    ``stats`` is the group's folders/files/size summary, the same string the
    editor header shows (design/grouping.md D4); a collapsed group renders its
    caption with the full summary and nothing else (D13).
    """

    __gtype_name__ = "VolnaGroupRow"

    def __init__(
        self,
        key: str,
        label: str,
        stats: str,
        collapsed: bool,
        *,
        others_collapsible: bool = True,
        any_expanded: bool = True,
        any_collapsed: bool = False,
    ) -> None:
        super().__init__()
        self.key = key
        self.label = label
        self.stats = stats
        self.collapsed = collapsed
        # Menu sensitivity is a property of the whole group set (D14); the tab
        # computes it once per render and hands it to every caption row.
        self.others_collapsible = others_collapsible
        self.any_expanded = any_expanded
        self.any_collapsed = any_collapsed


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

        self._header: GroupHeader | None = None
        self._group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        self._group.add_css_class("volna-dt-group-content")
        # The caption spans the name column, so its summary sits at the end of
        # that column like it does across the whole band in «Значки».
        self._group.set_halign(Gtk.Align.FILL)
        self._group.set_hexpand(True)
        self._group.set_valign(Gtk.Align.CENTER)

        self._group.set_visible(False)

        self.append(self._entry)
        self.append(self._group)

    def bind(
        self,
        row: ListingItem | GroupRow,
        *,
        on_group_action: Callable[[str, GroupAction], None],
        on_header: Callable[[str, GroupHeader], None],
    ) -> None:
        """Fill the cell for ``row``, switching between the two layouts."""
        if isinstance(row, GroupRow):
            self._show_group(row, on_group_action, on_header)
            return

        self._show_entry(row)

    def _show_group(
        self,
        row: GroupRow,
        on_group_action: Callable[[str, GroupAction], None],
        on_header: Callable[[str, GroupHeader], None],
    ) -> None:
        self.add_css_class(_GROUP_CELL)
        # A fresh header per bind: a recycled one keeps its key and menu state,
        # and rebuilding a small widget is cheaper than key bookkeeping here.
        if self._header is not None:
            self._group.remove(self._header)

        header = GroupHeader(row.key)
        header.set_caption(row.label, row.stats)
        header.set_collapsed(row.collapsed)
        header.set_action(on_group_action)
        header.set_menu_state(
            others_collapsible=row.others_collapsible,
            any_expanded=row.any_expanded,
            any_collapsed=row.any_collapsed,
        )
        on_header(row.key, header)
        self._group.append(header)
        self._header = header
        self._group.set_visible(True)
        self._entry.set_visible(False)

    def _show_entry(self, row: ListingItem) -> None:
        self.remove_css_class(_GROUP_CELL)
        self.picture.set_from_file(str(icon_path(row.icon_name, px(16))))
        # The icon is the only type cue in the table, so give it a name for AT.
        self.picture.update_property([Gtk.AccessibleProperty.LABEL], [row.icon_label])
        self.text.set_text(row.name)
        # Recycle safety: the caption widget is rebuilt per group row, so there
        # is no stale caption to clear.
        self._entry.set_visible(True)
        self._group.set_visible(False)


class DetailsView(ListingView):
    """A three-column table; ``render`` replaces the visible rows."""

    mode = ViewMode.DETAILS

    def __init__(
        self,
        *,
        on_activate: Callable[[ListingItem], None],
        on_group_action: Callable[[str, GroupAction], None] | None = None,
    ) -> None:
        super().__init__(on_activate=on_activate, on_group_action=on_group_action)
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
        # A group strip spans all three columns, but only the name cell hosts the
        # caption widget: the shared capture-phase routing finds the caption
        # under the pointer, so a click anywhere on the strip reaches it
        # (design/grouping.md D14). The scroller sits above the column view,
        # whose own click controllers claim right clicks first.
        self._install_group_clicks(self._scroller)

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        self._read_menu_state(sections)
        rows: list[ListingItem | GroupRow] = []
        for section in sections:
            if section.header is not None:
                rows.append(
                    GroupRow(
                        section.key or "",
                        section.header,
                        section.stats,
                        section.collapsed,
                        others_collapsible=self._others_collapsible,
                        any_expanded=self._any_expanded,
                        any_collapsed=self._any_collapsed,
                    )
                )
                if section.collapsed:
                    continue

            rows.extend(section.items)

        self.store.splice(0, self.store.get_n_items(), rows)

    def reset_scroll(self) -> None:
        adjustment = self._scroller.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)

    def _add_name_column(self, title: str) -> None:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_name)
        factory.connect("bind", self._bind_name_row)
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

    def _bind_name_row(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        item.get_child().bind(
            item.get_item(),
            on_group_action=self._on_group_action,
            on_header=self._remember_header,
        )

    def _remember_header(self, key: str, header: GroupHeader) -> None:
        self._headers[key] = header

    def _group_for_node(self, node: Gtk.Widget) -> GroupHeader | None:
        """A strip's number cell carries only the key: resolve it to the caption."""
        if isinstance(node, _NumericCell) and node.group_key is not None:
            return self._headers.get(node.group_key)
        return super()._group_for_node(node)


def _setup_name(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    item.set_child(_NameCell())


class _NumericCell(Gtk.Label):
    """A size/date cell; on a group strip it is empty but still interactive.

    It keeps the group key so a right click anywhere on the strip finds the
    caption's menu (design/grouping.md D14).
    """

    __gtype_name__ = "VolnaNumericCell"

    def __init__(self) -> None:
        super().__init__(xalign=1)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.add_css_class("volna-dt-num")
        self.group_key: str | None = None

    def bind(
        self, row: ListingItem | GroupRow, getter: Callable[[ListingItem], str]
    ) -> None:
        if isinstance(row, GroupRow):
            # An empty cell that still joins the strip: same background and
            # height, and a right click target.
            self.add_css_class(_GROUP_CELL)
            self.group_key = row.key
            self.set_text("")
            return

        self.remove_css_class(_GROUP_CELL)
        self.group_key = None
        self.set_text(getter(row))


def _setup_numeric(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
) -> None:
    item.set_child(_NumericCell())


def _bind_text(
    _factory: Gtk.SignalListItemFactory,
    item: Gtk.ListItem,
    getter: Callable[[ListingItem], str],
) -> None:
    item.get_child().bind(item.get_item(), getter)
