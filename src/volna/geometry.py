"""Hit-testing for the borderless window resize edges (no GTK imports)."""

from __future__ import annotations

from .size import px

EDGE = px(6)
CORNER = px(12)


def edge_at(x: int, y: int, width: int, height: int) -> str | None:
    """Return the surface edge name under (x, y), or None for the client area."""
    if width <= 0 or height <= 0:
        return None
    if x < 0 or y < 0 or x >= width or y >= height:
        return None

    north = y < EDGE
    south = y >= height - EDGE
    west = x < EDGE
    east = x >= width - EDGE

    if north and x < CORNER:
        return "nw"
    if north and x >= width - CORNER:
        return "ne"
    if south and x < CORNER:
        return "sw"
    if south and x >= width - CORNER:
        return "se"
    if north:
        return "n"
    if south:
        return "s"
    if west:
        return "w"
    if east:
        return "e"
    return None
