"""System tests for the «Вид» panel: behavior through the real window.

These tests drive the UI the way a user does (open the popover, toggle visible
controls) and assert on rendered rows and window state, not on the panel's or
the model's private structure.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.display import (  # noqa: E402
    Grouping,
    JsonViewSettingsStore,
    MemoryViewSettingsStore,
    SettingsPaths,
    SortKey,
    ViewSettings,
)


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _pump_until(condition, timeout: float = 5.0) -> bool:
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


def _window(
    path: Path,
    *,
    settings: ViewSettings | None = None,
    store=None,
    startup_issues: Sequence[str] = (),
):
    from volna.window import MainWindow

    storage = store or MemoryViewSettingsStore()
    if settings is None:
        settings = storage.load().view or ViewSettings()

    return MainWindow(
        start_path=path,
        initial_settings=settings,
        settings_store=storage,
        startup_issues=tuple(startup_issues),
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()


def _listed_names(window: object) -> list[str]:
    """Names of the rows the user actually sees in the active tab."""
    tab = window._active_tab
    if tab is None:
        return []

    labels = [label.get_text() for label in _by_class(tab.widget, "volna-dt-name")]

    return [text for text in labels if text]


def _wait_for_names(window: object, *names: str) -> None:
    assert _pump_until(lambda: all(name in _listed_names(window) for name in names)), (
        f"rows {names} never appeared in {_listed_names(window)}"
    )


def _open_panel(window: object) -> object:
    window.present()
    panel = window._view_panel
    panel.open()

    assert _pump_until(lambda: panel.popover.get_visible()), "the popover did not open"

    return panel


def _control(root: object, text: str) -> object:
    """Find a labeled control (radio, checkbox, segmented button) by its text.

    Only activatable widgets count: a preset may carry the same name as a
    setting («Без группировки» is both a preset and a grouping option).
    """
    for widget in _walk(root):
        if not hasattr(widget, "set_active"):
            continue
        getter = getattr(widget, "get_label", None)
        if getter is not None and getter() == text:
            return widget
        label = getattr(widget, "get_last_child", None)
        if label is not None:
            child = label()
            if (
                getattr(child, "get_text", None) is not None
                and child.get_text() == text
            ):
                return widget

    raise AssertionError(f"control {text!r} not found")


def _touch(path: Path, mtime: float) -> None:
    path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _make_listing(root: Path) -> None:
    # Explicit mtimes keep the default (newest first) order deterministic.
    _touch(root / "alpha.txt", 1_600_000_000)
    _touch(root / "beta.txt", 1_600_000_100)


def test_sort_controls_reorder_visible_rows(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")

        _control(panel.popover, "Имя").set_active(True)
        _control(panel.popover, "По возрастанию").set_active(True)

        assert _pump_until(
            lambda: _listed_names(window) == ["alpha.txt", "beta.txt"]
        ), f"unexpected order: {_listed_names(window)}"
        assert panel.popover.get_visible(), (
            "changing a setting must keep the popover open"
        )
    finally:
        _close(window)


def test_folders_first_toggle_mixes_folders_and_files(
    gtk_display, tmp_path: Path
) -> None:
    (tmp_path / "zzz").mkdir()
    _touch(tmp_path / "aaa.txt", 1_600_000_000)

    # The subject is the global flat order: folders first across the whole
    # listing. Grouping is on by default and would interleave date groups, so
    # this scenario runs ungrouped; within-group folders-first is covered by
    # tests/test_grouping.py (grouping.md D3).
    window = _window(tmp_path, settings=ViewSettings(grouping=Grouping.NONE))
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "aaa.txt", "zzz")

        _control(panel.popover, "Имя").set_active(True)
        _control(panel.popover, "По возрастанию").set_active(True)
        assert _pump_until(lambda: _listed_names(window) == ["zzz", "aaa.txt"]), (
            f"folders were not first: {_listed_names(window)}"
        )

        _control(panel.popover, "Папки перед файлами").set_active(False)
        assert _pump_until(lambda: _listed_names(window) == ["aaa.txt", "zzz"]), (
            f"folders were still first: {_listed_names(window)}"
        )
        assert window._active_tab.view_settings.folders_first is False
    finally:
        _close(window)


def test_sort_change_does_not_rescan(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")
        model = window._active_tab.model
        generation = model.generation
        state_before = model.state

        _control(panel.popover, "Размер").set_active(True)
        _pump_until(lambda: False, timeout=0.2)

        assert model.generation == generation
        assert model.state is state_before
    finally:
        _close(window)


def test_view_settings_are_per_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_listing(first)
    _make_listing(second)

    window = _window(first)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")

        first_tab = window._active_tab
        window._open_tab(second)
        second_tab = window._active_tab
        assert second_tab is not first_tab

        _control(panel.popover, "Имя").set_active(True)
        _control(panel.popover, "По возрастанию").set_active(True)
        assert _pump_until(lambda: second_tab.view_settings.sort_key is SortKey.NAME)

        assert first_tab.view_settings.sort_key is SortKey.MTIME
        assert second_tab.view_settings.sort_key is SortKey.NAME

        window._activate(first_tab)
        assert _pump_until(
            lambda: _listed_names(window) == ["beta.txt", "alpha.txt"]
        ), f"the first tab changed too: {_listed_names(window)}"
        assert _control(panel.popover, "Дата изменения").get_active()

        window._activate(second_tab)
        assert _pump_until(lambda: _listed_names(window) == ["alpha.txt", "beta.txt"])
    finally:
        _close(window)


def test_new_tab_inherits_the_active_view(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_listing(first)
    _make_listing(second)

    window = _window(first)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")

        _control(panel.popover, "Показывать скрытые файлы").set_active(True)
        _control(panel.popover, "Плотная раскладка").set_active(True)
        assert _pump_until(lambda: window._active_tab.view_settings.show_hidden)

        window._open_tab(second)
        assert window._active_tab.view_settings.show_hidden
        assert window._active_tab.view_settings.compact
    finally:
        _close(window)


def test_hidden_toggle_only_affects_the_active_tab(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_listing(first)
    _make_listing(second)
    (second / ".hidden.txt").write_text("", encoding="utf-8")

    window = _window(first)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")
        first_tab = window._active_tab

        window._open_tab(second)
        _wait_for_names(window, "alpha.txt", "beta.txt")
        assert ".hidden.txt" not in _listed_names(window)

        _control(panel.popover, "Показывать скрытые файлы").set_active(True)
        assert _pump_until(lambda: ".hidden.txt" in _listed_names(window)), (
            f"dotfile did not appear: {_listed_names(window)}"
        )
        assert not first_tab.view_settings.show_hidden

        window._activate(first_tab)
        _pump_until(lambda: _listed_names(window) == ["alpha.txt", "beta.txt"])
        assert ".hidden.txt" not in _listed_names(window)
    finally:
        _close(window)


def test_density_toggle_marks_the_window(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, "alpha.txt", "beta.txt")

        assert not window.has_css_class("volna-density-compact")
        _control(panel.popover, "Плотная раскладка").set_active(True)
        assert _pump_until(lambda: window.has_css_class("volna-density-compact"))

        _control(panel.popover, "Плотная раскладка").set_active(False)
        assert _pump_until(lambda: not window.has_css_class("volna-density-compact"))
    finally:
        _close(window)


def test_last_view_survives_a_restart(gtk_display, tmp_path: Path) -> None:
    listing = tmp_path / "listing"
    listing.mkdir()
    _make_listing(listing)
    config = tmp_path / "config"
    paths = SettingsPaths(directory=config, file=config / "settings.json")
    store = JsonViewSettingsStore(paths)

    first = _window(listing, store=store)
    try:
        panel = _open_panel(first)
        _wait_for_names(first, "alpha.txt", "beta.txt")
        _control(panel.popover, "Имя").set_active(True)
        assert _pump_until(
            lambda: first._active_tab.view_settings.sort_key is SortKey.NAME
        )
        _close(first)

        assert paths.file.exists(), "closing the window must persist the last view"
        document = JsonViewSettingsStore(paths).load()
        assert document.view is not None
        assert document.view.sort_key is SortKey.NAME
    finally:
        if first.get_realized():
            first.destroy()

    second = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        second.present()
        _wait_for_names(second, "alpha.txt", "beta.txt")
        assert second._active_tab.view_settings.sort_key is SortKey.NAME
        assert second._active_tab.model.sort_key is SortKey.NAME
    finally:
        _close(second)


def test_corrupt_config_does_not_block_startup(gtk_display, tmp_path: Path) -> None:
    listing = tmp_path / "listing"
    listing.mkdir()
    _make_listing(listing)
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.json").write_text("{not json", encoding="utf-8")

    store = JsonViewSettingsStore(
        SettingsPaths(directory=config, file=config / "settings.json")
    )
    document = store.load()
    assert document.view is None
    assert document.issues

    window = _window(listing, store=store, startup_issues=document.issues)
    try:
        window.present()
        _wait_for_names(window, "alpha.txt", "beta.txt")
        status = _by_class(window, "volna-status")[0]
        assert "повреждён" in status.get_text()
    finally:
        _close(window)


def test_read_only_config_keeps_the_app_usable(gtk_display, tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permissions do not restrict root")

    listing = tmp_path / "listing"
    listing.mkdir()
    _make_listing(listing)
    config = tmp_path / "config"
    config.mkdir()
    os.chmod(config, 0o500)
    try:
        store = JsonViewSettingsStore(
            SettingsPaths(directory=config, file=config / "settings.json")
        )
        window = _window(listing, store=store)
        try:
            panel = _open_panel(window)
            _wait_for_names(window, "alpha.txt", "beta.txt")
            _control(panel.popover, "Имя").set_active(True)
            assert _pump_until(
                lambda: window._active_tab.view_settings.sort_key is SortKey.NAME
            )
        finally:
            _close(window)
    finally:
        os.chmod(config, 0o700)
