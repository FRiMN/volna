"""File-name label: middle ellipsis and a tooltip only when actually clipped.

A truncated name keeps its head and its tail — the extension, version or date
that tells sibling files apart — so the ellipsis sits in the middle, not at the
end (design/spec/07-decisions.md D29). The full name is reachable through the
tooltip, but only while the name is really truncated: the "show full names"
setting does not forbid a cap (a «Значки» name can still exceed four lines), and
the user should not see a tooltip for a name that is fully visible.

The tooltip is therefore derived from Pango's own ellipsis state after
allocation, not from the setting.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango  # noqa: E402


class NameLabel(Gtk.Label):
    """A label for a file name: ``MIDDLE`` ellipsis plus an on-demand tooltip.

    Alignment, wrapping and the line cap stay with the caller: the table is
    left-aligned, a tile is centred and wraps.
    """

    __gtype_name__ = "VolnaNameLabel"

    def __init__(self) -> None:
        super().__init__()
        self.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._shown_tooltip: str | None = None

    def set_name(self, name: str) -> None:
        """Set the text; the tooltip is re-derived on the next allocation."""
        self.set_text(name)
        self._set_tooltip(None)

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        Gtk.Label.do_size_allocate(self, width, height, baseline)
        layout = self.get_layout()
        clipped = layout is not None and layout.is_ellipsized()
        self._set_tooltip(self.get_text() if clipped else None)

    def _set_tooltip(self, text: str | None) -> None:
        # Reading the state after every allocation would otherwise reset the
        # same tooltip over and over; GTK fires no change signal for it.
        if text == self._shown_tooltip:
            return

        self._shown_tooltip = text
        self.set_tooltip_text(text)
