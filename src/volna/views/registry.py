"""The list of view modes: one class per module, one registry line per mode.

The only place that knows which modes exist (design/view-modes.md D1). Adding
a mode = a new module in this package plus a line here; ``tab.py`` and the
View panel pick the available modes up from capabilities, not from this file.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..display import ViewMode
from .base import ListingView
from .columns import ColumnsView
from .details import DetailsView
from .icons import IconsView

MODE_VIEWS: tuple[type[ListingView], ...] = (IconsView, ColumnsView, DetailsView)

VIEWS_BY_MODE: Mapping[ViewMode, type[ListingView]] = {
    view.mode: view for view in MODE_VIEWS
}
