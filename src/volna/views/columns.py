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

from ..display import GroupAction, ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .group_header import header_box  # noqa: E402
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

# A wheel/touchpad notch pans the columns by this much (the mockup's band is a
# horizontally overflowing flex row, so any wheel axis is meant for it).
_WHEEL_STEP = px(100)


class ColumnGroup(GObject.Object):
    """One column: an optional group caption plus the items filling it.

    Grouped listings make one column per date group (design/grouping.md D7);
    the flat listing keeps caption-less columns of ``ROWS_PER_COLUMN`` rows.
    """

    __gtype_name__ = "VolnaColumnGroup"

    def __init__(
        self,
        items: tuple[ListingItem, ...],
        header: str | None = None,
        stats: str = "",
    ) -> None:
        super().__init__()
        self.items = items
        self.header = header
        self.stats = stats


class ColumnsView(ListingView):
    """A horizontal, virtualized column list; ``render`` re-chunks the flat list."""

    mode = ViewMode.COLUMNS

    def __init__(
        self,
        *,
        on_activate: Callable[[ListingItem], None],
        on_group_action: Callable[[str, GroupAction], None] | None = None,
    ) -> None:
        # The callback is stored contract-wide but unused here: «Столбцы» keep
        # static captions — collapsing groups is a «Подробности»/«Значки»
        # feature (design/grouping.md §12, owner decision 2026-11-17).
        super().__init__(on_activate=on_activate, on_group_action=on_group_action)
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

        # Both wheel axes pan the columns horizontally: the listing flows
        # left to right, so a plain vertical wheel (or SHIFT/tilt horizontal)
        # must move it along its own axis instead of doing nothing. The capture
        # phase matters: GtkScrolledWindow has its own wheel handling in the
        # bubble phase, and without capturing first it would consume the event.
        self._wheel = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
        )
        self._wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._wheel.connect("scroll", self._on_scroll)
        self._scroller.add_controller(self._wheel)

    @property
    def widget(self) -> Gtk.Widget:
        return self._scroller

    def render(self, sections: Sequence[Section]) -> None:
        """Grouped sections become one column each; a flat one is chunked."""
        if any(section.header is not None for section in sections):
            groups = [
                ColumnGroup(tuple(section.items), section.header, section.stats)
                for section in sections
                if section.items
            ]
        else:
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

    def _on_scroll(
        self, _controller: Gtk.EventControllerScroll, dx: float, dy: float
    ) -> bool:
        """Pan horizontally for either wheel axis; True consumes the event."""
        adjustment = self._scroller.get_hadjustment()
        if adjustment is None:
            return False

        # Wheel notches arrive as vertical deltas, tilted wheels and SHIFT+wheel
        # as horizontal ones: the larger magnitude is the user's intent.
        delta = dy if abs(dy) >= abs(dx) else dx
        if delta == 0:
            return False

        lower = adjustment.get_lower()
        upper = adjustment.get_upper()
        page = adjustment.get_page_size()
        last = max(lower, upper - page)
        if last <= lower:
            # Everything fits: nothing to pan, let the event bubble up.
            return False

        adjustment.set_value(
            max(lower, min(adjustment.get_value() + delta * _WHEEL_STEP, last))
        )
        return True

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

        group = item.get_item()
        if group.header is not None:
            # A column caption is narrow: the group summary does not fit there,
            # so it keeps the compact item count (design/grouping.md §12).
            caption = header_box(group.header, len(group.items))
            caption.add_css_class("volna-col-head")
            column.append(caption)

        for entry in group.items:
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
