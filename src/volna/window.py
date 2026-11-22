"""GTK4 main window for Volna (design direction C: Dolphin x JetBrains).

The window owns dynamic directory tabs and the toolbar: main menu, navigation,
display mode stub and the path widget (dropdown + inline editing). The right
panel from the design is temporarily hidden in the app.

Geometry follows the interface scale from design/spec/02-design-tokens.md §10:
the compact grid (100 %) is the base and size.px() scales it to the desktop's
UI scale, so the numbers below are the compact ones:

    40 toolbar + 1 hairline + app body + 1 hairline + 28 status = 900
    app body = 40 header band + 1 strong line + workspace + 1 line + 180 bottom
    workspace = 280 left panel + flex editor (the design's 300 right panel is hidden)

On a 125 % desktop the same numbers render as the design's «wide» preset
(50 / 350 / 225 / 1125) without a second stylesheet.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .core import ScanState  # noqa: E402
from .display import (  # noqa: E402
    BUILTIN_PRESETS,
    DEFAULT_CAPABILITIES,
    DEFAULT_PRESET_ID,
    MemoryPresetStore,
    Preset,
    PresetBook,
    PresetError,
    PresetStore,
    ViewCapabilities,
    ViewSettings,
    ViewSettingsStore,
    settings_fields,
)
from .geometry import edge_at as geometry_edge_at  # noqa: E402
from .glyph import icon, icon_path  # noqa: E402
from .size import px  # noqa: E402
from .tab import DirectoryTab  # noqa: E402
from .view_panel import ViewPanel  # noqa: E402
from .view_panel.preset_dialogs import (  # noqa: E402
    DeleteDialog,
    RenameDialog,
    SaveDialog,
)
from .view_panel.presets import PresetsSection  # noqa: E402
from .views.format import format_counters  # noqa: E402

_POINTER_CURSOR = Gdk.Cursor.new_from_name("pointer", None)

# Header areas without a control: Gtk.WindowHandle may open the window menu
# there (issue #20). Every other header widget is a control and must not.
_TITLEBAR_FREE = "volna-titlebar-free"

_LOG = logging.getLogger("volna.window")


def _downloads_path() -> Path:
    home = Path.home()
    for name in ("Загрузки", "Downloads"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home / "Downloads"


def _status_text(state: ScanState) -> str:
    if state is ScanState.SCANNING:
        return "Сканирование…"
    if state is ScanState.ERROR:
        return "Не удалось прочитать каталог"
    return "Готово."


def label(
    text: str,
    css_class: str | None = None,
    *,
    ellipsize: bool = False,
) -> Gtk.Label:
    widget = Gtk.Label(label=text)
    widget.set_halign(Gtk.Align.START)
    widget.set_valign(Gtk.Align.CENTER)
    if css_class:
        widget.add_css_class(css_class)
    if ellipsize:
        widget.set_ellipsize(Pango.EllipsizeMode.END)
    return widget


def hbox(spacing: int = 0) -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)


def vbox(spacing: int = 0) -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def make_clickable(widget: Gtk.Widget, callback: Callable[[], None]) -> None:
    gesture = Gtk.GestureClick()
    gesture.set_button(1)
    gesture.connect("released", lambda *_args: callback())
    widget.add_controller(gesture)
    widget.set_cursor(_POINTER_CURSOR)


def titlebar_free_space(widget: Gtk.Widget) -> Gtk.Widget:
    """Mark an empty part of the header that keeps the window menu (#20)."""
    widget.add_css_class(_TITLEBAR_FREE)
    return widget


def _inside_entry(widget: Gtk.Widget) -> bool:
    node: Gtk.Widget | None = widget
    while node is not None:
        if isinstance(node, Gtk.Entry):
            return True
        node = node.get_parent()
    return False


def _inside(widget: Gtk.Widget, ancestor: Gtk.Widget) -> bool:
    node: Gtk.Widget | None = widget
    while node is not None:
        if node is ancestor:
            return True
        node = node.get_parent()
    return False


def vertical_separator() -> Gtk.Box:
    separator = Gtk.Box()
    separator.add_css_class("volna-sep")
    separator.set_size_request(1, px(20))
    separator.set_valign(Gtk.Align.CENTER)
    separator.set_margin_start(px(6))
    separator.set_margin_end(px(6))
    return separator


def icon_stub(
    name: str,
    *,
    size: int = px(24),
    icon_size: int = px(16),
    tooltip: str | None = None,
    extra_class: str | None = None,
    dim: bool = False,
) -> Gtk.CenterBox:
    """Non-interactive control placeholder: a fixed box with a 1:1 icon."""
    # Gtk.Box packs a horizontal child at its natural width, so a glyph in a
    # fixed-size stub would hug the left edge of the hit area; CenterBox keeps
    # it in the middle.
    box = Gtk.CenterBox()
    box.add_css_class("volna-icon")
    if extra_class:
        box.add_css_class(extra_class)
    box.set_size_request(size, size)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    box.set_center_widget(icon(name, icon_size, dim=dim))
    if tooltip:
        box.set_tooltip_text(tooltip)
    return box


def nav_button(
    name: str,
    tooltip: str,
    callback: Callable[[], None],
) -> Gtk.Button:
    """Toolbar navigation button: a hit area around one glyph."""
    button = Gtk.Button()
    button.add_css_class("volna-icon")
    button.set_size_request(px(24), px(24))
    button.set_valign(Gtk.Align.CENTER)
    button.set_tooltip_text(tooltip)
    # Icon-only buttons need an accessible name: tooltips are not exposed as one.
    button.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    button.set_child(icon(name, px(16)))
    button.connect("clicked", lambda _button: callback())
    return button


class _PathMenu(Gtk.Popover):
    """The path field's popover shell: a bordered box of menu rows.

    Shared by the left-click navigation dropdown and the right-click context
    menu; each subclass fills the box with its own rows.
    """

    def __init__(self) -> None:
        super().__init__()
        self.add_css_class("volna-menu")
        self.set_has_arrow(False)

        self._items = vbox(px(2))
        self._items.add_css_class("volna-menu-box")
        self.set_child(self._items)

    def _clear(self) -> None:
        child = self._items.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._items.remove(child)
            child = following

    def add(self, item: Gtk.Widget) -> None:
        self._items.append(item)

    @property
    def items(self) -> Gtk.Box:
        return self._items

    def visible(self) -> bool:
        return self.get_visible()


class PathNavMenu(_PathMenu):
    """The path field's left-click dropdown: a list of known locations.

    Owns the chevron trigger; fills the popover on open and navigates the
    active tab when a row is chosen.
    """

    def __init__(
        self,
        *,
        known_paths: Callable[[], list[Path]],
        current_path: Callable[[], Path | None],
        on_select: Callable[[Path], None],
    ) -> None:
        super().__init__()
        self._known_paths = known_paths
        self._current_path = current_path
        self._on_select = on_select

        self._button = Gtk.MenuButton()
        self._button.add_css_class("volna-path-menu")
        self._button.set_valign(Gtk.Align.CENTER)
        self._button.set_tooltip_text("Перейти к пути")
        self._button.set_child(icon("down", px(16), dim=True))
        self._button.set_popover(self)
        self.connect("show", lambda *_args: self.fill())

    @property
    def button(self) -> Gtk.MenuButton:
        return self._button

    def fill(self) -> None:
        self._clear()
        current = self._current_path()
        for path in self._known_paths():
            self.add(self._row(path, path == current))

    def _row(self, path: Path, is_current: bool) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("volna-menu-item")
        button.add_css_class("volna-path-item")
        button.set_tooltip_text(str(path))
        if is_current:
            button.add_css_class("is-current")

        row = hbox(px(8))
        check_slot = Gtk.Box()
        check_slot.set_size_request(px(16), px(16))
        if is_current:
            check_slot.append(icon("check", px(16)))
        row.append(check_slot)
        path_label = label(str(path), "volna-menu-label", ellipsize=True)
        path_label.set_hexpand(True)
        path_label.set_max_width_chars(48)
        row.append(path_label)
        button.set_child(row)
        button.connect(
            "clicked", lambda _button, target=path: self._on_row_clicked(target)
        )
        return button

    def _on_row_clicked(self, path: Path) -> None:
        self.close()
        self._on_select(path)

    def open(self) -> None:
        self._button.set_active(True)

    def close(self) -> None:
        if self._button.get_active():
            self._button.set_active(False)


class PathContextMenu(_PathMenu):
    """The path field's right-click menu: copy the current path.

    Anchored to the location widget; the single row copies the active tab's
    path, not the ellipsized label.
    """

    def __init__(
        self,
        anchor: Gtk.Widget,
        *,
        on_copy: Callable[[], None],
    ) -> None:
        super().__init__()
        self.set_parent(anchor)
        self._on_copy = on_copy

        self.add(self._row())

    def _row(self) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("volna-menu-item")
        button.set_tooltip_text("Скопировать текущий путь")

        row = hbox(px(8))
        row.append(label("Копировать путь", "volna-menu-label"))
        button.set_child(row)
        button.connect("clicked", lambda *_args: self._on_row_clicked())
        return button

    def _on_row_clicked(self) -> None:
        self.popdown()
        self._on_copy()

    def popup_at(self, x: float, y: float) -> None:
        # Point the menu at the press: a popover anchored to a widget floats
        # near that widget, so aim it at the exact cursor rather than the anchor.
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self.set_pointing_to(rect)
        self.popup()


class MainWindow(Gtk.ApplicationWindow):
    """Main Volna window: chrome, header band, empty panels."""

    _toolbar_height = px(40)
    _window_button_width = px(40)

    def __init__(
        self,
        *,
        start_path: Path | None = None,
        initial_settings: ViewSettings,
        settings_store: ViewSettingsStore,
        capabilities: ViewCapabilities = DEFAULT_CAPABILITIES,
        startup_issues: tuple[str, ...] = (),
        preset_store: PresetStore | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.set_title("Волна")
        self.set_decorated(False)
        self.set_default_size(px(1440), px(900))
        self.set_size_request(px(900), px(600))
        self.set_resizable(True)
        self.add_css_class("volna-window")

        self._tabs: list[DirectoryTab] = []
        self._tab_widgets: dict[DirectoryTab, Gtk.Box] = {}
        self._tab_close_buttons: dict[DirectoryTab, Gtk.Button] = {}
        self._tab_title_labels: dict[DirectoryTab, Gtk.Label] = {}
        self._tab_icons: dict[DirectoryTab, Gtk.Image] = {}
        self._active_tab: DirectoryTab | None = None
        self._note_timeout: int | None = None
        self._capabilities = capabilities
        self._initial_settings = initial_settings.normalized(capabilities)
        self._settings_store = settings_store
        self._startup_issues = startup_issues
        self._preset_store = preset_store or MemoryPresetStore()
        preset_document = self._preset_store.load()
        self._startup_issues = startup_issues + preset_document.issues
        self._presets = PresetBook(preset_document.presets)
        initial_preset = self._presets.preset_for(self._initial_settings, capabilities)
        self._presets.select(initial_preset.id if initial_preset is not None else None)
        self._presets_section = PresetsSection(self)
        self._save_dialog = SaveDialog(self)
        self._rename_dialog = RenameDialog(self)
        self._delete_dialog = DeleteDialog(self)
        self._view_panel = self._create_view_panel()

        self._install_actions()
        self.set_child(self._content())
        self.connect("close-request", self._on_close_request)
        self._open_tab(Path(start_path) if start_path is not None else Path.home())

    # -- chrome -------------------------------------------------------

    def _toolbar(self) -> Gtk.Box:
        bar = hbox(px(8))
        bar.add_css_class("volna-toolbar")
        # Gaps between the controls are the header's free space (issue #20).
        bar.add_css_class(_TITLEBAR_FREE)
        bar.set_size_request(-1, px(40))

        bar.append(self._main_menu_button())
        bar.append(titlebar_free_space(vertical_separator()))

        navigation = hbox(px(2))
        self._back_button = nav_button("back", "Назад", self._go_back)
        self._fwd_button = nav_button("fwd", "Вперёд", self._go_forward)
        self._up_button = nav_button("up", "В родительскую папку", self._go_up)
        navigation.append(self._back_button)
        navigation.append(self._fwd_button)
        navigation.append(self._up_button)
        bar.append(navigation)
        bar.append(titlebar_free_space(vertical_separator()))

        bar.append(self._view_panel.trigger())
        bar.append(self._path_widget())

        spacer = titlebar_free_space(Gtk.Box())
        spacer.set_size_request(px(8), -1)
        bar.append(spacer)

        bar.append(icon_stub("gear", tooltip="Настройки"))
        bar.append(titlebar_free_space(vertical_separator()))
        bar.append(self._window_controls())

        return bar

    def _main_menu_button(self) -> Gtk.MenuButton:
        button = Gtk.MenuButton()
        button.add_css_class("volna-icon")
        button.add_css_class("volna-menu-button")
        button.set_size_request(px(32), px(32))
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text("Главное меню")
        button.set_child(icon("menu", px(20)))
        self._menu_button = button
        self._menu_popover = self._main_menu()
        # A tooltip on the trigger would hang over the open menu: drop it while
        # the menu is shown and restore it on close.
        self._menu_popover.connect(
            "show", lambda *_args: self._menu_button.set_tooltip_text(None)
        )
        self._menu_popover.connect(
            "closed", lambda *_args: self._menu_button.set_tooltip_text("Главное меню")
        )
        button.set_popover(self._menu_popover)
        return button

    def _main_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("volna-menu")
        popover.set_has_arrow(False)

        items = vbox(px(2))
        items.add_css_class("volna-menu-box")
        items.append(self._menu_item("Новая вкладка", "win.new-tab", shortcut="Ctrl+T"))
        items.append(self._menu_separator())
        self._close_menu_item = self._menu_item(
            "Закрыть вкладку", "win.close-tab", shortcut="Ctrl+W"
        )
        items.append(self._close_menu_item)

        popover.set_child(items)
        return popover

    def _menu_item(
        self, text: str, action: str, *, shortcut: str | None = None
    ) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("volna-menu-item")
        button.set_action_name(action)
        button.connect("clicked", lambda *_args: self._menu_popover.popdown())

        row = hbox(px(8))
        row.append(label(text, "volna-menu-label"))
        if shortcut is not None:
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            row.append(spacer)
            row.append(label(shortcut, "volna-menu-shortcut"))
        button.set_child(row)
        return button

    def _menu_separator(self) -> Gtk.Box:
        separator = Gtk.Box()
        separator.add_css_class("volna-menu-sep")
        separator.set_size_request(-1, 1)
        return separator

    def _create_view_panel(self) -> ViewPanel:
        return ViewPanel(
            settings=self._current_view_settings,
            update=self._update_view_settings,
            capabilities=self._capabilities,
            presets=self._presets_section,
        )

    # -- presets (PresetActions) ------------------------------------------

    def visible_presets(self) -> tuple[Preset, ...]:
        return self._presets.presets()

    def active_preset(self) -> Preset | None:
        """The preset the field names: the selection first, then any match.

        Two presets can hold the same snapshot (a custom copy of a built-in);
        the one the user picked must win over the first one in the list.
        """
        settings = self._current_view_settings()
        applied = self._presets.applied(settings, self._capabilities)
        if applied is not None:
            return applied

        return self._presets.preset_for(settings, self._capabilities)

    def apply_preset(self, preset_id: str) -> None:
        preset = self._presets.find(preset_id)
        tab = self._active_tab
        if preset is None or tab is None:
            return

        self._update_view_settings(**settings_fields(preset.settings))
        self._presets.select(preset_id)
        self._view_panel.sync()

    def open_rename_dialog(self, preset_id: str) -> None:
        preset = self._presets.find(preset_id)
        if preset is None or preset.builtin:
            return

        self._rename_dialog.open(
            preset.name,
            on_save=lambda name: self._rename_preset(preset_id, name),
            on_done=self._panel_restore(),
        )

    def close_panel(self) -> None:
        self._view_panel.close()

    def _rename_preset(self, preset_id: str, name: str) -> str | None:
        try:
            renamed = self._presets.rename(preset_id, name)
        except PresetError as exc:
            return str(exc)

        self._view_panel.sync()
        self._report_preset_saved(f"Пресет переименован: {renamed.name}")
        return None

    def open_save_dialog(self) -> None:
        current = self._current_view_settings()
        active = self._presets.preset_for(current, self._capabilities)
        suggested = f"{active.name} (копия)" if active is not None else "Мой вид"
        existing = [preset.name for preset in self._presets.presets()]
        self._save_dialog.open(
            suggested,
            existing,
            on_save=lambda name: self._save_preset(name, current),
            on_done=self._panel_restore(),
        )

    def _save_preset(self, name: str, settings: ViewSettings) -> str | None:
        try:
            saved = self._presets.save(name, settings)
        except PresetError as exc:
            return str(exc)

        self._view_panel.sync()
        self._report_preset_saved(f"Пресет сохранён: {saved.name}")
        return None

    def open_delete_dialog(self, preset_id: str) -> None:
        preset = self._presets.find(preset_id)
        if preset is None or preset.builtin:
            return

        self._delete_dialog.open(
            preset.name,
            on_confirm=lambda: self._delete_preset(preset_id),
            on_done=self._panel_restore(),
        )

    def _delete_preset(self, preset_id: str) -> None:
        preset = self._presets.find(preset_id)
        if preset is None:
            return

        was_selected = self._presets.delete(preset_id)
        if was_selected:
            self._presets.select(DEFAULT_PRESET_ID)
            default = BUILTIN_PRESETS[0]
            self._update_view_settings(**settings_fields(default.settings))

        self._view_panel.sync()
        self._report_preset_saved(f"Пресет удалён: {preset.name}")

    def _panel_restore(self) -> Callable[[], None]:
        """Close the panel for a dialog and hand it back when the dialog ends.

        The popover holds a grab, so an open dialog could not take keyboard
        focus. The preset menu is restored too: the action came from a row in
        it. The menu is a child popover, so it waits for the panel to be shown.
        """
        menu_was_open = self._presets_section.menu_open
        self._view_panel.close()

        def restore() -> None:
            self._view_panel.open()
            if menu_was_open:
                GLib.idle_add(self._reopen_preset_menu)

        return restore

    def _reopen_preset_menu(self) -> bool:
        self._presets_section.open_menu()
        return False

    def _persist_presets(self) -> bool:
        saved = self._preset_store.save(self._presets.custom)
        if not saved:
            _LOG.warning("cannot save presets; they stay in memory")
        return saved

    def _report_preset_saved(self, done: str) -> None:
        """Announce the change, but never claim a write that did not happen."""
        if self._persist_presets():
            self._show_status_note(done)
            return

        self._show_status_note(f"{done} (не сохранено: изменения только в памяти)")

    def _current_view_settings(self) -> ViewSettings:
        tab = self._active_tab
        return tab.view_settings if tab is not None else self._initial_settings

    def _update_view_settings(self, **changes: object) -> bool:
        tab = self._active_tab
        if tab is None:
            return False

        applied = tab.update_view_settings(**changes)
        if applied:
            self._apply_density(tab.view_settings.compact)
            self._forget_selection_if_manual()
        return applied

    def _forget_selection_if_manual(self) -> None:
        """A manual change to the snapshot ends the selection (design §18.3)."""
        if self._presets.selected() is None:
            return

        if (
            self._presets.applied(self._current_view_settings(), self._capabilities)
            is None
        ):
            self._presets.clear_selection()

    def _apply_density(self, compact: bool) -> None:
        if compact:
            self.add_css_class("volna-density-compact")
        else:
            self.remove_css_class("volna-density-compact")

    def _path_widget(self) -> Gtk.Box:
        wrapper = hbox(0)
        wrapper.add_css_class("volna-path")
        wrapper.set_hexpand(True)
        wrapper.set_size_request(-1, px(28))
        wrapper.set_valign(Gtk.Align.CENTER)
        self._path_wrapper = wrapper

        display = hbox(0)
        display.set_hexpand(True)

        location = hbox(px(6))
        location.add_css_class("volna-path-btn")
        location.set_hexpand(True)
        location.set_tooltip_text("Перейти к пути")
        location.append(icon("folder", px(16)))
        self._path_label = label(str(Path.home()), "volna-path-label", ellipsize=True)
        self._path_label.set_hexpand(True)
        location.append(self._path_label)
        self._path_location = location
        self._path_nav_menu = PathNavMenu(
            known_paths=self._nav_known_paths,
            current_path=self._nav_current_path,
            on_select=self._on_path_menu_selected,
        )
        self._path_context_menu = PathContextMenu(
            location, on_copy=self._copy_active_path
        )
        context_gesture = Gtk.GestureClick()
        context_gesture.set_button(3)
        context_gesture.connect("pressed", self._on_path_right_click)
        location.add_controller(context_gesture)
        make_clickable(location, self._open_path_menu)
        display.append(location)
        display.append(self._path_nav_menu.button)

        self._path_edit_button = icon_stub("pencil", tooltip="Изменить путь")
        make_clickable(self._path_edit_button, self._start_path_edit)
        display.append(self._path_edit_button)

        self._path_entry = Gtk.Entry()
        self._path_entry.add_css_class("volna-path-entry")
        self._path_entry.set_hexpand(True)
        self._path_entry.set_tooltip_text("Введите путь и нажмите Enter")
        self._path_entry.connect("activate", self._commit_path_edit)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_path_key_pressed)
        self._path_entry.add_controller(key_controller)
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_path_focus_leave)
        self._path_entry.add_controller(focus_controller)

        self._path_stack = Gtk.Stack()
        self._path_stack.set_hexpand(True)
        self._path_stack.add_named(display, "display")
        self._path_stack.add_named(self._path_entry, "edit")
        wrapper.append(self._path_stack)

        return wrapper

    def _open_path_menu(self) -> None:
        self._set_path_invalid(False)
        self._path_nav_menu.open()

    def _close_path_menu(self) -> None:
        self._path_nav_menu.close()

    def _on_path_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        del n_press
        if self._active_tab is None:
            return

        # Claim the press: Gtk.WindowHandle would otherwise turn it into the
        # titlebar menu (#20) — the path field is a header control.
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        self._path_context_menu.popup_at(x, y)

    def _copy_active_path(self) -> None:
        """Copy the active tab's path (issue #21), not the ellipsized label."""
        tab = self._active_tab
        if tab is None:
            return

        display = Gdk.Display.get_default()
        if display is None:
            return

        display.get_clipboard().set(str(tab.path))
        self._show_status_note("Путь скопирован")

    def _nav_known_paths(self) -> list[Path]:
        home = Path.home()
        candidates: list[Path] = []
        if self._active_tab is not None:
            candidates.append(self._active_tab.path)
        candidates.extend(
            [home, home / ".cache", _downloads_path(), Path("/home"), Path("/")]
        )

        paths: list[Path] = []
        for path in candidates:
            if path in paths or not path.is_dir():
                continue
            paths.append(path)
        return paths

    def _nav_current_path(self) -> Path | None:
        tab = self._active_tab
        return tab.path if tab is not None else None

    def _on_path_menu_selected(self, path: Path) -> None:
        self._navigate_active_tab(path)

    def _start_path_edit(self) -> None:
        tab = self._active_tab
        if tab is None:
            return
        self._set_path_invalid(False)
        self._close_path_menu()
        self._path_entry.set_text(str(tab.path))
        self._path_stack.set_visible_child_name("edit")
        if self.get_visible():
            GLib.idle_add(self._focus_path_entry)

    def _focus_path_entry(self) -> bool:
        self._path_entry.grab_focus()
        self._path_entry.select_region(0, -1)
        return False

    def _cancel_path_edit(self) -> None:
        self._path_stack.set_visible_child_name("display")
        if self._active_tab is not None:
            self._path_label.set_text(str(self._active_tab.path))

    def _on_path_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._cancel_path_edit()
            return True
        return False

    def _on_path_focus_leave(self, *_args: object) -> None:
        if self._path_stack.get_visible_child_name() == "edit":
            self._cancel_path_edit()

    def _commit_path_edit(self, entry: Gtk.Entry) -> None:
        path = self._parse_path(entry.get_text())
        self._cancel_path_edit()
        if path is None:
            self._set_path_invalid(True)
            self._show_status_note("Путь недоступен")
            return
        self._navigate_active_tab(path)

    def _parse_path(self, text: str) -> Path | None:
        value = text.strip()
        if not value:
            path = Path("/")
        else:
            try:
                path = Path(value).expanduser()
            except (OSError, RuntimeError):
                return None

        if not path.is_absolute():
            base = (
                self._active_tab.path if self._active_tab is not None else Path.home()
            )
            path = base / path
        path = Path(os.path.normpath(path))

        return path if path.is_dir() else None

    def _navigate_active_tab(self, path: Path) -> None:
        tab = self._active_tab
        if tab is None:
            return
        self._set_path_invalid(False)
        if not tab.navigate(path):
            self._path_label.set_text(str(tab.path))

    def _go_back(self) -> None:
        if self._active_tab is not None:
            self._active_tab.go_back()

    def _go_forward(self) -> None:
        if self._active_tab is not None:
            self._active_tab.go_forward()

    def _go_up(self) -> None:
        if self._active_tab is not None:
            self._active_tab.go_up()

    def _on_tab_navigated(self, tab: DirectoryTab) -> None:
        """Mirror a tab's new location in the toolbar (back/forward/up too)."""
        if tab is not self._active_tab:
            return
        if self._path_stack.get_visible_child_name() == "edit":
            self._cancel_path_edit()
        self._set_path_invalid(False)
        self._path_label.set_text(str(tab.path))
        self._refresh_tab_widget(tab)
        self._update_nav_buttons()
        self._update_active_status()

    def _update_nav_buttons(self) -> None:
        tab = self._active_tab
        self._back_button.set_sensitive(tab is not None and tab.can_go_back)
        self._fwd_button.set_sensitive(tab is not None and tab.can_go_forward)
        self._up_button.set_sensitive(tab is not None and tab.can_go_up)

    def _refresh_tab_widget(self, tab: DirectoryTab) -> None:
        title = self._tab_title_labels.get(tab)
        if title is not None:
            self._configure_tab_title(title, tab.title)

        tab_icon = self._tab_icons.get(tab)
        if tab_icon is not None:
            tab_icon.set_from_file(str(self._tab_icon_file(tab)))
            tab_icon.set_pixel_size(px(16))

        widget = self._tab_widgets.get(tab)
        if widget is not None:
            widget.set_tooltip_text(str(tab.path))

    def _show_status_note(self, text: str) -> None:
        self._status_label.set_text(text)
        if self._note_timeout is not None:
            GLib.source_remove(self._note_timeout)
        self._note_timeout = GLib.timeout_add(2000, self._clear_status_note)

    def _clear_status_note(self) -> bool:
        self._note_timeout = None
        self._set_path_invalid(False)
        self._update_active_status()
        return False

    def _set_path_invalid(self, invalid: bool) -> None:
        if invalid:
            self._path_wrapper.add_css_class("is-invalid")
        else:
            self._path_wrapper.remove_css_class("is-invalid")

    def _window_controls(self) -> Gtk.Box:
        controls = hbox(0)

        minimize = icon_stub(
            "min", size=px(40), tooltip="Свернуть", extra_class="volna-win"
        )
        make_clickable(minimize, self.minimize)

        maximize = icon_stub(
            "max",
            size=px(40),
            tooltip="Развернуть на весь экран",
            extra_class="volna-win",
        )
        make_clickable(maximize, self._toggle_maximize)

        close = icon_stub(
            "close", size=px(40), tooltip="Закрыть", extra_class="volna-win"
        )
        close.add_css_class("volna-win-close")
        make_clickable(close, self.close)

        for button in (minimize, maximize, close):
            controls.append(button)
        return controls

    def _toggle_maximize(self) -> None:
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def _add_resize_handles(self, overlay: Gtk.Overlay) -> None:
        self._resize_overlay = overlay
        self._resize_handles = []
        handles = (
            (
                "nw",
                Gdk.SurfaceEdge.NORTH_WEST,
                "nw-resize",
                Gtk.Align.START,
                Gtk.Align.START,
            ),
            ("n", Gdk.SurfaceEdge.NORTH, "n-resize", Gtk.Align.FILL, Gtk.Align.START),
            (
                "ne",
                Gdk.SurfaceEdge.NORTH_EAST,
                "ne-resize",
                Gtk.Align.END,
                Gtk.Align.START,
            ),
            ("w", Gdk.SurfaceEdge.WEST, "w-resize", Gtk.Align.START, Gtk.Align.FILL),
            ("e", Gdk.SurfaceEdge.EAST, "e-resize", Gtk.Align.END, Gtk.Align.FILL),
            (
                "sw",
                Gdk.SurfaceEdge.SOUTH_WEST,
                "sw-resize",
                Gtk.Align.START,
                Gtk.Align.END,
            ),
            ("s", Gdk.SurfaceEdge.SOUTH, "s-resize", Gtk.Align.FILL, Gtk.Align.END),
            (
                "se",
                Gdk.SurfaceEdge.SOUTH_EAST,
                "se-resize",
                Gtk.Align.END,
                Gtk.Align.END,
            ),
        )
        for name, edge, cursor_name, halign, valign in handles:
            handle = Gtk.Box()
            handle.add_css_class("volna-resize")
            handle.add_css_class(f"volna-resize-{name}")
            handle.set_halign(halign)
            handle.set_valign(valign)
            if halign == Gtk.Align.FILL:
                handle.set_hexpand(True)
                handle.set_size_request(-1, px(6))
            elif valign == Gtk.Align.FILL:
                handle.set_vexpand(True)
                handle.set_size_request(px(6), -1)
            else:
                handle.set_size_request(px(12), px(12))
            cursor = Gdk.Cursor.new_from_name(cursor_name, None)
            if cursor is not None:
                handle.set_cursor(cursor)
            gesture = Gtk.GestureDrag()
            gesture.set_button(1)
            gesture.connect(
                "drag-begin",
                lambda _gesture, px, py, e=edge, h=handle: self._on_resize_drag_begin(
                    e, _gesture, h, px, py
                ),
            )
            handle.add_controller(gesture)
            overlay.add_overlay(handle)
            self._resize_handles.append(handle)

    def _on_resize_drag_begin(
        self,
        edge: Gdk.SurfaceEdge,
        gesture: Gtk.GestureDrag,
        handle: Gtk.Widget,
        press_x: float,
        press_y: float,
    ) -> None:
        # The WM takes the pointer grab for the whole resize operation and GTK
        # never sees the button release. The gesture on the pressed handle can
        # therefore keep the implicit grab and receive the *next* press at
        # coordinates outside its own allocation; route those events instead
        # of starting a bogus resize.
        allocation = handle.get_allocation()
        inside = 0 <= press_x < allocation.width and 0 <= press_y < allocation.height
        if inside:
            self._begin_resize(edge, gesture, handle, press_x, press_y)
            return

        window_x = allocation.x + int(press_x)
        window_y = allocation.y + int(press_y)
        # Keep the handles: the stuck gesture on the handle keeps receiving
        # presses, and routing them here is what makes the window usable again
        # without waiting for a grab release GTK will never see.
        self._dispatch_stuck_press(window_x, window_y, gesture)

    def _dispatch_stuck_press(self, x: int, y: int, gesture: Gtk.GestureDrag) -> None:
        surface = self.get_surface()
        device = gesture.get_current_event_device()
        if surface is None or device is None:
            return
        edge = self._edge_at(x, y)
        if edge is not None:
            surface.begin_resize(
                edge, device, 1, x, y, gesture.get_current_event_time()
            )
            return

        if y >= self._toolbar_height:
            return

        width = self.get_width()
        controls_left = width - 3 * self._window_button_width
        if x >= controls_left:
            index = min(2, (x - controls_left) // self._window_button_width)
            action = (self.minimize, self._toggle_maximize, self.close)[index]
            action()
            return

        surface.begin_move(device, 1, x, y, gesture.get_current_event_time())

    _EDGES = {
        "nw": Gdk.SurfaceEdge.NORTH_WEST,
        "n": Gdk.SurfaceEdge.NORTH,
        "ne": Gdk.SurfaceEdge.NORTH_EAST,
        "w": Gdk.SurfaceEdge.WEST,
        "e": Gdk.SurfaceEdge.EAST,
        "sw": Gdk.SurfaceEdge.SOUTH_WEST,
        "s": Gdk.SurfaceEdge.SOUTH,
        "se": Gdk.SurfaceEdge.SOUTH_EAST,
    }

    def _edge_at(self, x: int, y: int) -> Gdk.SurfaceEdge | None:
        name = geometry_edge_at(x, y, self.get_width(), self.get_height())
        if name is None:
            return None
        return self._EDGES[name]

    def _begin_resize(
        self,
        edge: Gdk.SurfaceEdge,
        gesture: Gtk.GestureDrag,
        handle: Gtk.Widget,
        press_x: float,
        press_y: float,
    ) -> None:
        surface = self.get_surface()
        device = gesture.get_current_event_device()
        if surface is None or device is None:
            return
        allocation = handle.get_allocation()
        surface.begin_resize(
            edge,
            device,
            1,
            allocation.x + int(press_x),
            allocation.y + int(press_y),
            gesture.get_current_event_time(),
        )

    def _install_titlebar_right_click(self, handle: Gtk.WindowHandle) -> None:
        """Keep the window menu on free header space, not on its controls (#20).

        ``Gtk.WindowHandle`` treats a right click anywhere below it as a
        titlebar right click. The toolbar is both a titlebar and a control
        strip, so claim button 3 over a control in the capture phase: the
        handle's own bubble gesture then never opens the menu. Areas marked
        ``volna-titlebar-free`` keep the standard behaviour.
        """
        gesture = Gtk.GestureClick()
        gesture.set_button(3)
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect("pressed", self._on_titlebar_right_click)
        handle.add_controller(gesture)

    def _on_titlebar_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        del n_press

        handle = gesture.get_widget()
        if handle is None:
            return

        target = handle.pick(int(x), int(y), Gtk.PickFlags.DEFAULT)
        if target is None or target is handle:
            return
        if target.has_css_class(_TITLEBAR_FREE):
            return

        # An entry opens its own context menu and claims the press itself;
        # claiming here would hide that menu instead of showing it.
        if _inside_entry(target):
            return

        # The path field shows its own context menu (issue #21) for the same
        # reason: the location widget claims the press in its bubble handler.
        if _inside(target, self._path_location):
            return

        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    # -- body ---------------------------------------------------------

    def _content(self) -> Gtk.Overlay:
        root = vbox(0)
        window_handle = Gtk.WindowHandle()
        window_handle.set_child(self._toolbar())
        self._install_titlebar_right_click(window_handle)
        root.append(window_handle)
        root.append(self._hairline())
        root.append(self._app_body())
        root.append(self._hairline())
        root.append(self._statusbar())

        overlay = Gtk.Overlay()
        overlay.set_child(root)
        self._add_resize_handles(overlay)
        return overlay

    def _app_body(self) -> Gtk.Box:
        body = hbox(0)
        body.set_vexpand(True)

        body.append(self._rail())

        center = vbox(0)
        center.set_hexpand(True)
        center.set_vexpand(True)
        center.append(self._header_band())
        center.append(self._hairline(strong=True))
        center.append(self._workspace())
        center.append(self._hairline())
        center.append(self._bottom_window())
        body.append(center)

        return body

    def _header_band(self) -> Gtk.Box:
        band = hbox(0)
        band.add_css_class("volna-band")
        band.set_size_request(-1, px(40))

        left = Gtk.CenterBox()
        left.add_css_class("volna-panel-header")
        left.set_size_request(px(280), -1)

        title = hbox(px(6))
        title.add_css_class("volna-panel-title")
        title.set_tooltip_text("Свернуть панель")
        title.append(icon("down", px(16), dim=True))
        title.append(label("Места", "volna-panel-title-label"))
        left.set_start_widget(title)

        left_actions = hbox(px(8))
        left_actions.append(icon_stub("refresh", tooltip="Обновить"))
        left_actions.append(icon_stub("more", tooltip="Действия"))
        left_actions.append(icon_stub("min", tooltip="Скрыть панель"))
        left.set_end_widget(left_actions)

        tabs = hbox(0)
        tabs.add_css_class("volna-tab-strip")
        tabs.set_hexpand(True)
        self._tab_strip = tabs

        # Unbounded tabs must not widen the window: scroll the strip
        # horizontally instead of clipping the last tabs.
        tab_scroll = Gtk.ScrolledWindow()
        tab_scroll.add_css_class("volna-tab-scroll")
        tab_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        tab_scroll.set_propagate_natural_height(True)
        tab_scroll.set_hexpand(True)
        tab_scroll.set_child(tabs)
        self._tab_scroll = tab_scroll

        band.append(left)
        band.append(tab_scroll)
        return band

    def _tab_widget(self, tab: DirectoryTab) -> Gtk.Box:
        widget = hbox(px(6))
        widget.add_css_class("volna-tab")
        widget.set_tooltip_text(str(tab.path))

        tab_icon = icon(tab.icon_name, px(16))
        self._tab_icons[tab] = tab_icon
        widget.append(tab_icon)

        title = label(tab.title, "volna-tab-label", ellipsize=True)
        self._configure_tab_title(title, tab.title)
        self._tab_title_labels[tab] = title
        widget.append(title)

        close = Gtk.Button()
        close.add_css_class("volna-tab-close")
        close.set_child(icon("close", px(12)))
        close.set_valign(Gtk.Align.CENTER)
        close.set_tooltip_text("Закрыть вкладку")
        close.connect("clicked", lambda _button, current=tab: self._close_tab(current))
        self._tab_close_buttons[tab] = close
        widget.append(close)

        make_clickable(widget, lambda: self._activate(tab))
        return widget

    def _tab_icon_file(self, tab: DirectoryTab) -> Path:
        return icon_path(tab.icon_name, px(16))

    def _configure_tab_title(self, title: Gtk.Label, text: str) -> None:
        title.set_text(text)
        # width-chars keeps the label from collapsing to its "…" minimum when
        # many tabs compete for space; that minimum is what makes the scrolled
        # tab strip show its horizontal scrollbar instead of squeezing tabs.
        title.set_width_chars(min(len(text), 18))
        title.set_max_width_chars(18)

    def _workspace(self) -> Gtk.Box:
        workspace = hbox(0)
        workspace.set_vexpand(True)
        workspace.set_size_request(-1, px(200))

        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_panel.add_css_class("volna-panel")
        left_panel.add_css_class("volna-panel-left")
        left_panel.set_size_request(px(280), -1)
        left_panel.set_vexpand(True)

        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        editor.add_css_class("volna-editor")
        editor.set_hexpand(True)
        editor.set_size_request(px(200), -1)

        editor_header = hbox(0)
        editor_header.add_css_class("volna-editor-header")
        editor_header.set_size_request(-1, px(32))
        self._counts_label = label("", "volna-editor-counts", ellipsize=True)
        self._counts_label.set_hexpand(True)
        self._counts_label.set_margin_start(px(12))
        editor_header.append(self._counts_label)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)

        editor.append(editor_header)
        editor.append(self._stack)

        workspace.append(left_panel)
        workspace.append(editor)
        return workspace

    def _rail(self) -> Gtk.Box:
        rail = vbox(0)
        rail.add_css_class("volna-rail")
        rail.set_size_request(px(40), -1)
        rail.set_vexpand(True)

        items = [
            ("home", "Места", True),
            ("folder", "Файлы", False),
            ("star", "Закладки", False),
            ("clock", "Недавние", False),
            ("drive", "Устройства", False),
            ("network", "Сеть", False),
            ("separator", "", False),
            ("trash", "Корзина", False),
        ]

        for name, tooltip, active in items:
            if name == "separator":
                separator = Gtk.Box()
                separator.add_css_class("volna-rail-sep")
                separator.set_size_request(px(20), 1)
                separator.set_halign(Gtk.Align.CENTER)
                rail.append(separator)
                continue
            button = icon_stub(
                name,
                size=px(32),
                icon_size=px(20),
                tooltip=tooltip,
                extra_class="volna-rail-btn",
            )
            if active:
                button.add_css_class("is-active")
            rail.append(button)

        return rail

    def _bottom_window(self) -> Gtk.Box:
        bottom = vbox(0)
        bottom.add_css_class("volna-bottom")
        bottom.set_size_request(-1, px(180))

        header = Gtk.CenterBox()
        header.add_css_class("volna-bottom-header")
        header.set_size_request(-1, px(40))

        tabs = hbox(0)
        tabs.append(self._bottom_tab("Операции", active=True))
        tabs.append(self._bottom_tab("Журнал"))
        header.set_start_widget(tabs)

        actions = hbox(px(8))
        actions.set_margin_end(px(6))
        actions.append(icon_stub("min", tooltip="Свернуть панель"))
        actions.append(icon_stub("more", tooltip="Действия"))
        header.set_end_widget(actions)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.add_css_class("volna-bottom-content")
        content.set_size_request(-1, px(140))

        bottom.append(header)
        bottom.append(content)
        return bottom

    def _bottom_tab(self, text: str, *, active: bool = False) -> Gtk.Box:
        tab = hbox(0)
        tab.add_css_class("volna-bottom-tab")
        if active:
            tab.add_css_class("is-active")
        tab.append(label(text))
        return tab

    def _statusbar(self) -> Gtk.Box:
        status = hbox(px(12))
        status.add_css_class("volna-statusbar")
        status.set_size_request(-1, px(28))

        status_text = label("Готово.", "volna-status", ellipsize=True)
        status_text.set_hexpand(True)
        self._status_label = status_text
        status.append(status_text)

        right = hbox(px(8))
        right.append(icon("disk", px(14)))
        right.append(label("свободно 22,8 ГиБ", "volna-status-item"))
        right.append(label("·", "volna-status-sep"))
        right.append(label("sdc1", "volna-status-item volna-mono"))
        status.append(right)
        return status

    # -- tabs and actions -----------------------------------------------

    def _install_actions(self) -> None:
        new_tab = Gio.SimpleAction.new("new-tab", None)
        new_tab.connect("activate", self._on_new_tab_action)
        self.add_action(new_tab)

        self._close_action = Gio.SimpleAction.new("close-tab", None)
        self._close_action.connect("activate", self._on_close_tab_action)
        self.add_action(self._close_action)

    def _on_new_tab_action(self, *_args: object) -> None:
        self._open_tab(self._new_tab_path())

    def _on_close_tab_action(self, *_args: object) -> None:
        self._close_active_tab()

    def _new_tab_path(self) -> Path:
        if self._active_tab is not None:
            return self._active_tab.path
        return Path.home()

    def _open_tab(self, path: Path) -> DirectoryTab:
        parent = self._active_tab
        view_settings = (
            parent.view_settings if parent is not None else self._initial_settings
        )
        tab = DirectoryTab(
            path,
            on_change=self._on_tab_change,
            on_navigate=self._on_tab_navigated,
            view_settings=view_settings,
            capabilities=self._capabilities,
        )
        self._tabs.append(tab)
        self._stack.add_child(tab.widget)

        widget = self._tab_widget(tab)
        self._tab_widgets[tab] = widget
        self._tab_strip.append(widget)

        self._activate(tab)
        self._refresh_tab_controls()
        return tab

    def _activate(self, tab: DirectoryTab) -> None:
        if tab not in self._tab_widgets:
            return

        self._active_tab = tab
        self._stack.set_visible_child(tab.widget)
        if self._path_stack.get_visible_child_name() == "edit":
            self._cancel_path_edit()
        self._path_label.set_text(str(tab.path))
        for current, widget in self._tab_widgets.items():
            if current is tab:
                widget.add_css_class("is-active")
            else:
                widget.remove_css_class("is-active")
        tab.ensure_loaded()
        self._apply_density(tab.view_settings.compact)
        self._update_active_status()
        self._update_nav_buttons()
        self._view_panel.sync()
        self._reveal_tab(tab)

    def _reveal_tab(self, tab: DirectoryTab) -> None:
        if not self.get_visible():
            return
        # The tab is laid out only after this turn: scroll on the next idle so
        # its allocation is known.
        GLib.idle_add(self._scroll_tab_into_view, tab, 0)

    def _scroll_tab_into_view(self, tab: DirectoryTab, attempts: int) -> bool:
        widget = self._tab_widgets.get(tab)
        if widget is None or widget.get_width() == 0:
            if attempts < 5:
                GLib.idle_add(self._scroll_tab_into_view, tab, attempts + 1)
            return False

        ok, bounds = widget.compute_bounds(self._tab_strip)
        if not ok:
            return False

        adjustment = self._tab_scroll.get_hadjustment()
        if adjustment is None:
            return False
        value = adjustment.get_value()
        page = adjustment.get_page_size()
        left = bounds.get_x()
        right = left + bounds.get_width()
        if left < value:
            adjustment.set_value(left)
        elif right > value + page:
            adjustment.set_value(min(right - page, adjustment.get_upper() - page))
        return False

    def _close_active_tab(self) -> None:
        if self._active_tab is not None:
            self._close_tab(self._active_tab)

    def _close_tab(self, tab: DirectoryTab) -> None:
        if len(self._tabs) <= 1 or tab not in self._tabs:
            return

        index = self._tabs.index(tab)
        was_active = tab is self._active_tab
        self._tabs.pop(index)
        self._stack.remove(tab.widget)
        self._tab_strip.remove(self._tab_widgets.pop(tab))
        self._tab_close_buttons.pop(tab)
        self._tab_title_labels.pop(tab)
        self._tab_icons.pop(tab)
        tab.close()

        if was_active:
            self._activate(self._tabs[max(0, index - 1)])
        self._refresh_tab_controls()

    def _refresh_tab_controls(self) -> None:
        can_close = len(self._tabs) > 1
        for button in self._tab_close_buttons.values():
            button.set_visible(can_close)
        self._close_action.set_enabled(can_close)
        self._close_menu_item.set_sensitive(can_close)
        self._update_nav_buttons()

    def _on_tab_change(self, tab: DirectoryTab) -> None:
        if tab is not self._active_tab:
            return
        self._update_active_status()

    def _update_active_status(self) -> None:
        tab = self._active_tab
        if tab is None:
            return
        self._counts_label.set_text(format_counters(tab.model.counters()))

        if tab.model.state is ScanState.READY and self._startup_issues:
            note = self._startup_issues[0]
            self._startup_issues = ()
            self._show_status_note(note)
            return

        self._status_label.set_text(_status_text(tab.model.state))

    def _on_close_request(self, *_args: object) -> bool:
        if self._note_timeout is not None:
            GLib.source_remove(self._note_timeout)
            self._note_timeout = None

        self._view_panel.close()
        self._save_view_settings()

        for tab in self._tabs:
            tab.close()
        return False

    def _save_view_settings(self) -> None:
        tab = self._active_tab
        if tab is None:
            return

        if not self._settings_store.save(tab.view_settings):
            _LOG.warning("cannot save the last view; the session keeps it")

    def _hairline(self, *, strong: bool = False) -> Gtk.Box:
        line = Gtk.Box()
        line.add_css_class("hairline")
        if strong:
            line.add_css_class("strong")
        line.set_size_request(-1, 1)
        return line
