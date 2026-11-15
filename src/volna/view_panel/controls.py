"""Reusable widget rows for the View panel.

The controls are plain native GTK widgets (``CheckButton``/``ToggleButton``)
so focus, keyboard and accessibility come from the toolkit; the panel only
groups them and applies the ``volna-*`` CSS classes from ``theme.css``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

ValueT = TypeVar("ValueT")


def section(title: str) -> tuple[Gtk.Box, Gtk.Box]:
    """A titled panel section; returns ``(container, body)`` to append rows to."""
    container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    container.add_css_class("volna-view-section")

    heading = Gtk.Label(label=title)
    heading.set_halign(Gtk.Align.START)
    heading.add_css_class("volna-view-section-title")
    container.append(heading)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    container.append(body)

    return container, body


def separator() -> Gtk.Box:
    """1 px line between sections (GTK CSS has no ::before/after separators)."""
    line = Gtk.Box()
    line.add_css_class("volna-view-separator")
    line.set_size_request(-1, 1)
    return line


def radio_row(text: str) -> Gtk.CheckButton:
    """One row of a single-choice group; group the buttons with ``set_group``."""
    button = Gtk.CheckButton(label=text)
    button.add_css_class("volna-radio")
    button.set_hexpand(True)
    return button


def checkbox_row(text: str) -> Gtk.CheckButton:
    button = Gtk.CheckButton(label=text)
    button.add_css_class("volna-check")
    button.set_hexpand(True)
    return button


def segmented(
    options: Sequence[tuple[ValueT, str]],
) -> tuple[Gtk.Box, dict[ValueT, Gtk.ToggleButton]]:
    """A radio-like segmented control; returns ``(container, buttons by value)``."""
    container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    container.add_css_class("volna-seg")

    buttons: dict[ValueT, Gtk.ToggleButton] = {}
    group: Gtk.ToggleButton | None = None
    for value, text in options:
        button = Gtk.ToggleButton(label=text)
        button.add_css_class("volna-seg-btn")
        button.set_hexpand(True)
        if group is not None:
            button.set_group(group)
        else:
            group = button
        container.append(button)
        buttons[value] = button

    return container, buttons


def footer(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text)
    label.set_halign(Gtk.Align.START)
    label.add_css_class("volna-view-footer")
    return label
