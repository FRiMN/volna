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
from .group_header import GroupHeader  # noqa: E402
from .item import ListingItem  # noqa: E402


@dataclass(frozen=True, slots=True)
class Section:
    """A part of the listing under an optional header (one group).

    The tab builds one unnamed section (``header=None``) for an ungrouped
    listing and one named section per group otherwise; the header's item
    summary is ``stats`` — folders, files and size, the same string the editor
    header shows (design/grouping.md D4). ``key`` identifies the group to the
    tab's collapse state and ``collapsed`` says whether the tab
    currently hides this group's content (design/grouping.md D13): a view only
    *renders* the state, the tab decides it.
    """

    items: tuple[ListingItem, ...]
    header: str | None = None
    key: str | None = None
    collapsed: bool = False
    stats: str = ""


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
        # Where group clicks are picked from (the mode's scrollable); ``None``
        # until the widget tree exists.
        self._click_root: Gtk.Widget | None = None
        # Captions by group key: ``Gtk.ListView`` recycles row widgets, and the
        # details table hosts a caption only in its first column.
        self._headers: dict[str, GroupHeader] = {}

    @property
    @abc.abstractmethod
    def widget(self) -> Gtk.Widget:
        """Root widget; the tab puts it into its own stack."""

    @abc.abstractmethod
    def render(self, sections: Sequence[Section]) -> None:
        """Replace everything on screen with ``sections``."""

    # -- group interaction ------------------------------------------------

    def _install_group_clicks(self, root: Gtk.Widget) -> None:
        """Route clicks on group captions through the view, not the widgets.

        ``Gtk.ListView`` and ``Gtk.ColumnView`` claim right clicks in their own
        capture phase, so a handler on the caption never sees them; a handler on
        the scroller does, and it also reaches the empty cells of a details
        strip. Left clicks on the chevron are left to the button.
        """
        self._click_root = root
        # A `Gtk.GestureClick` with the default button (=0) only sees the
        # primary button in this GTK build, so the right button gets its own
        # controller; both capture the press before a ListView row sees it.
        for button in (1, 3):
            click = Gtk.GestureClick()
            click.set_button(button)
            click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            click.connect("pressed", self._on_group_pressed, button)
            root.add_controller(click)

    def _on_group_pressed(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
        button: int,
    ) -> bool:
        del n_press
        return self._handle_group_press(button, x, y, gesture)

    def _handle_group_press(
        self,
        button: int,
        x: float,
        y: float,
        gesture: Gtk.GestureClick | None = None,
    ) -> bool:
        """Toggle on the left button, open the menu on the right; claim it.

        Returns ``True`` when the press is consumed. ``gesture`` is optional so
        that tests can drive the routing without a real input device.
        """
        if self._click_root is None:
            return False

        header, on_chevron = self._group_at(x, y)
        if header is None:
            return False

        if button == 1 and on_chevron:
            return False

        if button == 1:
            header.toggle()
        elif button == 3:
            header.open_menu()
        else:
            return False

        if gesture is not None:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        return True

    def _group_at(self, x: float, y: float) -> tuple[GroupHeader | None, bool]:
        """The caption under a point and whether the point is on its chevron."""
        root = self._click_root
        if root is None:
            return None, False

        node = root.pick(int(x), int(y), Gtk.PickFlags.DEFAULT)
        on_chevron = False
        while node is not None and node is not root:
            if isinstance(node, Gtk.Button) and node.has_css_class(
                "volna-group-chevron"
            ):
                on_chevron = True

            found = self._group_for_node(node)
            if found is not None:
                return found, on_chevron

            node = node.get_parent()

        return None, False

    def _group_for_node(self, node: Gtk.Widget) -> GroupHeader | None:
        """The caption a picked node belongs to; views extend this (details cells)."""
        return node if isinstance(node, GroupHeader) else None

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
