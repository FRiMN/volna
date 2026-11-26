"""«Столбцы» — a horizontally scrolling list of columns (design/view-modes.md D5).

The model of the outer list holds *columns* (chunks of the listing), so GTK
virtualizes whole columns; a column's rows are plain widgets inside it and never
need their own virtualization. The number of rows is height-driven: whatever
does not fit the visible band continues in the next column to the right.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from ..display import GroupAction, ViewMode  # noqa: E402
from ..glyph import icon_path  # noqa: E402
from ..size import px  # noqa: E402
from .base import ListingView, Section  # noqa: E402
from .group_header import header_box  # noqa: E402
from .item import ListingItem  # noqa: E402
from .name_label import NameLabel  # noqa: E402

# Upper bound of rows per column from the mockup (perColumn = 6). The actual
# count is height-driven: an element that would fall below the visible band
# continues in the next column to the right instead of producing a vertical
# scrollbar (owner decision 2026-11-23, design/grouping.md D7).
ROWS_PER_COLUMN = 6

# Gap between two rows inside a column (the column box's spacing).
_ROW_GAP = px(2)

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

    A section longer than the visible band is split into continuation columns
    (``header=None`` after the first one), so every element is reachable by
    panning right rather than by scrolling the band down. ``count`` keeps the
    section's total in the first caption when the section is split.
    """

    __gtype_name__ = "VolnaColumnGroup"

    def __init__(
        self,
        items: tuple[ListingItem, ...],
        header: str | None = None,
        stats: str = "",
        *,
        count: int | None = None,
        continued: bool = False,
    ) -> None:
        super().__init__()
        self.items = items
        self.header = header
        self.stats = stats
        self.count = count
        # A continuation keeps the caption band but not its text, so the rows
        # of every column in a section start at the same height.
        self.continued = continued


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
        self._sections: tuple[Section, ...] = ()
        self._rows_per_column = ROWS_PER_COLUMN
        self._capacity_scheduled = False
        self._capacity_attempts = 0

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_column)
        factory.connect("bind", self._bind_column)

        self._list = _ColumnsListView(
            on_height=self._on_height_changed,
            model=Gtk.NoSelection(model=self.store),
            factory=factory,
        )
        self._list.set_orientation(Gtk.Orientation.HORIZONTAL)
        # A tab can become visible at a size it never laid out while hidden;
        # re-measure when it appears so the height-driven chunking is current.
        self._list.connect("map", self._on_map)

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
        """Split sections into columns that fit the visible band height."""
        self._sections = tuple(sections)
        self._rows_per_column = self._capacity()
        self._capacity_attempts = 0
        self._populate()
        # Rows may have been re-measured (density, full names): check again
        # once the next frame has laid them out.
        self._schedule_capacity_check()

    def _populate(self) -> None:
        groups = self._chunks()
        self.store.splice(0, self.store.get_n_items(), groups)

    def _chunks(self) -> list[ColumnGroup]:
        """Columns in reading order: top-to-bottom, then right.

        Grouped sections become one column per chunk, caption on the first;
        the flat listing keeps caption-less chunks.
        """
        groups: list[ColumnGroup] = []
        for section in self._sections:
            if not section.items:
                continue

            chunks = _split(section.items, self._rows_per_column)
            for index, chunk in enumerate(chunks):
                first = index == 0
                groups.append(
                    ColumnGroup(
                        chunk,
                        section.header if first else None,
                        section.stats if first else "",
                        count=len(section.items) if first else None,
                        continued=not first and section.header is not None,
                    )
                )

        return groups

    def _capacity(self) -> int:
        """Rows that fit the band, capped by the mockup's six.

        One row is measured after layout: multi-line names change its height,
        and the row is the unit that must not fall below the visible band.
        """
        row_height = self._measured_height("volna-col-item")
        if row_height <= 0:
            return ROWS_PER_COLUMN

        # The vertical adjustment's page size is the band actually visible to
        # the user (it already excludes a horizontal scrollbar); the widget
        # height is the fallback before the first allocation.
        adjustment = self._scroller.get_vadjustment()
        height = int(adjustment.get_page_size()) if adjustment is not None else 0
        if height <= 0:
            height = self._scroller.get_height()
        if height <= 0:
            return ROWS_PER_COLUMN

        grouped = any(section.header is not None for section in self._sections)
        header_height = (
            self._measured_height("volna-col-head") + _ROW_GAP if grouped else 0
        )
        available = height - header_height
        if available <= 0:
            return 1

        capacity = available // (row_height + _ROW_GAP)
        return max(1, min(ROWS_PER_COLUMN, capacity))

    def _measured_height(self, css_class: str) -> int:
        """The minimum height the ``ListView`` reserves for a row of a class.

        The allocated height is not reliable here: a recycled row can still
        report the size of its previous column. ``measure`` asks for the
        minimum the layout will actually need, wrapped at the column's width.
        """
        found = _find_by_class(self._list, css_class)
        if found is None:
            return 0

        # Wrap at the column's width: the row's own width can be a stale pool
        # allocation.
        width = found.get_parent().get_width() or found.get_width()
        if width <= 0:
            width = self._scroller.get_width()

        return found.measure(Gtk.Orientation.VERTICAL, width).minimum

    def _on_height_changed(self, _height: int) -> None:
        self._capacity_attempts = 0
        self._schedule_capacity_check()

    def _on_map(self, *_args: object) -> None:
        self._capacity_attempts = 0
        self._schedule_capacity_check()

    def _schedule_capacity_check(self) -> None:
        if self._capacity_scheduled:
            return

        self._capacity_scheduled = True
        # A zero delay still runs before GTK's next layout in some cases; the
        # short timeout runs after the frame that allocates the row widgets.
        GLib.timeout_add(32, self._refresh_capacity)

    def _refresh_capacity(self) -> bool:
        self._capacity_scheduled = False
        if not self._list.get_mapped():
            # A detached or not-yet-shown tab measures nothing; the height
            # callback schedules another check once it is on screen.
            return False

        capacity = self._capacity()
        if capacity == self._rows_per_column:
            return False

        # A measurement can oscillate around the scrollbar edge; a handful of
        # corrections is enough, and an endless loop would re-chunk every frame.
        self._capacity_attempts += 1
        if self._capacity_attempts > 4:
            return False

        self._rows_per_column = capacity
        self._populate()
        # A ListView caches its item height from the old chunking and does not
        # always forget it on a store splice; resetting the model drops the
        # pooled items so the new content height reaches the scroller.
        self._reset_model()
        # The rebuilt rows may measure differently (a caption appears, CSS
        # settles): converge on the capacity that actually fits the band.
        self._schedule_capacity_check()
        return False

    def _reset_model(self) -> None:
        """Drop the ListView's pooled items after a re-chunk (height cache)."""
        adjustment = self._scroller.get_hadjustment()
        offset = adjustment.get_value() if adjustment is not None else 0.0
        self._list.set_model(None)
        self._list.set_model(Gtk.NoSelection(model=self.store))
        if adjustment is not None:
            GLib.idle_add(self._restore_offset, adjustment, offset)

    @staticmethod
    def _restore_offset(adjustment: Gtk.Adjustment, offset: float) -> bool:
        adjustment.set_value(offset)
        return False

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
            # so it keeps the compact item count (design/grouping.md §12). A
            # split section keeps its total on the first caption.
            count = group.count if group.count is not None else len(group.items)
            caption = header_box(group.header, count, count_at_end=False)
            caption.add_css_class("volna-col-head")
            column.append(caption)
        elif group.continued:
            # The band continues across the section, so a continuation column
            # aligns its first row with the first column's.
            column.append(_empty_caption())

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

        name = NameLabel()
        name.set_name(entry.name)
        name.set_xalign(0)
        name.set_hexpand(True)
        # GTK CSS has no max-width: the char budget is what keeps the column's
        # width inside the design range instead of following the name. The
        # width is *requested* too: an ellipsizing label's minimum width is
        # tiny, and a ListView sizes a column by its minimum, so max-width alone
        # would leave the name with only the CSS minimum. With the request the
        # column gets the budget and the name wraps inside it: two lines in
        # «резать» mode, four in «показывать имена целиком»; anything longer is
        # ellipsized in the middle (design/spec/07-decisions.md D29).
        name.set_width_chars(_MAX_NAME_CHARS)
        name.set_max_width_chars(_MAX_NAME_CHARS)
        name.set_wrap(True)
        name.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        name.set_justify(Gtk.Justification.LEFT)
        name.set_lines(4 if self._settings.show_full_names else 2)
        name.add_css_class("volna-col-name")
        if self._settings.show_full_names:
            name.add_css_class("volna-col-name-full")
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


def _empty_caption() -> Gtk.Box:
    """A caption-height band with no text (a continued section, D7)."""
    band = Gtk.Box()
    # The same classes as a real caption, minus its text: the border and the
    # min-height are what keep every column's first row on one line.
    band.add_css_class("volna-group-header")
    band.add_css_class("volna-col-head")
    band.add_css_class("volna-col-head-continued")

    return band


def _split(items: Sequence[ListingItem], size: int) -> list[tuple[ListingItem, ...]]:
    return [tuple(items[start : start + size]) for start in range(0, len(items), size)]


def _find_by_class(root: Gtk.Widget, css_class: str) -> Gtk.Widget | None:
    """The first *visible* widget of a class.

    A ``ListView`` pools its row widgets: an unmapped leftover keeps the size it
    had for another column, so measuring it would understate the row height.
    """
    child = root.get_first_child()
    while child is not None:
        if child.get_mapped() and child.has_css_class(css_class):
            return child

        found = _find_by_class(child, css_class)
        if found is not None:
            return found

        child = child.get_next_sibling()

    return None


class _ColumnsListView(Gtk.ListView):
    """A ``ListView`` that reports its allocated height: rows re-chunk on resize.

    GTK 4 has no ``size-allocate`` signal, so the height is read in the vfunc.
    """

    def __init__(self, *, on_height: Callable[[int], None], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._on_height = on_height
        self._height = 0

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        Gtk.ListView.do_size_allocate(self, width, height, baseline)
        if height == self._height:
            return

        self._height = height
        self._on_height(height)


def _setup_column(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
    column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(2))
    column.add_css_class("volna-col")
    item.set_child(column)
