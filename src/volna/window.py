"""GTK4 main window for Volna (design direction C: Dolphin x JetBrains).

First milestone: window chrome and empty panels; header controls are stubs.
Geometry follows the size preset from design/spec/02-design-tokens.md §10:
the «wide» preset is the default (125 % of the compact grid), so the compact
numbers used below are scaled with size.px():

    50 toolbar + 1 hairline + app body + 1 hairline + 35 status = 1125
    app body = 50 header band + 1 strong line + workspace + 1 line + 225 bottom
    workspace = 350 left panel + flex editor + 375 right panel (rails 50 each)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, Gtk, Pango  # noqa: E402

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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Волна")
        self.set_decorated(False)
        self.set_default_size(px(1440), px(900))
        self.set_size_request(px(900), px(600))
        self.set_resizable(True)
        self.add_css_class("volna-window")
        self.add_css_class(SIZE_CLASS)

        self._tab_specs = [
            ("folder", ".cache", Path.home() / ".cache"),
            ("home", "Домашняя папка", Path.home()),
            ("down", "Загрузки", _downloads_path()),
        ]
        self._tabs: list[DirectoryTab] = []
        self._tab_widgets: list[Gtk.Box] = []
        self._active_index = 1

        self.set_child(self._content())
        self.connect("close-request", self._on_close_request)
        self._activate(self._active_index)

    # -- chrome -------------------------------------------------------

    def _toolbar(self) -> Gtk.Box:
        bar = hbox(px(8))
        bar.add_css_class("volna-toolbar")
        bar.set_size_request(-1, px(40))

        bar.append(
            icon_stub("menu", size=px(32), icon_size=px(20), tooltip="Главное меню")
        )
        bar.append(vertical_separator())

        navigation = hbox(px(2))
        navigation.append(
            icon_stub(
                "back", tooltip="Назад — недоступно", extra_class="volna-disabled"
            )
        )
        navigation.append(icon_stub("fwd", tooltip="Следующая вкладка"))
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
        wrapper = hbox(px(2))
        wrapper.add_css_class("volna-path")
        wrapper.set_hexpand(True)
        wrapper.set_size_request(-1, px(28))
        wrapper.set_valign(Gtk.Align.CENTER)

        location = hbox(px(6))
        location.add_css_class("volna-path-btn")
        location.set_hexpand(True)
        location.set_tooltip_text("Перейти к пути")
        location.append(icon("folder", px(16)))
        path_label = label(str(Path.home()), "volna-path-label", ellipsize=True)
        path_label.set_hexpand(True)
        self._path_label = path_label
        location.append(path_label)
        location.append(icon("down", px(16), dim=True))
        wrapper.append(location)

        wrapper.append(icon_stub("pencil", tooltip="Изменить путь"))
        return wrapper

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

        body.append(self._rail(left=True))

        center = vbox(0)
        center.set_hexpand(True)
        center.set_vexpand(True)
        center.append(self._header_band())
        center.append(self._hairline(strong=True))
        center.append(self._workspace())
        center.append(self._hairline())
        center.append(self._bottom_window())
        body.append(center)

        body.append(self._rail(left=False))
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
        self._tab_widgets = []
        for index, (icon_name, title, _path) in enumerate(self._tab_specs):
            widget = self._tab(icon_name, title, index=index)
            self._tab_widgets.append(widget)
            tabs.append(widget)

        right = Gtk.CenterBox()
        right.add_css_class("volna-panel-header")
        right.set_size_request(px(300), -1)
        right.set_start_widget(label("Сведения", "volna-panel-title-label"))

        right_actions = hbox(px(8))
        right_actions.append(icon_stub("more", tooltip="Действия"))
        right_actions.append(icon_stub("min", tooltip="Скрыть панель"))
        right.set_end_widget(right_actions)

        band.append(left)
        band.append(tabs)
        band.append(right)
        return band

    def _tab(self, icon_name: str, text: str, *, index: int) -> Gtk.Box:
        tab = hbox(px(6))
        tab.add_css_class("volna-tab")
        tab.append(icon(icon_name, px(16)))
        tab.append(label(text, "volna-tab-label", ellipsize=True))
        close = icon("close", px(12))
        close.add_css_class("volna-tab-close")
        tab.append(close)
        make_clickable(tab, lambda i=index: self._activate(i))
        return tab

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
        self._tabs = []
        for _icon, _title, path in self._tab_specs:
            tab = DirectoryTab(path, on_change=self._on_tab_change)
            self._tabs.append(tab)
            self._stack.add_child(tab.widget)

        editor.append(editor_header)
        editor.append(self._stack)

        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_panel.add_css_class("volna-panel")
        right_panel.add_css_class("volna-panel-right")
        right_panel.set_size_request(px(300), -1)
        right_panel.set_vexpand(True)

        workspace.append(left_panel)
        workspace.append(editor)
        workspace.append(right_panel)
        return workspace

    def _rail(self, *, left: bool) -> Gtk.Box:
        rail = vbox(0)
        rail.add_css_class("volna-rail")
        rail.set_size_request(px(40), -1)
        rail.set_vexpand(True)

        if left:
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
        else:
            items = [
                ("info", "Сведения", True),
                ("eye", "Предпросмотр", False),
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

    # -- tab wiring ---------------------------------------------------

    def _activate(self, index: int) -> None:
        self._active_index = index
        tab = self._tabs[index]
        self._stack.set_visible_child(tab.widget)
        self._path_label.set_text(str(tab.path))
        for position, widget in enumerate(self._tab_widgets):
            if position == index:
                widget.add_css_class("is-active")
            else:
                widget.remove_css_class("is-active")
        tab.ensure_loaded()
        self._update_active_status()

    def _on_tab_change(self, tab: DirectoryTab) -> None:
        if tab is not self._tabs[self._active_index]:
            return
        self._update_active_status()

    def _update_active_status(self) -> None:
        tab = self._tabs[self._active_index]
        self._status_label.set_text(_status_text(tab.model.state))
        counters = tab.model.counters()
        self._counts_label.set_text(
            f"{counters.folders} папок · {counters.files} файлов "
            f"({format_size(counters.total_size)})"
        )

    def _on_close_request(self, *_args: object) -> bool:
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
