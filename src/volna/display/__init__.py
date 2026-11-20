"""Display settings and their last-view storage (pure, no GTK)."""

from ..core import SortKey
from .grouping import GroupAction, group_key, group_label
from .presets import (
    BUILTIN_PRESETS,
    DEFAULT_PRESET_ID,
    Preset,
    PresetBook,
    PresetError,
    clean_name,
    settings_fields,
)
from .presets_store import (
    MemoryPresetStore,
    PresetDocument,
    PresetStore,
    create_preset_store,
)
from .settings import (
    COLLAPSE_MODES,
    DEFAULT_CAPABILITIES,
    DEFAULT_VIEW_SETTINGS,
    GROUPING_ORDER,
    MODE_ORDER,
    Grouping,
    ViewCapabilities,
    ViewMode,
    ViewSettings,
)
from .store import (
    SCHEMA_VERSION,
    JsonViewSettingsStore,
    MemoryViewSettingsStore,
    SettingsDocument,
    SettingsPaths,
    ViewSettingsStore,
    create_store,
)

__all__ = [
    "BUILTIN_PRESETS",
    "COLLAPSE_MODES",
    "DEFAULT_CAPABILITIES",
    "DEFAULT_PRESET_ID",
    "DEFAULT_VIEW_SETTINGS",
    "GROUPING_ORDER",
    "GroupAction",
    "Grouping",
    "JsonViewSettingsStore",
    "MODE_ORDER",
    "MemoryPresetStore",
    "MemoryViewSettingsStore",
    "Preset",
    "PresetBook",
    "PresetDocument",
    "PresetError",
    "PresetStore",
    "SCHEMA_VERSION",
    "SettingsDocument",
    "SettingsPaths",
    "SortKey",
    "ViewCapabilities",
    "ViewMode",
    "ViewSettings",
    "ViewSettingsStore",
    "clean_name",
    "create_preset_store",
    "create_store",
    "group_key",
    "group_label",
    "settings_fields",
]
