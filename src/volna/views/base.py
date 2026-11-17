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

from ..display import GroupAction, ViewMode, ViewSettings  # noqa: E402
from .item import ListingItem  # noqa: E402


@dataclass(frozen=True, slots=True)
class Section:
    """A part of the listing under an optional header (a date group).

    The tab builds one unnamed section (``header=None``) for an ungrouped
    listing and one named section per date group otherwise; the header's item
    count is ``len(items)`` (design/grouping.md D4). ``key`` identifies the
    group to the tab's collapse state and ``collapsed`` says whether the tab
    currently hides this group's content (design/grouping.md D13): a view only
    *renders* the state, the tab decides it.
    """

    items: tuple[ListingItem, ...]
    header: str | None = None
    key: str | None = None
    collapsed: bool = False


class ListingView(abc.ABC):
    """One presentation of the listing: build a widget, render sections."""

    mode: ClassVar[ViewMode]

    def __init__(
        self,
        *,
        on_activate: Callable[[ListingItem], None],
        on_group_action: Callable[[str, GroupAction], None] | None = None,
    ) -> None:
        self._on_activate = on_activate
        self._on_group_action = on_group_action or (lambda *_args: None)
        self._settings = ViewSettings()
        # Group-menu sensitivity, recomputed from the sections on every render
        # (design/grouping.md D14): a view cannot see the whole group set from a
        # single header, but it does see every section it is about to paint.
        self._others_collapsible = False
        self._any_expanded = False
        self._any_collapsed = False

    @property
    @abc.abstractmethod
    def widget(self) -> Gtk.Widget:
        """Root widget; the tab puts it into its own stack."""

    @abc.abstractmethod
    def render(self, sections: Sequence[Section]) -> None:
        """Replace everything on screen with ``sections``."""

    def _read_menu_state(self, sections: Sequence[Section]) -> None:
        """Cache what the group menu may offer, from the sections themselves."""
        self._others_collapsible = len(sections) > 1
        self._any_expanded = any(not section.collapsed for section in sections)
        self._any_collapsed = any(section.collapsed for section in sections)

    def apply(self, settings: ViewSettings) -> None:
        """React to display settings (density); the default re-render uses it."""
        self._settings = settings

    # Intentional no-op default: a mode without its own scroller needs no
    # override, so this is not an abstract method (ruff B027 suppressed).
    def reset_scroll(self) -> None:  # noqa: B027
        """Return to the start; called when this mode becomes active."""
