"""Local glyph lookup: the nearest shipped SVG set (no per-scale assets)."""

from __future__ import annotations

import pytest

pytest.importorskip("gi")


def _glyph():
    # Importing volna.glyph pulls in Gtk, so keep it inside the tests: GTK must
    # not be initialised before the session fixture sets its private display.
    from volna import glyph

    return glyph


def test_shipped_sizes_are_the_numeric_directories() -> None:
    sizes = _glyph().icon_sizes()
    assert sizes, "the package ships no glyphs"
    assert list(sizes) == sorted(sizes)
    assert 16 in sizes and 50 in sizes and 75 in sizes


def test_nearest_size_is_used_for_unshipped_metrics() -> None:
    nearest = _glyph().nearest_icon_size
    assert nearest(16) == 16
    assert nearest(48) == 50
    assert nearest(40) == 50
    assert nearest(30) == 25
    assert nearest(100) == 75
    assert nearest(0) == 12


def test_any_requested_size_resolves_to_an_existing_file() -> None:
    """The compact grid asks for 48/40 px, which were never generated."""
    icon_path = _glyph().icon_path
    for name in ("back", "folder-filled", "file", "check"):
        for requested in (12, 16, 20, 25, 40, 48, 60, 75):
            path = icon_path(name, requested)
            assert path.is_file(), path
            assert path.name == f"{name}.svg"
