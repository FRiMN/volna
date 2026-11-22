"""Window behavior: tab lifecycle, the main menu and the visible panes.

The window needs a display, so the module runs under a private Xvfb and skips
when Xvfb or GTK4 is unavailable.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.size import px  # noqa: E402


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _path_label(window: object) -> str:
    labels = _by_class(window, "volna-path-label")
    assert len(labels) == 1
    return labels[0].get_text()


def _tabs(window: object) -> list[object]:
    return _by_class(window, "volna-tab")


def _details_view(window: object):
    """The details-mode view of the active tab (the dispatcher owns all modes)."""
    from volna.display import ViewMode

    return window._active_tab._views[ViewMode.DETAILS]


def _active_tabs(window: object) -> list[object]:
    return [tab for tab in _tabs(window) if tab.has_css_class("is-active")]


def _close_buttons(window: object) -> list[object]:
    return _by_class(window, "volna-tab-close")


def _menu_item(window: object, action: str):
    for item in _by_class(window, "volna-menu-item"):
        if item.get_action_name() == action:
            return item
    raise AssertionError(f"menu item for action {action!r} not found")


def _main_window(path: Path):
    from volna.display import MemoryViewSettingsStore, ViewSettings
    from volna.window import MainWindow

    return MainWindow(
        start_path=path,
        initial_settings=ViewSettings(),
        settings_store=MemoryViewSettingsStore(),
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()


def _status_text(window: object) -> str:
    return _by_class(window, "volna-status")[0].get_text()


def test_window_starts_with_one_tab(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        assert len(_tabs(window)) == 1
        assert _active_tabs(window) == _tabs(window)
        assert _path_label(window) == str(tmp_path)

        close_buttons = _close_buttons(window)
        assert len(close_buttons) == 1
        assert not close_buttons[0].get_visible()
    finally:
        _close(window)


def test_main_menu_has_new_tab_item(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        assert _menu_item(window, "win.new-tab") is not None
        assert _menu_item(window, "win.close-tab") is not None

        label = _by_class(_menu_item(window, "win.new-tab"), "volna-menu-label")[0]
        assert label.get_text() == "Новая вкладка"
    finally:
        _close(window)


def test_new_tab_action_adds_and_activates_tab(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        assert window.activate_action("win.new-tab", None) is True

        tabs = _tabs(window)
        assert len(tabs) == 2
        assert _active_tabs(window) == [tabs[-1]]
        assert _path_label(window) == str(tmp_path)

        assert all(button.get_visible() for button in _close_buttons(window))
    finally:
        _close(window)


def test_new_tab_opens_the_active_directory(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window = _main_window(first)
    try:
        window._open_tab(second)
        window.activate_action("win.new-tab", None)

        assert len(_tabs(window)) == 3
        assert _path_label(window) == str(second)
        assert window._tabs[-1].path == second
    finally:
        _close(window)


def test_close_action_closes_active_tab_and_keeps_one_tab(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.activate_action("win.new-tab", None)
        window.activate_action("win.new-tab", None)
        assert len(_tabs(window)) == 3

        assert window.activate_action("win.close-tab", None) is True
        tabs = _tabs(window)
        assert len(tabs) == 2
        assert _active_tabs(window) == [tabs[-1]]

        assert window.activate_action("win.close-tab", None) is True
        assert len(_tabs(window)) == 1
        assert window.lookup_action("close-tab").get_enabled() is False
        assert _menu_item(window, "win.close-tab").get_sensitive() is False
        window.activate_action("win.close-tab", None)
        assert len(_tabs(window)) == 1
    finally:
        _close(window)


def test_tab_close_button_removes_its_tab(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        window.activate_action("win.new-tab", None)

        _close_buttons(window)[-1].emit("clicked")

        assert len(_tabs(window)) == 1
        assert _active_tabs(window) == _tabs(window)
    finally:
        _close(window)


def test_close_inactive_tab_keeps_active_one(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        window.activate_action("win.new-tab", None)
        assert _active_tabs(window) == [_tabs(window)[-1]]

        _close_buttons(window)[0].emit("clicked")

        tabs = _tabs(window)
        assert len(tabs) == 1
        assert _active_tabs(window) == tabs
        assert _path_label(window) == str(tmp_path)
    finally:
        _close(window)


def test_close_active_first_tab_activates_the_next_one(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.activate_action("win.new-tab", None)
        window._activate(window._tabs[0])

        _close_buttons(window)[0].emit("clicked")

        assert len(_tabs(window)) == 1
        assert _active_tabs(window) == _tabs(window)
        assert _path_label(window) == str(tmp_path)
    finally:
        _close(window)


def test_switch_tab_updates_path_and_visible_listing(
    gtk_display, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window = _main_window(first)
    try:
        window._open_tab(second)
        assert _path_label(window) == str(second)

        window._activate(window._tabs[0])
        assert _path_label(window) == str(first)
        assert window._stack.get_visible_child() is window._tabs[0].widget
        assert _active_tabs(window) == [_tabs(window)[0]]
    finally:
        _close(window)


def test_navigation_buttons_start_with_a_clean_history(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        assert not window._back_button.get_sensitive()
        assert not window._fwd_button.get_sensitive()
        assert window._up_button.get_sensitive()
        assert window._back_button.get_tooltip_text() == "Назад"
        assert window._fwd_button.get_tooltip_text() == "Вперёд"
        assert window._up_button.get_tooltip_text() == "В родительскую папку"

        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        for button in (
            window._back_button,
            window._fwd_button,
            window._up_button,
        ):
            assert Gtk.test_accessible_has_property(
                button, Gtk.AccessibleProperty.LABEL
            )
    finally:
        _close(window)


def test_up_is_disabled_at_the_filesystem_root(gtk_display) -> None:
    window = _main_window(Path("/"))
    try:
        assert not window._up_button.get_sensitive()
        assert not window._back_button.get_sensitive()
    finally:
        _close(window)


def test_directory_row_activation_opens_the_directory(
    gtk_display, tmp_path: Path
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")

    window = _main_window(tmp_path)
    try:
        window.present()
        assert not _details_view(window)._column_view.get_single_click_activate()
        _activate_listed_row(window, "child")

        assert window._active_tab.path == child
        assert _path_label(window) == str(child)
        assert window._tab_title_labels[window._active_tab].get_text() == "child"
        assert window._back_button.get_sensitive()
        assert window._up_button.get_sensitive()
        assert not window._fwd_button.get_sensitive()
    finally:
        _close(window)


def test_file_row_activation_keeps_the_directory(gtk_display, tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")

    window = _main_window(tmp_path)
    try:
        window.present()
        _activate_listed_row(window, "note.txt")

        assert window._active_tab.path == tmp_path
        assert _path_label(window) == str(tmp_path)
        assert not window._back_button.get_sensitive()
    finally:
        _close(window)


def test_back_and_forward_walk_the_navigation_history(
    gtk_display, tmp_path: Path
) -> None:
    child = tmp_path / "child"
    grand = child / "grand"
    grand.mkdir(parents=True)

    window = _main_window(tmp_path)
    try:
        window.present()
        _activate_listed_row(window, "child")
        assert window._active_tab.path == child

        _activate_listed_row(window, "grand")
        assert window._active_tab.path == grand
        assert window._back_button.get_sensitive()
        assert not window._fwd_button.get_sensitive()

        window._back_button.emit("clicked")
        assert window._active_tab.path == child
        assert _path_label(window) == str(child)
        assert window._fwd_button.get_sensitive()

        window._back_button.emit("clicked")
        assert window._active_tab.path == tmp_path
        assert not window._back_button.get_sensitive()

        window._fwd_button.emit("clicked")
        assert window._active_tab.path == child
        window._fwd_button.emit("clicked")
        assert window._active_tab.path == grand
        assert not window._fwd_button.get_sensitive()
    finally:
        _close(window)


def test_new_navigation_after_back_drops_the_forward_branch(
    gtk_display, tmp_path: Path
) -> None:
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()

    window = _main_window(tmp_path)
    try:
        window.present()
        _activate_listed_row(window, "first")
        window._back_button.emit("clicked")
        assert window._active_tab.path == tmp_path
        assert window._fwd_button.get_sensitive()

        _activate_listed_row(window, "second")

        assert window._active_tab.path == tmp_path / "second"
        assert not window._fwd_button.get_sensitive()
    finally:
        _close(window)


def test_up_navigates_to_the_parent_and_back_returns(
    gtk_display, tmp_path: Path
) -> None:
    child = tmp_path / "child"
    child.mkdir()

    window = _main_window(child)
    try:
        assert window._up_button.get_sensitive()

        window._up_button.emit("clicked")

        assert window._active_tab.path == tmp_path
        assert _path_label(window) == str(tmp_path)
        assert window._tab_title_labels[window._active_tab].get_text() == tmp_path.name
        assert window._back_button.get_sensitive()

        window._back_button.emit("clicked")
        assert window._active_tab.path == child
        assert _path_label(window) == str(child)
    finally:
        _close(window)


def test_history_is_kept_per_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    (first / "nested").mkdir(parents=True)
    second.mkdir()
    (second / "inside").mkdir()

    window = _main_window(first)
    try:
        window._open_tab(second)
        window._activate(window._tabs[0])
        window._navigate_active_tab(first / "nested")
        assert window._back_button.get_sensitive()

        window._activate(window._tabs[1])
        assert not window._back_button.get_sensitive()
        assert not window._fwd_button.get_sensitive()

        window.present()
        _activate_listed_row(window, "inside")
        assert window._tabs[1].path == second / "inside"

        window._activate(window._tabs[0])
        assert window._back_button.get_sensitive()
        window._back_button.emit("clicked")
        assert window._tabs[0].path == first

        assert window._tabs[1].path == second / "inside"
    finally:
        _close(window)


def test_path_edit_records_a_history_entry(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text(str(second))
        window._path_entry.emit("activate")

        assert window._active_tab.path == second
        assert window._back_button.get_sensitive()

        window._back_button.emit("clicked")
        assert window._active_tab.path == first
        assert _path_label(window) == str(first)
    finally:
        _close(window)


def test_right_panel_is_hidden(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        assert _by_class(window, "volna-panel-right") == []
        assert len(_by_class(window, "volna-rail")) == 1

        titles = [
            label.get_text() for label in _by_class(window, "volna-panel-title-label")
        ]
        assert titles == ["Места"]
    finally:
        _close(window)


def test_path_edit_navigates_active_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text(str(second))
        window._path_entry.emit("activate")

        assert _path_label(window) == str(second)
        assert window._active_tab.path == second
        assert _by_class(window, "volna-tab-label")[0].get_text() == "second"
        assert window._path_stack.get_visible_child_name() == "display"
    finally:
        _close(window)


def test_path_edit_only_changes_the_active_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for path in (first, second, third):
        path.mkdir()

    window = _main_window(first)
    try:
        window._open_tab(second)
        window._activate(window._tabs[0])

        window._start_path_edit()
        window._path_entry.set_text(str(third))
        window._path_entry.emit("activate")

        assert window._tabs[0].path == third
        assert window._tabs[1].path == second
        assert _path_label(window) == str(third)
    finally:
        _close(window)


def test_invalid_path_keeps_the_directory_and_reports_it(
    gtk_display, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    first.mkdir()

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text(str(tmp_path / "missing"))
        window._path_entry.emit("activate")

        assert _path_label(window) == str(first)
        assert window._active_tab.path == first
        assert window._path_stack.get_visible_child_name() == "display"
        assert _status_text(window) == "Путь недоступен"

        path_widget = _by_class(window, "volna-path")[0]
        assert path_widget.has_css_class("is-invalid")
        window._clear_status_note()
        assert not path_widget.has_css_class("is-invalid")
        assert _status_text(window) != "Путь недоступен"
    finally:
        _close(window)


def test_starting_a_new_edit_clears_invalid_highlight(
    gtk_display, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    first.mkdir()

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text(str(tmp_path / "missing"))
        window._path_entry.emit("activate")

        path_widget = _by_class(window, "volna-path")[0]
        assert path_widget.has_css_class("is-invalid")

        window._start_path_edit()
        assert not path_widget.has_css_class("is-invalid")
    finally:
        _close(window)


def test_escape_cancels_path_edit(gtk_display, tmp_path: Path) -> None:
    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text(str(second))

        assert window._on_path_key_pressed(None, Gdk.KEY_Escape, 0, 0) is True
        assert window._path_stack.get_visible_child_name() == "display"
        assert _path_label(window) == str(first)
        assert window._active_tab.path == first
    finally:
        _close(window)


def test_path_menu_lists_known_locations(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        window._path_nav_menu.fill()
        items = _by_class(window, "volna-path-item")
        paths = [item.get_tooltip_text() for item in items]

        assert str(tmp_path) in paths
        assert str(Path.home()) in paths
        assert str(Path("/")) in paths

        current = [item for item in items if item.has_css_class("is-current")]
        assert len(current) == 1
        assert current[0].get_tooltip_text() == str(tmp_path)
    finally:
        _close(window)


def test_path_menu_selection_navigates(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        window._path_nav_menu.fill()
        home_item = next(
            item
            for item in _by_class(window, "volna-path-item")
            if item.get_tooltip_text() == str(Path.home())
        )

        home_item.emit("clicked")

        assert window._active_tab.path == Path.home()
        assert _path_label(window) == str(Path.home())
        assert _by_class(window, "volna-tab-label")[0].get_text() == "Домашняя папка"
    finally:
        _close(window)


def test_path_edit_accepts_relative_path(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    nested = first / "nested"
    nested.mkdir(parents=True)

    window = _main_window(first)
    try:
        window._start_path_edit()
        window._path_entry.set_text("nested")
        window._path_entry.emit("activate")

        assert window._active_tab.path == nested
        assert _path_label(window) == str(nested)
    finally:
        _close(window)


def _path_context_item(window: object):
    """The «Копировать путь» row of the path field's context menu."""
    for item in _by_class(window._path_context_menu, "volna-menu-item"):
        labels = _by_class(item, "volna-menu-label")
        if labels and labels[0].get_text() == "Копировать путь":
            return item
    raise AssertionError("«Копировать путь» is missing from the path context menu")


def _open_path_context_menu(window: object) -> None:
    """Right click the path label, the way a pointer does."""
    x, y = _root_point(window, window._path_label)
    _fake_click(x, y, button=3)
    _pump_seconds(0.3)


def _clipboard_text() -> str | None:
    """Default clipboard text; the read is async, so the loop is pumped."""
    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    assert display is not None

    result: dict[str, str | None] = {}

    def on_read(source: object, res: object) -> None:
        result["text"] = source.read_text_finish(res)

    display.get_clipboard().read_text_async(None, on_read)
    assert _pump_until(lambda: "text" in result)
    return result["text"]


def test_path_dropdown_stays_a_list_of_known_paths(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        window._path_nav_menu.fill()

        labels = [
            item.get_text()
            for item in _by_class(window._path_nav_menu.items, "volna-menu-label")
        ]
        assert "Копировать путь" not in labels
        assert len(labels) == len(_by_class(window, "volna-path-item"))
    finally:
        _close(window)


def test_right_click_on_the_path_opens_a_context_menu(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.present()
        _pump_seconds(0.3)
        assert not window._path_context_menu.visible()

        _open_path_context_menu(window)

        assert window._path_context_menu.visible()
        assert _window_menu(window) is None
    finally:
        _close(window)


def test_path_context_menu_copies_the_active_path(gtk_display, tmp_path: Path) -> None:
    target = tmp_path / "first" / "nested"
    target.mkdir(parents=True)

    window = _main_window(target)
    try:
        window.present()
        # The initial scan ends with its own status line; let it land first.
        assert _pump_until(lambda: _status_text(window) == "Готово.")
        assert window._path_stack.get_visible_child_name() == "display"

        _open_path_context_menu(window)
        _path_context_item(window).emit("clicked")
        _pump_seconds(0.2)

        assert _clipboard_text() == str(target)
        assert not window._path_context_menu.visible()
        assert window._path_stack.get_visible_child_name() == "display"
        assert _status_text(window) == "Путь скопирован"

        window._clear_status_note()
        assert _status_text(window) != "Путь скопирован"
    finally:
        _close(window)


def test_copy_path_of_the_root_is_a_single_slash(gtk_display) -> None:
    window = _main_window(Path("/"))
    try:
        window.present()
        _pump_seconds(0.3)
        _open_path_context_menu(window)
        _path_context_item(window).emit("clicked")

        assert _clipboard_text() == "/"
    finally:
        _close(window)


def test_copy_path_follows_the_active_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for path in (first, second, third):
        path.mkdir()

    window = _main_window(first)
    try:
        window.present()
        _pump_seconds(0.3)

        window._open_tab(second)
        _pump_seconds(0.2)
        _open_path_context_menu(window)
        _path_context_item(window).emit("clicked")
        assert _clipboard_text() == str(second)

        window._activate(window._tabs[0])
        _pump_seconds(0.2)
        _open_path_context_menu(window)
        _path_context_item(window).emit("clicked")
        assert _clipboard_text() == str(first)

        window._navigate_active_tab(third)
        _pump_seconds(0.2)
        assert _clipboard_text() == str(first)
    finally:
        _close(window)


def test_copy_path_keeps_the_tab_and_history(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for path in (first, second):
        path.mkdir()

    window = _main_window(first)
    try:
        window.present()
        _pump_seconds(0.3)
        window._navigate_active_tab(second)
        _pump_seconds(0.2)

        tab = window._active_tab
        before = (tab.path, tab.can_go_back, tab.can_go_forward, len(window._tabs))

        for _ in range(2):
            _open_path_context_menu(window)
            _path_context_item(window).emit("clicked")
            _pump_seconds(0.2)

        after = (tab.path, tab.can_go_back, tab.can_go_forward, len(window._tabs))
        assert after == before
        assert tab.path == second
        assert _path_label(window) == str(second)
        assert _clipboard_text() == str(second)
    finally:
        _close(window)


def _pump_until(condition, timeout: float = 5.0) -> bool:
    """Run the GTK main loop until ``condition`` holds (listing is async)."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return True
        time.sleep(0.01)
    return False


def _name_cell_rows(window: object) -> dict[str, str]:
    """Map a visible row label to the file name of its type glyph."""
    import gi

    from volna.glyph import nearest_icon_size
    from volna.size import px

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    rows: dict[str, str] = {}
    for image in _by_class(window, "volna-dt-icon"):
        cell = image.get_parent()
        label = cell.get_last_child()
        name = label.get_text()
        if not name:
            # The recycled name cell bound to a date caption: the group branch
            # is shown and the entry branch keeps an empty, hidden label.
            continue
        assert image.get_pixel_size() == px(16)
        assert Gtk.test_accessible_has_property(image, Gtk.AccessibleProperty.LABEL)
        glyph = image.get_property("file")
        assert glyph is not None, "the row glyph was not loaded from a file"
        path = Path(glyph if isinstance(glyph, str) else glyph.get_path())
        # Glyphs are SVG: the file comes from the nearest shipped set and is
        # painted at the requested pixel size.
        assert path.parent.name == str(nearest_icon_size(px(16)))
        rows[name] = path.name

    return rows


def test_details_rows_show_kind_icons(gtk_display, tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.txt").write_text("x", encoding="utf-8")

    window = _main_window(tmp_path)
    try:
        window.present()
        assert _pump_until(lambda: len(_by_class(window, "volna-dt-icon")) >= 2), (
            "the details rows were not rendered"
        )

        assert _name_cell_rows(window) == {
            "alpha": "folder-filled.svg",
            "beta.txt": "file.svg",
        }
    finally:
        _close(window)


def test_row_glyph_accessible_name_tracks_the_bound_kind(
    gtk_display, tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.txt").write_text("x", encoding="utf-8")

    from volna.naming import content_icon as real_content_icon

    icon_kinds: list[bool] = []
    label_kinds: list[bool] = []

    def icon_spy(is_dir: bool) -> str:
        icon_kinds.append(is_dir)
        return real_content_icon(is_dir)

    def label_spy(is_dir: bool) -> str:
        label_kinds.append(is_dir)
        return "Папка" if is_dir else "Файл"

    # The glyph names live on ListingItem, which the details view binds.
    import volna.views.item as item_module

    monkeypatch.setattr(item_module, "content_icon", icon_spy)
    monkeypatch.setattr(item_module, "content_icon_label", label_spy)

    window = _main_window(tmp_path)
    try:
        window.present()
        assert _pump_until(
            lambda: (
                len(_by_class(window, "volna-dt-icon")) >= 2
                and icon_kinds == label_kinds
                and {True, False} <= set(label_kinds)
            )
        ), "the row glyph names were not bound"

        assert icon_kinds == label_kinds
    finally:
        _close(window)


def _entry_rows(window: object) -> list[object]:
    """The entry rows of the active listing: date captions are not entries.

    Grouping is on by default, so the details store is heterogeneous: it holds
    ``GroupRow`` captions between the ``ListingItem`` rows (grouping.md D5).
    """
    from volna.views.item import ListingItem

    store = _details_view(window).store
    return [
        row
        for row in (store.get_item(index) for index in range(store.get_n_items()))
        if isinstance(row, ListingItem)
    ]


def _listed_names(window: object) -> list[str]:
    return [row.name for row in _entry_rows(window)]


def _wait_for_listing(window: object, *names: str) -> None:
    assert _pump_until(lambda: all(name in _listed_names(window) for name in names)), (
        f"rows {names} never appeared in {_listed_names(window)}"
    )


def _activate_listed_row(window: object, name: str) -> None:
    """Emit the ColumnView activation GTK sends for a double click / Enter."""
    from volna.views.item import ListingItem

    store = _details_view(window).store
    _wait_for_listing(window, name)
    position = next(
        index
        for index in range(store.get_n_items())
        if isinstance(store.get_item(index), ListingItem)
        and store.get_item(index).name == name
    )
    _details_view(window)._column_view.emit("activate", position)


def test_navigation_clears_the_old_listing(gtk_display, tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    (child / "inner").mkdir()

    window = _main_window(tmp_path)
    try:
        window.present()
        _wait_for_listing(window, "child")
        view = _details_view(window)
        assert view.store.get_n_items() > 0

        window._navigate_active_tab(child)

        assert window._active_tab.path == child
        assert view.store.get_n_items() == 0
    finally:
        _close(window)


def test_activation_of_a_row_from_the_previous_listing_is_ignored(
    gtk_display, tmp_path: Path
) -> None:
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()

    window = _main_window(tmp_path)
    try:
        window.present()
        _wait_for_listing(window, "beta")
        stale = next(row for row in _entry_rows(window) if row.name == "beta")

        window._navigate_active_tab(alpha)
        window._active_tab._on_item_activated(stale)

        assert window._active_tab.path == alpha
    finally:
        _close(window)


def _pump_seconds(seconds: float) -> None:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


_X11_LIBRARIES = None


def _x11_libraries():
    """Load libX11/libXtst and declare prototypes; skip without them."""
    global _X11_LIBRARIES

    if _X11_LIBRARIES is not None:
        return _X11_LIBRARIES

    import ctypes
    import ctypes.util

    x11_path = ctypes.util.find_library("X11")
    xtst_path = ctypes.util.find_library("Xtst")
    if x11_path is None or xtst_path is None:
        pytest.skip("libX11/libXtst are not installed")

    x11 = ctypes.CDLL(x11_path)
    xtst = ctypes.CDLL(xtst_path)

    # Display* is a 64-bit pointer: without restype ctypes truncates it to
    # c_int, which crashes on PIE builds where the address does not fit.
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultScreen.restype = ctypes.c_int
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XFlush.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XTranslateCoordinates.restype = ctypes.c_int
    x11.XTranslateCoordinates.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong),
    ]
    xtst.XTestFakeMotionEvent.restype = ctypes.c_int
    xtst.XTestFakeMotionEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_ulong,
    ]
    xtst.XTestFakeButtonEvent.restype = ctypes.c_int
    xtst.XTestFakeButtonEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_ulong,
    ]

    _X11_LIBRARIES = (x11, xtst)
    return _X11_LIBRARIES


def _root_point(window, widget, dx: float = 0.0, dy: float = 0.0) -> tuple[int, int]:
    """Center of ``widget`` in X11 root coordinates (for XTestFake*)."""
    import ctypes

    import gi

    gi.require_version("GdkX11", "4.0")
    gi.require_version("Graphene", "1.0")
    from gi.repository import GdkX11, Graphene

    x11, _xtst = _x11_libraries()
    display = x11.XOpenDisplay(None)
    assert display, "cannot open the X display"
    try:
        root = x11.XDefaultRootWindow(display)
        origin_x = ctypes.c_int()
        origin_y = ctypes.c_int()
        child = ctypes.c_ulong()
        surface = window.get_native().get_surface()
        x11.XTranslateCoordinates(
            display,
            GdkX11.X11Surface.get_xid(surface),
            root,
            0,
            0,
            ctypes.byref(origin_x),
            ctypes.byref(origin_y),
            ctypes.byref(child),
        )
        surface_x, surface_y = window.get_native().get_surface_transform()
        center = Graphene.Point().init(
            widget.get_width() / 2 + dx, widget.get_height() / 2 + dy
        )
        result = widget.compute_point(window, center)
        point = result[1] if isinstance(result, tuple) else result

        return (
            origin_x.value + int(surface_x + point.x),
            origin_y.value + int(surface_y + point.y),
        )
    finally:
        x11.XCloseDisplay(display)


def _fake_click(x: int, y: int, count: int = 1, button: int = 1) -> None:
    """Send real X11 button events (the pointer press path GTK handles)."""
    x11, xtst = _x11_libraries()
    display = x11.XOpenDisplay(None)
    assert display, "cannot open the X display"
    try:
        screen = x11.XDefaultScreen(display)
        xtst.XTestFakeMotionEvent(display, screen, x, y, 0)
        x11.XFlush(display)
        _pump_seconds(0.05)
        for _ in range(count):
            xtst.XTestFakeButtonEvent(display, button, True, 0)
            xtst.XTestFakeButtonEvent(display, button, False, 0)
            x11.XFlush(display)
            _pump_seconds(0.08)
    finally:
        x11.XCloseDisplay(display)


def _details_label(window, text: str):
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    for widget in _walk(window):
        if (
            isinstance(widget, Gtk.Label)
            and widget.get_text() == text
            and "volna-dt-name" in widget.get_css_classes()
        ):
            return widget
    raise AssertionError(f"row {text!r} is not rendered")


@pytest.mark.slow
def test_real_double_click_opens_a_directory(gtk_display, tmp_path: Path) -> None:
    """The GTK gesture, not just ColumnView::activate: one click vs two."""
    (tmp_path / "child").mkdir()

    window = _main_window(tmp_path)
    try:
        window.present()
        _wait_for_listing(window, "child")
        _pump_seconds(0.2)

        status = _by_class(window, "volna-status")[0]
        _fake_click(*_root_point(window, status))
        _pump_seconds(0.3)

        x, y = _root_point(window, _details_label(window, "child"))

        _fake_click(x, y)
        _pump_seconds(0.4)
        assert window._active_tab.path == tmp_path

        _fake_click(x, y, count=2)
        _pump_seconds(0.8)
        assert window._active_tab.path == tmp_path / "child"
        assert _path_label(window) == str(tmp_path / "child")
    finally:
        _close(window)


def _window_menu(window):
    """The window menu Gtk.WindowHandle builds when no WM answers it."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    for widget in _walk(window):
        if not isinstance(widget, Gtk.PopoverMenu) or not widget.get_visible():
            continue
        # The fallback window menu is parented to the handle itself; an entry's
        # context menu also lives under the handle, but deeper in the tree.
        if isinstance(widget.get_parent(), Gtk.WindowHandle):
            return widget
    return None


def _entry_menu(window):
    """The text context menu of an entry, likewise a GtkPopoverMenu."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    for widget in _walk(window):
        if not isinstance(widget, Gtk.PopoverMenu) or not widget.get_visible():
            continue
        node = widget.get_parent()
        while node is not None:
            if isinstance(node, Gtk.Entry):
                return widget
            node = node.get_parent()
    return None


def _pointer_grabbed() -> bool:
    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    seat = display.get_default_seat()
    return display.device_is_grabbed(seat.get_pointer())


def _header_controls(window) -> dict[str, object]:
    window_buttons = _by_class(window, "volna-win")
    assert len(window_buttons) == 3
    return {
        "main menu": window._menu_button,
        "back": window._back_button,
        "forward": window._fwd_button,
        "up": window._up_button,
        "view": window._view_panel.trigger(),
        "path": window._path_wrapper,
        "path chevron": window._path_nav_menu.button,
        "path pencil": window._path_edit_button,
        "minimize": window_buttons[0],
        "maximize": window_buttons[1],
        "close": window_buttons[2],
    }


def test_right_click_on_header_controls_keeps_the_window_menu_away(
    gtk_display, tmp_path: Path
) -> None:
    """Issue #20: only free header space is a title bar, controls are not."""
    window = _main_window(tmp_path)
    try:
        window.present()
        _pump_seconds(0.3)

        for name, control in _header_controls(window).items():
            x, y = _root_point(window, control)
            _fake_click(x, y, button=3)
            _pump_seconds(0.2)

            assert _window_menu(window) is None, name
            if name == "path":
                # The path field opens its own context menu (#21); an open
                # popover takes the pointer grab on purpose.
                assert window._path_context_menu.visible()
                window._path_context_menu.popdown()
                _pump_seconds(0.1)
            assert not _pointer_grabbed(), name
    finally:
        _close(window)


def test_right_click_on_the_view_trigger_does_not_eat_the_next_click(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.present()
        _pump_seconds(0.3)
        trigger = window._view_panel.trigger()

        x, y = _root_point(window, trigger)
        _fake_click(x, y, button=3)
        assert _window_menu(window) is None
        assert not _pointer_grabbed()

        _fake_click(x, y)
        _pump_seconds(0.3)
        assert window._view_panel.popover.get_visible()
    finally:
        _close(window)


def test_right_click_on_free_header_space_opens_the_window_menu(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.present()
        _pump_seconds(0.3)
        trigger = window._view_panel.trigger()

        # The 8 px gap between the view trigger and the path field.
        x, y = _root_point(window, trigger, dx=trigger.get_width() / 2 + 4)
        _fake_click(x, y, button=3)
        _pump_seconds(0.3)

        menu = _window_menu(window)
        assert menu is not None
        assert _pointer_grabbed()

        menu.popdown()
        _pump_seconds(0.2)
        assert not _pointer_grabbed()
    finally:
        _close(window)


def test_right_click_on_the_path_entry_keeps_its_own_menu(
    gtk_display, tmp_path: Path
) -> None:
    window = _main_window(tmp_path)
    try:
        window.present()
        _pump_seconds(0.3)
        window._start_path_edit()
        _pump_seconds(0.3)

        x, y = _root_point(window, window._path_entry)
        _fake_click(x, y, button=3)
        _pump_seconds(0.3)

        assert _window_menu(window) is None
        assert _entry_menu(window) is not None
    finally:
        _close(window)


# -- interface scale ----------------------------------------------------------

_THEME_PX = 14.0  # the compact grid at 100 % (design/spec/02 §10)


def _load_theme(font_px: float):
    """Load ``theme.css`` plus the root font size the app sets at startup."""
    from gi.repository import Gdk, Gtk

    theme = Path(__file__).resolve().parents[1] / "src" / "volna" / "theme.css"
    providers = []
    for css in (
        theme.read_text(encoding="utf-8"),
        f".volna-window {{ font-size: {font_px}px; }}",
    ):
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        providers.append(provider)

    display = Gdk.Display.get_default()
    for provider in providers:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    return display, providers


def _toolbar_height(tmp_path: Path, font_px: float) -> int:
    from gi.repository import Gtk

    display, providers = _load_theme(font_px)
    window = _main_window(tmp_path)
    try:
        window.present()
        toolbar = _by_class(window, "volna-toolbar")[0]
        assert _pump_until(lambda: toolbar.get_height() > 0)
        return toolbar.get_height()
    finally:
        _close(window)
        for provider in providers:
            Gtk.StyleContext.remove_provider_for_display(display, provider)


def test_interface_scale_comes_from_the_root_font(gtk_display, tmp_path: Path) -> None:
    """The stylesheet is one compact em grid; the root font selects the preset.

    ``main`` resolves the desktop scale into a root font size (14 px on a
    100 % desktop, 17.5 px on 125 %), so the same rules must render the compact
    and the design's wide chrome from that value alone.
    """
    assert _toolbar_height(tmp_path, _THEME_PX) == px(40)
    assert _toolbar_height(tmp_path, 17.5) == round(px(40) * 1.25)
