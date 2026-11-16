"""Contract for one display setting inside the View panel.

A setting feature owns exactly one control and the ``ViewSettings`` field(s) it
edits; it knows nothing about the window, the tabs, the model or the other
settings. The panel only composes the registered features and forwards their
declarative change dicts to ``update(**changes)``; applying a change stays in
the single mechanism (``DirectoryTab.update_view_settings``).

To add a setting: subclass ``SettingFeature`` in its own module, implement
``widget``/``sync``, and append the class to ``SETTING_FEATURES`` in this
package's ``__init__``. No edits to ``panel.py`` are needed.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ...display import ViewCapabilities, ViewSettings  # noqa: E402

ChangeCallback = Callable[[dict[str, object]], None]


class SettingsSection(StrEnum):
    """Popover sections, in design order; the value is the visible title.

    A ``str`` mixin so the panel can hand a section straight to
    ``controls.section(title)`` and tests can compare it against titles;
    injected features may still declare a custom section title.
    """

    view_mode = "Режим просмотра"
    sorting = "Сортировка"
    params = "Параметры"


class SettingFeature:
    """One setting's row(s): build a widget, sync it, report declarative changes."""

    id: ClassVar[str]
    section: ClassVar[SettingsSection | str]

    def __init__(self, on_change: ChangeCallback) -> None:
        self._on_change = on_change

    def available(self, capabilities: ViewCapabilities) -> bool:
        """Whether this build can apply the setting (drives the capabilities model)."""
        return True

    def widget(self) -> Gtk.Widget:
        """Build the row(s); called once, before the first ``sync``."""
        raise NotImplementedError

    def sync(self, settings: ViewSettings) -> None:
        """Reflect the snapshot without reporting it back as a user change."""
        raise NotImplementedError

    def _emit(self, **changes: object) -> None:
        self._on_change(changes)
