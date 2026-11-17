"""Grouped «Столбцы»: one column per date group (design/grouping.md D7)."""

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


def test_grouped_sections_are_not_chunked(gtk_display) -> None:
    columns = view()
    from volna.views.columns import ROWS_PER_COLUMN

    entries = tuple(item(f"f{index}") for index in range(ROWS_PER_COLUMN + 3))

    columns.render((section(entries, header="Сегодня"),))

    assert columns.store.get_n_items() == 1
    assert len(columns.store.get_item(0).items) == ROWS_PER_COLUMN + 3


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


def test_empty_grouped_listing_renders_nothing(gtk_display) -> None:
    columns = view()

    columns.render((section((), header="Сегодня"),))

    assert columns.store.get_n_items() == 0


def _columns(columns) -> list:
    return [
        columns.store.get_item(index) for index in range(columns.store.get_n_items())
    ]
