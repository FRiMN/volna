"""Interface size preset (see design/spec/02-design-tokens.md §10).

The product defaults to the «wide» preset (125 % of the compact grid); the
compact 100 % preset is kept as the base for the future interface-size setting.
"""

from __future__ import annotations

UI_SCALE = 1.25
SIZE_CLASS = "volna-size-wide"


def px(base: int) -> int:
    """Scale a compact-grid metric to the active interface size."""
    return max(1, int(base * UI_SCALE + 0.5))
