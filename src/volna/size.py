"""Interface scale derived from the desktop's UI settings.

The design grid is the compact 100 % layout (design/spec/02 §10): on the
reference desktop (10 pt UI font at 96 dpi) the root font is 14 px and the
chrome uses the compact metrics. The «wide» 125 % preset is the same grid on a
125 % desktop scale (root font 17.5 px), so it needs no second set of rules.

The scale follows the system font: ``GtkSettings:gtk-font-name`` at the
effective Xft DPI gives the desktop's UI text size, and the app keeps the
design's convention of being 5 % larger than the toolkit default (14 px at
10 pt). A different desktop font size therefore scales the interface instead
of leaving it at a hardcoded preset.
"""

from __future__ import annotations

import logging
from typing import Final

_LOG = logging.getLogger("volna.size")

# Compact design grid: 14 px body on the reference 100 % desktop.
BASE_FONT_PX: Final = 14.0
# Reference desktop: 10 pt UI font at 96 dpi, the toolkit default.
REFERENCE_FONT_PX: Final = 96 * 10 / 72
DEFAULT_DPI: Final = 96.0
MIN_SCALE: Final = 0.75
MAX_SCALE: Final = 2.5

# Compact 100 % until ``configure()`` reads the desktop: importing GtkSettings
# earlier would initialise GTK on whatever display the process happens to see,
# which is exactly what the application and the test suite must avoid.
_scale: float = 1.0


def ui_scale() -> float:
    """The interface scale (1.0 = compact 100 % grid)."""
    return _scale


def configure() -> float:
    """Resolve the scale once, after ``Gtk.init()`` has read the desktop settings."""
    global _scale
    _scale = detect_ui_scale()
    _LOG.info("interface scale %.3f (root font %.2f px)", _scale, base_font_px())
    return _scale


def base_font_px() -> float:
    """Root font size for the stylesheet: 14 px on the compact grid."""
    return BASE_FONT_PX * ui_scale()


# Every surface root, not just the window: a popover and a dialog window are
# their own surfaces in GTK, and a font size set on the window class does not
# reach them — the View panel then renders at the toolkit default (13.33 px)
# and silently ignores the interface scale.
SURFACE_FONT_SELECTOR: Final = "window, popover"


def root_font_css() -> str:
    """The stylesheet that puts the design's root font on every surface root."""
    return f"{SURFACE_FONT_SELECTOR} {{ font-size: {base_font_px():.4f}px; }}"


def px(base: int) -> int:
    """Scale a compact-grid metric to the active interface size."""
    return max(1, int(base * ui_scale() + 0.5))


def scale_for_font(font_px: float | None) -> float:
    """Scale from the effective UI font size; 1.0 when it cannot be read."""
    if font_px is None or font_px <= 0:
        return 1.0
    return min(MAX_SCALE, max(MIN_SCALE, font_px / REFERENCE_FONT_PX))


def detect_ui_scale() -> float:
    """Scale of the current desktop; 1.0 without GTK or an initialised display."""
    return scale_for_font(system_font_px())


def system_font_px() -> float | None:
    """Effective UI font size in logical pixels, or ``None`` when unavailable."""
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, Pango
    except (ImportError, ValueError):
        return None

    # Reading GtkSettings before Gtk.init() initialises GTK on its own and
    # opens whatever display DISPLAY points at; the app must not do that behind
    # the application's back, and tests rely on their own display.
    if not Gtk.is_initialized():
        return None

    settings = Gtk.Settings.get_default()
    if settings is None:
        return None

    name = settings.get_property("gtk-font-name") or "Sans 10"
    description = Pango.FontDescription.from_string(name)
    size = description.get_size()
    if size <= 0:
        return None
    if description.get_size_is_absolute():
        return size / Pango.SCALE

    dpi = settings.get_property("gtk-xft-dpi")
    dpi = dpi / 1024.0 if dpi and dpi > 0 else DEFAULT_DPI
    return size / Pango.SCALE * dpi / 72.0
