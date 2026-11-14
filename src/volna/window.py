"""GTK4 main window for Volna (design direction C: Dolphin x JetBrains).

The window owns dynamic directory tabs and the toolbar: main menu, navigation,
display mode stub and the path widget (dropdown + inline editing). The right
panel from the design is temporarily hidden in the app.

Geometry follows the size preset from design/spec/02-design-tokens.md §10:
the «wide» preset is the default (125 % of the compact grid), so the compact
numbers used below are scaled with size.px():

    50 toolbar + 1 hairline + app body + 1 hairline + 35 status = 1125
    app body = 50 header band + 1 strong line + workspace + 1 line + 225 bottom
    workspace = 350 left panel + flex editor (the design's 375 right panel is hidden)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .core import ScanState  # noqa: E402
from .geometry import edge_at as geometry_edge_at  # noqa: E402
from .size import SIZE_CLASS, px  # noqa: E402
from .tab import DirectoryTab  # noqa: E402
from .views.format import format_size  # noqa: E402

_ICONS_DIR = Path(__file__).resolve().parent / "icons"
_POINTER_CURSOR = Gdk.Cursor.new_from_name("pointer", None)


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


def icon(name: str, size: int = px(16), *, dim: bool = False) -> Gtk.Image:
    image = Gtk.Image.new_from_file(str(_ICONS_DIR / str(size) / f"{name}.svg"))
    # GtkImage measures its paintable at 16px by default (GTK 4.14), ignoring the
    # SVG's intrinsic size: without the explicit pixel size the 12/20px glyphs of
    # the toolbar, tabs and rails are all drawn at 16px with rescaled strokes.
    image.set_pixel_size(size)
    image.set_halign(Gtk.Align.CENTER)
    image.set_valign(Gtk.Align.CENTER)
    if dim:
        image.add_css_class("volna-icon-dim")
    return image


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


class MainWindow(Gtk.ApplicationWindow):
    """Main Volna window: chrome, header band, empty panels."""

    _toolbar_height = px(40)
    _window_button_width = px(40)

    def __init__(self, *, start_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Волна")
        self.set_decorated(False)
        self.set_default_size(px(1440), px(900))
        self.set_size_request(px(900), px(600))
        self.set_resizable(True)
        self.add_css_class("volna-window")
        self.add_css_class(SIZE_CLASS)

        self._tabs: list[DirectoryTab] = []
        self._tab_widgets: dict[DirectoryTab, Gtk.Box] = {}
        self._tab_close_buttons: dict[DirectoryTab, Gtk.Button] = {}
        self._tab_title_labels: dict[DirectoryTab, Gtk.Label] = {}
        self._tab_icons: dict[DirectoryTab, Gtk.Image] = {}
        self._active_tab: DirectoryTab | None = None
        self._note_timeout: int | None = None

        self._install_actions()
        self.set_child(self._content())
        self.connect("close-request", self._on_close_request)
        self._open_tab(Path(start_path) if start_path is not None else Path.home())

    # -- chrome -------------------------------------------------------

    def _toolbar(self) -> Gtk.Box:
        bar = hbox(px(8))
        bar.add_css_class("volna-toolbar")
        bar.set_size_request(-1, px(40))

        bar.append(self._main_menu_button())
        bar.append(vertical_separator())

        navigation = hbox(px(2))
        navigation.append(
            icon_stub(
                "back", tooltip="Назад — недоступно", extra_class="volna-disabled"
            )
        )
        self._fwd_button = icon_stub("fwd", tooltip="Следующая вкладка")
        make_clickable(self._fwd_button, self._activate_next_tab)
        navigation.append(self._fwd_button)
        navigation.append(icon_stub("up", tooltip="В родительскую папку"))
        bar.append(navigation)
        bar.append(vertical_separator())

        bar.append(self._view_widget())
        bar.append(self._path_widget())

        spacer = Gtk.Box()
        spacer.set_size_request(px(8), -1)
        bar.append(spacer)

        bar.append(icon_stub("gear", tooltip="Настройки"))
        bar.append(vertical_separator())
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

    def _view_widget(self) -> Gtk.Box:
        button = hbox(px(6))
        button.add_css_class("volna-view")
        button.set_size_request(-1, px(28))
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text("Вид")
        button.append(icon("columns", px(16)))
        button.append(label("Вид", "volna-view-label"))
        button.append(icon("down", px(16), dim=True))
        return button

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
        self._path_menu_button = self._create_path_menu_button()
        make_clickable(location, self._open_path_menu)
        display.append(location)
        display.append(self._path_menu_button)

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

    def _create_path_menu_button(self) -> Gtk.MenuButton:
        button = Gtk.MenuButton()
        button.add_css_class("volna-path-menu")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text("Перейти к пути")
        button.set_child(icon("down", px(16), dim=True))

        popover = Gtk.Popover()
        popover.add_css_class("volna-menu")
        popover.set_has_arrow(False)
        items = vbox(px(2))
        items.add_css_class("volna-menu-box")
        items.add_css_class("volna-path-menu-box")
        popover.set_child(items)
        popover.connect("show", self._fill_path_menu)
        button.set_popover(popover)

        self._path_popover = popover
        self._path_menu_items = items
        return button

    def _open_path_menu(self) -> None:
        self._set_path_invalid(False)
        self._path_menu_button.set_active(True)

    def _close_path_menu(self) -> None:
        if self._path_menu_button.get_active():
            self._path_menu_button.set_active(False)

    def _fill_path_menu(self, *_args: object) -> None:
        child = self._path_menu_items.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._path_menu_items.remove(child)
            child = following

        for path in self._known_paths():
            self._path_menu_items.append(self._path_menu_item(path))

    def _known_paths(self) -> list[Path]:
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

    def _path_menu_item(self, path: Path) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("volna-menu-item")
        button.add_css_class("volna-path-item")
        button.set_tooltip_text(str(path))

        current = self._active_tab is not None and path == self._active_tab.path
        if current:
            button.add_css_class("is-current")

        row = hbox(px(8))
        check_slot = Gtk.Box()
        check_slot.set_size_request(px(16), px(16))
        if current:
            check_slot.append(icon("check", px(16)))
        row.append(check_slot)
        path_label = label(str(path), "volna-menu-label", ellipsize=True)
        path_label.set_hexpand(True)
        path_label.set_max_width_chars(48)
        row.append(path_label)
        button.set_child(row)
        button.connect(
            "clicked", lambda _button, target=path: self._on_path_menu_selected(target)
        )
        return button

    def _on_path_menu_selected(self, path: Path) -> None:
        self._close_path_menu()
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

    def _on_path_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
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
        if path == tab.path:
            self._path_label.set_text(str(tab.path))
            return

        tab.navigate(path)
        self._path_label.set_text(str(tab.path))
        self._refresh_tab_widget(tab)
        self._update_active_status()

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

    # -- body ---------------------------------------------------------

    def _content(self) -> Gtk.Overlay:
        root = vbox(0)
        window_handle = Gtk.WindowHandle()
        window_handle.set_child(self._toolbar())
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

        make_clickable(widget, lambda current=tab: self._activate(current))
        return widget

    def _tab_icon_file(self, tab: DirectoryTab) -> Path:
        return _ICONS_DIR / str(px(16)) / f"{tab.icon_name}.svg"

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
        tab = DirectoryTab(path, on_change=self._on_tab_change)
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
        self._update_active_status()
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

    def _activate_next_tab(self) -> None:
        if len(self._tabs) < 2 or self._active_tab is None:
            return
        index = self._tabs.index(self._active_tab)
        self._activate(self._tabs[(index + 1) % len(self._tabs)])

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
        self._fwd_button.set_sensitive(can_close)
        self._fwd_button.remove_css_class("volna-disabled")
        if not can_close:
            self._fwd_button.add_css_class("volna-disabled")

    def _on_tab_change(self, tab: DirectoryTab) -> None:
        if tab is not self._active_tab:
            return
        self._update_active_status()

    def _update_active_status(self) -> None:
        tab = self._active_tab
        if tab is None:
            return
        self._status_label.set_text(_status_text(tab.model.state))
        counters = tab.model.counters()
        self._counts_label.set_text(
            f"{counters.folders} папок · {counters.files} файлов "
            f"({format_size(counters.total_size)})"
        )

    def _on_close_request(self, *_args: object) -> bool:
        if self._note_timeout is not None:
            GLib.source_remove(self._note_timeout)
            self._note_timeout = None
        for tab in self._tabs:
            tab.close()
        return False

    def _hairline(self, *, strong: bool = False) -> Gtk.Box:
        line = Gtk.Box()
        line.add_css_class("hairline")
        if strong:
            line.add_css_class("strong")
        line.set_size_request(-1, 1)
        return line
