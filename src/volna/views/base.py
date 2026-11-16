"""Contract every listing view implements.

One mode = one module implementing :class:`ListingView`; the tab owns the
dispatch (design/view-modes.md D1–D4). Data is identical across modes — only
the widget tree differs — so ``render`` receives the same sections everywhere.
"""

from __future__ import annotations

import abc
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ..display import ViewMode, ViewSettings  # noqa: E402
from .item import ListingItem  # noqa: E402


@dataclass(frozen=True, slots=True)
class Section:
    """A part of the listing under an optional header (future date groups).

    Today the tab always builds one unnamed section (``header=None``); date
    grouping later turns it into several named ones without touching the views.
    """

    items: tuple[ListingItem, ...]
    header: str | None = None


class ListingView(abc.ABC):
    """One presentation of the listing: build a widget, render sections."""

    mode: ClassVar[ViewMode]

    def __init__(self, *, on_activate: Callable[[ListingItem], None]) -> None:
        self._on_activate = on_activate
        self._settings = ViewSettings()

    @property
    @abc.abstractmethod
    def widget(self) -> Gtk.Widget:
        """Root widget; the tab puts it into its own stack."""

    @abc.abstractmethod
    def render(self, sections: Sequence[Section]) -> None:
        """Replace everything on screen with ``sections``."""

    def apply(self, settings: ViewSettings) -> None:
        """React to display settings (density); the default re-render uses it."""
        self._settings = settings

    # Intentional no-op default: a mode without its own scroller needs no
    # override, so this is not an abstract method (ruff B027 suppressed).
    def reset_scroll(self) -> None:  # noqa: B027
        """Return to the start; called when this mode becomes active."""
