"""«Группировка» section: choose the listing grouping strategy or none.

Labels and order come from the strategy registry in ``display``; this module
never hardcodes them, the same as the view-mode feature.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import (  # noqa: E402
    GROUPING_STRATEGIES,
    Grouping,
    ViewCapabilities,
    ViewSettings,
)
from ..controls import radio_row  # noqa: E402
from .base import ChangeCallback, SettingFeature, SettingsSection  # noqa: E402


class GroupingSetting(SettingFeature):
    id = "grouping"
    section = SettingsSection.grouping

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._buttons: dict[Grouping, Gtk.CheckButton] = {}

    def available(self, capabilities: ViewCapabilities) -> bool:
        return capabilities.grouping

    def widget(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

        group: Gtk.CheckButton | None = None
        for grouping, strategy in GROUPING_STRATEGIES:
            button = radio_row(strategy.label)
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("toggled", self._on_toggled, grouping)
            box.append(button)
            self._buttons[grouping] = button

        return box

    def sync(self, settings: ViewSettings) -> None:
        button = self._buttons.get(settings.grouping)
        if button is not None:
            button.set_active(True)

    def _on_toggled(self, button: Gtk.CheckButton, grouping: Grouping) -> None:
        if not button.get_active():
            return
        self._emit(grouping=grouping)
