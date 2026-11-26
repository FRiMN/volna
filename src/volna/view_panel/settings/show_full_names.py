"""«Параметры» section: show file names in full instead of trimming them.

The details table always truncates to its column width, so the control stays
visible but insensitive there — a mode-dependent gate, not a capability gate
(design/view-panel.md §2.11): the popover must not jump when the mode changes,
and the setting must stay findable.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import ViewMode, ViewSettings  # noqa: E402
from ..controls import checkbox_row  # noqa: E402
from .base import ChangeCallback, SettingFeature, SettingsSection  # noqa: E402

_TABLE_TOOLTIP = "Не применяется к таблице"


class ShowFullNamesSetting(SettingFeature):
    id = "show-full-names"
    section = SettingsSection.params

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._button: Gtk.CheckButton | None = None

    def widget(self) -> Gtk.Widget:
        self._button = checkbox_row("Показывать имена целиком")
        self._button.connect("toggled", self._on_toggled)

        return self._button

    def sync(self, settings: ViewSettings) -> None:
        if self._button is None:
            return

        self._button.set_active(settings.show_full_names)
        in_table = settings.view_mode is ViewMode.DETAILS
        self._button.set_sensitive(not in_table)
        self._button.set_tooltip_text(_TABLE_TOOLTIP if in_table else None)

    def _on_toggled(self, button: Gtk.CheckButton) -> None:
        self._emit(show_full_names=button.get_active())
