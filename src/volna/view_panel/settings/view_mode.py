"""«Режим просмотра» section: a radio group over the available view modes.

Labels and order come from ``display`` (``mode.label`` / ``MODE_ORDER``) — this
module never hardcodes them. Modes this build cannot render are not shown.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import MODE_ORDER, ViewCapabilities, ViewMode, ViewSettings  # noqa: E402
from ..controls import radio_row  # noqa: E402
from .base import ChangeCallback, SettingFeature, SettingsSection  # noqa: E402


class ViewModeSetting(SettingFeature):
    id = "view-mode"
    section = SettingsSection.view_mode

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._buttons: dict[ViewMode, Gtk.CheckButton] = {}
        # The panel calls available() before widget() (see panel.py), so the
        # filter records which modes to render; MODE_ORDER is the fallback for
        # a feature used outside the panel (tests).
        self._modes: tuple[ViewMode, ...] = MODE_ORDER

    def available(self, capabilities: ViewCapabilities) -> bool:
        self._modes = tuple(mode for mode in MODE_ORDER if mode in capabilities.modes)
        return len(self._modes) > 1

    def widget(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

        group: Gtk.CheckButton | None = None
        for mode in self._modes:
            button = radio_row(mode.label)
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("toggled", self._on_toggled, mode)
            box.append(button)
            self._buttons[mode] = button

        return box

    def sync(self, settings: ViewSettings) -> None:
        button = self._buttons.get(settings.view_mode)
        if button is not None:
            button.set_active(True)

    def _on_toggled(self, button: Gtk.CheckButton, mode: ViewMode) -> None:
        if not button.get_active():
            return
        self._emit(view_mode=mode)
