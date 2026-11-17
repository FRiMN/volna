"""«Параметры» section: show hidden files."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import ViewSettings  # noqa: E402
from ..controls import checkbox_row  # noqa: E402
from .base import ChangeCallback, SettingFeature, SettingsSection  # noqa: E402


class ShowHiddenSetting(SettingFeature):
    id = "show-hidden"
    section = SettingsSection.params

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._button: Gtk.CheckButton | None = None

    def widget(self) -> Gtk.Widget:
        self._button = checkbox_row("Показывать скрытые файлы")
        self._button.connect("toggled", self._on_toggled)

        return self._button

    def sync(self, settings: ViewSettings) -> None:
        if self._button is not None:
            self._button.set_active(settings.show_hidden)

    def _on_toggled(self, button: Gtk.CheckButton) -> None:
        self._emit(show_hidden=button.get_active())
