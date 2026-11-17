"""Group collapse: session-level folding of date groups (design/grouping.md §12).

Decisions under test (owner, 2026-11-17): collapse works in «Подробности» and
«Значки», «Столбцы» keep static captions; the state lives on the tab for the
session only (not in the settings file) and is cleared on navigation; the
header offers toggle, «Свернуть остальные», «Свернуть все» and «Развернуть
все».

GTK and ``volna`` modules are imported inside the tests: importing them at
module level would initialise GDK before the session Xvfb fixture sets
DISPLAY (see tests/conftest.py).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.core import (  # noqa: E402
    Group,
    GroupBucket,
    ScanState,  # noqa: E402
)
from volna.display import (  # noqa: E402
    GroupAction,
    MemoryViewSettingsStore,
    ViewMode,
    ViewSettings,
    group_key,
)

_DAY = 86_400.0


# -- helpers (patterns from tests/test_view_modes.py) --------------------------


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _pump(seconds: float = 0.2) -> None:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)


def _pump_until(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        _pump(0.02)

    return False


def _make_listing(root: Path) -> None:
    now = time.time()
    entries = {
        "today.txt": 0.0,
        "yesterday.txt": 1.0,
        "older.txt": 10.0,
    }
    for name, age in entries.items():
        path = root / name
        path.write_text("x", encoding="utf-8")
        stamp = now - age * _DAY - 60
        import os

        os.utime(path, (stamp, stamp))


def _sections(tab) -> tuple:
    return tab._sections()


def _captions(root: object) -> list[str]:
    return [
        label.get_text()
        for label in _by_class(root, "volna-group-title")
        if label.get_text()
    ]


def _summaries(root: object) -> list[str]:
    return [
        label.get_text()
        for label in _by_class(root, "volna-group-stats")
        if label.get_text()
    ]


def _window(path: Path, *, settings: ViewSettings | None = None):
    from volna.window import MainWindow

    return MainWindow(
        start_path=path,
        initial_settings=settings or ViewSettings(),
        settings_store=MemoryViewSettingsStore(),
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()


# -- group_key (D12) -----------------------------------------------------------


def test_group_key_is_semantic_and_session_stable() -> None:
    local_day = time.mktime((2026, 11, 11, 0, 0, 0, 0, 0, -1))

    assert group_key(Group(GroupBucket.TODAY, [])) == "today"
    assert group_key(Group(GroupBucket.YESTERDAY, [])) == "yesterday"
    assert group_key(Group(GroupBucket.OLDER, [])) == "older"
    assert group_key(Group(GroupBucket.UNKNOWN, [])) == "unknown"
    week = Group(GroupBucket.THIS_WEEK, [], day=local_day)
    assert group_key(week) == "week:2026-11-11"
    assert group_key(week) == group_key(Group(GroupBucket.THIS_WEEK, [], day=local_day))


# -- header widget (D14) --------------------------------------------------------


def test_header_toggles_from_its_chevron_and_its_own_api(gtk_display) -> None:
    from volna.views.group_header import GroupHeader

    actions: list[tuple[str, GroupAction]] = []
    header = GroupHeader("today")
    header.set_caption("Сегодня", "1 папок · 2 файлов (5 Б)")
    header.set_action(lambda key, action: actions.append((key, action)))
    header.set_collapsed(True)

    header._chevron.emit("clicked")
    _pump(0.05)
    assert actions == [("today", GroupAction.TOGGLE)]

    # The row-level toggle is the view's click routing; it calls this.
    header.toggle()
    assert actions == [
        ("today", GroupAction.TOGGLE),
        ("today", GroupAction.TOGGLE),
    ]


def test_header_menu_opens_with_state_sensitive_items(gtk_display) -> None:
    from gi.repository import Gtk

    from volna.views.group_header import GroupHeader

    actions: list[tuple[str, GroupAction]] = []
    header = GroupHeader("today")
    header.set_caption("Сегодня", "1 папок · 2 файлов (5 Б)")
    header.set_action(lambda key, action: actions.append((key, action)))

    # A popover needs a realized parent to pop up: show the header in a window.
    window = Gtk.Window()
    window.set_child(header)
    window.present()
    _pump(0.2)

    # Sensitivity is data from the view (D14). Two groups, one collapsed:
    # «Свернуть все» has nothing to do (nothing is expanded); «Развернуть все»
    # does have something to expand.
    header.set_menu_state(
        others_collapsible=True, any_expanded=False, any_collapsed=True
    )
    header.open_menu()
    _pump(0.1)
    assert header._menu.get_visible()
    assert header._collapse_others.get_sensitive()
    assert not header._collapse_all.get_sensitive(), "something is collapsed"
    assert header._expand_all.get_sensitive()

    header._collapse_all.emit("clicked")
    _pump(0.05)
    assert actions == [("today", GroupAction.COLLAPSE_ALL)]
    assert not header._menu.get_visible(), "choosing an item closes the menu"

    header.set_menu_state(
        others_collapsible=False, any_expanded=True, any_collapsed=False
    )
    header.open_menu()
    _pump(0.1)
    assert not header._collapse_others.get_sensitive(), "a single group"
    assert header._collapse_all.get_sensitive(), "everything is expanded"
    assert not header._expand_all.get_sensitive()

    window.destroy()


def test_header_menu_is_a_plain_popover(gtk_display) -> None:
    """The caption menu must not re-use GtkPopoverMenu's child internals.

    ``Gtk.PopoverMenu`` builds a ScrolledWindow → Viewport → Stack chain for
    its menu model APIs; replacing its child with custom buttons left that
    chain missing, so every open/close logged GTK_IS_SCROLLED_WINDOW /
    GTK_IS_VIEWPORT / GTK_IS_STACK criticals. The menu is a plain popover now:
    opening it must not emit a GTK critical.
    """
    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    from volna.views.group_header import GroupHeader

    header = GroupHeader("today")
    header.set_caption("Сегодня", "1 папок · 2 файлов (5 Б)")
    header.set_action(lambda key, action: None)

    window = Gtk.Window()
    window.set_child(header)
    window.present()
    _pump(0.2)

    assert not isinstance(header._menu, Gtk.PopoverMenu)

    criticals: list[str] = []

    def on_critical(_domain: str, _level: int, message: str, _data) -> None:
        criticals.append(message)

    handler = GLib.log_set_handler(
        "Gtk", GLib.LogLevelFlags.LEVEL_CRITICAL, on_critical, None
    )
    try:
        header.open_menu()
        _pump(0.1)
        header._menu.popdown()
        _pump(0.1)
        header.open_menu()
        _pump(0.1)
    finally:
        header._menu.popdown()
        GLib.log_remove_handler("Gtk", handler)
        window.destroy()

    assert criticals == []


# -- view rendering (D13) --------------------------------------------------------


def test_details_view_hides_the_collapsed_groups_items(gtk_display) -> None:
    from volna.views.base import Section
    from volna.views.details import DetailsView, GroupRow
    from volna.views.item import ListingItem

    view = DetailsView(on_activate=lambda _item: None)
    items = tuple(
        ListingItem(name, f"/d/{name}", "1 Б", "01.01.2026 00:00", False)
        for name in ("a.txt", "b.txt")
    )

    view.render(
        (
            Section(items=items, header="Сегодня", key="today", collapsed=False),
            Section(items=items[:1], header="Вчера", key="yesterday", collapsed=True),
        )
    )

    from volna.views.item import ListingItem as Item

    rows = [view.store.get_item(i) for i in range(view.store.get_n_items())]
    captions = [row for row in rows if isinstance(row, GroupRow)]
    names = [row.name for row in rows if isinstance(row, Item)]

    assert [caption.label for caption in captions] == ["Сегодня", "Вчера"]
    assert captions[1].collapsed
    assert names == ["a.txt", "b.txt"], "yesterday's items are hidden"


def test_icons_view_hides_the_collapsed_groups_tiles(gtk_display) -> None:
    from gi.repository import Gtk

    from volna.views.base import Section
    from volna.views.icons import HeaderRow, IconsView, TileRow
    from volna.views.item import ListingItem

    view = IconsView(on_activate=lambda _item: None)
    items = tuple(
        ListingItem(f"f{index}.txt", f"/d/f{index}", "1 Б", "01.01.2026 00:00", False)
        for index in range(4)
    )

    # The tile count per band follows the view's width, so it has to be
    # presented: an unallocated view lays out one tile per band.
    window = Gtk.Window()
    window.set_default_size(900, 900)
    window.set_child(view.widget)
    window.present()
    _pump(0.3)
    try:
        view.render(
            (
                Section(items=items, header="Сегодня", key="today", collapsed=True),
                Section(
                    items=items[:2], header="Вчера", key="yesterday", collapsed=False
                ),
            )
        )
        # The first layout re-chunks in an idle once the width is known.
        _pump(0.4)

        rows = [view.store.get_item(index) for index in range(view.store.get_n_items())]
        captions = [row for row in rows if isinstance(row, HeaderRow)]
        bands = [row for row in rows if isinstance(row, TileRow)]

        assert [caption.label for caption in captions] == ["Сегодня", "Вчера"]
        assert captions[0].collapsed
        assert [len(band.items) for band in bands] == [2], "today's tiles are hidden"
    finally:
        window.destroy()


def test_columns_view_keeps_static_captions(gtk_display) -> None:
    from volna.views.base import Section
    from volna.views.columns import ColumnsView
    from volna.views.item import ListingItem

    view = ColumnsView(on_activate=lambda _item: None)
    items = (ListingItem("a.txt", "/d/a.txt", "1 Б", "01.01.2026 00:00", False),)

    view.render((Section(items=items, header="Сегодня", key="today", collapsed=True),))

    assert view.store.get_n_items() == 1
    column = view.store.get_item(0)
    assert [entry.name for entry in column.items] == ["a.txt"], (
        "«Столбцы» do not collapse (design/grouping.md §12)"
    )
    assert len(_by_class(view.widget, "volna-group-chevron")) == 0


# -- tab state machine (D11, D13, D14) --------------------------------------------


def _tab(tmp_path: Path, *, view_mode: ViewMode = ViewMode.DETAILS):
    from volna.tab import DirectoryTab

    settings = ViewSettings(view_mode=view_mode)
    return DirectoryTab(
        tmp_path,
        on_change=lambda _tab: None,
        on_navigate=lambda _tab: None,
        view_settings=settings,
    )


def test_tab_toggles_a_group_without_rescanning(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    tab = _tab(tmp_path)
    tab.ensure_loaded()
    _pump_until(lambda: tab.model.state is ScanState.READY)
    _pump(0.3)

    generation = tab.model.generation
    state = tab.model.state
    counters = tab.model.counters()

    keys = [section.key for section in _sections(tab)]
    assert keys == ["today", "yesterday", "older"]

    tab._on_group_action("today", GroupAction.TOGGLE)

    assert tab.model.generation == generation, "collapse must not rescan"
    assert tab.model.state is state
    assert tab.model.counters() == counters
    assert [section.collapsed for section in _sections(tab)] == [True, False, False]

    tab._on_group_action("today", GroupAction.TOGGLE)
    assert [section.collapsed for section in _sections(tab)] == [False, False, False]


def test_tab_collapse_others_all_and_expand_all(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    tab = _tab(tmp_path)
    tab.ensure_loaded()
    _pump_until(lambda: tab.model.state is ScanState.READY)
    _pump(0.3)

    tab._on_group_action("today", GroupAction.COLLAPSE_OTHERS)
    assert [section.collapsed for section in _sections(tab)] == [False, True, True]

    tab._on_group_action("today", GroupAction.EXPAND_ALL)
    assert all(not section.collapsed for section in _sections(tab))

    tab._on_group_action("today", GroupAction.COLLAPSE_ALL)
    assert all(section.collapsed for section in _sections(tab))


def test_tab_collapse_survives_a_mode_switch_but_not_navigation(
    gtk_display, tmp_path: Path
) -> None:
    from volna.display import ViewMode as Mode

    _make_listing(tmp_path)
    tab = _tab(tmp_path)
    tab.ensure_loaded()
    _pump_until(lambda: tab.model.state is ScanState.READY)
    _pump(0.3)

    tab._on_group_action("yesterday", GroupAction.TOGGLE)
    tab.update_view_settings(view_mode=Mode.ICONS)
    assert tab.view_mode is Mode.ICONS
    assert [section.collapsed for section in _sections(tab)] == [False, True, False], (
        "the collapse set is shared by the collapsible modes (D11)"
    )

    tab.update_view_settings(view_mode=Mode.COLUMNS)
    assert all(not section.collapsed for section in _sections(tab)), (
        "«Столбцы» never show collapsed groups"
    )

    tab.update_view_settings(view_mode=Mode.DETAILS)
    assert [section.collapsed for section in _sections(tab)] == [False, True, False]

    # A same-path navigate is a no-op (guard clause); navigating elsewhere
    # drops the collapsed set with the listing that owned it.
    other = tmp_path / "sub"
    other.mkdir()
    tab.navigate(other)
    assert all(not section.collapsed for section in _sections(tab)), (
        "navigation clears the session collapse set (D11)"
    )


# -- system: the real window (D14) ------------------------------------------------


def test_window_collapses_a_group_from_its_header(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)

        def headers() -> list:
            return _by_class(tab._active_view.widget, "volna-group-chevron")

        assert _pump_until(lambda: len(headers()) >= 3)

        before = len(
            [
                row
                for row in _by_class(tab._active_view.widget, "volna-dt-name")
                if getattr(row, "get_text", lambda: "")()
            ]
        )
        headers()[0].emit("clicked")

        # The toggled group's items disappear; its caption and count stay.
        def names_shown() -> int:
            return len(
                [
                    row
                    for row in _by_class(tab._active_view.widget, "volna-dt-name")
                    if getattr(row, "get_text", lambda: "")()
                ]
            )

        assert _pump_until(lambda: names_shown() < before), (
            "collapsing hides the group's rows"
        )

        assert "today" in tab._collapsed_groups

        headers()[0].emit("clicked")
        assert _pump_until(lambda: "today" not in tab._collapsed_groups)
    finally:
        _close(window)


def test_window_menu_state_follows_the_whole_group_set(
    gtk_display, tmp_path: Path
) -> None:
    """Right click offers only what the current group set can do (D14)."""
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)

        def first_header() -> object:
            chevrons = _by_class(tab._active_view.widget, "volna-group-chevron")
            assert chevrons
            return chevrons[0].get_parent()

        assert _pump_until(
            lambda: len(_by_class(tab._active_view.widget, "volna-group-chevron")) >= 3
        )

        header = first_header()
        header.open_menu()
        _pump(0.2)
        try:
            assert header._collapse_others.get_sensitive(), "more than one group"
            assert header._collapse_all.get_sensitive(), "everything is expanded"
            assert not header._expand_all.get_sensitive()
        finally:
            header._menu.popdown()
            _pump(0.1)

        tab._on_group_action("today", GroupAction.COLLAPSE_ALL)
        assert _pump_until(lambda: tab._collapsed_groups == tab._group_keys())
        # The refresh is scheduled: wait for the rebound captions to show it.
        assert _pump_until(lambda: first_header()._collapsed)

        header = first_header()
        header.open_menu()
        _pump(0.2)
        try:
            assert not header._collapse_all.get_sensitive(), "everything is collapsed"
            assert header._expand_all.get_sensitive(), "there is something to expand"
        finally:
            header._menu.popdown()
            _pump(0.1)
    finally:
        _close(window)


def test_details_strip_opens_the_menu_from_any_cell(
    gtk_display, tmp_path: Path
) -> None:
    """A group strip spans the table: right click works outside the name cell."""
    from gi.repository import Gtk

    from volna.views.details import _NumericCell

    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)
        assert _pump_until(
            lambda: len(_by_class(tab._active_view.widget, "volna-group-chevron")) >= 3
        )

        view = tab._active_view
        root = view._click_root

        def strip_point() -> tuple[int, int] | None:
            """A point over a number cell (not the name cell) of a group strip."""
            for y in range(0, root.get_height(), 4):
                for x in range(0, root.get_width(), 24):
                    node = root.pick(x, y, Gtk.PickFlags.DEFAULT)
                    if isinstance(node, _NumericCell) and node.group_key == "today":
                        return x, y
            return None

        assert _pump_until(lambda: strip_point() is not None)
        x, y = strip_point()
        header = view._headers["today"]

        assert view._handle_group_press(3, float(x), float(y))
        _pump(0.2)
        try:
            assert header._menu.get_visible(), "the strip's header menu opened"
        finally:
            header._menu.popdown()
            _pump(0.1)

        # The name cell is the caption widget itself: a left click toggles.
        title_point = None
        for y in range(0, root.get_height(), 4):
            for x in range(0, root.get_width(), 24):
                node = root.pick(x, y, Gtk.PickFlags.DEFAULT)
                if isinstance(node, Gtk.Widget) and node.has_css_class(
                    "volna-group-title"
                ):
                    title_point = (x, y)
                    break
            if title_point is not None:
                break

        assert title_point is not None
        x, y = title_point
        assert view._handle_group_press(1, float(x), float(y))
        assert _pump_until(lambda: "today" in tab._collapsed_groups)
    finally:
        _close(window)


def test_icons_header_menu_opens_from_a_right_click(
    gtk_display, tmp_path: Path
) -> None:
    """«Значки» route the same caption clicks as the table (D14)."""
    from gi.repository import Gtk

    _make_listing(tmp_path)
    window = _window(tmp_path, settings=ViewSettings(view_mode=ViewMode.ICONS))
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)
        assert _pump_until(
            lambda: len(_by_class(tab._active_view.widget, "volna-group-chevron")) >= 3
        )

        view = tab._active_view
        root = view._click_root

        point = None
        for y in range(0, root.get_height(), 4):
            for x in range(0, root.get_width(), 24):
                node = root.pick(x, y, Gtk.PickFlags.DEFAULT)
                if isinstance(node, Gtk.Widget) and node.has_css_class(
                    "volna-group-title"
                ):
                    point = (x, y)
                    break
            if point is not None:
                break

        assert point is not None
        x, y = point
        header = view._headers["today"]

        assert view._handle_group_press(3, float(x), float(y))
        _pump(0.2)
        try:
            assert header._menu.get_visible(), "the caption menu opened in «Значки»"
        finally:
            header._menu.popdown()
            _pump(0.1)
    finally:
        _close(window)


def test_right_click_outside_a_caption_is_ignored(gtk_display, tmp_path: Path) -> None:
    """Only group captions consume a right click; rows keep their own handling."""

    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)
        assert _pump_until(
            lambda: len(_by_class(tab._active_view.widget, "volna-group-chevron")) >= 3
        )

        import gi

        gi.require_version("Graphene", "1.0")
        from gi.repository import Graphene

        view = tab._active_view
        root = view._click_root

        def center_in_root(widget: object) -> tuple[float, float]:
            ok, rect = widget.compute_bounds(view.widget)
            assert ok
            middle = Graphene.Point().init(
                rect.origin.x + rect.size.width / 2,
                rect.origin.y + rect.size.height / 2,
            )
            ok, point = view.widget.compute_point(root, middle)
            assert ok
            return point.x, point.y

        def row_label() -> object | None:
            for label in _by_class(view.widget, "volna-dt-name"):
                if label.get_text() == "today.txt":
                    return label
            return None

        assert _pump_until(lambda: row_label() is not None)
        x, y = center_in_root(row_label())
        assert not view._handle_group_press(3, x, y), (
            "a regular row must not open a group menu"
        )

        # The number cells of a regular row are empty too, and they must not
        # resolve to the caption above them.
        def regular_number_cell() -> object | None:
            for cell in _by_class(view.widget, "volna-dt-num"):
                if cell.group_key is None and cell.get_mapped():
                    return cell
            return None

        assert _pump_until(lambda: regular_number_cell() is not None)
        cell = regular_number_cell()
        x, y = center_in_root(cell)
        assert not cell.has_css_class("volna-dt-group"), "not a strip cell"
        assert not view._handle_group_press(3, x, y), (
            "an empty number cell of a regular row belongs to no group"
        )

        # An empty spot under the last caption is nobody's click either.
        assert not view._handle_group_press(3, 5.0, float(root.get_height() - 5))
    finally:
        _close(window)


def test_icons_right_click_on_a_tile_is_ignored(gtk_display, tmp_path: Path) -> None:
    """A tile is not a caption: the group menu stays closed over the grid."""
    import gi

    gi.require_version("Graphene", "1.0")
    from gi.repository import Graphene

    _make_listing(tmp_path)
    window = _window(tmp_path, settings=ViewSettings(view_mode=ViewMode.ICONS))
    try:
        window.present()
        tab = window._active_tab
        assert _pump_until(lambda: tab.model.state is ScanState.READY)
        _pump(0.4)
        assert _pump_until(
            lambda: len(_by_class(tab._active_view.widget, "volna-group-chevron")) >= 3
        )

        view = tab._active_view
        root = view._click_root

        def tile_name() -> object | None:
            for label in _by_class(view.widget, "volna-icons-name"):
                if label.get_text() == "today.txt" and label.get_mapped():
                    return label
            return None

        assert _pump_until(lambda: tile_name() is not None)
        label = tile_name()
        ok, rect = label.compute_bounds(view.widget)
        assert ok
        middle = Graphene.Point().init(
            rect.origin.x + rect.size.width / 2, rect.origin.y + rect.size.height / 2
        )
        ok, point = view.widget.compute_point(root, middle)
        assert ok

        assert not view._handle_group_press(3, point.x, point.y)
        assert not any(header._menu.get_visible() for header in view._headers.values())
    finally:
        _close(window)
