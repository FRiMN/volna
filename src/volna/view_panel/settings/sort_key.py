"""«Сортировка» section: sort key choice."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import SortKey, ViewSettings  # noqa: E402
from ..controls import radio_row  # noqa: E402
from .base import ChangeCallback, SettingFeature  # noqa: E402

_ROWS: tuple[tuple[SortKey, str], ...] = (
    (SortKey.MTIME, "Дата изменения"),
    (SortKey.SIZE, "Размер"),
    (SortKey.NAME, "Имя"),
)


class SortKeySetting(SettingFeature):
    id = "sort-key"
    section = "Сортировка"

    def __init__(self, on_change: ChangeCallback) -> None:
        super().__init__(on_change)
        self._buttons: dict[SortKey, Gtk.CheckButton] = {}

    def widget(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

        group: Gtk.CheckButton | None = None
        for sort_key, text in _ROWS:
            button = radio_row(text)
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("toggled", self._on_toggled, sort_key)
            box.append(button)
            self._buttons[sort_key] = button

        return box

    def sync(self, settings: ViewSettings) -> None:
        button = self._buttons.get(settings.sort_key)
        if button is not None:
            button.set_active(True)

    def _on_toggled(self, button: Gtk.CheckButton, sort_key: SortKey) -> None:
        if not button.get_active():
            return
        self._emit(sort_key=sort_key)
