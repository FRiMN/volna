"""System tests for presets: the feature through the real window.

A user opens «Вид», picks a preset, saves one, renames and deletes it; these
tests drive exactly that and assert on the rendered list, the field label, the
active tab's snapshot and the stored file — never on private structure.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.display import (  # noqa: E402
    BUILTIN_PRESETS,
    DEFAULT_PRESET_ID,
    Grouping,
    MemoryViewSettingsStore,
    Preset,
    SortKey,
    ViewMode,
    ViewSettings,
)
from volna.display.presets_store import JsonPresetStore, MemoryPresetStore  # noqa: E402
from volna.display.store import SettingsPaths  # noqa: E402

BUILTIN_NAMES = [preset.name for preset in BUILTIN_PRESETS]


def _unmanaged_label() -> str:
    """The «manual» label; imported late because the panel package pulls GTK in."""
    from volna.view_panel.presets import UNMANAGED_LABEL

    return UNMANAGED_LABEL


# -- helpers ----------------------------------------------------------------


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _pump(seconds: float = 0.1) -> None:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


def _pump_until(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _pump(0.02)
        if condition():
            return True
    return False


def _window(
    path: Path, *, presets: object = None, settings: ViewSettings | None = None
):
    from volna.window import MainWindow

    return MainWindow(
        start_path=path,
        initial_settings=settings or ViewSettings(),
        settings_store=MemoryViewSettingsStore(),
        preset_store=presets or MemoryPresetStore(),
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()
    _pump(0.05)


@pytest.fixture
def window_factory(gtk_display, project_theme) -> Iterator[Callable[..., object]]:
    created: list[object] = []

    def factory(path: Path, **kwargs: object) -> object:
        window = _window(path, **kwargs)
        created.append(window)
        return window

    yield factory

    for window in created:
        _close(window)


def _open_panel(window: object) -> None:
    window.present()
    panel = window._view_panel
    panel.open()
    assert _pump_until(lambda: panel.popover.get_visible()), "the popover did not open"
    _pump(0.05)


def _section(window: object):
    return window._view_panel.presets


def _label_text(window: object) -> str:
    labels = _by_class(_section(window).widget(), "volna-preset-name")
    assert len(labels) == 1

    return labels[0].get_text()


def _list_names(window: object) -> list[str]:
    """Preset names the open inline list shows, in order."""
    section = _section(window)
    names = []
    for item in _by_class(section.widget(), "volna-preset-item"):
        buttons = _by_class(item, "volna-preset-apply")
        if not buttons:
            continue
        rows = _by_class(buttons[0], "volna-preset-item-name")
        names.append(rows[0].get_text() if rows else "")
    return names


def _expand_list(window: object) -> None:
    if _section(window).list_open:
        return

    select = _by_class(_section(window).widget(), "volna-preset-select")
    assert len(select) == 1
    select[0].emit("clicked")
    _pump(0.05)
    assert _section(window).list_open


def _apply(window: object, name: str) -> None:
    for item in _by_class(_section(window).widget(), "volna-preset-item"):
        apply = _by_class(item, "volna-preset-apply")
        if not apply:
            continue
        if _by_class(apply[0], "volna-preset-item-name")[0].get_text() == name:
            apply[0].emit("clicked")
            _pump(0.1)
            return
    raise AssertionError(f"preset {name!r} is not in the list")


def _settings(window: object) -> ViewSettings:
    return window._active_tab.view_settings


def _dialog_button(dialog: object, label: str):
    for button in _by_class(dialog.widget, "volna-preset-dialog-button"):
        if button.get_label() == label:
            return button
    raise AssertionError(f"dialog button {label!r} not found")


# -- the section in the panel ------------------------------------------------


def test_the_presets_section_is_the_first_one(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)

    from volna.view_panel.presets import PRESETS_TITLE

    titles = [
        label.get_text()
        for label in _by_class(window._view_panel.popover, "volna-view-section-title")
    ]
    assert titles[0] == PRESETS_TITLE
    assert titles.count(PRESETS_TITLE) == 1


def test_the_field_names_the_preset_that_matches_the_initial_view() -> None:
    """A stored view equal to a preset's snapshot is labelled with that preset."""
    default = BUILTIN_PRESETS[0]
    window = _window(Path("/"), settings=default.settings)
    try:
        _open_panel(window)
        assert _label_text(window) == "По умолчанию"
        assert window._presets.selected_id == DEFAULT_PRESET_ID
    finally:
        _close(window)


def test_the_field_says_manual_when_no_preset_matches() -> None:
    window = _window(Path("/"), settings=ViewSettings())  # details, not a preset
    try:
        _open_panel(window)
        assert _label_text(window) == _unmanaged_label()
        assert window._presets.selected_id is None
    finally:
        _close(window)


def test_the_list_shows_the_four_builtin_presets(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)

    assert _list_names(window) == BUILTIN_NAMES


def test_the_trigger_opens_and_closes_the_list(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    select = _by_class(_section(window).widget(), "volna-preset-select")[0]

    select.emit("clicked")
    _pump(0.05)
    assert _section(window).list_open

    select.emit("clicked")
    _pump(0.05)
    assert not _section(window).list_open


def test_builtin_presets_have_no_rename_or_delete_actions(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)

    assert _by_class(_section(window).widget(), "volna-preset-act") == []


# -- applying ----------------------------------------------------------------


def test_applying_a_preset_writes_its_snapshot_into_the_active_tab(
    window_factory,
) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)

    _apply(window, "Крупные значки")

    settings = _settings(window)
    assert settings.view_mode is ViewMode.ICONS
    assert settings.sort_key is SortKey.NAME
    assert settings.reverse is False
    assert settings.zoom == 85
    assert _label_text(window) == "Крупные значки"


def test_applying_a_preset_closes_the_list(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)

    _apply(window, "Без группировки")

    assert not _section(window).list_open
    assert window._view_panel.popover.get_visible()


def test_a_manual_change_switches_the_label_to_manual(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)
    _apply(window, "Плотный список")
    assert _label_text(window) == "Плотный список"

    # The user unticks «Плотная раскладка» in «Параметры».
    window._view_panel._on_change({"compact": False})
    _pump(0.05)

    assert _label_text(window) == _unmanaged_label()


def test_returning_to_the_preset_snapshot_names_it_again(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)
    _apply(window, "Плотный список")

    window._view_panel._on_change({"compact": False})
    _pump(0.05)
    window._view_panel._on_change({"compact": True})
    _pump(0.05)

    assert _label_text(window) == "Плотный список"


# -- saving ------------------------------------------------------------------


def _open_save(window: object) -> object:
    _by_class(_section(window).widget(), "volna-preset-save")[0].emit("clicked")
    _pump(0.1)
    assert window._save_dialog.is_open

    return window._save_dialog


def _entry(dialog: object) -> object:
    return _by_class(dialog.widget, "volna-preset-dialog-entry")[0]


def test_the_save_dialog_suggests_the_current_preset_name_copy() -> None:
    default = BUILTIN_PRESETS[0]
    window = _window(Path("/"), settings=default.settings)
    try:
        _open_panel(window)
        _open_save(window)
        assert _entry(window._save_dialog).get_text() == "По умолчанию (копия)"
    finally:
        _close(window)


def test_the_save_dialog_suggests_my_view_in_manual_mode(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)

    assert _entry(dialog).get_text() == "Мой вид"
    assert _by_class(dialog.widget, "volna-preset-hint")[0].get_text() == (
        "Новый пресет будет добавлен в список"
    )


def test_saving_creates_a_custom_preset_and_selects_it(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("Мой вид")
    _dialog_button(dialog, "Сохранить").emit("clicked")
    _pump(0.1)

    assert not dialog.is_open
    custom = window._presets.custom
    assert [preset.name for preset in custom] == ["Мой вид"]
    assert _label_text(window) == "Мой вид"
    # The dialog hands the panel back to the user.
    assert _pump_until(lambda: window._view_panel.popover.get_visible())


def test_a_saved_preset_is_offered_in_the_list(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _entry(_open_save(window)).set_text("Мой вид")
    _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
    _pump(0.1)

    _open_panel(window)
    _expand_list(window)

    assert _list_names(window) == [*BUILTIN_NAMES, "Мой вид"]


def test_save_is_disabled_for_an_empty_name(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("   ")
    _pump(0.05)

    assert not _dialog_button(dialog, "Сохранить").get_sensitive()


def test_the_dialog_warns_before_overwriting_an_existing_name(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("плотный СПИСОК")
    _pump(0.05)

    hint = _by_class(dialog.widget, "volna-preset-hint")[0]
    assert hint.get_text() == "Пресет с таким именем будет перезаписан"
    assert hint.has_css_class("is-warning")


def test_saving_with_a_builtin_name_overrides_it_in_the_list(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _entry(_open_save(window)).set_text("Плотный список")
    _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
    _pump(0.1)

    _open_panel(window)
    _expand_list(window)

    assert _list_names(window) == BUILTIN_NAMES  # same slot, custom behind it
    assert window._presets.find(DEFAULT_PRESET_ID) is not None
    assert window._presets.find("dense-list") is None


def test_cancelling_the_dialog_changes_nothing(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("Мой вид")
    _dialog_button(dialog, "Отмена").emit("clicked")
    _pump(0.1)

    assert not dialog.is_open
    assert window._presets.custom == ()
    assert _label_text(window) == _unmanaged_label()


# -- renaming ----------------------------------------------------------------


def _saved_window(window_factory) -> object:
    window = window_factory(Path("/"))
    _open_panel(window)
    _entry(_open_save(window)).set_text("Фото")
    _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
    _pump(0.1)
    _open_panel(window)
    _expand_list(window)
    return window


def _row(window: object, name: str) -> object:
    for item in _by_class(_section(window).widget(), "volna-preset-item"):
        apply = _by_class(item, "volna-preset-apply")
        if not apply:
            continue
        if _by_class(apply[0], "volna-preset-item-name")[0].get_text() == name:
            return item
    raise AssertionError(f"preset {name!r} is not in the list")


def _open_rename(window: object, name: str) -> object:
    """Click the pencil of ``name`` and return the rename dialog."""
    _by_class(_row(window, name), "volna-preset-act")[0].emit("clicked")
    _pump(0.1)
    assert window._rename_dialog.is_open

    return window._rename_dialog


def test_a_custom_preset_gets_rename_and_delete_actions(window_factory) -> None:
    window = _saved_window(window_factory)

    assert len(_by_class(_section(window).widget(), "volna-preset-act")) == 2


def test_rename_opens_a_dialog_prefilled_with_the_current_name(
    window_factory,
) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")

    titles = [
        label.get_text()
        for label in _by_class(dialog.widget, "volna-preset-dialog-title")
    ]
    assert titles == ["Переименовать пресет"]
    assert _entry(dialog).get_text() == "Фото"
    assert not _dialog_button(dialog, "Переименовать").get_sensitive(), (
        "confirming an unchanged name would write nothing"
    )


def test_rename_does_not_rebuild_the_list_rows(window_factory) -> None:
    """The old inline editor rebuilt every row and scrolled the list away."""
    window = _saved_window(window_factory)
    before = _by_class(_section(window).widget(), "volna-preset-item")

    _open_rename(window, "Фото")

    after = _by_class(_section(window).widget(), "volna-preset-item")
    assert [id(item) for item in after] == [id(item) for item in before]


def test_rename_updates_the_name_and_the_field(window_factory) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("Снимки")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.1)

    assert not dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Снимки"]
    assert _label_text(window) == "Снимки"


def test_rename_keeps_the_list_open_and_the_panel_visible(window_factory) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("Снимки")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.2)

    assert _section(window).list_open
    assert window._view_panel.popover.get_visible()
    assert "Снимки" in _list_names(window)


def test_rename_rejects_a_builtin_name_and_keeps_the_dialog_open(
    window_factory,
) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("Крупные значки")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.1)

    assert dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Фото"]
    hint = _by_class(dialog.widget, "volna-preset-hint")
    assert [label.get_text() for label in hint if label.get_visible()] == [
        "Пресет с таким именем уже существует"
    ]


def test_rename_rejects_another_custom_name(window_factory) -> None:
    window = _saved_window(window_factory)
    _open_panel(window)
    _entry(_open_save(window)).set_text("Видео")
    _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
    _pump(0.1)
    _open_panel(window)
    _expand_list(window)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("видео")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.1)

    assert dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Фото", "Видео"]


def test_rename_confirm_is_disabled_for_an_empty_name(window_factory) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("   ")
    _pump(0.05)

    assert not _dialog_button(dialog, "Переименовать").get_sensitive()
    _entry(dialog).emit("activate")
    _pump(0.05)
    assert dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Фото"]


def test_cancelling_rename_keeps_the_old_name(window_factory) -> None:
    window = _saved_window(window_factory)

    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("Снимки")
    _dialog_button(dialog, "Отмена").emit("clicked")
    _pump(0.1)

    assert not dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Фото"]
    assert _label_text(window) == "Фото"


def test_rename_can_be_undone_by_renaming_again(window_factory) -> None:
    """A mis-rename is recoverable: rename is a name change, not a new preset."""
    window = _saved_window(window_factory)
    dialog = _open_rename(window, "Фото")
    _entry(dialog).set_text("Опечатка")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.1)

    dialog = _open_rename(window, "Опечатка")
    _entry(dialog).set_text("Фото")
    _dialog_button(dialog, "Переименовать").emit("clicked")
    _pump(0.1)

    assert [preset.name for preset in window._presets.custom] == ["Фото"]


# -- deleting ----------------------------------------------------------------


def test_delete_asks_for_confirmation_with_the_name(window_factory) -> None:
    window = _saved_window(window_factory)

    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")  # the bin
    _pump(0.1)

    dialog = window._delete_dialog
    assert dialog.is_open
    texts = [
        label.get_text()
        for label in _by_class(dialog.widget, "volna-preset-dialog-text")
    ]
    assert texts == ["Пресет «Фото» будет удалён. Это действие нельзя отменить."]
    assert [preset.name for preset in window._presets.custom] == ["Фото"]


def test_confirming_delete_removes_the_preset(window_factory) -> None:
    window = _saved_window(window_factory)
    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.1)

    _dialog_button(window._delete_dialog, "Удалить").emit("clicked")
    _pump(0.1)

    assert window._presets.custom == ()
    assert not window._delete_dialog.is_open


def test_deleting_the_current_preset_falls_back_to_the_default(
    window_factory,
) -> None:
    window = _saved_window(window_factory)
    assert _label_text(window) == "Фото"

    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.1)
    _dialog_button(window._delete_dialog, "Удалить").emit("clicked")
    _pump(0.1)

    assert window._presets.selected_id == DEFAULT_PRESET_ID
    assert _label_text(window) == "По умолчанию"
    assert _settings(window).view_mode is ViewMode.COLUMNS


def test_cancelling_delete_keeps_the_preset(window_factory) -> None:
    window = _saved_window(window_factory)
    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.1)

    _dialog_button(window._delete_dialog, "Отмена").emit("clicked")
    _pump(0.1)

    assert [preset.name for preset in window._presets.custom] == ["Фото"]
    assert _label_text(window) == "Фото"


def test_deleting_an_override_restores_the_builtin(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _entry(_open_save(window)).set_text("Плотный список")
    _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
    _pump(0.1)
    _open_panel(window)
    _expand_list(window)
    assert window._presets.find("dense-list") is None

    item = _by_class(_section(window).widget(), "volna-preset-item")[1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.1)
    _dialog_button(window._delete_dialog, "Удалить").emit("clicked")
    _pump(0.1)

    assert window._presets.find("dense-list") is not None
    assert window._presets.find("dense-list").builtin


# -- persistence --------------------------------------------------------------


def _paths(tmp_path: Path) -> SettingsPaths:
    directory = tmp_path / "volna"
    return SettingsPaths(directory=directory, file=directory / "settings.json")


def test_custom_presets_survive_a_restart(gtk_display, project_theme, tmp_path) -> None:
    store = JsonPresetStore(_paths(tmp_path))
    first = _window(tmp_path, presets=store)
    try:
        first._presets.save("Фото", ViewSettings(view_mode=ViewMode.ICONS))
        first._persist_presets()
    finally:
        _close(first)

    assert (
        json.loads((tmp_path / "volna" / "presets.json").read_text("utf-8"))["presets"][
            0
        ]["name"]
        == "Фото"
    )

    second = _window(tmp_path, presets=JsonPresetStore(_paths(tmp_path)))
    try:
        assert [preset.name for preset in second._presets.custom] == ["Фото"]
    finally:
        _close(second)


def test_presets_are_stored_separately_from_the_last_view(
    gtk_display, project_theme, tmp_path
) -> None:
    store = JsonPresetStore(_paths(tmp_path))
    window = _window(tmp_path, presets=store)
    try:
        window._presets.save("Фото", ViewSettings())
        window._persist_presets()
    finally:
        _close(window)

    assert not (_paths(tmp_path).file).exists(), "presets must not touch settings.json"
    assert (tmp_path / "volna" / "presets.json").exists()


def test_broken_presets_file_does_not_block_start_up(
    gtk_display, project_theme, tmp_path
) -> None:
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    (paths.directory / "presets.json").write_text("{oops", encoding="utf-8")

    window = _window(tmp_path, presets=JsonPresetStore(paths))
    try:
        assert window._presets.custom == ()
        assert window._startup_issues
        assert [preset.name for preset in window._presets.presets()] == BUILTIN_NAMES
    finally:
        _close(window)


def test_a_preloaded_custom_preset_matching_the_view_is_named(
    gtk_display, project_theme, tmp_path
) -> None:
    snapshot = ViewSettings(view_mode=ViewMode.ICONS)
    preset = Preset("custom-a", "Фото", snapshot)
    window = _window(tmp_path, presets=MemoryPresetStore((preset,)), settings=snapshot)
    try:
        _open_panel(window)
        assert _label_text(window) == "Фото"
        assert window._presets.selected_id == "custom-a"
    finally:
        _close(window)


def test_grouping_and_sort_fields_travel_with_a_preset(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)

    _apply(window, "Без группировки")

    settings = _settings(window)
    assert settings.grouping is Grouping.NONE
    assert settings.sort_key is SortKey.SIZE
    assert settings.reverse is True


# -- dialog keyboard and backdrop ---------------------------------------------


def test_the_dialog_is_its_own_modal_window(window_factory) -> None:
    """Not an overlay of the main window: an overlay re-snapshots it entirely.

    That full-window repaint on open and close is what made the panel take
    noticeably long to come back after a rename.
    """
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)

    root = dialog.widget.get_root()
    assert isinstance(root, Gtk.Window)
    assert root is not window
    assert root.get_modal()
    assert root.get_transient_for() is window


def _press_key(widget: object, keyval: int) -> bool:
    """Deliver a key press to the widget's key controller (the real handler)."""
    for controller in widget.observe_controllers():
        if type(controller).__name__ == "EventControllerKey":
            handled = controller.emit("key-pressed", keyval, 0, 0)
            _pump(0.05)
            return bool(handled)
    raise AssertionError("the widget has no key controller")


def test_escape_cancels_the_save_dialog(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("Не сохранять")

    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    assert _press_key(_entry(dialog), Gdk.KEY_Escape)

    assert not dialog.is_open
    assert window._presets.custom == ()


def test_enter_in_the_entry_saves_the_preset(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    dialog = _open_save(window)
    _entry(dialog).set_text("С клавиатуры")

    _entry(dialog).emit("activate")
    _pump(0.1)

    assert not dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["С клавиатуры"]


def test_the_delete_dialog_focuses_cancel(window_factory) -> None:
    window = _saved_window(window_factory)
    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.2)

    dialog = window._delete_dialog
    assert dialog._cancel_button.has_focus() or _pump_until(
        lambda: dialog._cancel_button.has_focus(), 2.0
    )


def test_escape_closes_the_delete_dialog_without_deleting(window_factory) -> None:
    window = _saved_window(window_factory)
    item = _by_class(_section(window).widget(), "volna-preset-item")[-1]
    _by_class(item, "volna-preset-act")[1].emit("clicked")
    _pump(0.1)

    window._delete_dialog.cancel()
    _pump(0.05)

    assert not window._delete_dialog.is_open
    assert [preset.name for preset in window._presets.custom] == ["Фото"]


def test_a_read_only_store_keeps_presets_in_memory_and_says_so(
    gtk_display, project_theme, tmp_path
) -> None:
    class _ReadOnly:
        def load(self):
            from volna.display.presets_store import PresetDocument

            return PresetDocument()

        def save(self, presets):
            return False

    window = _window(tmp_path, presets=_ReadOnly())
    try:
        _open_panel(window)
        _entry(_open_save(window)).set_text("В памяти")
        _dialog_button(window._save_dialog, "Сохранить").emit("clicked")
        _pump(0.1)

        assert [preset.name for preset in window._presets.custom] == ["В памяти"]
        status = _by_class(window, "volna-status")[0].get_text()
        assert "не сохранено" in status
        assert "В памяти" in status
    finally:
        _close(window)


# -- per-tab semantics and no rescan ------------------------------------------


def test_applying_a_preset_does_not_rescan_the_directory(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)
    tab = window._active_tab
    assert _pump_until(lambda: tab.model.state.name == "READY")

    _apply(window, "Крупные значки")

    assert tab.model.state.name == "READY", "applying a preset must not rescan"


def test_a_preset_applies_to_the_active_tab_only(window_factory) -> None:
    window = window_factory(Path("/"))
    _open_panel(window)
    _expand_list(window)
    first = window._active_tab

    second = window._open_tab(first.path)
    _pump(0.1)
    window._view_panel.sync()
    _apply(window, "Крупные значки")

    assert second.view_settings.view_mode is ViewMode.ICONS
    assert first.view_settings.view_mode is not ViewMode.ICONS, (
        "a preset is a global template applied to the active tab only"
    )


def test_expanding_the_list_does_not_drop_the_accessible_state(
    window_factory,
) -> None:
    """The a11y EXPANDED state must reach GTK without a g_value warning."""
    import warnings

    window = window_factory(Path("/"))
    _open_panel(window)
    select = _by_class(_section(window).widget(), "volna-preset-select")[0]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        select.emit("clicked")
        _pump(0.05)
        select.emit("clicked")
        _pump(0.05)

    messages = [str(item.message) for item in caught]
    assert not [text for text in messages if "g_value" in text], messages
