"""Pure tests for display settings; see design/view-panel.md §4.1, §7.1."""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError

import pytest

from volna.core import SortKey
from volna.display import (
    DEFAULT_CAPABILITIES,
    DEFAULT_VIEW_SETTINGS,
    GROUPING_ORDER,
    Grouping,
    ViewCapabilities,
    ViewMode,
    ViewSettings,
)

ALL_MODES = frozenset({ViewMode.DETAILS, ViewMode.COLUMNS, ViewMode.ICONS})
ALL_CAPABILITIES = ViewCapabilities(
    modes=ALL_MODES, grouping=True, density=True, zoom_modes=ALL_MODES
)
UNGROUPED_CAPABILITIES = ViewCapabilities(
    modes=ALL_MODES, grouping=False, density=True, zoom_modes=ALL_MODES
)
ONLY_ICONS = ViewCapabilities(
    modes=frozenset({ViewMode.ICONS}),
    grouping=False,
    density=False,
    zoom_modes=frozenset(),
)
DETAILS_ONLY = ViewCapabilities(
    modes=frozenset({ViewMode.DETAILS}),
    grouping=False,
    density=True,
    zoom_modes=frozenset(),
)


def test_defaults() -> None:
    settings = ViewSettings()

    assert settings == DEFAULT_VIEW_SETTINGS
    assert settings.view_mode is ViewMode.DETAILS
    assert settings.grouping is Grouping.DATE
    assert settings.sort_key is SortKey.MTIME
    assert settings.reverse is True
    assert settings.folders_first is True
    assert settings.show_hidden is False
    assert settings.compact is False
    assert settings.zoom == 50


def test_enum_values_match_stored_json() -> None:
    assert ViewMode.DETAILS == "details"
    assert ViewMode.COLUMNS == "columns"
    assert ViewMode.ICONS == "icons"
    assert Grouping.DATE == "date"
    assert Grouping.NONE == "none"
    assert SortKey.MTIME.value == "mtime"


def test_to_mapping_has_the_documented_keys() -> None:
    mapping = ViewSettings().to_mapping()

    assert set(mapping) == {
        "view_mode",
        "grouping",
        "sort_key",
        "reverse",
        "folders_first",
        "show_hidden",
        "compact",
        "zoom",
    }
    # The mapping is the on-disk view object, so it must be JSON-serializable.
    assert json.loads(json.dumps(mapping)) == mapping


@pytest.mark.parametrize(
    "settings",
    [
        ViewSettings(),
        ViewSettings(
            view_mode=ViewMode.ICONS,
            grouping=Grouping.NONE,
            sort_key=SortKey.NAME,
            reverse=False,
            folders_first=False,
            show_hidden=True,
            compact=True,
            zoom=85,
        ),
        ViewSettings(sort_key=SortKey.SIZE, zoom=0),
        ViewSettings(sort_key=SortKey.NAME, zoom=100),
    ],
)
def test_mapping_round_trip(settings: ViewSettings) -> None:
    assert ViewSettings.from_mapping(settings.to_mapping()) == settings


def test_from_mapping_with_no_keys_returns_defaults() -> None:
    assert ViewSettings.from_mapping({}) == DEFAULT_VIEW_SETTINGS


def test_from_mapping_ignores_unknown_keys_and_junk() -> None:
    raw = {
        "view_mode": "icons",
        "presets": [{"name": "По умолчанию"}],
        "schema_version": 99,
        "nonsense": {"deep": [1, 2, 3]},
        "zoom": 85,
    }

    assert ViewSettings.from_mapping(raw) == ViewSettings(
        view_mode=ViewMode.ICONS, zoom=85
    )


@pytest.mark.parametrize("raw", [None, [], "details", 42, ("view_mode", "details")])
def test_from_mapping_accepts_non_mapping_input(raw: object) -> None:
    assert ViewSettings.from_mapping(raw) == DEFAULT_VIEW_SETTINGS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (150, 100),
        (100, 100),
        (101, 100),
        (50, 50),
        (0, 0),
        (-10, 0),
        (-0.4, 0),
        (49.6, 50),
        (1000, 100),
    ],
)
def test_from_mapping_clamps_and_rounds_zoom(raw: object, expected: int) -> None:
    assert ViewSettings.from_mapping({"zoom": raw}).zoom == expected


@pytest.mark.parametrize("raw", [True, False])
def test_from_mapping_rejects_bool_zoom(raw: bool) -> None:
    # JSON booleans are ints in Python; they must not become 1/0 here.
    assert ViewSettings.from_mapping({"zoom": raw}).zoom == 50


@pytest.mark.parametrize("raw", ["80", None, [], {}, "big"])
def test_from_mapping_rejects_non_numeric_zoom(raw: object) -> None:
    assert ViewSettings.from_mapping({"zoom": raw}).zoom == 50


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("view_mode", "gallery", ViewMode.DETAILS),
        ("view_mode", 7, ViewMode.DETAILS),
        ("grouping", "size", Grouping.DATE),
        ("grouping", None, Grouping.DATE),
        ("sort_key", "owner", SortKey.MTIME),
        ("sort_key", [], SortKey.MTIME),
    ],
)
def test_unknown_enum_falls_back_to_default(
    key: str, raw: object, expected: object
) -> None:
    assert getattr(ViewSettings.from_mapping({key: raw}), key) is expected


def test_enum_instances_are_accepted() -> None:
    settings = ViewSettings.from_mapping(
        {
            "view_mode": ViewMode.ICONS,
            "grouping": Grouping.NONE,
            "sort_key": SortKey.SIZE,
        }
    )

    assert settings.view_mode is ViewMode.ICONS
    assert settings.grouping is Grouping.NONE
    assert settings.sort_key is SortKey.SIZE


def test_bool_fields_accept_json_booleans_and_int_flags() -> None:
    settings = ViewSettings.from_mapping(
        {"reverse": False, "folders_first": 0, "show_hidden": True, "compact": 0}
    )

    assert settings.reverse is False
    assert settings.folders_first is False
    assert settings.show_hidden is True
    assert settings.compact is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", False),
        (2, False),
        (-1, False),
        (None, False),
        ({}, False),
    ],
)
def test_bool_fields_fall_back_on_junk(raw: object, expected: bool) -> None:
    assert ViewSettings.from_mapping({"show_hidden": raw}).show_hidden is expected


@pytest.mark.parametrize(
    ("capabilities", "stored", "expected"),
    [
        # The default build renders all three modes, so a stored mode survives.
        (DEFAULT_CAPABILITIES, ViewMode.DETAILS, ViewMode.DETAILS),
        (DEFAULT_CAPABILITIES, ViewMode.ICONS, ViewMode.ICONS),
        (DEFAULT_CAPABILITIES, ViewMode.COLUMNS, ViewMode.COLUMNS),
        # A build with fewer modes falls back to its preferred mode.
        (DETAILS_ONLY, ViewMode.ICONS, ViewMode.DETAILS),
        (DETAILS_ONLY, ViewMode.COLUMNS, ViewMode.DETAILS),
        (ONLY_ICONS, ViewMode.DETAILS, ViewMode.ICONS),
        (
            ViewCapabilities(
                modes=frozenset({ViewMode.COLUMNS, ViewMode.ICONS}),
                grouping=True,
                density=True,
                zoom_modes=frozenset(),
            ),
            ViewMode.DETAILS,
            ViewMode.COLUMNS,
        ),
        (ALL_CAPABILITIES, ViewMode.ICONS, ViewMode.ICONS),
    ],
)
def test_normalized_maps_mode_to_what_the_build_can_render(
    capabilities: ViewCapabilities,
    stored: ViewMode,
    expected: ViewMode,
) -> None:
    settings = ViewSettings(view_mode=stored)

    assert settings.normalized(capabilities).view_mode is expected


def test_default_capabilities_enable_grouping() -> None:
    assert DEFAULT_CAPABILITIES.grouping is True


def test_grouping_labels_and_order_follow_the_mockup() -> None:
    assert [grouping.label for grouping in GROUPING_ORDER] == [
        "По дате изменения",
        "Без группировки",
    ]
    assert GROUPING_ORDER == (Grouping.DATE, Grouping.NONE)


def test_normalized_forces_ungrouped_when_grouping_is_unavailable() -> None:
    assert ViewSettings(grouping=Grouping.DATE).normalized(
        UNGROUPED_CAPABILITIES
    ).grouping is (Grouping.NONE)


def test_normalized_keeps_grouping_when_available() -> None:
    settings = ViewSettings(grouping=Grouping.DATE)

    assert settings.normalized(ALL_CAPABILITIES).grouping is Grouping.DATE


@pytest.mark.parametrize(("raw", "expected"), [(150, 100), (-5, 0), (0, 0), (100, 100)])
def test_normalized_clamps_zoom(raw: int, expected: int) -> None:
    settings = ViewSettings(zoom=raw)

    assert settings.normalized(DEFAULT_CAPABILITIES).zoom == expected


def test_normalized_preserves_fields_it_does_not_own() -> None:
    settings = ViewSettings(
        view_mode=ViewMode.COLUMNS,
        grouping=Grouping.DATE,
        sort_key=SortKey.NAME,
        reverse=False,
        folders_first=False,
        show_hidden=True,
        compact=True,
        zoom=70,
    )

    normalized = settings.normalized(UNGROUPED_CAPABILITIES)

    assert normalized.sort_key is SortKey.NAME
    assert normalized.reverse is False
    assert normalized.folders_first is False
    assert normalized.show_hidden is True
    assert normalized.compact is True
    assert normalized.view_mode is ViewMode.COLUMNS
    assert normalized.grouping is Grouping.NONE
    assert normalized.zoom == 70


def test_merged_applies_changes_and_normalizes() -> None:
    base = ViewSettings()

    merged = base.merged(
        DEFAULT_CAPABILITIES,
        view_mode=ViewMode.ICONS,
        grouping=Grouping.DATE,
        sort_key=SortKey.NAME,
        reverse=False,
        show_hidden=True,
        compact=True,
        zoom=140,
    )

    assert merged == ViewSettings(
        view_mode=ViewMode.ICONS,
        grouping=Grouping.DATE,
        sort_key=SortKey.NAME,
        reverse=False,
        show_hidden=True,
        compact=True,
        zoom=100,
    )
    assert base == ViewSettings()


def test_merged_without_changes_is_normalized() -> None:
    base = ViewSettings(view_mode=ViewMode.ICONS, grouping=Grouping.DATE)

    assert base.merged(DEFAULT_CAPABILITIES) == base.normalized(DEFAULT_CAPABILITIES)


def test_settings_are_frozen() -> None:
    settings = ViewSettings()

    with pytest.raises(FrozenInstanceError):
        settings.zoom = 60  # type: ignore[misc]


def test_settings_have_value_equality() -> None:
    first = ViewSettings(sort_key=SortKey.SIZE)
    second = ViewSettings(sort_key=SortKey.SIZE)

    assert first == second
    assert hash(first) == hash(second)
    assert first != ViewSettings(sort_key=SortKey.NAME)


def test_display_import_does_not_pull_gtk_or_ui_modules() -> None:
    # design/view-panel.md §7.1: the domain stays importable without a
    # display, so a subprocess keeps the check independent of other test imports.
    script = (
        "import sys\n"
        "import volna.display\n"
        "banned = [\n"
        "    name\n"
        "    for name in ('gi', 'volna.views', 'volna.view_panel', 'volna.tab', 'volna.window')\n"
        "    if name in sys.modules\n"
        "]\n"
        "assert not banned, banned\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )

    assert result.returncode == 0, result.stderr
