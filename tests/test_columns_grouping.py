"""«Столбцы»: a section flows into as many height-bound columns as it needs."""

from __future__ import annotations

import pytest

pytest.importorskip("gi")

# GTK modules are imported inside the tests: importing them at module level
# would initialise GDK before the session Xvfb fixture sets DISPLAY.


def item(name: str):
    from volna.views.item import ListingItem

    return ListingItem(name, f"/d/{name}", "1 Б", "01.01.2026 00:00", False)


def view():
    from volna.views.columns import ColumnsView

    return ColumnsView(on_activate=lambda _item: None)


def section(items, header=None):
    from volna.views.base import Section

    return Section(items=items, header=header)


def test_grouped_sections_become_one_column_each(gtk_display) -> None:
    columns = view()

    columns.render(
        (
            section((item("a"), item("b")), header="Сегодня"),
            section((item("c"),), header="Вчера"),
        )
    )

    assert columns.store.get_n_items() == 2
    first = columns.store.get_item(0)
    second = columns.store.get_item(1)
    assert (first.header, [entry.name for entry in first.items]) == (
        "Сегодня",
        ["a", "b"],
    )
    assert (second.header, [entry.name for entry in second.items]) == (
        "Вчера",
        ["c"],
    )


def test_a_long_group_continues_in_the_next_column(gtk_display) -> None:
    """Without an allocated height the six-row cap still applies (D7)."""
    columns = view()
    from volna.views.columns import ROWS_PER_COLUMN

    entries = tuple(item(f"f{index}") for index in range(ROWS_PER_COLUMN + 3))

    columns.render((section(entries, header="Сегодня"),))

    assert columns.store.get_n_items() == 2
    first, second = _columns(columns)
    assert first.header == "Сегодня"
    assert first.count == ROWS_PER_COLUMN + 3
    assert len(first.items) == ROWS_PER_COLUMN
    assert second.header is None
    assert second.count is None
    assert second.continued is True
    assert [entry.name for entry in second.items] == ["f6", "f7", "f8"]


def test_a_short_band_moves_overflow_rows_to_the_right(
    gtk_display, project_theme
) -> None:
    """Rows that no longer fit the visible band continue to the right (D7)."""
    import time

    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    from volna.views.columns import ROWS_PER_COLUMN

    columns = view()
    entries = tuple(item(f"f{index:02d}") for index in range(20))
    columns.render((section(entries, header="Сегодня"),))

    window = Gtk.Window()
    window.set_default_size(900, 400)
    window.set_child(columns.widget)
    window.present()

    context = GLib.MainContext.default()

    def pump_until(condition, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            if condition():
                return True
            time.sleep(0.01)
        return False

    try:
        assert pump_until(
            lambda: (
                0 < columns._rows_per_column < ROWS_PER_COLUMN
                and columns.store.get_n_items() > 1
            )
        ), (columns._rows_per_column, columns.store.get_n_items())

        chunks = _columns(columns)
        assert [entry.name for chunk in chunks for entry in chunk.items] == [
            entry.name for entry in entries
        ]
        assert all(len(chunk.items) <= columns._rows_per_column for chunk in chunks)
        assert chunks[0].header == "Сегодня"
        assert chunks[0].count == len(entries)
        assert all(chunk.header is None for chunk in chunks[1:])

        # Nothing falls below the band: no vertical scrollbar, the overflow
        # went to the next columns to the right.
        adjustment = columns._scroller.get_vadjustment()
        assert adjustment is not None
        assert adjustment.get_upper() <= adjustment.get_page_size()
    finally:
        window.destroy()


def test_flat_listing_keeps_headerless_columns(gtk_display) -> None:
    from volna.views.columns import ROWS_PER_COLUMN

    columns = view()
    entries = tuple(item(f"f{index}") for index in range(ROWS_PER_COLUMN + 1))

    columns.render((section(entries),))

    assert columns.store.get_n_items() == 2
    assert [len(column.items) for column in _columns(columns)] == [
        ROWS_PER_COLUMN,
        1,
    ]
    assert all(column.header is None for column in _columns(columns))


def _walk(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root, name: str) -> list:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def test_continuation_columns_keep_the_header_band_and_align_rows(
    gtk_display, project_theme
) -> None:
    """A continued section reads as one header band: rows start at one height."""
    import time

    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    columns = view()
    entries = tuple(item(f"f{index:02d}") for index in range(20))
    columns.render((section(entries, header="Сегодня"),))

    window = Gtk.Window()
    window.set_default_size(900, 400)
    window.set_child(columns.widget)
    window.present()

    context = GLib.MainContext.default()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if 0 < columns._rows_per_column < 6 and columns.store.get_n_items() > 2:
            break
        time.sleep(0.01)

    try:
        # Every visible column of the section, including the continuations,
        # carries the caption band; only the first one has the text.
        bands = [
            band
            for band in _by_class(columns._list, "volna-col-head")
            if band.get_mapped()
        ]
        assert len(bands) >= 3
        captions = [
            band for band in bands if not band.has_css_class("volna-col-head-continued")
        ]
        assert len(captions) == 1

        # The first row of every column starts at the same y: the header band
        # keeps the continuations aligned with the captioned column.
        first_rows = []
        for column_widget in _by_class(columns._list, "volna-col"):
            if not column_widget.get_mapped():
                continue
            rows = [
                widget
                for widget in _by_class(column_widget, "volna-col-item")
                if widget.get_mapped()
            ]
            if rows:
                found, bounds = rows[0].compute_bounds(columns._list)
                assert found
                first_rows.append(round(bounds.get_y()))

        assert len(first_rows) >= 3, first_rows
        assert len(set(first_rows)) == 1, first_rows

        # The count stays next to the title instead of flying to the far edge.
        count = next(
            widget
            for widget in _by_class(columns._list, "volna-group-count")
            if widget.get_mapped()
        )
        caption = count.get_parent()
        found, bounds = count.compute_bounds(caption)
        assert found
        assert bounds.get_x() < caption.get_width() / 2, (
            bounds.get_x(),
            caption.get_width(),
        )
    finally:
        window.destroy()


def test_empty_grouped_listing_renders_nothing(gtk_display) -> None:
    columns = view()

    columns.render((section((), header="Сегодня"),))

    assert columns.store.get_n_items() == 0


def _columns(columns) -> list:
    return [
        columns.store.get_item(index) for index in range(columns.store.get_n_items())
    ]
