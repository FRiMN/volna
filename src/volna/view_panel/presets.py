"""«Пресеты» section of the View panel: select field, save button, inline list.

The section owns only widgets and whether its list is expanded. Every rule
(names, overrides, selection, deletion fallback) and every mutation goes
through ``PresetActions``, which the window implements (design/spec/04 §2,
05 §18); the row buttons open the window's dialogs for rename and delete.
"""

from __future__ import annotations

from typing import Protocol

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

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

    def notify(self, text: str) -> None:
        """Show a short status note (the «bandNote» of the design)."""
        ...


class PresetsSection:
    """Select field + save button + list; rebuilt from the window on each sync."""

    def __init__(self, actions: PresetActions) -> None:
        self._actions = actions
        self._list_open = False
        self._container, self._body = section(PRESETS_TITLE)

        self._select = Gtk.Button()
        self._select.add_css_class("volna-preset-select")
        self._select.set_hexpand(True)
        self._select.set_halign(Gtk.Align.FILL)
        self._select.connect("clicked", self._on_select_clicked)
        # Screen readers announce the field as the owner of a popup list.
        self._select.update_property([Gtk.AccessibleProperty.HAS_POPUP], [True])

        self._name = Gtk.Label()
        self._name.add_css_class("volna-preset-name")
        self._name.set_halign(Gtk.Align.START)
        self._name.set_hexpand(True)
        self._name.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self._select.set_child(self._select_child())

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

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self._list.add_css_class("volna-preset-list")

        # The design caps the list at 174 px and scrolls it (04 §2): a long
        # preset list must not push the settings below it out of the panel.
        self._list_scroller = Gtk.ScrolledWindow()
        self._list_scroller.add_css_class("volna-preset-scroller")
        self._list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list_scroller.set_max_content_height(px(174))
        self._list_scroller.set_propagate_natural_height(True)
        self._list_scroller.set_visible(False)
        self._list_scroller.set_child(self._list)
        self._body.append(self._list_scroller)

    # -- public surface ---------------------------------------------------

    def widget(self) -> Gtk.Widget:
        return self._container

    @property
    def list_open(self) -> bool:
        return self._list_open

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

    def open_list(self) -> None:
        if self._list_open:
            return

        self._list_open = True
        self._list_scroller.set_visible(True)
        self._select.add_css_class("is-expanded")
        self._set_expanded(True)

    def close_list(self) -> None:
        if not self._list_open:
            return

        self._list_open = False
        self._list_scroller.set_visible(False)
        self._select.remove_css_class("is-expanded")
        self._set_expanded(False)

    # -- construction -----------------------------------------------------

    def _select_child(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(6))
        row.append(self._name)
        row.append(icon("down", px(16), dim=True))
        return row

    def _rebuild_rows(self, active: Preset | None) -> None:
        # Rebuilding replaces every row, and the scroller would show the first
        # one again; the user's position in a long list must survive a rename.
        adjustment = self._list_scroller.get_vadjustment()
        scroll = adjustment.get_value() if adjustment is not None else 0.0

        child = self._list.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._list.remove(child)
            child = following

        for preset in self._actions.visible_presets():
            is_current = active is not None and preset.id == active.id
            self._list.append(self._row(preset, is_current=is_current))

        if adjustment is not None and scroll > 0:
            # After the layout: the new rows give the adjustment its range.
            GLib.idle_add(self._restore_scroll, scroll)

    def _restore_scroll(self, scroll: float) -> bool:
        adjustment = self._list_scroller.get_vadjustment()
        if adjustment is not None:
            limit = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
            adjustment.set_value(min(scroll, limit))
        return False

    def _row(self, preset: Preset, *, is_current: bool) -> Gtk.Widget:
        item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        item.add_css_class("volna-preset-item")
        if is_current:
            item.add_css_class("is-current")

        apply = Gtk.Button()
        apply.add_css_class("volna-preset-apply")
        apply.set_hexpand(True)
        apply.set_halign(Gtk.Align.FILL)
        apply.set_tooltip_text(f"Применить пресет «{preset.name}»")
        apply.connect("clicked", self._on_apply_clicked, preset.id)

        text = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(8))
        check = icon("check", px(14))
        check.set_opacity(1.0 if is_current else 0.0)
        text.append(check)
        name = Gtk.Label(label=preset.name)
        name.add_css_class("volna-preset-item-name")
        name.set_halign(Gtk.Align.START)
        name.set_hexpand(True)
        text.append(name)
        apply.set_child(text)
        item.append(apply)

        if not preset.builtin:
            item.append(self._action_buttons(preset))

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

    # -- list interaction -------------------------------------------------

    def _on_select_clicked(self, _button: Gtk.Button) -> None:
        if self._list_open:
            self.close_list()
            return

        self.open_list()

    def _set_expanded(self, expanded: bool) -> None:
        # EXPANDED is a tristate and PyGObject only accepts it as a plain int
        # (a bool or the enum object is dropped with a g_value assertion).
        value = (
            Gtk.AccessibleTristate.TRUE if expanded else Gtk.AccessibleTristate.FALSE
        )
        self._select.update_state([Gtk.AccessibleState.EXPANDED], [int(value)])

    def _on_apply_clicked(self, _button: Gtk.Button, preset_id: str) -> None:
        self._actions.apply_preset(preset_id)
        self.close_list()
        self.sync()


__all__ = ["PRESETS_TITLE", "PresetActions", "PresetsSection", "UNMANAGED_LABEL"]
