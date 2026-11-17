"""Local SVG glyphs: asset paths and a ``Gtk.Image`` factory.

Icons ship pre-rendered per interface size under ``icons/<size>/``, but every
variant shares the same 16-unit viewBox and only differs in its intrinsic
width/height, so any of them is a vector that ``Gtk.Image`` renders at the
pixel size the caller asks for. The nearest shipped size is used, which keeps
the chrome crisp at arbitrary interface scales instead of failing on a size
directory that was never generated (the compact grid asks for 48/40 px, for
example).
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from .size import px  # noqa: E402

ICONS_DIR = Path(__file__).resolve().parent / "icons"

_ICON_SIZES: tuple[int, ...] | None = None


def icon_sizes() -> tuple[int, ...]:
    """Shipped glyph sizes (the numeric directories under ``icons/``)."""
    global _ICON_SIZES
    if _ICON_SIZES is None:
        _ICON_SIZES = tuple(
            sorted(
                int(path.name)
                for path in ICONS_DIR.iterdir()
                if path.is_dir() and path.name.isdigit()
            )
        )
    return _ICON_SIZES


def nearest_icon_size(size: int) -> int:
    """The shipped glyph size closest to ``size`` (larger on a tie)."""
    return min(icon_sizes(), key=lambda candidate: (abs(candidate - size), -candidate))


def icon_path(name: str, size: int = px(16)) -> Path:
    """Path to the ``name`` glyph, rendered at ``size`` px by ``icon()``."""
    return ICONS_DIR / str(nearest_icon_size(size)) / f"{name}.svg"


def icon(name: str, size: int = px(16), *, dim: bool = False) -> Gtk.Image:
    """A ``Gtk.Image`` with the ``name`` glyph drawn at ``size`` px."""
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
