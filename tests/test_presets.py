"""Preset rules and their JSON store (pure, no GTK).

Specs: design/spec/05-interactions.md §18. The rules are checked on the book
itself, so the widgets cannot bypass them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from volna.core import SortKey
from volna.display import (
    BUILTIN_PRESETS,
    DEFAULT_CAPABILITIES,
    DEFAULT_PRESET_ID,
    Grouping,
    Preset,
    PresetBook,
    PresetError,
    ViewMode,
    ViewSettings,
    clean_name,
    create_preset_store,
    settings_fields,
)
from volna.display.presets_store import JsonPresetStore, MemoryPresetStore
from volna.display.store import SettingsPaths

BUILTIN_NAMES = [b.name for b in BUILTIN_PRESETS]


def _ids(counter: list[int]):
    def make() -> str:
        counter[0] += 1
        return f"custom-{counter[0]:04d}"

    return make


def _book(*custom: Preset, selected: str | None = None) -> PresetBook:
    return PresetBook(custom, selected_id=selected, make_id=_ids([0]))


def _custom(preset_id: str, name: str, **changes: object) -> Preset:
    return Preset(preset_id, name, ViewSettings(**changes))


# -- built-in set -----------------------------------------------------------


def test_builtin_set_matches_the_spec() -> None:
    assert BUILTIN_NAMES == [
        "По умолчанию",
        "Плотный список",
        "Крупные значки",
        "Без группировки",
    ]
    default = BUILTIN_PRESETS[0]
    assert default.id == DEFAULT_PRESET_ID
    assert default.settings.view_mode is ViewMode.COLUMNS
    assert all(preset.builtin for preset in BUILTIN_PRESETS)


def test_builtin_ids_are_unique() -> None:
    assert len({preset.id for preset in BUILTIN_PRESETS}) == len(BUILTIN_PRESETS)


def test_presets_lists_builtins_first() -> None:
    assert [p.name for p in PresetBook().presets()] == BUILTIN_NAMES


# -- name validation --------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_empty_name_is_rejected(raw: str) -> None:
    with pytest.raises(PresetError, match="не может быть пустым"):
        clean_name(raw)


def test_name_is_trimmed() -> None:
    assert clean_name("  Мой вид  ") == "Мой вид"


def test_long_name_is_cut_to_the_limit() -> None:
    assert len(clean_name("я" * 200)) == 64


# -- save -------------------------------------------------------------------


def test_save_creates_and_selects_a_custom_preset() -> None:
    book = _book()
    settings = ViewSettings(view_mode=ViewMode.ICONS, zoom=85)

    saved = book.save("Фото", settings)

    assert saved.name == "Фото"
    assert saved.settings == settings
    assert not saved.builtin
    assert book.selected_id == saved.id
    assert book.presets()[-1] == saved


def test_save_with_existing_custom_name_overwrites_it_keeping_the_id() -> None:
    book = _book(_custom("custom-a", "Фото"), selected=None)

    saved = book.save("фото", ViewSettings(compact=True))

    assert saved.id == "custom-a"
    assert saved.name == "фото"
    assert saved.settings.compact is True
    assert [p.id for p in book.custom] == ["custom-a"]


def test_save_with_builtin_name_overrides_the_builtin_in_place() -> None:
    book = _book()

    saved = book.save("Плотный список", ViewSettings(compact=False))

    names = [p.name for p in book.presets()]
    assert names == BUILTIN_NAMES
    assert book.find("dense-list") is None  # hidden by the override
    assert book.presets()[1] == saved
    assert not book.presets()[1].builtin


def test_save_rejects_an_empty_name() -> None:
    book = _book()

    with pytest.raises(PresetError):
        book.save("  ", ViewSettings())

    assert book.custom == ()


# -- rename -----------------------------------------------------------------


def test_rename_changes_only_the_name() -> None:
    settings = ViewSettings(zoom=85)
    book = _book(Preset("custom-a", "Старое", settings))

    renamed = book.rename("custom-a", "Новое")

    assert renamed.id == "custom-a"
    assert renamed.settings == settings
    assert book.find("custom-a").name == "Новое"


def test_rename_to_the_same_name_is_a_no_op() -> None:
    book = _book(Preset("custom-a", "Фото", ViewSettings()))

    assert book.rename("custom-a", "фото").name == "фото"


def test_rename_rejects_a_taken_custom_name() -> None:
    book = _book(
        Preset("custom-a", "Фото", ViewSettings()),
        Preset("custom-b", "Видео", ViewSettings()),
    )

    with pytest.raises(PresetError, match="уже существует"):
        book.rename("custom-b", "ФОТО")


@pytest.mark.parametrize("builtin_name", BUILTIN_NAMES)
def test_rename_rejects_a_builtin_name(builtin_name: str) -> None:
    book = _book(Preset("custom-a", "Фото", ViewSettings()))

    with pytest.raises(PresetError, match="уже существует"):
        book.rename("custom-a", builtin_name)


def test_builtin_presets_cannot_be_renamed() -> None:
    with pytest.raises(PresetError):
        PresetBook().rename(DEFAULT_PRESET_ID, "Другое")


def test_rename_keeps_the_selection() -> None:
    book = _book(Preset("custom-a", "Фото", ViewSettings()), selected="custom-a")

    book.rename("custom-a", "Фото 2")

    assert book.selected_id == "custom-a"
    assert book.selected().name == "Фото 2"


# -- delete -----------------------------------------------------------------


def test_delete_reports_whether_the_selection_was_removed() -> None:
    book = _book(Preset("custom-a", "Фото", ViewSettings()), selected="custom-a")

    assert book.delete("custom-a") is True
    assert book.selected_id is None
    assert book.custom == ()


def test_delete_of_another_preset_keeps_the_selection() -> None:
    book = _book(
        Preset("custom-a", "Фото", ViewSettings()),
        Preset("custom-b", "Видео", ViewSettings()),
        selected="custom-a",
    )

    assert book.delete("custom-b") is False
    assert book.selected_id == "custom-a"


def test_builtin_presets_cannot_be_deleted() -> None:
    with pytest.raises(PresetError):
        PresetBook().delete("dense-list")


def test_deleting_an_override_brings_the_builtin_back() -> None:
    book = _book(Preset("custom-a", "Плотный список", ViewSettings(compact=False)))
    assert book.presets()[1].id == "custom-a"

    book.delete("custom-a")

    assert book.presets()[1].id == "dense-list"


# -- selection and manual state ----------------------------------------------


def test_select_ignores_unknown_ids() -> None:
    book = PresetBook()

    book.select("missing")

    assert book.selected_id is None


def test_applied_matches_the_snapshot_of_the_selected_preset() -> None:
    book = PresetBook(selected_id="dense-list")
    snapshot = BUILTIN_PRESETS[1].settings.normalized(DEFAULT_CAPABILITIES)

    assert book.applied(snapshot, DEFAULT_CAPABILITIES) is BUILTIN_PRESETS[1]


def test_a_changed_snapshot_is_manual() -> None:
    book = PresetBook(selected_id="dense-list")
    changed = ViewSettings(view_mode=ViewMode.ICONS, compact=True)

    assert book.applied(changed, DEFAULT_CAPABILITIES) is None
    assert book.selected_id == "dense-list"


def test_applied_is_none_without_a_selection() -> None:
    assert PresetBook().applied(ViewSettings(), DEFAULT_CAPABILITIES) is None


def test_clear_selection() -> None:
    book = PresetBook(selected_id=DEFAULT_PRESET_ID)

    book.clear_selection()

    assert book.selected() is None


def test_settings_fields_round_trip_through_the_change_mapping() -> None:
    settings = ViewSettings(
        view_mode=ViewMode.ICONS,
        grouping=Grouping.NONE,
        sort_key=SortKey.NAME,
        reverse=False,
        folders_first=False,
        show_hidden=True,
        compact=True,
        zoom=85,
    )

    fields = settings_fields(settings)

    assert ViewSettings().merged(DEFAULT_CAPABILITIES, **fields) == settings.normalized(
        DEFAULT_CAPABILITIES
    )


# -- JSON store ---------------------------------------------------------------


def _paths(tmp_path: Path) -> SettingsPaths:
    directory = tmp_path / "volna"
    return SettingsPaths(directory=directory, file=directory / "settings.json")


def test_store_round_trips_custom_presets(tmp_path: Path) -> None:
    store = JsonPresetStore(_paths(tmp_path))
    presets = (Preset("custom-a", "Фото", ViewSettings(view_mode=ViewMode.ICONS)),)

    assert store.save(presets) is True

    loaded = JsonPresetStore(_paths(tmp_path)).load()
    assert loaded.presets == presets
    assert loaded.issues == ()


def test_store_never_writes_builtin_presets(tmp_path: Path) -> None:
    store = JsonPresetStore(_paths(tmp_path))

    store.save(BUILTIN_PRESETS)

    document = json.loads((tmp_path / "volna" / "presets.json").read_text("utf-8"))
    assert document == {"schema_version": 1, "presets": []}


def test_missing_file_loads_no_presets(tmp_path: Path) -> None:
    document = JsonPresetStore(_paths(tmp_path)).load()

    assert document.presets == ()
    assert document.issues == ()


def test_corrupt_file_is_kept_on_save(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    file = paths.directory / "presets.json"
    file.write_text("{not json", encoding="utf-8")
    store = JsonPresetStore(paths)

    document = store.load()
    store.save((Preset("custom-a", "Фото", ViewSettings()),))

    assert document.issues
    backups = list(paths.directory.glob("presets.json.invalid-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not json"


def test_invalid_entries_are_skipped_with_an_issue(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    (paths.directory / "presets.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "presets": [
                    {"id": "custom-a", "name": "Фото", "settings": {}},
                    {"id": "dense-list", "name": "Чужой", "settings": {}},
                    {"id": "custom-b", "name": "  ", "settings": {}},
                    {"id": "custom-c", "name": "фото", "settings": {}},
                    "junk",
                ],
            }
        ),
        encoding="utf-8",
    )

    document = JsonPresetStore(paths).load()

    assert [p.id for p in document.presets] == ["custom-a"]
    assert document.issues


def test_newer_schema_is_read_only(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    file = paths.directory / "presets.json"
    file.write_text('{"schema_version": 9, "presets": []}', encoding="utf-8")
    store = JsonPresetStore(paths)

    document = store.load()

    assert document.issues
    assert store.save((Preset("custom-a", "Фото", ViewSettings()),)) is False
    assert file.read_text(encoding="utf-8") == '{"schema_version": 9, "presets": []}'


def test_unwritable_directory_reports_failure(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a directory", encoding="utf-8")
    store = JsonPresetStore(SettingsPaths(blocker / "volna", blocker / "x"))

    assert store.save((Preset("custom-a", "Фото", ViewSettings()),)) is False


def test_memory_store_keeps_presets_in_memory() -> None:
    store = MemoryPresetStore()
    presets = (Preset("custom-a", "Фото", ViewSettings()),)

    assert store.save(presets) is True
    assert store.load().presets == presets


def test_no_config_directory_falls_back_to_memory() -> None:
    assert isinstance(create_preset_store(None), MemoryPresetStore)
