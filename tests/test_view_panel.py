"""View panel widget tests (Xvfb): trigger, popover contents, sync and updates.

The panel is composed in isolation (a bare :class:`Gtk.Window`), so these tests
do not depend on the real window integration. Native GTK controls are asserted
through their own state (``get_active``), never through pixels.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

_WINDOW_SIZE = (1200, 700)
_POPOVER_WIDTH_BASE = 320  # design/spec 03 §11; scaled by size.px()


# -- GTK / app imports -------------------------------------------------------
# Importing Gtk before the private Xvfb exists can hang, so every GTK and volna
# import happens inside helpers called from tests (the gtk_display fixture has
# already set DISPLAY by then).


def _gtk():
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    return Gtk


def _glib():
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    return GLib


def _gdk():
    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    return Gdk


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _texts(root: object, css_class: str) -> list[str]:
    return [widget.get_text() for widget in _by_class(root, css_class)]


def _pump(seconds: float = 0.1) -> None:
    GLib = _glib()
    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


# -- harness -----------------------------------------------------------------


class _Harness:
    """A window hosting one View panel wired to a mutable fake tab snapshot."""

    def __init__(
        self,
        *,
        settings: object | None = None,
        capabilities: object | None = None,
        sync_on_update: bool = False,
        setting_features: object | None = None,
    ) -> None:
        from volna.display import V1_CAPABILITIES, ViewSettings
        from volna.view_panel import ViewPanel

        self._sync_on_update = sync_on_update
        self.capabilities = (
            capabilities if capabilities is not None else V1_CAPABILITIES
        )
        self.settings = settings if settings is not None else ViewSettings()
        self.calls: list[dict[str, object]] = []

        self.panel = ViewPanel(
            settings=self._snapshot,
            update=self._update,
            capabilities=self.capabilities,
            setting_features=setting_features,
        )

        Gtk = _gtk()
        self.window = Gtk.Window()
        self.window.set_default_size(*_WINDOW_SIZE)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.append(self.panel.trigger())
        self.window.set_child(row)
        self.window.present()
        _pump(0.2)

    # callbacks the panel talks to

    def _snapshot(self) -> object:
        return self.settings

    def _update(self, **changes: object) -> bool:
        self.calls.append(changes)
        self.settings = self.settings.merged(self.capabilities, **changes)
        if self._sync_on_update:
            self.panel.sync()
        return True

    # convenience

    @property
    def trigger(self):
        return self.panel.trigger()

    @property
    def popover(self):
        return self.panel.popover

    def open(self) -> None:
        self.panel.open()
        _pump(0.3)

    def sync(self) -> None:
        self.panel.sync()
        _pump(0.05)

    def close(self) -> None:
        self.panel.close()
        _pump(0.2)

    def widget_by_label(self, css_class: str, label: str):
        for widget in _by_class(self.window, css_class):
            if widget.get_label() == label:
                return widget
        raise AssertionError(f"{css_class} row {label!r} is not rendered")

    # -- geometry (X11 root coordinates) ------------------------------

    def trigger_root_rect(self) -> tuple[int, int, int, int]:
        """The trigger's box on the screen."""
        return _widget_root_rect(self.window, self.trigger)

    def surface_root_rect(self) -> tuple[int, int, int, int]:
        """The popup surface's box on the screen (it includes the shadow)."""
        native = self.popover.get_native()
        if native is None:
            return (0, 0, 0, 0)
        surface = native.get_surface()
        if surface is None:
            return (0, 0, 0, 0)
        origin = _surface_origin(surface)
        if origin is None:
            return (0, 0, 0, 0)
        return (
            origin[0],
            origin[1],
            self.popover.get_width(),
            self.popover.get_height(),
        )

    def shadow_inset(self) -> int:
        """How far the popup surface reaches beyond the panel's card.

        GTK builds the surface around the card: the drop shadow of the theme
        becomes a transparent margin of the surface.
        """
        surface = self.surface_root_rect()
        return (surface[2] - self.popover.get_size_request()[0]) // 2

    def destroy(self) -> None:
        self.panel.popover.popdown()
        _pump(0.1)
        self.window.destroy()
        _pump(0.05)


@pytest.fixture(scope="session")
def project_theme(gtk_display) -> Iterator[None]:
    """Load the project theme: the popup geometry depends on its CSS.

    GTK builds the popup surface around the drop shadow of ``theme.css``, so
    the geometry assertions are only meaningful with the real stylesheet.
    """
    Gdk = _gdk()
    Gtk = _gtk()

    provider = Gtk.CssProvider()
    provider.load_from_string(_theme_css_path().read_text(encoding="utf-8"))
    display = Gdk.Display.get_default()
    if display is None:
        pytest.skip("no display")

    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    yield


@pytest.fixture
def panel(gtk_display, project_theme) -> Iterator[object]:
    created: list[_Harness] = []

    def factory(**kwargs: object) -> _Harness:
        harness = _Harness(**kwargs)
        created.append(harness)
        return harness

    yield factory

    for harness in created:
        harness.destroy()


def _settings(**changes: object):
    from volna.display import ViewSettings

    return ViewSettings(**changes)


def _px(base: int) -> int:
    from volna.size import px

    return px(base)


# -- trigger -----------------------------------------------------------------


def test_trigger_is_the_view_menu_button(panel) -> None:
    Gtk = _gtk()
    harness = panel()

    trigger = harness.trigger
    assert isinstance(trigger, Gtk.MenuButton)
    assert trigger.has_css_class("volna-view-trigger")
    assert trigger.has_css_class("volna-menu-button")
    assert trigger.get_accessible_role() == Gtk.AccessibleRole.BUTTON

    views = _by_class(trigger, "volna-view")
    assert len(views) == 1
    assert _texts(trigger, "volna-view-label") == ["Вид"]
    assert trigger.get_tooltip_text() == "Вид"


def test_trigger_opens_and_closes_the_popover(panel) -> None:
    harness = panel()

    harness.open()
    assert harness.popover.get_visible()
    assert harness.trigger.get_active()

    harness.close()
    assert not harness.popover.get_visible()
    assert not harness.trigger.get_active()

    harness.trigger.set_active(True)
    _pump(0.3)
    assert harness.popover.get_visible()


# -- popover contents --------------------------------------------------------


def test_popover_geometry_contract(panel) -> None:
    Gtk = _gtk()
    harness = panel()

    popover = harness.popover
    assert isinstance(popover, Gtk.Popover)
    assert popover.has_css_class("volna-view-popover")
    assert popover.get_has_arrow() is False
    # The content box is exactly `px(320)`; the popover *surface* adds
    # transparent shadow margins, so the rendered surface is wider.
    assert popover.get_size_request()[0] == _px(_POPOVER_WIDTH_BASE)

    scroller = popover.get_child()
    assert isinstance(scroller, Gtk.ScrolledWindow)
    assert scroller.get_policy().vscrollbar_policy == Gtk.PolicyType.AUTOMATIC
    assert scroller.get_max_content_height() == _px(820)
    assert scroller.get_propagate_natural_height()


def test_popover_has_only_live_v1_sections(panel) -> None:
    harness = panel()

    assert _texts(harness.window, "volna-view-section-title") == [
        "Сортировка",
        "Параметры",
    ]
    assert [
        widget.get_label() for widget in _by_class(harness.window, "volna-radio")
    ] == ["Дата изменения", "Размер", "Имя"]
    assert [
        widget.get_label() for widget in _by_class(harness.window, "volna-check")
    ] == ["Папки перед файлами", "Показывать скрытые файлы", "Плотная раскладка"]
    assert [
        widget.get_label() for widget in _by_class(harness.window, "volna-seg-btn")
    ] == [
        "По убыванию",
        "По возрастанию",
    ]
    assert _texts(harness.window, "volna-view-footer") == [
        "Изменения применяются сразу"
    ]

    # Deferred V1 sections must not be rendered at all (no dead controls).
    labels = [
        widget.get_text()
        for widget in _walk(harness.window)
        if hasattr(widget, "get_text")
    ]
    for deferred in ("Пресеты", "Группировка", "Режим просмотра", "Масштаб"):
        assert deferred not in labels


def test_density_checkbox_requires_the_capability(panel) -> None:
    from volna.display import ViewCapabilities, ViewMode

    capabilities = ViewCapabilities(
        modes=frozenset({ViewMode.DETAILS}),
        grouping=False,
        density=False,
        zoom_modes=frozenset(),
    )
    harness = panel(capabilities=capabilities)

    assert [
        widget.get_label() for widget in _by_class(harness.window, "volna-check")
    ] == ["Папки перед файлами", "Показывать скрытые файлы"]


# -- feature decomposition ---------------------------------------------------


def test_setting_features_are_separate_classes_and_modules() -> None:
    from volna.view_panel.settings import SETTING_FEATURES
    from volna.view_panel.settings.base import SettingFeature

    assert all(issubclass(feature, SettingFeature) for feature in SETTING_FEATURES)
    ids = [feature.id for feature in SETTING_FEATURES]
    assert len(set(ids)) == len(ids), f"duplicate setting ids: {ids}"
    assert [feature.section for feature in SETTING_FEATURES] == [
        "Сортировка",
        "Сортировка",
        "Сортировка",
        "Параметры",
        "Параметры",
    ]
    modules = {feature.__module__ for feature in SETTING_FEATURES}
    assert len(modules) == len(SETTING_FEATURES), "each setting must own its module"


def test_panel_composes_injected_features(panel) -> None:
    from volna.view_panel.controls import checkbox_row
    from volna.view_panel.settings.base import SettingFeature

    class FakeSetting(SettingFeature):
        id = "fake"
        section = "Тест"

        def __init__(self, on_change):
            super().__init__(on_change)
            self._button = None

        def widget(self):
            self._button = checkbox_row("Тестовая настройка")
            self._button.connect(
                "toggled", lambda button: self._emit(compact=button.get_active())
            )
            return self._button

        def sync(self, settings):
            if self._button is not None:
                self._button.set_active(settings.compact)

    harness = panel(setting_features=(FakeSetting,))

    # The injected feature replaces the default registry: the panel is generic.
    assert _texts(harness.window, "volna-view-section-title") == ["Тест"]
    assert [
        widget.get_label() for widget in _by_class(harness.window, "volna-check")
    ] == ["Тестовая настройка"]

    harness.widget_by_label("volna-check", "Тестовая настройка").set_active(True)
    _pump(0.1)

    assert harness.calls == [{"compact": True}]
    assert harness.settings.compact is True


def test_feature_changes_only_touch_view_settings_fields(panel) -> None:
    from dataclasses import fields

    from volna.display import ViewSettings

    harness = panel()
    harness.widget_by_label("volna-radio", "Имя").set_active(True)
    harness.widget_by_label("volna-seg-btn", "По возрастанию").set_active(True)
    harness.widget_by_label("volna-check", "Папки перед файлами").set_active(False)
    harness.widget_by_label("volna-check", "Показывать скрытые файлы").set_active(True)
    harness.widget_by_label("volna-check", "Плотная раскладка").set_active(True)
    _pump(0.1)

    known = {field.name for field in fields(ViewSettings)}
    emitted = {key for changes in harness.calls for key in changes}
    assert emitted == {"sort_key", "reverse", "folders_first", "show_hidden", "compact"}
    assert emitted <= known, f"features reported unknown fields: {emitted - known}"


# -- sync --------------------------------------------------------------------


def test_sync_reflects_the_active_snapshot(panel) -> None:
    from volna.display import SortKey

    harness = panel()
    harness.settings = _settings(
        sort_key=SortKey.NAME,
        reverse=False,
        folders_first=False,
        show_hidden=True,
        compact=True,
    )
    harness.sync()

    assert harness.widget_by_label("volna-radio", "Имя").get_active()
    assert harness.widget_by_label("volna-seg-btn", "По возрастанию").get_active()
    assert not harness.widget_by_label(
        "volna-check", "Папки перед файлами"
    ).get_active()
    assert harness.widget_by_label(
        "volna-check", "Показывать скрытые файлы"
    ).get_active()
    assert harness.widget_by_label("volna-check", "Плотная раскладка").get_active()
    assert not harness.widget_by_label("volna-radio", "Дата изменения").get_active()


def test_sync_does_not_report_changes_back(panel) -> None:
    from volna.display import SortKey

    harness = panel()
    harness.settings = _settings(sort_key=SortKey.SIZE, show_hidden=True)
    harness.sync()

    assert harness.calls == []


def test_open_resynchronizes_the_controls(panel) -> None:
    from volna.display import SortKey

    harness = panel()
    harness.settings = _settings(sort_key=SortKey.NAME, reverse=False)
    harness.open()

    assert harness.widget_by_label("volna-radio", "Имя").get_active()
    assert harness.widget_by_label("volna-seg-btn", "По возрастанию").get_active()


# -- user input --------------------------------------------------------------


def test_sort_key_change_calls_update(panel) -> None:
    from volna.display import SortKey

    harness = panel()
    harness.widget_by_label("volna-radio", "Имя").set_active(True)
    _pump(0.1)

    assert harness.calls == [{"sort_key": SortKey.NAME}]
    assert harness.settings.sort_key == SortKey.NAME


def test_direction_change_calls_update(panel) -> None:
    harness = panel()
    harness.widget_by_label("volna-seg-btn", "По возрастанию").set_active(True)
    _pump(0.1)

    assert harness.calls == [{"reverse": False}]
    assert harness.settings.reverse is False


def test_folders_first_change_calls_update(panel) -> None:
    harness = panel()
    assert harness.widget_by_label("volna-check", "Папки перед файлами").get_active()

    harness.widget_by_label("volna-check", "Папки перед файлами").set_active(False)
    _pump(0.1)

    assert harness.calls == [{"folders_first": False}]
    assert harness.settings.folders_first is False


def test_checkbox_changes_call_update(panel) -> None:
    harness = panel()

    harness.widget_by_label("volna-check", "Показывать скрытые файлы").set_active(True)
    _pump(0.1)
    harness.widget_by_label("volna-check", "Плотная раскладка").set_active(True)
    _pump(0.1)

    assert harness.calls == [{"show_hidden": True}, {"compact": True}]
    assert harness.settings.show_hidden is True
    assert harness.settings.compact is True


def test_update_that_syncs_does_not_recurse(panel) -> None:
    harness = panel(sync_on_update=True)

    harness.widget_by_label("volna-radio", "Размер").set_active(True)
    _pump(0.1)

    assert len(harness.calls) == 1


def test_toggling_the_active_radio_off_reports_nothing(panel) -> None:
    harness = panel()
    current = harness.widget_by_label("volna-radio", "Дата изменения")
    assert current.get_active()

    # A grouped CheckButton cannot be unchecked by a user click, but the
    # handler must stay silent if it happens programmatically.
    current.set_active(False)
    _pump(0.1)

    assert harness.calls == []


# -- geometry ----------------------------------------------------------------


def test_popover_is_left_aligned_with_the_trigger(panel) -> None:
    """The panel starts at the trigger's left edge and hangs 4 px below it."""
    harness = panel()
    harness.open()

    # The layout is part of the popup geometry and never changes while the
    # panel is open: GTK centres the popup on its anchor otherwise.
    assert harness.popover.get_halign() == _gtk().Align.START
    offset = harness.popover.get_offset()
    assert offset.x_offset == 0
    assert offset.y_offset == 4

    trigger = harness.trigger_root_rect()
    surface = harness.surface_root_rect()
    card_left = surface[0] + harness.shadow_inset()
    assert abs(card_left - trigger[0]) <= 1, "the card must start at the trigger"


def test_the_popover_surface_does_not_cover_the_trigger(panel) -> None:
    """The popup surface must not reach the trigger.

    GTK builds the popup surface around the panel's drop shadow: the shadow
    margin becomes part of the surface and swallows the clicks aimed at the
    trigger, so the panel eats every second click (the user has to click twice
    to open it again). The surface therefore has to start at the trigger's
    bottom edge, and the panel may not hang lower than its 4 px gap.
    """
    harness = panel()
    harness.open()

    trigger = harness.trigger_root_rect()
    surface = harness.surface_root_rect()
    bottom = trigger[1] + trigger[3]
    assert bottom <= surface[1] <= bottom + 4, (
        f"the popup surface does not fit between the trigger and the gap: "
        f"{surface} vs {trigger}"
    )


def test_the_panel_is_not_moved_after_it_is_shown(panel) -> None:
    """The panel appears where it stays: no re-positioning after the show.

    A geometry change while the popover is open makes GTK present the popup
    again, and the panel jumps under the cursor (a visible flicker).
    """
    harness = panel()
    shown_at: list[tuple[int, int]] = []

    def on_show(*_args: object) -> None:
        shown_at.append(harness.surface_root_rect()[:2])

    harness.popover.connect("show", on_show)
    harness.open()

    assert shown_at, "the popover was not shown"
    assert harness.surface_root_rect()[:2] == shown_at[0]


def test_tooltip_is_dropped_while_the_popover_is_open(panel) -> None:
    harness = panel()

    harness.open()
    assert harness.trigger.get_tooltip_text() is None

    harness.close()
    assert harness.trigger.get_tooltip_text() == "Вид"


def test_the_trigger_state_follows_the_panel(panel) -> None:
    """`active` describes the panel, not the other way round."""
    harness = panel()

    harness.open()
    assert harness.trigger.get_active()

    harness.close()
    assert not harness.trigger.get_active()
    assert not harness.popover.get_visible()


# -- keyboard ----------------------------------------------------------------

_X11_LIBRARIES = None


def _x11_libraries():
    global _X11_LIBRARIES

    if _X11_LIBRARIES is not None:
        return _X11_LIBRARIES

    x11_path = ctypes.util.find_library("X11")
    xtst_path = ctypes.util.find_library("Xtst")
    if x11_path is None or xtst_path is None:
        pytest.skip("libX11/libXtst are not installed")

    x11 = ctypes.CDLL(x11_path)
    xtst = ctypes.CDLL(xtst_path)

    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
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
    xtst.XTestFakeKeyEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_ulong,
    ]

    _X11_LIBRARIES = (x11, xtst)
    return _X11_LIBRARIES


def _surface_origin(surface) -> tuple[int, int] | None:
    """The origin of a GdkSurface in X11 root coordinates."""
    import gi

    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11

    x11, _ = _x11_libraries()
    display = x11.XOpenDisplay(None)
    if not display:
        pytest.skip("cannot open the X display")

    try:
        xid = GdkX11.X11Surface.get_xid(surface)
        ox, oy, child = ctypes.c_int(), ctypes.c_int(), ctypes.c_ulong()
        ok = x11.XTranslateCoordinates(
            display,
            xid,
            x11.XDefaultRootWindow(display),
            0,
            0,
            ctypes.byref(ox),
            ctypes.byref(oy),
            ctypes.byref(child),
        )
        return (ox.value, oy.value) if ok else None
    finally:
        x11.XCloseDisplay(display)


def _widget_root_rect(window, widget) -> tuple[int, int, int, int]:
    """The widget's box in X11 root coordinates."""
    native = window.get_native()
    surface = native.get_surface() if native is not None else None
    origin = _surface_origin(surface) if surface is not None else None
    if origin is None:
        pytest.skip("cannot locate the window on the X display")

    ok, bounds = widget.compute_bounds(window)
    if not ok:
        pytest.skip("the widget has no bounds yet")

    shift_x, shift_y = native.get_surface_transform()
    return (
        origin[0] + int(shift_x + bounds.get_x()),
        origin[1] + int(shift_y + bounds.get_y()),
        int(bounds.get_width()),
        int(bounds.get_height()),
    )


def _fake_key(name: str) -> None:
    x11, xtst = _x11_libraries()
    display = x11.XOpenDisplay(None)
    if not display:
        pytest.skip("cannot open the X display")

    try:
        keysym = x11.XStringToKeysym(name.encode())
        keycode = x11.XKeysymToKeycode(display, keysym)
        xtst.XTestFakeKeyEvent(display, keycode, True, 0)
        xtst.XTestFakeKeyEvent(display, keycode, False, 0)
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)
    _pump(0.3)


def test_escape_closes_the_popover(panel) -> None:
    harness = panel()
    harness.open()
    assert harness.popover.get_visible()

    _fake_key("Escape")

    assert not harness.popover.get_visible()
    assert not harness.trigger.get_active()


# -- theme contract ----------------------------------------------------------


def _theme_css_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "volna" / "theme.css"


def test_theme_stylesheet_parses() -> None:
    """theme.css must load without GTK parser errors (catches invalid selectors)."""
    Gtk = _gtk()
    errors: list[str] = []
    provider = Gtk.CssProvider()
    provider.connect(
        "parsing-error",
        lambda _provider, _section, error: errors.append(str(error)),
    )
    css = _theme_css_path().read_text(encoding="utf-8")
    try:
        provider.load_from_string(css)  # GTK >= 4.12
    except AttributeError:
        provider.load_from_data(css.encode())

    assert errors == []


def test_theme_stylesheet_has_a_view_panel_block() -> None:
    """theme.css is shipped as package data; guard the CSS contract classes."""
    css = _theme_css_path().read_text(encoding="utf-8")
    for selector in (
        ".volna-view-trigger",
        "popover.volna-view-popover > contents",
        ".volna-view-section",
        ".volna-radio > radio",
        ".volna-check > check",
        ".volna-seg button.toggle",
        ".volna-view-footer",
        ".volna-density-compact .volna-dt-name",
    ):
        assert selector in css
