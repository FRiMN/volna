"""The listing area must be the design canvas, not the GTK theme's background.

Issue #7: the listing views painted the background of the GTK theme, so under a
light theme the file captions (``#dfe1e5``) were almost unreadable and the
canvas token of ``design/spec/tokens.json`` was nowhere on screen. The check
reads the pixels of the presented window — the only way to see what the user
sees, and the only way to catch a rule that the cascade resolves elsewhere.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.display import (  # noqa: E402
    Grouping,
    MemoryViewSettingsStore,
    ViewMode,
    ViewSettings,
)

# The «bg.canvas» token of the dark theme (design/spec/tokens.json).
CANVAS = (0x1E, 0x1F, 0x22)


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _pump_until(condition, timeout: float = 10.0) -> bool:
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


def _pump(seconds: float = 0.3) -> None:
    """Let GTK finish the frame it started."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


def _listing_rect(window: object) -> tuple[int, int, int, int]:
    """The listing's rectangle in the coordinates of the window's surface.

    The window shows the whole app, so the check needs the listing's own
    rectangle rather than the colours of every pixel on the screen.
    """
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    editors = _by_class(window, "volna-editor")
    assert editors, "the window has no editor box"

    scrollers = [
        widget for widget in _walk(editors[0]) if isinstance(widget, Gtk.ScrolledWindow)
    ]
    scroller = next((s for s in scrollers if s.get_width() > 0), None)
    assert scroller is not None, "the listing has no allocated scrolled window"

    content = window.get_child()
    found, bounds = scroller.compute_bounds(content)
    assert found, "the listing is not inside the window"
    return (
        int(bounds.get_x()),
        int(bounds.get_y()),
        int(bounds.get_width()),
        int(bounds.get_height()),
    )


def _listing_is_painted(window: object) -> bool:
    """The editor counters turn on once the listing has been rendered."""
    counters = _by_class(window, "volna-editor-counts")
    return bool(counters and counters[0].get_text())


def _window(path: Path, settings: ViewSettings):
    from volna.window import MainWindow

    return MainWindow(
        start_path=path,
        initial_settings=settings,
        settings_store=MemoryViewSettingsStore(),
    )


def _directory(tmp_path: Path) -> Path:
    root = tmp_path / "каталог"
    root.mkdir()
    for index in range(12):
        (root / f"файл-{index}.txt").write_text("x" * index, encoding="utf-8")
    (root / "папка").mkdir()
    return root


def _surface(window: object):
    native = window.get_native()
    surface = native.get_surface() if native is not None else None
    assert surface is not None, "the window has no surface to read"
    return surface


def _same_origin(window: object, surface: object) -> None:
    """The content widget has to fill the surface, or the pixels are shifted.

    The listing's rectangle is computed in the coordinates of the window's
    content, and the pixels are read from the surface: both start at the top
    left corner only while the content covers the whole surface. A window with
    decorations or client-side shadows would shift the two apart, and the
    check would silently read another part of the window.
    """
    content = window.get_child()
    assert content.get_width() == surface.get_width(), (
        "the window content does not fill the surface: the pixel coordinates "
        "would be shifted"
    )
    assert content.get_height() == surface.get_height(), (
        "the window content does not fill the surface: the pixel coordinates "
        "would be shifted"
    )


# The four ways the app can present the listing: one table, one grid of tiles,
# one grid of tiles without groups and one band of columns.
_LISTINGS = {
    "details": ViewSettings(view_mode=ViewMode.DETAILS),
    "icons": ViewSettings(view_mode=ViewMode.ICONS),
    "icons-flat": ViewSettings(view_mode=ViewMode.ICONS, grouping=Grouping.NONE),
    "columns": ViewSettings(view_mode=ViewMode.COLUMNS),
}


@pytest.mark.parametrize("listing", sorted(_LISTINGS))
def test_the_listing_area_is_the_canvas(
    listing: str, tmp_path: Path, gtk_display, project_theme, x11_region
) -> None:
    """The listing is painted with the canvas colour, whatever the mode is.

    The listing used to take the background of the GTK theme (issue #7): under
    a light theme it was a nearly white rectangle with unreadable captions.
    """
    window = _window(_directory(tmp_path), _LISTINGS[listing])
    window.present()
    try:
        assert _pump_until(lambda: _listing_is_painted(window)), (
            "the listing never rendered"
        )
        _pump()

        x, y, width, height = _listing_rect(window)
        assert width > 0 and height > 0, "the listing has no size"

        surface = _surface(window)
        _same_origin(window, surface)
        colours = x11_region(surface, x, y, width, height)
        dominant, count = colours.most_common(1)[0]
        assert dominant == CANVAS, (
            f"the listing is painted #{dominant[0]:02x}{dominant[1]:02x}"
            f"{dominant[2]:02x}, not the canvas; "
            f"the colours are {colours.most_common(3)}"
        )
        assert count * 2 > width * height, (
            "the canvas does not cover the listing: the theme paints its rows"
        )
    finally:
        window.destroy()


def test_the_listing_ignores_the_theme_of_the_system(
    tmp_path: Path, gtk_display, project_theme, x11_region
) -> None:
    """A theme that paints the views in its own colour must not win.

    The canvas has to be the application's decision, not the theme's: the
    listings of issue #7 followed the theme, and the file captions became
    unreadable under a light theme.
    """
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gtk

    # A light theme, as the system would paint the views.
    hostile = Gtk.CssProvider()
    hostile.load_from_string(
        "columnview, listview, gridview { background-color: #ffffff; }"
        "columnview > header > button { background-color: #ffffff; }"
    )
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(
        display, hostile, Gtk.STYLE_PROVIDER_PRIORITY_THEME
    )
    try:
        window = _window(_directory(tmp_path), _LISTINGS["details"])
        window.present()
        try:
            assert _pump_until(lambda: _listing_is_painted(window)), (
                "the listing never rendered"
            )
            _pump()

            x, y, width, height = _listing_rect(window)
            surface = _surface(window)
            _same_origin(window, surface)
            colours = x11_region(surface, x, y, width, height)
            dominant, count = colours.most_common(1)[0]
            assert dominant == CANVAS, (
                "the listing followed the theme instead of the canvas"
            )
            assert count * 2 > width * height
        finally:
            window.destroy()
    finally:
        Gtk.StyleContext.remove_provider_for_display(display, hostile)


def _selectors(css: str) -> set[str]:
    """The selectors of a stylesheet, without their declarations."""
    selectors: set[str] = set()
    for block in re.findall(r"([^{}]+)\{", css):
        for part in block.split(","):
            selectors.add(" ".join(part.split()))
    return selectors


def test_the_theme_paints_the_listing_views_with_the_canvas() -> None:
    """A stylesheet lint: the canvas rule has to reach the views (issue #7).

    The behaviour is checked by the pixel tests above; this one keeps the
    stylesheet from losing the rule again. The rule on the scrolled window
    alone is not enough: the GTK theme paints the view widgets themselves.
    A commented-out rule is not a rule, so the comments are stripped first.
    """
    css = (Path(__file__).resolve().parents[1] / "src/volna/theme.css").read_text(
        encoding="utf-8"
    )
    active = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    selectors = _selectors(active)

    for selector in (
        ".volna-editor columnview",
        ".volna-editor listview",
        ".volna-editor gridview",
        ".volna-editor columnview > header > button",
    ):
        assert selector in selectors, f"the theme no longer paints {selector}"
