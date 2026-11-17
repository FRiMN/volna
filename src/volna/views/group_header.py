"""Group header widgets shared by the listing views (design/grouping.md D4).

The header is one caption row above a date group: the group title on the left
and the item count on the right. Metrics and colours live in ``theme.css``
under the ``volna-group-*`` classes; each mode only places the pieces.

Details draws its own row (the row has to span the table columns), so it uses
the label helpers and not :func:`header_box`.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango  # noqa: E402


def title_label(text: str) -> Gtk.Label:
    """The group name: 13/600 secondary, ellipsized when the row is narrow."""
    label = Gtk.Label(label=text, xalign=0)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    label.add_css_class("volna-group-title")
    return label


def count_label(count: int) -> Gtk.Label:
    """The item count: 12 mono muted, never shrinks."""
    label = Gtk.Label(label=str(count), xalign=1)
    label.add_css_class("volna-group-count")
    return label


def header_box(text: str, count: int) -> Gtk.Box:
    """A full-width caption row: title left, count right (28 px, `theme.css`)."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.add_css_class("volna-group-header")

    title = title_label(text)
    title.set_hexpand(True)
    box.append(title)

    count_widget = count_label(count)
    count_widget.set_halign(Gtk.Align.END)
    box.append(count_widget)

    return box
