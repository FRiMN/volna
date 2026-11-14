"""Icon assets: declared size, viewBox and ink placement inside the canvas.

The app draws these SVGs with GtkImage, the mockup uses the same geometry as an
inline sprite; an icon whose ink overflows the viewBox is clipped and optically
off-centre, which shows up as "shifted" icons in the chrome.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

gi = pytest.importorskip("gi")
gi.require_version("GdkPixbuf", "2.0")
GdkPixbuf = pytest.importorskip("gi.repository.GdkPixbuf")

ICONS_DIR = Path(__file__).resolve().parents[1] / "src" / "volna" / "icons"
SIZES = (12, 14, 15, 16, 18, 20, 25)
SUPERSAMPLE = 4
INK_ALPHA = 8
EDGE_MARGIN = 0.25  # px at the declared icon size
CENTER_TOLERANCE = 1.0  # px at the declared icon size


def _icon_paths() -> list[Path]:
    return sorted(ICONS_DIR.glob("*/*.svg"))


def _declared(path: Path) -> tuple[int, int, tuple[float, ...]]:
    root = ET.parse(path).getroot()
    view_box = tuple(float(part) for part in root.get("viewBox", "").split())
    return int(root.get("width")), int(root.get("height")), view_box


def _ink_bbox(path: Path, size: int) -> tuple[float, float, float, float]:
    """Ink bounds in px of the declared icon size."""
    pixels = size * SUPERSAMPLE
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), pixels, pixels, True)
    assert pixbuf.get_has_alpha()

    data = pixbuf.get_pixels()
    channels = pixbuf.get_n_channels()
    rowstride = pixbuf.get_rowstride()
    width, height = pixbuf.get_width(), pixbuf.get_height()
    xmin, ymin, xmax, ymax = width, height, -1, -1

    for y in range(height):
        row = data[y * rowstride : (y + 1) * rowstride]
        for x in range(width):
            if row[x * channels + channels - 1] > INK_ALPHA:
                xmin, xmax = min(xmin, x), max(xmax, x)
                ymin, ymax = min(ymin, y), max(ymax, y)

    assert xmax >= 0, f"{path} has no ink"
    return (
        xmin / SUPERSAMPLE,
        ymin / SUPERSAMPLE,
        (xmax + 1) / SUPERSAMPLE,
        (ymax + 1) / SUPERSAMPLE,
    )


def test_sizes_are_complete() -> None:
    names = {path.name for path in ICONS_DIR.glob(f"{SIZES[0]}/*.svg")}

    for size in SIZES:
        assert {path.name for path in ICONS_DIR.glob(f"{size}/*.svg")} == names


def test_icons_declare_their_size() -> None:
    for path in _icon_paths():
        size = int(path.parent.name)
        width, height, view_box = _declared(path)

        assert (width, height) == (size, size), path
        assert len(view_box) == 4 and view_box[0] == 0 and view_box[1] == 0, path
        assert view_box[2] == view_box[3], path


def test_ink_stays_inside_the_canvas() -> None:
    for path in _icon_paths():
        size = int(path.parent.name)
        x0, y0, x1, y1 = _ink_bbox(path, size)

        assert x0 >= EDGE_MARGIN, path
        assert y0 >= EDGE_MARGIN, path
        assert x1 <= size - EDGE_MARGIN, path
        assert y1 <= size - EDGE_MARGIN, path


def test_ink_is_optically_centered() -> None:
    for path in _icon_paths():
        size = int(path.parent.name)
        x0, y0, x1, y1 = _ink_bbox(path, size)

        assert abs((x0 + x1) / 2 - size / 2) <= CENTER_TOLERANCE, path
        assert abs((y0 + y1) / 2 - size / 2) <= CENTER_TOLERANCE, path
