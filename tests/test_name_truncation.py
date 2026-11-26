"""Name truncation: middle ellipsis, real-clipping tooltips and full names.

The design (design/spec/07-decisions.md D29) keeps the tail of a clipped name
visible, puts the full name in a tooltip only while the name is really clipped,
and lets «Показывать имена целиком» lift the truncation in «Столбцы» and
«Значки». «Подробности» always truncate to the column width.

Widget tests build one view at a time under the shared Xvfb display; the mode is
driven directly, so these checks do not depend on the window's composition.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

pytest.importorskip("gi")

from volna.display import Grouping, ViewMode, ViewSettings  # noqa: E402
from volna.size import px  # noqa: E402

LONG_NAME = "Договор_2026_финальная_версия_3.pdf"
HUGE_NAME = (
    "презентация_" + "_".join(["финальная_редакция"] * 12) + "_10.20.30.dist.tar.gz"
)
SHORT_NAME = "a.txt"


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _labels(root: object, css_class: str) -> list[object]:
    """Non-empty labels under ``css_class`` (recycled cells keep hidden ones)."""
    found = []
    for widget in _by_class(root, css_class):
        getter = getattr(widget, "get_text", None)
        if getter is None or not getter():
            continue
        found.append(widget)
    return found


def _pump(seconds: float = 0.2) -> None:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


def _pump_until(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        _pump(0.02)

    return False


def _item(name: str):
    from volna.views.item import ListingItem

    return ListingItem(name, f"/tmp/listing/{name}", "1 КиБ", "23.11.2026 10:12", False)


@contextmanager
def _presented(
    view: object, *, width: int = 420, height: int = 400
) -> Iterator[object]:
    from gi.repository import Gtk

    window = Gtk.Window()
    window.set_default_size(width, height)
    window.set_child(view.widget)
    window.present()
    try:
        assert _pump_until(lambda: window.get_mapped() and view.widget.get_width() > 0)
        _pump(0.3)
        yield window
    finally:
        window.destroy()


def _mode_of(label: object) -> object:
    return label.get_ellipsize()


# -- the shared NameLabel -----------------------------------------------------


def test_name_label_ellipsizes_in_the_middle(gtk_display) -> None:
    from gi.repository import Pango

    from volna.views.name_label import NameLabel

    label = NameLabel()
    label.set_name(LONG_NAME)

    assert label.get_ellipsize() is Pango.EllipsizeMode.MIDDLE
    assert label.get_text() == LONG_NAME


def test_name_label_tooltip_follows_real_clipping(gtk_display) -> None:
    from gi.repository import Gtk, Pango

    from volna.views.name_label import NameLabel

    window = Gtk.Window()
    window.set_default_size(200, 100)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    long = NameLabel()
    long.set_name(LONG_NAME)
    long.set_size_request(80, -1)
    short = NameLabel()
    short.set_name(SHORT_NAME)
    short.set_size_request(80, -1)
    box.append(long)
    box.append(short)
    window.set_child(box)
    window.present()
    try:
        assert _pump_until(lambda: long.get_width() > 0 and short.get_width() > 0)
        _pump(0.2)

        assert long.get_tooltip_text() == LONG_NAME
        assert short.get_tooltip_text() is None
        assert long.get_layout().is_ellipsized()
        assert not short.get_layout().is_ellipsized()
        assert long.get_ellipsize() is Pango.EllipsizeMode.MIDDLE
    finally:
        window.destroy()


# -- «Подробности» ------------------------------------------------------------


def _details_view():
    from volna.views.details import DetailsView

    return DetailsView(on_activate=lambda _item: None)


def test_details_always_truncates_in_the_middle(gtk_display) -> None:
    from gi.repository import Pango

    from volna.views.base import Section

    view = _details_view()
    long_item = _item(LONG_NAME)
    short_item = _item(SHORT_NAME)
    view.render((Section(items=(long_item, short_item)),))

    with _presented(view, width=380):
        labels = _labels(view.widget, "volna-dt-name")
        assert [label.get_text() for label in labels] == [LONG_NAME, SHORT_NAME]
        assert all(_mode_of(label) is Pango.EllipsizeMode.MIDDLE for label in labels)

        # The table ignores the setting: its name column truncates regardless.
        view.apply(ViewSettings(show_full_names=True))
        _pump(0.3)
        labels = _labels(view.widget, "volna-dt-name")
        assert all(_mode_of(label) is Pango.EllipsizeMode.MIDDLE for label in labels)
        assert labels[0].get_max_width_chars() == -1


def test_details_tooltip_only_when_the_name_is_clipped(gtk_display) -> None:
    from volna.views.base import Section

    view = _details_view()
    long_item = _item(LONG_NAME)
    short_item = _item(SHORT_NAME)
    view.render((Section(items=(long_item, short_item)),))

    with _presented(view, width=380):
        assert _pump_until(
            lambda: (
                [
                    label.get_tooltip_text()
                    for label in _labels(view.widget, "volna-dt-name")
                ]
                == [LONG_NAME, None]
            )
        ), [label.get_tooltip_text() for label in _labels(view.widget, "volna-dt-name")]


def test_details_keeps_names_with_unusual_shapes(gtk_display) -> None:
    from volna.views.base import Section

    names = ("Папка без расширения", ".tar.gz", "v1.2.3", "archive.tar.gz")
    view = _details_view()
    view.render((Section(items=tuple(_item(name) for name in names)),))

    with _presented(view):
        texts = [label.get_text() for label in _labels(view.widget, "volna-dt-name")]

    assert texts == list(names)


# -- «Столбцы» ----------------------------------------------------------------


def _columns_view(settings: ViewSettings):
    from volna.views.columns import ColumnsView

    view = ColumnsView(on_activate=lambda _item: None)
    view.apply(settings)
    return view


def test_columns_cut_mode_keeps_the_28_char_budget(gtk_display) -> None:
    from gi.repository import Pango

    from volna.views.base import Section

    view = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS))
    view.render((Section(items=(_item(LONG_NAME),)),))

    with _presented(view):
        labels = _labels(view.widget, "volna-col-name")
        assert labels
        label = labels[0]
        assert label.get_ellipsize() is Pango.EllipsizeMode.MIDDLE
        assert label.get_max_width_chars() == 28
        assert label.get_lines() == 2
        assert label.get_wrap()
        assert label.get_text() == LONG_NAME


def test_columns_full_mode_keeps_the_width_but_allows_four_lines(
    gtk_display,
) -> None:
    from gi.repository import Pango

    from volna.views.base import Section

    view = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS, show_full_names=True))
    view.render((Section(items=(_item(LONG_NAME),)),))

    with _presented(view):
        label = _labels(view.widget, "volna-col-name")[0]
        assert label.get_ellipsize() is Pango.EllipsizeMode.MIDDLE
        assert label.get_max_width_chars() == 28
        assert label.get_lines() == 4
        assert label.get_text() == LONG_NAME


def test_columns_cut_mode_width_stays_in_the_design_range(
    gtk_display, project_theme
) -> None:
    from volna.views.base import Section

    view = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS))
    view.render((Section(items=(_item(LONG_NAME), _item("b.txt"))),))

    with _presented(view, width=900):
        columns = _by_class(view.widget, "volna-col")
        assert columns
        # The design range for a cut column is 190..300 base px.
        for column in columns:
            assert px(190) <= column.get_width() <= px(300), column.get_width()


def test_columns_full_mode_keeps_the_column_in_the_design_range(
    gtk_display, project_theme
) -> None:
    from volna.views.base import Section

    full = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS, show_full_names=True))
    full.render((Section(items=(_item(LONG_NAME), _item("b.txt"))),))

    with _presented(full, width=900):
        columns = _by_class(full.widget, "volna-col")
        assert columns
        for column in columns:
            assert px(190) <= column.get_width() <= px(300), column.get_width()


def test_columns_cut_mode_shows_two_lines_before_clipping(gtk_display) -> None:
    from volna.views.base import Section

    # About two lines at the 28-char budget: «резать» shows it whole.
    two_lines = "Договор_2026_финальная_версия_3_подписанный.pdf"
    view = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS))
    view.render((Section(items=(_item(two_lines),)),))

    with _presented(view):
        label = _labels(view.widget, "volna-col-name")[0]
        layout = label.get_layout()
        assert layout is not None
        assert 1 < layout.get_line_count() <= 2, layout.get_line_count()
        assert not layout.is_ellipsized()
        assert label.get_tooltip_text() is None


def test_columns_cut_mode_clips_the_third_line_and_shows_the_tooltip(
    gtk_display,
) -> None:
    from volna.views.base import Section

    # More than the two lines «резать» allows; «целиком» shows four.
    three_lines = "Договор_" + "финальная_версия_" * 4 + "3.pdf"
    cut = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS))
    full = _columns_view(ViewSettings(view_mode=ViewMode.COLUMNS, show_full_names=True))
    cut.render((Section(items=(_item(three_lines),)),))
    full.render((Section(items=(_item(three_lines),)),))

    with _presented(cut):
        label = _labels(cut.widget, "volna-col-name")[0]
        layout = label.get_layout()
        assert layout is not None
        assert layout.is_ellipsized()
        assert label.get_tooltip_text() == three_lines

    with _presented(full):
        label = _labels(full.widget, "volna-col-name")[0]
        layout = label.get_layout()
        assert layout is not None
        assert not layout.is_ellipsized()
        assert label.get_tooltip_text() is None


# -- «Значки» -----------------------------------------------------------------


def _icons_view(settings: ViewSettings):
    from volna.views.icons import IconsView

    view = IconsView(on_activate=lambda _item: None)
    view.apply(settings)
    return view


def test_icons_cut_mode_reserves_two_lines(gtk_display) -> None:
    from gi.repository import Pango

    from volna.views.base import Section

    view = _icons_view(ViewSettings(view_mode=ViewMode.ICONS, grouping=Grouping.NONE))
    view.render((Section(items=(_item(LONG_NAME),)),))

    with _presented(view, width=900):
        labels = _labels(view.widget, "volna-icons-name")
        assert labels
        label = labels[0]
        assert label.get_lines() == 2
        assert label.get_ellipsize() is Pango.EllipsizeMode.MIDDLE
        assert label.get_text() == LONG_NAME


def test_icons_full_mode_allows_four_lines(gtk_display) -> None:
    from volna.views.base import Section

    view = _icons_view(
        ViewSettings(
            view_mode=ViewMode.ICONS, grouping=Grouping.NONE, show_full_names=True
        )
    )
    view.render((Section(items=(_item(LONG_NAME),)),))

    with _presented(view, width=900):
        label = _labels(view.widget, "volna-icons-name")[0]

    assert label.get_lines() == 4


def test_icons_tooltip_appears_when_the_name_is_really_clipped(gtk_display) -> None:
    from volna.views.base import Section

    view = _icons_view(
        ViewSettings(
            view_mode=ViewMode.ICONS, grouping=Grouping.NONE, show_full_names=True
        )
    )
    view.render((Section(items=(_item(HUGE_NAME), _item(SHORT_NAME))),))

    with _presented(view, width=900):
        assert _pump_until(
            lambda: (
                [
                    label.get_tooltip_text()
                    for label in _labels(view.widget, "volna-icons-name")
                ]
                == [HUGE_NAME, None]
            )
        ), [
            label.get_tooltip_text()
            for label in _labels(view.widget, "volna-icons-name")
        ]


def test_icons_full_mode_tile_width_grows_to_the_ceiling(gtk_display) -> None:
    """Grouped tiles widen before the name gets its fourth line (D29)."""
    from volna.views.base import Section

    cut = _icons_view(ViewSettings(view_mode=ViewMode.ICONS))
    full = _icons_view(ViewSettings(view_mode=ViewMode.ICONS, show_full_names=True))
    section = Section(
        items=tuple(_item(f"file{index:03d}.txt") for index in range(4)),
        header="Сегодня",
    )
    cut.render((section,))
    full.render((section,))

    with _presented(cut, width=1200, height=600):
        cut_width = cut._tile_width

    with _presented(full, width=1200, height=600):
        full_width = full._tile_width
        assert _pump_until(lambda: full._list.get_width() > 0)
        _pump(0.3)

    assert px(150) <= cut_width <= px(178), cut_width
    assert cut_width < full_width <= px(240), (cut_width, full_width)


def test_icons_full_mode_keeps_the_grid_equal_width(gtk_display) -> None:
    from volna.views.base import Section

    view = _icons_view(ViewSettings(view_mode=ViewMode.ICONS, show_full_names=True))
    view.render(
        (
            Section(
                items=tuple(_item(f"file{index:03d}.txt") for index in range(4)),
                header="Сегодня",
            ),
        )
    )

    with _presented(view, width=1200, height=600):
        tiles = _labels(view.widget, "volna-icons-name")
        widths = {tile.get_parent().get_width() for tile in tiles}
        assert len(widths) == 1, widths
        assert max(widths) <= px(240)


def test_icons_flat_full_mode_uses_width_driven_bands(
    gtk_display, project_theme
) -> None:
    """The flat grid cannot cap a stretched tile, so full names use bands."""
    from volna.views.base import Section

    view = _icons_view(
        ViewSettings(
            view_mode=ViewMode.ICONS, grouping=Grouping.NONE, show_full_names=True
        )
    )
    view.render(
        (Section(items=tuple(_item(f"file{index:03d}.txt") for index in range(5))),)
    )

    with _presented(view, width=1200, height=600):
        assert view._scroller.get_child() is view._list
        assert view.store is view._rows
        assert px(150) <= view._tile_width <= px(240), view._tile_width

        widths = {
            label.get_parent().get_width()
            for label in _labels(view.widget, "volna-icons-name")
        }
        assert len(widths) == 1, widths
        assert max(widths) <= px(240)

    cut = _icons_view(ViewSettings(view_mode=ViewMode.ICONS, grouping=Grouping.NONE))
    cut.render(
        (Section(items=tuple(_item(f"file{index:03d}.txt") for index in range(5))),)
    )
    with _presented(cut, width=1200, height=600):
        assert cut._scroller.get_child() is cut._grid
