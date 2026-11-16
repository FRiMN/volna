"""Display settings: what a tab shows and how its listing is ordered.

Pure data, no GTK. A directory tab owns one immutable snapshot; the View
panel edits it through ``DirectoryTab.update_view_settings``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeVar

from ..core import SortKey


class ViewMode(StrEnum):
    """Listing renderer; each mode is one module in ``volna.views``."""

    DETAILS = "details"
    COLUMNS = "columns"
    ICONS = "icons"

    @property
    def label(self) -> str:
        """Display name for controls (the View panel radio group)."""
        return _MODE_LABELS[self]


_MODE_LABELS: dict[ViewMode, str] = {
    ViewMode.DETAILS: "Подробности",
    ViewMode.COLUMNS: "Столбцы",
    ViewMode.ICONS: "Значки",
}

# Presentation order for controls: the mockup lists modes «Значки / Столбцы /
# Подробности»; the enum order reflects nothing user-facing.
MODE_ORDER: tuple[ViewMode, ...] = (
    ViewMode.ICONS,
    ViewMode.COLUMNS,
    ViewMode.DETAILS,
)


class Grouping(StrEnum):
    DATE = "date"
    NONE = "none"


# Preference order used when a stored mode is not available in this build.
_MODE_PREFERENCE = (ViewMode.DETAILS, ViewMode.COLUMNS, ViewMode.ICONS)


@dataclass(frozen=True, slots=True)
class ViewCapabilities:
    """What the current build can actually render and apply."""

    modes: frozenset[ViewMode]
    grouping: bool
    density: bool
    zoom_modes: frozenset[ViewMode]

    def preferred_mode(self) -> ViewMode:
        for mode in _MODE_PREFERENCE:
            if mode in self.modes:
                return mode
        return ViewMode.DETAILS


DEFAULT_CAPABILITIES = ViewCapabilities(
    modes=frozenset(MODE_ORDER),
    grouping=False,
    density=True,
    zoom_modes=frozenset(),
)


@dataclass(frozen=True, slots=True)
class ViewSettings:
    """One tab's snapshot of the display fields.

    Fields the current build cannot apply are still stored: they keep presets
    and the settings file forward-compatible. ``normalized`` is the gate that
    maps a snapshot onto real capabilities.
    """

    view_mode: ViewMode = ViewMode.DETAILS
    grouping: Grouping = Grouping.DATE
    sort_key: SortKey = SortKey.MTIME
    reverse: bool = True  # True = descending, matching the design default
    folders_first: bool = True
    show_hidden: bool = False
    compact: bool = False
    zoom: int = 50  # 0..100; 50 renders as "100 %"

    def normalized(self, capabilities: ViewCapabilities) -> ViewSettings:
        """Clamp a stored snapshot to what this build can render."""
        mode = (
            self.view_mode
            if self.view_mode in capabilities.modes
            else capabilities.preferred_mode()
        )
        grouping = self.grouping if capabilities.grouping else Grouping.NONE
        zoom = _clamp_zoom(self.zoom)

        return replace(self, view_mode=mode, grouping=grouping, zoom=zoom)

    def merged(self, capabilities: ViewCapabilities, **changes: object) -> ViewSettings:
        """Apply UI changes to a copy and normalize the result."""
        return replace(self, **changes).normalized(capabilities)

    def to_mapping(self) -> dict[str, object]:
        return {
            "view_mode": self.view_mode.value,
            "grouping": self.grouping.value,
            "sort_key": self.sort_key.value,
            "reverse": self.reverse,
            "folders_first": self.folders_first,
            "show_hidden": self.show_hidden,
            "compact": self.compact,
            "zoom": self.zoom,
        }

    @classmethod
    def from_mapping(cls, raw: object) -> ViewSettings:
        """Decode a JSON mapping; never raises on user data."""
        if not isinstance(raw, Mapping):
            return cls()

        defaults = cls()

        return cls(
            view_mode=_enum(ViewMode, raw.get("view_mode"), defaults.view_mode),
            grouping=_enum(Grouping, raw.get("grouping"), defaults.grouping),
            sort_key=_enum(SortKey, raw.get("sort_key"), defaults.sort_key),
            reverse=_bool(raw.get("reverse"), defaults.reverse),
            folders_first=_bool(raw.get("folders_first"), defaults.folders_first),
            show_hidden=_bool(raw.get("show_hidden"), defaults.show_hidden),
            compact=_bool(raw.get("compact"), defaults.compact),
            zoom=_zoom(raw.get("zoom"), defaults.zoom),
        )


DEFAULT_VIEW_SETTINGS = ViewSettings()


def _clamp_zoom(value: int) -> int:
    return max(0, min(100, value))


EnumT = TypeVar("EnumT", bound=StrEnum)


def _enum(enum_type: type[EnumT], raw: object, default: EnumT) -> EnumT:
    if isinstance(raw, enum_type):
        return raw
    if isinstance(raw, str):
        try:
            return enum_type(raw)
        except ValueError:
            return default

    return default


def _bool(raw: object, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)

    return default


def _zoom(raw: object, default: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return default

    return _clamp_zoom(round(raw))
