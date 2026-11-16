"""«Столбцы» — a horizontally scrolling list of columns (design/view-modes.md D5).

The model of the outer list holds *columns* (chunks of the flat listing), so
GTK virtualizes whole columns; a column's six rows are plain widgets inside it
and never need their own virtualization.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk, Pango  # noqa: E402

from ..display import ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .item import ListingItem  # noqa: E402

# Rows per column, fixed like the mockup (perColumn = 6); growing the band
# does not re-chunk the listing — the seam for a height-driven count is here.
ROWS_PER_COLUMN = 6

# Name budget for the column's natural width: ~28 chars at the wide preset
# keep the column within the design's 190..300 base px (GTK CSS has no
# max-width, see theme.css).
_MAX_NAME_CHARS = 28

# Column icons from the mockup: 48 base px, 40 base px when compact.
_COLUMN_ICON = px(48)
_COLUMN_ICON_COMPACT = px(40)


class ColumnGroup(GObject.Object):
    """One column: the items filling it top to bottom."""

    __gtype_name__ = "VolnaColumnGroup"

    def __init__(self, items: tuple[ListingItem, ...]) -> None:
        super().__init__()
        self.items = items


class ColumnsView(ListingView):
    """A horizontal, virtualized column list; ``render`` re-chunks the flat list."""

    mode = ViewMode.COLUMNS

    def __init__(self, *, on_activate: Callable[[ListingItem], None]) -> None:
        super().__init__(on_activate=on_activate)
        self.store = Gio.ListStore.new(ColumnGroup)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_column)
        factory.connect("bind", self._bind_column)

        self._list = Gtk.ListView(
            model=Gtk.NoSelection(model=self.store), factory=factory
        )
        self._list.set_orientation(Gtk.Orientation.HORIZONTAL)

        self._scroller = Gtk.ScrolledWindow(vexpand=True)
        # Horizontal scrolling is the mode's own; vertical stays automatic
        # because POLICY_NEVER would propagate the content's natural height
        # into the window (measured on GTK 4.14) instead of scrolling it.
        self._scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._scroller.set_child(self._list)

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        items = [item for section in sections for item in section.items]
        groups = [
            ColumnGroup(tuple(items[start : start + ROWS_PER_COLUMN]))
            for start in range(0, len(items), ROWS_PER_COLUMN)
        ]
        self.store.splice(0, self.store.get_n_items(), groups)

    def reset_scroll(self) -> None:
        adjustment = self._scroller.get_hadjustment()
        if adjustment is not None:
            adjustment.set_value(0.0)

    # -- factory -------------------------------------------------------

    def _bind_column(
        self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem
    ) -> None:
        column = item.get_child()
        child = column.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            column.remove(child)
            child = following

        for entry in item.get_item().items:
            column.append(self._row(entry))

    def _row(self, entry: ListingItem) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(10))
        row.add_css_class("volna-col-item")
        row.set_hexpand(True)

        icon_size = _COLUMN_ICON_COMPACT if self._settings.compact else _COLUMN_ICON
        picture = Gtk.Image.new_from_file(str(icon_path(entry.icon_name, icon_size)))
        picture.set_pixel_size(icon_size)
        picture.set_halign(Gtk.Align.CENTER)
        picture.set_valign(Gtk.Align.CENTER)
        # The row shows no other type cue, so give the glyph a name for AT.
        picture.update_property([Gtk.AccessibleProperty.LABEL], [entry.icon_label])

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text.set_hexpand(True)

        name = Gtk.Label(label=entry.name, xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        # GTK CSS has no max-width: this char budget is what keeps the column's
        # natural width inside the design range instead of following the name.
        name.set_max_width_chars(_MAX_NAME_CHARS)
        name.set_hexpand(True)
        name.add_css_class("volna-col-name")
        text.append(name)

        # hexpand lets the label take the width the column has left (the icon
        # takes its own), so the date/size use the full text width and only
        # ellipsize when even that is not enough.
        size = Gtk.Label(
            label=entry.size_text, xalign=0, ellipsize=Pango.EllipsizeMode.END
        )
        size.set_hexpand(True)
        size.add_css_class("volna-col-meta")
        text.append(size)

        date = Gtk.Label(
            label=entry.date_text, xalign=0, ellipsize=Pango.EllipsizeMode.END
        )
        date.set_hexpand(True)
        date.add_css_class("volna-col-meta")
        text.append(date)

        row.append(picture)
        row.append(text)

        # Rows have no GTK-level activate signal inside a column; a double
        # click on the row opens it (design D5: activation by double click).
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_row_pressed, entry)
        row.add_controller(click)
        return row

    def _on_row_pressed(
        self,
        _click: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        entry: ListingItem,
    ) -> None:
        if n_press == 2:
            self._on_activate(entry)


def _setup_column(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(2))
    column.add_css_class("volna-col")
    item.set_child(column)
