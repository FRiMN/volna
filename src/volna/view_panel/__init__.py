"""«Вид»: toolbar trigger and the display-settings popover (a plain module).

The panel itself is not a feature; the individual settings inside it are
separate feature modules composed through ``SETTING_FEATURES``.
"""

from .panel import ViewPanel
from .settings import SETTING_FEATURES

__all__ = ["SETTING_FEATURES", "ViewPanel"]
