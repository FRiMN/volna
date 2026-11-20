"""View presets: named snapshots of the display settings (pure, no GTK).

A preset is a stable id, a name and a :class:`ViewSettings` snapshot. Built-in
presets are data in code; custom ones are stored by ``presets_store``. The
``PresetBook`` owns the rules (overwrite, override, conflicts, selection) so the
widgets only call it and show its answers. Specs: design/spec/05-interactions.md
§18, design/view-panel.md §10.1.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields, replace

from ..core import SortKey
from .settings import Grouping, ViewCapabilities, ViewMode, ViewSettings

MAX_NAME_LENGTH = 64
DEFAULT_PRESET_ID = "default"

ERR_EMPTY_NAME = "Имя пресета не может быть пустым"
ERR_NAME_TAKEN = "Пресет с таким именем уже существует"
ERR_BUILTIN_READONLY = "Встроенный пресет нельзя изменить"


class PresetError(ValueError):
    """A rule the user can see: the message is the text shown to them."""


@dataclass(frozen=True, slots=True)
class Preset:
    id: str
    name: str
    settings: ViewSettings
    builtin: bool = False


BUILTIN_PRESETS: tuple[Preset, ...] = (
    Preset(
        DEFAULT_PRESET_ID,
        "По умолчанию",
        ViewSettings(
            view_mode=ViewMode.COLUMNS,
            grouping=Grouping.DATE,
            sort_key=SortKey.MTIME,
            reverse=True,
            show_hidden=False,
            compact=False,
            zoom=50,
        ),
        builtin=True,
    ),
    Preset(
        "dense-list",
        "Плотный список",
        ViewSettings(
            view_mode=ViewMode.DETAILS,
            grouping=Grouping.DATE,
            sort_key=SortKey.MTIME,
            reverse=True,
            compact=True,
            zoom=50,
        ),
        builtin=True,
    ),
    Preset(
        "large-icons",
        "Крупные значки",
        ViewSettings(
            view_mode=ViewMode.ICONS,
            grouping=Grouping.DATE,
            sort_key=SortKey.NAME,
            reverse=False,
            compact=False,
            zoom=85,
        ),
        builtin=True,
    ),
    Preset(
        "no-grouping",
        "Без группировки",
        ViewSettings(
            view_mode=ViewMode.COLUMNS,
            grouping=Grouping.NONE,
            sort_key=SortKey.SIZE,
            reverse=True,
            compact=False,
            zoom=50,
        ),
        builtin=True,
    ),
)


def clean_name(raw: str) -> str:
    """Trim and validate a preset name; raises ``PresetError`` when unusable."""
    name = raw.strip()
    if not name:
        raise PresetError(ERR_EMPTY_NAME)
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH].rstrip()

    return name


def new_custom_id() -> str:
    return f"custom-{secrets.token_hex(6)}"


def _same_name(left: str, right: str) -> bool:
    return left.casefold() == right.casefold()


class PresetBook:
    """Built-in and custom presets plus the selected one.

    A custom preset with the same name as a built-in one replaces it in the
    list (design §18.4); deleting the custom one brings the built-in back.
    """

    def __init__(
        self,
        custom: Iterable[Preset] = (),
        *,
        selected_id: str | None = None,
        make_id: Callable[[], str] = new_custom_id,
    ) -> None:
        self._custom: list[Preset] = [p for p in custom if not p.builtin]
        self._selected_id = selected_id
        self._make_id = make_id

    # -- queries --------------------------------------------------------

    @property
    def custom(self) -> tuple[Preset, ...]:
        return tuple(self._custom)

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def presets(self) -> tuple[Preset, ...]:
        """Built-in order first, customs after; an override takes the built-in's place."""
        listed: list[Preset] = []
        used: set[str] = set()
        for builtin in BUILTIN_PRESETS:
            override = self._custom_named(builtin.name)
            if override is None:
                listed.append(builtin)
            else:
                listed.append(override)
                used.add(override.id)

        listed.extend(p for p in self._custom if p.id not in used)
        return tuple(listed)

    def find(self, preset_id: str) -> Preset | None:
        return next((p for p in self.presets() if p.id == preset_id), None)

    def selected(self) -> Preset | None:
        if self._selected_id is None:
            return None

        return self.find(self._selected_id)

    def preset_for(
        self, settings: ViewSettings, capabilities: ViewCapabilities
    ) -> Preset | None:
        """The preset whose snapshot is ``settings`` — the derived field label.

        The label is a product of the snapshot, not of the selection: a manual
        change that lands on a preset's snapshot names that preset again
        (design/view-panel.md §10.1).
        """
        return next(
            (
                preset
                for preset in self.presets()
                if preset.settings.normalized(capabilities) == settings
            ),
            None,
        )

    def applied(
        self, settings: ViewSettings, capabilities: ViewCapabilities
    ) -> Preset | None:
        """The selected preset when ``settings`` still equal its snapshot.

        «Настроено вручную» is derived (design/view-panel.md §10.1): a manual
        change makes the selection stop matching, nothing is cleared.
        """
        preset = self.selected()
        if preset is None:
            return None

        if preset.settings.normalized(capabilities) != settings:
            return None

        return preset

    # -- selection ------------------------------------------------------

    def select(self, preset_id: str | None) -> None:
        self._selected_id = preset_id if self.find(preset_id or "") else None

    def clear_selection(self) -> None:
        self._selected_id = None

    # -- mutations ------------------------------------------------------

    def save(self, name: str, settings: ViewSettings) -> Preset:
        """Create or overwrite the custom preset ``name`` and select it."""
        name = clean_name(name)
        existing = self._custom_named(name)
        if existing is not None:
            saved = replace(existing, name=name, settings=settings)
            self._custom[self._custom.index(existing)] = saved
        else:
            saved = Preset(self._make_id(), name, settings)
            self._custom.append(saved)

        self._selected_id = saved.id
        return saved

    def rename(self, preset_id: str, name: str) -> Preset:
        target = self._custom_by_id(preset_id)
        if target is None:
            raise PresetError(ERR_BUILTIN_READONLY)

        name = clean_name(name)
        if name == target.name:
            return target

        if self._name_taken(name, exclude=preset_id):
            raise PresetError(ERR_NAME_TAKEN)

        renamed = replace(target, name=name)
        self._custom[self._custom.index(target)] = renamed
        return renamed

    def delete(self, preset_id: str) -> bool:
        """Remove a custom preset; ``True`` when it was the selected one."""
        target = self._custom_by_id(preset_id)
        if target is None:
            raise PresetError(ERR_BUILTIN_READONLY)

        self._custom.remove(target)
        was_selected = self._selected_id == preset_id
        if was_selected:
            self._selected_id = None
        return was_selected

    # -- helpers --------------------------------------------------------

    def _custom_by_id(self, preset_id: str) -> Preset | None:
        return next((p for p in self._custom if p.id == preset_id), None)

    def _custom_named(self, name: str) -> Preset | None:
        return next((p for p in self._custom if _same_name(p.name, name)), None)

    def _name_taken(self, name: str, *, exclude: str) -> bool:
        """Any other custom or built-in preset already uses ``name``."""
        if any(_same_name(b.name, name) for b in BUILTIN_PRESETS):
            return True

        return any(_same_name(p.name, name) for p in self._custom if p.id != exclude)


def settings_fields(settings: ViewSettings) -> dict[str, object]:
    """Snapshot as keyword changes for ``DirectoryTab.update_view_settings``."""
    return {field.name: getattr(settings, field.name) for field in fields(settings)}
