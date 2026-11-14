"""Local SVG glyphs: asset paths and a ``Gtk.Image`` factory.

Icons ship pre-rendered per interface size under ``icons/<size>/`` and declare
that size in the SVG, so callers ask for the scaled size with ``px(16)`` and
never rescale the chrome: the wide preset uses the 20 px variants.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from .size import px  # noqa: E402

ICONS_DIR = Path(__file__).resolve().parent / "icons"


def icon_path(name: str, size: int = px(16)) -> Path:
    """Path to the ``size``-px variant of the ``name`` glyph."""
    return ICONS_DIR / str(size) / f"{name}.svg"


def icon(name: str, size: int = px(16), *, dim: bool = False) -> Gtk.Image:
    """A ``Gtk.Image`` with the ``size``-px ``name`` glyph from the local set."""
    image = Gtk.Image.new_from_file(str(icon_path(name, size)))
    # GtkImage measures its paintable at 16px by default (GTK 4.14), ignoring the
    # SVG's intrinsic size: without the explicit pixel size the 12/20px glyphs of
    # the toolbar, tabs and rails are all drawn at 16px with rescaled strokes.
    image.set_pixel_size(size)
    image.set_halign(Gtk.Align.CENTER)
    image.set_valign(Gtk.Align.CENTER)
    if dim:
        image.add_css_class("volna-icon-dim")
    return image
