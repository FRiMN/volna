"""«Пресеты» section of the View panel: select field, save button, dropdown list.

The field is a ``Gtk.MenuButton``: the preset list opens as a dropdown menu
under it instead of growing the panel. A menu row keeps the design's anatomy
(check, name, rename/delete for custom presets) and clicking a row's action does
not select the preset — measured: the button consumes the press, the row stays
inactive and the menu stays open.

The section owns only widgets and whether the menu is open. Every rule (names,
overrides, selection, deletion fallback) and every mutation goes through
``PresetActions``, which the window implements (design/spec/04 §2, 05 §18, and
design/view-panel.md §10.1 for the dropdown decision).
"""

from __future__ import annotations

from typing import Protocol

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ..display.presets import Preset  # noqa: E402
from ..glyph import icon  # noqa: E402
from ..size import px  # noqa: E402
from .controls import section  # noqa: E402

PRESETS_TITLE = "Пресеты"
UNMANAGED_LABEL = "Настроено вручную"


class PresetActions(Protocol):
    """What the section asks of the window; no GTK, no storage here."""

    def visible_presets(self) -> tuple[Preset, ...]: ...

    def active_preset(self) -> Preset | None: ...

    def apply_preset(self, preset_id: str) -> None: ...

    def open_rename_dialog(self, preset_id: str) -> None: ...

    def open_save_dialog(self) -> None: ...

    def open_delete_dialog(self, preset_id: str) -> None: ...


class PresetsSection:
    """Select field + save button; the preset list is the field's dropdown menu."""

    def __init__(self, actions: PresetActions) -> None:
        self._actions = actions
        self._rows: dict[Gtk.ListBoxRow, str] = {}
        self._container, self._body = section(PRESETS_TITLE)

        self._name = Gtk.Label()
        self._name.add_css_class("volna-preset-name")
        self._name.set_halign(Gtk.Align.START)
        self._name.set_hexpand(True)
        self._name.set_ellipsize(3)  # Pango.EllipsizeMode.END

        self._select = Gtk.MenuButton()
        self._select.add_css_class("volna-preset-select")
        self._select.set_hexpand(True)
        self._select.set_halign(Gtk.Align.FILL)
        self._select.set_valign(Gtk.Align.CENTER)
        self._select.set_child(self._select_child())

        self._popover = Gtk.Popover()
        self._popover.add_css_class("volna-preset-menu-popover")
        self._popover.set_has_arrow(False)
        self._list = Gtk.ListBox()
        self._list.add_css_class("volna-preset-menu")
        # No selection state: the check mark names the current preset, and a
        # selected row would paint a second, competing highlight over it.
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.connect("row-activated", self._on_row_activated)
        self._popover.set_child(self._list)
        self._select.set_popover(self._popover)

        self._save = Gtk.Button()
        self._save.add_css_class("volna-preset-save")
        self._save.set_tooltip_text("Сохранить пресет")
        self._save.update_property([Gtk.AccessibleProperty.LABEL], ["Сохранить пресет"])
        self._save.set_child(icon("save", px(16)))
        self._save.connect("clicked", lambda _b: self._actions.open_save_dialog())

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(4))
        row.add_css_class("volna-preset-row")
        row.append(self._select)
        row.append(self._save)
        self._body.append(row)

    # -- public surface ---------------------------------------------------

    def widget(self) -> Gtk.Widget:
        return self._container

    @property
    def menu_open(self) -> bool:
        return self._popover.get_visible()

    def open_menu(self) -> None:
        self._select.set_active(True)

    def close_menu(self) -> None:
        self._select.set_active(False)

    def sync(self) -> None:
        """Reflect the current presets, selection and derived label."""
        active = self._actions.active_preset()
        label_text = active.name if active is not None else UNMANAGED_LABEL
        self._name.set_text(label_text)
        self._select.set_tooltip_text(f"Пресет: {label_text}")
        self._select.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"Пресет: {label_text}"]
        )
        self._rebuild_rows(active)

    # -- construction -----------------------------------------------------

    def _select_child(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(6))
        row.append(self._name)
        row.append(icon("down", px(16), dim=True))
        return row

    def _rebuild_rows(self, active: Preset | None) -> None:
        child = self._list.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._list.remove(child)
            child = following

        self._rows.clear()
        for preset in self._actions.visible_presets():
            is_current = active is not None and preset.id == active.id
            row = self._row(preset, is_current=is_current)
            self._rows[row] = preset.id
            self._list.append(row)

    def _row(self, preset: Preset, *, is_current: bool) -> Gtk.ListBoxRow:
        item = Gtk.ListBoxRow()
        item.add_css_class("volna-preset-item")
        if is_current:
            item.add_css_class("is-current")

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        check = icon("check", px(14))
        check.set_opacity(1.0 if is_current else 0.0)
        line.append(check)

        name = Gtk.Label(label=preset.name)
        name.add_css_class("volna-preset-item-name")
        name.set_halign(Gtk.Align.START)
        name.set_hexpand(True)
        line.append(name)

        if not preset.builtin:
            line.append(self._action_buttons(preset))

        item.set_child(line)
        return item

    def _action_buttons(self, preset: Preset) -> Gtk.Widget:
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(2))

        rename = Gtk.Button()
        rename.add_css_class("volna-preset-act")
        rename.set_tooltip_text("Переименовать")
        rename.update_property([Gtk.AccessibleProperty.LABEL], ["Переименовать"])
        rename.set_child(icon("pencil", px(14)))
        rename.connect(
            "clicked", lambda _b: self._actions.open_rename_dialog(preset.id)
        )
        actions.append(rename)

        delete = Gtk.Button()
        delete.add_css_class("volna-preset-act")
        delete.add_css_class("is-danger")
        delete.set_tooltip_text("Удалить")
        delete.update_property([Gtk.AccessibleProperty.LABEL], ["Удалить"])
        delete.set_child(icon("trash", px(14)))
        delete.connect(
            "clicked", lambda _b: self._actions.open_delete_dialog(preset.id)
        )
        actions.append(delete)

        return actions

    # -- menu interaction -------------------------------------------------

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        preset_id = self._rows.get(row)
        if preset_id is None:
            return

        self._actions.apply_preset(preset_id)
        self.close_menu()
        self.sync()


__all__ = ["PRESETS_TITLE", "PresetActions", "PresetsSection", "UNMANAGED_LABEL"]
