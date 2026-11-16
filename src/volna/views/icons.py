"""«Значки» — a virtualized grid of tiles (design/view-modes.md D5)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, Gtk, Pango  # noqa: E402

from ..display import ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .item import ListingItem  # noqa: E402

# Tile icon from the mockup at the default zoom: ``--tile-icon`` = 60 base px,
# scaled by the wide preset (px()).
_TILE_ICON = px(60)

# GtkGridView caps the grid at 7 columns by default; the design range needs
# more in a wide band, so the cap is lifted and the tile width drives the count.
_MAX_COLUMNS = 64


class IconsView(ListingView):
    """A vertically scrolling grid; ``render`` replaces the tiles."""

    mode = ViewMode.ICONS

    def __init__(self, *, on_activate: Callable[[ListingItem], None]) -> None:
        super().__init__(on_activate=on_activate)
        self.store = Gio.ListStore.new(ListingItem)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_tile)
        factory.connect("bind", _bind_tile)

        self._grid = Gtk.GridView(
            model=Gtk.NoSelection(model=self.store), factory=factory
        )
        self._grid.set_max_columns(_MAX_COLUMNS)
        self._grid.connect("activate", self._activate_tile)

        self._scroller = Gtk.ScrolledWindow(vexpand=True)
        self._scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroller.set_child(self._grid)

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        items = [item for section in sections for item in section.items]
        self.store.splice(0, self.store.get_n_items(), items)

    def reset_scroll(self) -> None:
        adjustment = self._scroller.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)

    def _activate_tile(self, _grid: Gtk.GridView, position: int) -> None:
        item = self.store.get_item(position)
        if item is not None:
            self._on_activate(item)


def _setup_tile(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
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

    item.set_child(tile)


def _bind_tile(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    entry: ListingItem = item.get_item()
    tile = item.get_child()

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
