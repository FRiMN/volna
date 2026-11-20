"""«Значки» — a virtualized grid of tiles, optionally split into date groups.

The flat listing keeps the :class:`Gtk.GridView` path (design/view-modes.md
D5). Date grouping switches to a vertical :class:`Gtk.ListView` whose model
holds whole rows — a group caption or one band of tiles — so GTK still
virtualizes and a 100k-entry catalog never materialises a widget per entry
(design/grouping.md D6).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gio, GLib, GObject, Graphene, Gsk, Gtk, Pango  # noqa: E402

from ..display import GroupAction, ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .group_header import GroupHeader  # noqa: E402
from .item import ListingItem  # noqa: E402

# Tile icon from the mockup at the default zoom: ``--tile-icon`` = 60 base px,
# scaled by the wide preset (px()).
_TILE_ICON = px(60)

# GtkGridView caps the grid at 7 columns by default; the design range needs
# more in a wide band, so the cap is lifted and the tile width drives the count.
_MAX_COLUMNS = 64

# Tile width and gap from the mockup's ``repeat(auto-fill, minmax(150px,
# 178px))`` grid (04-components §6.2). Grouped rows are chunked to ``N`` tiles:
# ``N = floor((band_width + gap) / (_TILE_MIN + gap))``, and the tiles get the
# width that fits, clamped to the design range (grouping.md D6).
_TILE_MIN = px(150)
_TILE_MAX = px(178)
_GAP = px(6)


class IconsRow(GObject.Object):
    """One row of the grouped listing (a GObject for the typed ``ListStore``)."""

    __gtype_name__ = "VolnaIconsRow"


class HeaderRow(IconsRow):
    """A group caption row: the date title and the group summary (28 px)."""

    __gtype_name__ = "VolnaIconsHeaderRow"

    def __init__(self, key: str, label: str, stats: str, collapsed: bool) -> None:
        super().__init__()
        self.key = key
        self.label = label
        self.stats = stats
        self.collapsed = collapsed
        self.position = 0


class TileRow(IconsRow):
    """One band of at most ``N`` equal-width tiles."""

    __gtype_name__ = "VolnaIconsTileRow"

    def __init__(self, items: tuple[ListingItem, ...]) -> None:
        super().__init__()
        self.items = items
        self.position = 0


class TileBand(Gtk.Widget):
    """One band of fixed-width tiles.

    GTK has only a *minimum* width request, so a band built from a ``Gtk.Box``
    would freeze the ListView's minimum width at the band's current width and
    the window could never shrink (no re-chunk). This widget therefore reports
    a zero minimum width and allocates its tiles by hand: the natural width is
    the design's tile width times the tiles in the row (design/grouping.md D6).

    The tiles are parented by hand, so the band releases them itself: when it
    leaves a rooted tree (:meth:`do_unroot`, the common path) and when GTK
    disposes it (:meth:`_on_destroy`, the backstop for a band that was never
    rooted). GTK releases no children of a custom widget, and a leftover child
    makes it warn on finalization while leaking the tile. The view builds a
    fresh band on every bind, so a released band is not re-used.
    """

    __gtype_name__ = "VolnaTileBand"

    def __init__(self, *, tile_width: int) -> None:
        super().__init__()
        self._tiles: list[Gtk.Widget] = []
        self._tile_width = tile_width
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.connect("destroy", self._on_destroy)

    def append(self, tile: Gtk.Widget) -> None:
        tile.set_parent(self)
        self._tiles.append(tile)
        self.queue_resize()

    def release(self) -> None:
        """Unparent every tile; a released band must not be re-used afterwards."""
        child = self.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            child.unparent()
            child = following

        self._tiles.clear()

    def set_tile_width(self, tile_width: int) -> None:
        if tile_width == self._tile_width:
            return

        self._tile_width = tile_width
        self.queue_resize()

    def do_unroot(self) -> None:
        # The prompt path: the view takes the band out of a rooted tree as soon
        # as the ListView discards its row, and the tiles must go with it then,
        # not at the next Python cycle-GC pass (the destroy handler below holds
        # the band in a reference cycle until then).
        self.release()
        Gtk.Widget.do_unroot(self)

    def _on_destroy(self, *_args: object) -> None:
        # The guaranteed path: GTK emits destroy from gtk_widget_dispose for
        # every widget, including one that was never rooted (unroot only comes
        # to rooted widgets) or is disposed during teardown. Children parented
        # by hand have no container to release them, and GObject's ``dispose``
        # — the usual place for that — cannot be overridden from Python; a band
        # finalized with a leftover child makes GTK warn and leaks the tile.
        self.release()

    def do_measure(self, orientation: int, for_size: int) -> tuple[int, int, int, int]:
        count = len(self._tiles)
        if orientation == Gtk.Orientation.HORIZONTAL:
            natural = count * self._tile_width + max(0, count - 1) * _GAP
            return 0, natural, -1, -1

        height = 0
        for tile in self._tiles:
            _minimum, natural, _minimum_baseline, _natural_baseline = tile.measure(
                Gtk.Orientation.VERTICAL, self._tile_width
            )
            height = max(height, natural)

        return height, height, -1, -1

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        x = 0
        for tile in self._tiles:
            if not tile.get_visible():
                continue

            # A band that no longer fits (the ListView allocates the previous
            # rows once more between a resize and the idle re-chunk) is clipped
            # by the scroller instead of squeezing the tiles to zero width: a
            # tile narrower than its padding makes GTK allocate the padded
            # children with negative sizes.
            transform = Gsk.Transform.new().translate(Graphene.Point().init(x, 0))
            tile.allocate(self._tile_width, height, -1, transform)
            x += self._tile_width + _GAP


class IconsView(ListingView):
    """A vertically scrolling listing: a flat grid or grouped tile bands."""

    mode = ViewMode.ICONS

    def __init__(
        self,
        *,
        on_activate: Callable[[ListingItem], None],
        on_group_action: Callable[[str, GroupAction], None] | None = None,
    ) -> None:
        super().__init__(on_activate=on_activate, on_group_action=on_group_action)

        self._grid_store = Gio.ListStore.new(ListingItem)
        grid_factory = Gtk.SignalListItemFactory()
        grid_factory.connect("setup", _setup_tile)
        grid_factory.connect("bind", _bind_tile)

        self._grid = Gtk.GridView(
            model=Gtk.NoSelection(model=self._grid_store), factory=grid_factory
        )
        self._grid.set_max_columns(_MAX_COLUMNS)
        self._grid.connect("activate", self._activate_tile)

        self._rows = Gio.ListStore.new(IconsRow)
        rows_factory = Gtk.SignalListItemFactory()
        rows_factory.connect("setup", _setup_row)
        rows_factory.connect("bind", self._bind_row)

        self._list = _IconsListView(
            on_width=self._on_width_changed,
            model=Gtk.NoSelection(model=self._rows),
            factory=rows_factory,
        )
        self._list.set_show_separators(False)

        self._scroller = Gtk.ScrolledWindow(vexpand=True)
        self._scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroller.set_child(self._grid)
        # A ListView claims right clicks before they reach a row widget, so the
        # caption clicks are routed from above it (design/grouping.md D14).
        self._install_group_clicks(self._scroller)

        # ``store`` is the model of the visible presentation: tiles when flat,
        # rows (captions + tile bands) when grouped. Tests and the tab read it.
        self.store = self._grid_store
        self._sections: tuple[Section, ...] = ()
        self._grouped = False
        self._columns = _columns_for(0)
        self._tile_width = _TILE_MIN
        self._width = 0
        self._rechunk_scheduled = False
        self._fresh_layout = False

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        self._sections = tuple(sections)
        self._read_menu_state(sections)

        if any(section.header is not None for section in sections):
            self._render_grouped()
            return

        self._render_flat()

    def reset_scroll(self) -> None:
        adjustment = self._scroller.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)

    # -- flat -----------------------------------------------------------------

    def _render_flat(self) -> None:
        """One unnamed section: the unchanged ``GtkGridView`` of tiles."""
        self._grouped = False
        self._fresh_layout = False
        self.store = self._grid_store
        # The grouped rows would keep every item alive while unused.
        self._rows.splice(0, self._rows.get_n_items(), [])

        items = [item for section in self._sections for item in section.items]
        self._show_widget(self._grid)
        self._grid_store.splice(0, self._grid_store.get_n_items(), items)

    def _activate_tile(self, _grid: Gtk.GridView, position: int) -> None:
        item = self._grid_store.get_item(position)
        if item is not None:
            self._on_activate(item)

    # -- grouped --------------------------------------------------------------

    def _render_grouped(self) -> None:
        """Named sections: one caption row plus tile bands per date group."""
        self._grouped = True
        # Without an allocated width the first band layout is still unknown:
        # keeping a reading position there would scroll the first caption away.
        # A re-render in a sized window knows its width, so later re-chunks keep
        # the anchor instead of being treated as the first layout forever.
        self._fresh_layout = self._band_width() <= 0
        self.store = self._rows
        # The flat tiles would keep every item alive while unused.
        self._grid_store.splice(0, self._grid_store.get_n_items(), [])

        band_width = self._band_width()
        self._columns = _columns_for(band_width)
        self._tile_width = _tile_width_for(band_width, self._columns)
        self._show_widget(self._list)
        self._rows.splice(0, self._rows.get_n_items(), self._build_rows())

    def _band_width(self) -> int:
        """The width available to the rows: the list, else the scroller.

        The list is not allocated yet on the first grouped render, while the
        scroller usually is (the flat grid was on screen) — using it avoids
        chunking the whole listing into single-tile bands first.
        """
        return self._list.get_width() or self._scroller.get_width() or self._width

    def _build_rows(self) -> list[IconsRow]:
        rows: list[IconsRow] = []
        for section in self._sections:
            if not section.items:
                continue

            rows.append(
                HeaderRow(
                    section.key or "",
                    section.header or "",
                    section.stats,
                    section.collapsed,
                )
            )
            if section.collapsed:
                # A collapsed group is its caption row only (design/grouping.md
                # D13); the count still says what is inside.
                continue

            for start in range(0, len(section.items), self._columns):
                band = section.items[start : start + self._columns]
                rows.append(TileRow(band))

        for position, row in enumerate(rows):
            row.position = position

        return rows

    def _show_widget(self, widget: Gtk.Widget) -> None:
        if self._scroller.get_child() is not widget:
            self._scroller.set_child(widget)

    def _bind_row(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        row = item.get_item()
        box = item.get_child()
        _clear(box)
        # The widget keeps its row: the anchor of the reading position is read
        # back from the materialised children on a re-chunk (see _top_row).
        box.icon_row = row

        if isinstance(row, HeaderRow):
            # A fresh header per bind: a recycled one keeps its key and menu
            # state, and rebuilding a small widget is cheaper than key
            # bookkeeping here.
            header = GroupHeader(row.key)
            header.set_caption(row.label, row.stats)
            header.set_collapsed(row.collapsed)
            header.set_action(self._on_group_action)
            header.set_menu_state(
                others_collapsible=self._others_collapsible,
                any_expanded=self._any_expanded,
                any_collapsed=self._any_collapsed,
            )
            header.add_css_class("volna-icons-head")
            self._headers[row.key] = header
            box.append(header)
            return

        # Fixed-width tiles along the row: a short band must not stretch two
        # tiles across the whole band (the mockup keeps columns 150..178 px and
        # lets the leftover width stay to the right). The band reports a zero
        # minimum width, so a row never freezes the window's minimum size.
        band = TileBand(tile_width=self._tile_width)
        for entry in row.items:
            band.append(self._tile(entry))
        box.append(band)

    def _tile(self, entry: ListingItem) -> Gtk.Widget:
        tile = _make_tile()
        _fill_tile(tile, entry)

        # A row holds several tiles, so the row-level ``activate`` cannot say
        # which one was opened: each tile gets its own double-click handler.
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_tile_pressed, entry)
        tile.add_controller(click)
        return tile

    def _on_tile_pressed(
        self,
        _click: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        entry: ListingItem,
    ) -> None:
        if n_press == 2:
            self._on_activate(entry)

    # -- width-driven re-chunking ---------------------------------------------

    def _on_width_changed(self, width: int) -> None:
        self._width = width
        if not self._grouped or width <= 0:
            return

        if _columns_for(width) == self._columns:
            return

        self._schedule_rechunk()

    def _schedule_rechunk(self) -> None:
        if self._rechunk_scheduled:
            return

        self._rechunk_scheduled = True
        GLib.idle_add(self._rechunk)

    def _rechunk(self) -> bool:
        self._rechunk_scheduled = False
        if not self._grouped:
            return False

        columns = _columns_for(self._band_width())
        if columns == self._columns:
            return False

        # The first layout only learns the widget width; there is no reading
        # position to keep yet, and anchoring would scroll the first caption off.
        # At the very top there is nothing to keep either: a re-chunk must leave
        # the first caption visible instead of pinning the first tile row.
        anchor = None
        if not self._fresh_layout and self._scroll_offset() > 0:
            anchor = self._first_visible_item()

        self._fresh_layout = False
        self._columns = columns
        self._tile_width = _tile_width_for(self._band_width(), columns)
        self._rows.splice(0, self._rows.get_n_items(), self._build_rows())

        if anchor is not None:
            # After the splice GTK lays the new rows out on the next frame;
            # scrolling in an idle keeps the anchor in view (approximation:
            # ``scroll_to`` brings the row into view, it does not pin it to the
            # top, because this GTK build has no ALIGN_TOP scroll flag).
            GLib.idle_add(self._scroll_to_item, anchor)

        return False

    def _scroll_offset(self) -> float:
        adjustment = self._scroller.get_vadjustment()
        if adjustment is None:
            return 0.0

        return adjustment.get_value()

    def _scroll_to_item(self, item: ListingItem) -> bool:
        position = self._row_position(item)
        if position is None:
            return False

        self._list.scroll_to(position, Gtk.ListScrollFlags.NONE)
        return False

    def _row_position(self, item: ListingItem) -> int | None:
        for position in range(self._rows.get_n_items()):
            row = self._rows.get_item(position)
            if isinstance(row, TileRow) and any(
                candidate is item for candidate in row.items
            ):
                return position

        return None

    def _first_visible_item(self) -> ListingItem | None:
        """The first item the user is reading: top row's first tile."""
        row = self._top_row()
        if row is None:
            return self._first_item_by_offset()

        if isinstance(row, TileRow):
            return row.items[0] if row.items else None

        following = row.position + 1
        if following >= self._rows.get_n_items():
            return None

        next_row = self._rows.get_item(following)
        if isinstance(next_row, TileRow) and next_row.items:
            return next_row.items[0]

        return None

    def _top_row(self) -> HeaderRow | TileRow | None:
        """The materialised row overlapping the top edge of the viewport."""
        height = self._list.get_height()
        if height <= 0:
            return None

        best: tuple[float, HeaderRow | TileRow] | None = None
        child = self._list.get_first_child()
        while child is not None:
            place = child.compute_bounds(self._list)
            row = getattr(child.get_first_child(), "icon_row", None)
            # Pool widgets that are not on screen stay unmapped and keep stale
            # bounds; only mapped children are a reading position.
            if child.get_mapped() and place[0] and row is not None:
                top = place[1].get_y()
                bottom = top + place[1].get_height()
                if bottom > 0 and top < height and (best is None or top < best[0]):
                    best = (top, row)

            child = child.get_next_sibling()

        return None if best is None else best[1]

    def _first_item_by_offset(self) -> ListingItem | None:
        """Fallback anchor before layout: the row under the scroll offset."""
        adjustment = self._scroller.get_vadjustment()
        if adjustment is None or adjustment.get_upper() <= 0:
            return None

        row_count = self._rows.get_n_items()
        if row_count == 0:
            return None

        share = adjustment.get_value() / adjustment.get_upper()
        position = min(row_count - 1, max(0, int(share * row_count)))

        for index in range(position, row_count):
            row = self._rows.get_item(index)
            if isinstance(row, TileRow) and row.items:
                return row.items[0]

        return None


class _IconsListView(Gtk.ListView):
    """A ``ListView`` that reports its allocated width: rows re-chunk on resize.

    GTK 4 has no ``size-allocate`` signal, so the width is read in the vfunc.
    """

    def __init__(self, *, on_width: Callable[[int], None], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._on_width = on_width
        self._width = 0

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        Gtk.ListView.do_size_allocate(self, width, height, baseline)
        if width == self._width:
            return

        self._width = width
        self._on_width(width)


def _columns_for(width: int) -> int:
    """Tiles that fit into a band of ``width`` pixels (D6)."""
    if width <= 0:
        return 1

    return max(1, (width + _GAP) // (_TILE_MIN + _GAP))


def _tile_width_for(width: int, columns: int) -> int:
    """Tile width that fills the band within the design's 150..178 px range."""
    if width <= 0 or columns <= 0:
        return _TILE_MIN

    available = width - (columns - 1) * _GAP
    return max(_TILE_MIN, min(_TILE_MAX, available // columns))


def _setup_row(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    row.set_valign(Gtk.Align.START)
    row.set_halign(Gtk.Align.FILL)
    # The bands relax the tiles' CSS min-width: a row's minimum width would
    # otherwise become the ListView's minimum and freeze the window's width
    # (design/grouping.md D6: rows re-chunk as the band gets narrower). The
    # matching `min-width: 0` rule lives in theme.css (D9).
    row.add_css_class("volna-icons-band")
    item.set_child(row)


def _clear(box: Gtk.Box) -> None:
    child = box.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


def _setup_tile(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    item.set_child(_make_tile())


def _make_tile() -> Gtk.Box:
    tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(4))
    tile.add_css_class("volna-icons-tile")
    tile.set_halign(Gtk.Align.FILL)

    picture = Gtk.Image()
    picture.set_pixel_size(_TILE_ICON)
    picture.set_halign(Gtk.Align.CENTER)
    tile.append(picture)

    name = Gtk.Label(xalign=0.5)
    name.set_wrap(True)
    name.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    name.set_lines(2)
    name.set_ellipsize(Pango.EllipsizeMode.END)
    name.set_justify(Gtk.Justification.CENTER)
    name.add_css_class("volna-icons-name")
    tile.append(name)

    size = Gtk.Label(xalign=0.5, ellipsize=Pango.EllipsizeMode.END)
    size.add_css_class("volna-icons-meta")
    tile.append(size)

    date = Gtk.Label(xalign=0.5, ellipsize=Pango.EllipsizeMode.END)
    date.add_css_class("volna-icons-meta")
    tile.append(date)

    return tile


def _bind_tile(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    entry: ListingItem = item.get_item()
    _fill_tile(item.get_child(), entry)


def _fill_tile(tile: Gtk.Widget, entry: ListingItem) -> None:
    picture, name, size, date = _children(tile)
    picture.set_from_file(str(icon_path(entry.icon_name, _TILE_ICON)))
    # The tile shows no other type cue, so give the glyph a name for AT.
    picture.update_property([Gtk.AccessibleProperty.LABEL], [entry.icon_label])
    name.set_text(entry.name)
    size.set_text(entry.size_text)
    date.set_text(entry.date_text)


def _children(tile: Gtk.Widget) -> tuple[Gtk.Widget, Gtk.Label, Gtk.Label, Gtk.Label]:
    picture = tile.get_first_child()
    name = picture.get_next_sibling()
    size = name.get_next_sibling()
    date = size.get_next_sibling()
    return picture, name, size, date
