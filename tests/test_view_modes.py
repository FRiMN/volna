"""View modes: the registry contract, the panel control and mode switching.

System-level tests drive the real window the way a user does (open the
popover, pick a mode) and assert on rendered names and window state; the
registry/contract checks live in the same module because they need GTK
imported under the private Xvfb (see tests/test_view_panel.py on imports).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.display import (  # noqa: E402
    DEFAULT_CAPABILITIES,
    MODE_ORDER,
    JsonViewSettingsStore,
    MemoryViewSettingsStore,
    SettingsPaths,
    ViewCapabilities,
    ViewMode,
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
    capabilities: ViewCapabilities = DEFAULT_CAPABILITIES,
    store=None,
):
    from volna.window import MainWindow

    storage = store or MemoryViewSettingsStore()
    if settings is None:
        settings = storage.load().view or ViewSettings()

    return MainWindow(
        start_path=path,
        initial_settings=settings,
        settings_store=storage,
        capabilities=capabilities,
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()


def _open_panel(window: object) -> object:
    window.present()
    panel = window._view_panel
    panel.open()
    assert _pump_until(lambda: panel.popover.get_visible()), "the popover did not open"
    return panel


def _control(root: object, text: str) -> object:
    for widget in _walk(root):
        getter = getattr(widget, "get_label", None)
        if getter is not None and getter() == text:
            return widget
    raise AssertionError(f"control {text!r} not found")


def _names(window: object, css_class: str) -> list[str]:
    """Names the user sees: the active tab's visible mode view only."""
    tab = window._active_tab
    root = tab.widget.get_visible_child() or tab.widget
    labels = [label.get_text() for label in _by_class(root, css_class)]
    return [text for text in labels if text]


_MODE_CLASS = {
    ViewMode.DETAILS: "volna-dt-name",
    ViewMode.ICONS: "volna-icons-name",
    ViewMode.COLUMNS: "volna-col-name",
}


def _wait_for_names(window: object, mode: ViewMode, *names: str) -> None:
    css_class = _MODE_CLASS[mode]
    assert _pump_until(lambda: all(n in _names(window, css_class) for n in names)), (
        f"{mode} never showed {names}: {_names(window, css_class)}"
    )


def _make_listing(root: Path) -> None:
    (root / "alpha.txt").write_text("x", encoding="utf-8")
    (root / "beta.txt").write_text("y", encoding="utf-8")


# -- contract (registry, labels, sections) ----------------------------------


def test_labels_and_order_follow_the_mockup() -> None:
    assert MODE_ORDER == (ViewMode.ICONS, ViewMode.COLUMNS, ViewMode.DETAILS)
    assert [mode.label for mode in MODE_ORDER] == ["Значки", "Столбцы", "Подробности"]


def test_registry_has_one_view_per_mode(gtk_display) -> None:
    from volna.views.base import ListingView
    from volna.views.registry import MODE_VIEWS, VIEWS_BY_MODE

    assert set(VIEWS_BY_MODE) == set(ViewMode)
    assert set(MODE_VIEWS) == set(VIEWS_BY_MODE.values())
    assert all(issubclass(view, ListingView) for view in MODE_VIEWS)

    modes = [view.mode for view in MODE_VIEWS]
    assert len(set(modes)) == len(modes), f"duplicate modes: {modes}"
    for mode, view in VIEWS_BY_MODE.items():
        assert view.mode is mode


def test_section_is_one_unnamed_chunk(gtk_display) -> None:
    from volna.views.base import Section

    section = Section(items=())

    assert section.header is None
    assert section.items == ()


def test_listing_item_carries_presentation_data(gtk_display) -> None:
    from volna.views.item import ListingItem

    item = ListingItem("docs", "/home/u/docs", "—", "01.01.2026 00:00", True)

    assert item.name == "docs"
    assert item.icon_name == "folder-filled"
    assert item.icon_label == "Папка"

    file_item = ListingItem(
        "a.txt", "/home/u/a.txt", "1 КиБ", "01.01.2026 00:00", False
    )
    assert file_item.icon_name == "file"
    assert file_item.icon_label == "Файл"


# -- panel -------------------------------------------------------------------


def test_mode_section_lists_every_available_mode(gtk_display) -> None:
    from volna.view_panel import ViewPanel

    panel = ViewPanel(
        settings=lambda: ViewSettings(),
        update=lambda **_changes: True,
        capabilities=DEFAULT_CAPABILITIES,
    )

    labels = [
        widget.get_label()
        for widget in _walk(panel.popover)
        if widget.has_css_class("volna-radio")
    ]
    assert labels == [
        "Значки",
        "Столбцы",
        "Подробности",
        "Дата изменения",
        "Размер",
        "Имя",
    ]


def test_mode_section_disappears_with_one_mode(gtk_display) -> None:
    from volna.view_panel import ViewPanel

    capabilities = ViewCapabilities(
        modes=frozenset({ViewMode.DETAILS}),
        grouping=False,
        density=True,
        zoom_modes=frozenset(),
    )
    panel = ViewPanel(
        settings=lambda: ViewSettings(),
        update=lambda **_changes: True,
        capabilities=capabilities,
    )

    titles = [
        label.get_text()
        for label in _walk(panel.popover)
        if label.has_css_class("volna-view-section-title")
    ]
    assert "Режим просмотра" not in titles
    labels = [
        widget.get_label()
        for widget in _walk(panel.popover)
        if widget.has_css_class("volna-radio")
    ]
    assert "Значки" not in labels


# -- system: switching through the real window -------------------------------


def test_each_mode_shows_the_same_listing(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, ViewMode.DETAILS, "alpha.txt", "beta.txt")

        _control(panel.popover, "Значки").set_active(True)
        _wait_for_names(window, ViewMode.ICONS, "alpha.txt", "beta.txt")

        _control(panel.popover, "Столбцы").set_active(True)
        _wait_for_names(window, ViewMode.COLUMNS, "alpha.txt", "beta.txt")

        _control(panel.popover, "Подробности").set_active(True)
        _wait_for_names(window, ViewMode.DETAILS, "alpha.txt", "beta.txt")
    finally:
        _close(window)


def test_mode_switch_does_not_rescan(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, ViewMode.DETAILS, "alpha.txt")
        model = window._active_tab.model
        generation = model.generation
        state_before = model.state

        _control(panel.popover, "Значки").set_active(True)
        _pump_until(lambda: False, timeout=0.2)

        assert model.generation == generation
        assert model.state is state_before
        assert window._active_tab.view_mode is ViewMode.ICONS
    finally:
        _close(window)


def test_mode_is_per_tab_and_inherited(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_listing(first)
    _make_listing(second)

    window = _window(first)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, ViewMode.DETAILS, "alpha.txt")
        first_tab = window._active_tab

        _control(panel.popover, "Столбцы").set_active(True)
        _wait_for_names(window, ViewMode.COLUMNS, "alpha.txt")
        assert first_tab.view_mode is ViewMode.COLUMNS

        window._open_tab(second)
        assert window._active_tab is not first_tab
        assert window._active_tab.view_mode is ViewMode.COLUMNS, (
            "a new tab must inherit the active tab's mode"
        )
        _wait_for_names(window, ViewMode.COLUMNS, "alpha.txt")

        # The first tab kept its mode while inactive.
        _control(panel.popover, "Значки").set_active(True)
        _wait_for_names(window, ViewMode.ICONS, "alpha.txt")
        assert first_tab.view_mode is ViewMode.COLUMNS
    finally:
        _close(window)


def test_mode_survives_a_restart(gtk_display, tmp_path: Path) -> None:
    listing = tmp_path / "listing"
    listing.mkdir()
    _make_listing(listing)
    paths = SettingsPaths(
        directory=tmp_path / "config", file=tmp_path / "config" / "settings.json"
    )

    first = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        panel = _open_panel(first)
        _wait_for_names(first, ViewMode.DETAILS, "alpha.txt")
        _control(panel.popover, "Значки").set_active(True)
        _wait_for_names(first, ViewMode.ICONS, "alpha.txt")
        _close(first)
    finally:
        if first.get_realized():
            first.destroy()

    assert paths.file.exists()
    assert JsonViewSettingsStore(paths).load().view.view_mode is ViewMode.ICONS

    second = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        second.present()
        _wait_for_names(second, ViewMode.ICONS, "alpha.txt")
        assert second._active_tab.view_mode is ViewMode.ICONS
    finally:
        _close(second)


def test_unavailable_modes_are_not_offered(gtk_display, tmp_path: Path) -> None:
    _make_listing(tmp_path)
    capabilities = ViewCapabilities(
        modes=frozenset({ViewMode.DETAILS}),
        grouping=False,
        density=True,
        zoom_modes=frozenset(),
    )
    window = _window(tmp_path, capabilities=capabilities)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, ViewMode.DETAILS, "alpha.txt")

        titles = [
            label.get_text()
            for label in _by_class(panel.popover, "volna-view-section-title")
        ]
        assert "Режим просмотра" not in titles
        # A stored foreign mode is normalized away before the tab sees it.
        assert window._active_tab.view_mode is ViewMode.DETAILS
        assert set(window._active_tab._views) == {ViewMode.DETAILS}
    finally:
        _close(window)


def test_double_click_in_icons_mode_opens_a_folder(gtk_display, tmp_path: Path) -> None:
    (tmp_path / "child").mkdir()
    _make_listing(tmp_path)

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _wait_for_names(window, ViewMode.DETAILS, "child")
        _control(panel.popover, "Значки").set_active(True)
        _wait_for_names(window, ViewMode.ICONS, "child")

        grid = window._active_tab._views[ViewMode.ICONS]._grid
        position = next(
            index
            for index in range(
                window._active_tab._views[ViewMode.ICONS].store.get_n_items()
            )
            if window._active_tab._views[ViewMode.ICONS].store.get_item(index).name
            == "child"
        )
        grid.emit("activate", position)

        assert _pump_until(lambda: window._active_tab.path == tmp_path / "child")
    finally:
        _close(window)
