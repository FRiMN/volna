"""«Сортировка» section: sort direction (segmented control)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import ViewSettings  # noqa: E402
from ..controls import segmented  # noqa: E402
from .base import ChangeCallback, SettingFeature, SettingsSection  # noqa: E402

_ROWS: tuple[tuple[bool, str], ...] = (
    (True, "По убыванию"),
    (False, "По возрастанию"),
)


class SortDirectionSetting(SettingFeature):
    id = "sort-direction"
    section = SettingsSection.sorting

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._buttons: dict[bool, Gtk.ToggleButton] = {}

    def widget(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.add_css_class("volna-view-seg-row")

        control, self._buttons = segmented(list(_ROWS))
        for reverse, button in self._buttons.items():
            button.connect("toggled", self._on_toggled, reverse)
        row.append(control)

        return row

    def sync(self, settings: ViewSettings) -> None:
        button = self._buttons.get(settings.reverse)
        if button is not None:
            button.set_active(True)

    def _on_toggled(self, button: Gtk.ToggleButton, reverse: bool) -> None:
        if not button.get_active():
            return
        self._emit(reverse=reverse)
