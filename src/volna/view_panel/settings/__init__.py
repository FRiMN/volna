"""Registered View-panel settings, one module per setting.

The tuple is the only place that knows which settings exist and in what order
they appear; the panel groups them by ``section``. Adding a setting means a new
module next to the others plus one line here — ``panel.py`` stays untouched.
"""

from .base import SettingFeature
from .density import DensitySetting
from .folders_first import FoldersFirstSetting
from .grouping import GroupingSetting
from .show_hidden import ShowHiddenSetting
from .sort_direction import SortDirectionSetting
from .sort_key import SortKeySetting
from .view_mode import ViewModeSetting

# Order defines the section order in the popover: «Режим просмотра», then
# «Группировка», then «Сортировка», then «Параметры» (first-seen grouping in
# panel.py; design/spec/03-layout.md §8).
SETTING_FEATURES: tuple[type[SettingFeature], ...] = (
    ViewModeSetting,
    GroupingSetting,
    SortKeySetting,
    SortDirectionSetting,
    FoldersFirstSetting,
    ShowHiddenSetting,
    DensitySetting,
)

__all__ = [
    "SETTING_FEATURES",
    "DensitySetting",
    "FoldersFirstSetting",
    "GroupingSetting",
    "SettingFeature",
    "ShowHiddenSetting",
    "SortDirectionSetting",
    "SortKeySetting",
    "ViewModeSetting",
]
