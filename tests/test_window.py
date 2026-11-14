"""Window behavior: tab lifecycle, the main menu and the visible panes.

The window needs a display, so the module runs under a private Xvfb and skips
when Xvfb or GTK4 is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")


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


def _active_tabs(window: object) -> list[object]:
    return [tab for tab in _tabs(window) if tab.has_css_class("is-active")]


def _close_buttons(window: object) -> list[object]:
    return _by_class(window, "volna-tab-close")


def _menu_item(window: object, action: str):
    for item in _by_class(window, "volna-menu-item"):
        if item.get_action_name() == action:
            return item
    raise AssertionError(f"menu item for action {action!r} not found")


def _free_display() -> int | None:
    for number in range(100, 140):
        if not Path(f"/tmp/.X11-unix/X{number}").exists():
            return number
    return None


def _start_xvfb() -> tuple[subprocess.Popen, str]:
    if shutil.which("Xvfb") is None:
        pytest.skip("Xvfb is not installed")

    number = _free_display()
    if number is None:
        pytest.skip("no free X display")

    process = subprocess.Popen(
        ["Xvfb", f":{number}", "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    socket = Path(f"/tmp/.X11-unix/X{number}")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if socket.exists():
            return process, f":{number}"
        if process.poll() is not None:
            break
        time.sleep(0.05)

    process.terminate()
    process.wait(5)
    pytest.skip("Xvfb did not start")


@pytest.fixture(scope="module")
def gtk_display() -> Iterator[None]:
    process, display = _start_xvfb()
    previous = {
        name: os.environ.get(name)
        for name in ("DISPLAY", "GDK_BACKEND", "GSK_RENDERER")
    }
    os.environ["DISPLAY"] = display
    os.environ["GDK_BACKEND"] = "x11"
    os.environ["GSK_RENDERER"] = "cairo"

    try:
        import gi

        try:
            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib, Gtk
        except (ImportError, ValueError) as exc:
            pytest.skip(f"GTK4 is not available: {exc}")

        try:
            Gtk.init()
        except GLib.Error as exc:
            pytest.skip(f"cannot initialize GTK4: {exc}")

        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        process.terminate()
        process.wait(5)


def _main_window(path: Path):
    from volna.window import MainWindow

    return MainWindow(start_path=path)


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


def test_forward_button_cycles_tabs(gtk_display, tmp_path: Path) -> None:
    window = _main_window(tmp_path)
    try:
        assert not window._fwd_button.get_sensitive()
        assert window._fwd_button.has_css_class("volna-disabled")

        window.activate_action("win.new-tab", None)
        window.activate_action("win.new-tab", None)
        assert window._fwd_button.get_sensitive()
        assert _active_tabs(window) == [_tabs(window)[-1]]

        window._activate_next_tab()
        assert _active_tabs(window) == [_tabs(window)[0]]

        window._activate_next_tab()
        assert _active_tabs(window) == [_tabs(window)[1]]

        window._activate_next_tab()
        assert _active_tabs(window) == [_tabs(window)[-1]]
        assert _path_label(window) == str(tmp_path)
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
        window._fill_path_menu()
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
        window._fill_path_menu()
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
