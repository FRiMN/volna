"""«Сортировка» section: folders before files."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import ViewSettings  # noqa: E402
from ..controls import checkbox_row  # noqa: E402
from .base import ChangeCallback, SettingFeature  # noqa: E402


class FoldersFirstSetting(SettingFeature):
    id = "folders-first"
    section = "Сортировка"

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._button: Gtk.CheckButton | None = None

    def widget(self) -> Gtk.Widget:
        self._button = checkbox_row("Папки перед файлами")
        self._button.connect("toggled", self._on_toggled)

        return self._button

    def sync(self, settings: ViewSettings) -> None:
        if self._button is not None:
            self._button.set_active(settings.folders_first)

    def _on_toggled(self, button: Gtk.CheckButton) -> None:
        self._emit(folders_first=button.get_active())
