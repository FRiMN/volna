"""Group header widgets shared by the listing views (design/grouping.md D4).

The header is one caption row above a date group: the group title on the left
and the item count on the right. Metrics and colours live in ``theme.css``
under the ``volna-group-*`` classes; each mode only places the pieces.

Details draws its own row (the row has to span the table columns), so it uses
the label helpers and not :func:`header_box`.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango  # noqa: E402

from ..display import GroupAction  # noqa: E402
from ..glyph import icon  # noqa: E402
from ..size import px  # noqa: E402


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


class GroupHeader(Gtk.Box):
    """An interactive date-group caption (design/grouping.md D13/D14).

    The whole row toggles on click; a chevron button shows the state and
    toggles too (a real ``Gtk.Button``, so focus and keyboard come from the
    toolkit). Right click opens the context menu with the sensitive-by-state
    items. The view wires ``key`` in; the tab decides what the state is, so
    ``set_collapsed`` only paints.
    """

    __gtype_name__ = "VolnaGroupHeader"

    def __init__(self, key: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(6))
        self.add_css_class("volna-group-header")
        self._key = key
        self._collapsed = False
        # Menu sensitivity defaults; the view overrides them on every bind.
        self._others_collapsible = True
        self._any_expanded = not self._collapsed
        self._any_collapsed = self._collapsed
        self._on_group_action: Callable[[str, GroupAction], None] = lambda *_args: None

        self._chevron = Gtk.Button()
        self._chevron.add_css_class("volna-group-chevron")
        self._chevron.set_child(icon("down", px(16)))
        self._chevron.set_valign(Gtk.Align.CENTER)
        self._chevron.connect("clicked", self._on_toggle)
        self.append(self._chevron)

        self._title = title_label("")
        self._title.set_hexpand(True)
        self.append(self._title)

        self._count = count_label(0)
        self._count.set_halign(Gtk.Align.END)
        self.append(self._count)

        self.set_hexpand(True)
        self._sync_state()

        # Toggle on any press over the caption; the context menu opens on the
        # right button. A gesture both ways: the row is clickable, the button
        # handles its own click first (it is inside the row).
        self._click = Gtk.GestureClick()
        self._click.connect("pressed", self._on_pressed)
        self.add_controller(self._click)

        self._menu = self._build_menu()
        self._menu.set_parent(self)
        self._menu.set_has_arrow(False)

    def set_caption(self, text: str, count: int) -> None:
        """Paint the caption; called on every bind (rows are recycled)."""
        self._title.set_text(text)
        self._count.set_text(str(count))

    def set_action(self, callback: Callable[[str, GroupAction], None]) -> None:
        """Where this header reports its interactions (the owning view)."""
        self._on_group_action = callback

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._sync_state()

    def set_menu_state(
        self,
        *,
        others_collapsible: bool,
        any_expanded: bool,
        any_collapsed: bool,
    ) -> None:
        """Sensitivity of the context menu, decided by the tab (D14).

        The header alone cannot know whether «Свернуть все» makes sense (it
        does not, when everything is already collapsed) or whether anything
        is collapsed to expand; the tab owns the whole group set.
        """
        self._others_collapsible = others_collapsible
        self._any_expanded = any_expanded
        self._any_collapsed = any_collapsed

    # -- construction ----------------------------------------------------

    def _sync_state(self) -> None:
        verb = "Развернуть" if self._collapsed else "Свернуть"
        self._chevron.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"{verb} группу"]
        )
        self._chevron.set_tooltip_text(f"{verb} группу")
        if self._collapsed:
            self.add_css_class("volna-group-collapsed")
        else:
            self.remove_css_class("volna-group-collapsed")

    def _build_menu(self) -> Gtk.PopoverMenu:
        menu = Gtk.PopoverMenu()
        menu.add_css_class("volna-menu")

        items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(2))
        items.add_css_class("volna-menu-box")

        self._collapse_others = self._menu_item("Свернуть остальные")
        self._collapse_others.connect(
            "clicked", self._on_menu_action, GroupAction.COLLAPSE_OTHERS
        )
        self._collapse_all = self._menu_item("Свернуть все")
        self._collapse_all.connect(
            "clicked", self._on_menu_action, GroupAction.COLLAPSE_ALL
        )
        self._expand_all = self._menu_item("Развернуть все")
        self._expand_all.connect(
            "clicked", self._on_menu_action, GroupAction.EXPAND_ALL
        )

        items.append(self._collapse_others)
        items.append(self._collapse_all)
        items.append(self._expand_all)
        menu.set_child(items)

        return menu

    def _menu_item(self, text: str) -> Gtk.Button:
        button = Gtk.Button(label=text)
        button.add_css_class("volna-menu-item")
        return button

    # -- interaction -----------------------------------------------------

    def _on_toggle(self, *_args: object) -> None:
        self._on_group_action(self._key, GroupAction.TOGGLE)

    def _on_pressed(
        self,
        click: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        if n_press != 1:
            return

        button = click.get_current_button()
        if button == 3:
            self._open_menu()
        elif button == 1:
            self._on_toggle()

    def _on_menu_action(self, button: Gtk.Button, action: GroupAction) -> None:
        self._menu.popdown()
        self._on_group_action(self._key, action)

    def _open_menu(self) -> None:
        # «Свернуть остальные» has a target only with several groups;
        # «Свернуть все»/«Развернуть все» have one whenever anything is
        # respectively expanded/collapsed (D14).
        self._collapse_others.set_sensitive(self._others_collapsible)
        self._collapse_all.set_sensitive(self._any_expanded)
        self._expand_all.set_sensitive(self._any_collapsed)
        self._menu.popup()
