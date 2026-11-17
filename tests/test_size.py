"""Interface scale resolution (design/spec/02 §10).

The stylesheet is one compact em grid; these tests pin the mapping from the
desktop's UI font to the scale that grid and ``px()`` use.
"""

from __future__ import annotations

import pytest

from volna import size as size_module


def test_the_reference_desktop_is_unscaled() -> None:
    """10 pt at 96 dpi is the 100 % desktop the compact grid was drawn for."""
    assert size_module.scale_for_font(size_module.REFERENCE_FONT_PX) == 1.0


@pytest.mark.parametrize(
    ("font_px", "expected"),
    [
        (16.6667, 1.25),  # 125 % desktop: 10 pt at 120 dpi
        (20.0, 1.5),  # 150 % desktop
        (26.6667, 2.0),
    ],
)
def test_scaled_desktops(font_px: float, expected: float) -> None:
    assert size_module.scale_for_font(font_px) == pytest.approx(expected, rel=1e-4)


def test_unreadable_font_falls_back_to_the_compact_grid() -> None:
    assert size_module.scale_for_font(None) == 1.0
    assert size_module.scale_for_font(0) == 1.0
    assert size_module.scale_for_font(-10) == 1.0


def test_the_scale_stays_inside_the_usable_range() -> None:
    assert size_module.scale_for_font(1.0) == size_module.MIN_SCALE
    assert size_module.scale_for_font(1000.0) == size_module.MAX_SCALE


@pytest.fixture
def use_scale(monkeypatch: pytest.MonkeyPatch):
    """Set the resolved scale without touching the desktop settings."""

    def apply(scale: float) -> None:
        monkeypatch.setattr(size_module, "_scale", scale)

    return apply


def test_px_scales_compact_metrics(use_scale) -> None:
    use_scale(1.25)
    assert size_module.px(40) == 50
    assert size_module.px(16) == 20
    assert size_module.px(1) == 1


def test_px_keeps_the_compact_grid_on_a_100_percent_desktop(use_scale) -> None:
    use_scale(1.0)
    assert size_module.px(40) == 40
    assert size_module.px(48) == 48


def test_px_rounds_half_up_and_never_returns_zero(use_scale) -> None:
    use_scale(1.1)
    assert size_module.px(16) == 18  # 17.6 -> 18
    assert size_module.px(1) == 1


def test_root_font_keeps_the_design_convention(use_scale) -> None:
    """14 px at 100 %, 17.5 px at 125 %: the app is 5 % larger than toolkit text."""
    use_scale(1.0)
    assert size_module.base_font_px() == 14.0
    use_scale(1.25)
    assert size_module.base_font_px() == 17.5


def test_configure_resolves_the_scale_from_the_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(size_module, "_scale", 1.0)
    monkeypatch.setattr(size_module, "detect_ui_scale", lambda: 1.25)

    assert size_module.configure() == 1.25
    assert size_module.ui_scale() == 1.25
    assert size_module.px(40) == 50
    assert size_module.base_font_px() == 17.5


def test_the_scale_stays_compact_until_configured() -> None:
    """Importing the app must not read desktop settings (it would init GTK)."""
    assert size_module.ui_scale() == 1.0
