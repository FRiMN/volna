"""Pure tests for the last-view store; see design/view-panel.md §4.2, §5."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from volna.core import SortKey
from volna.display import (
    SCHEMA_VERSION,
    Grouping,
    JsonViewSettingsStore,
    MemoryViewSettingsStore,
    SettingsPaths,
    ViewMode,
    ViewSettings,
    create_store,
)

RUNNING_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def _paths(tmp_path: Path) -> SettingsPaths:
    directory = tmp_path / "volna"
    return SettingsPaths(directory=directory, file=directory / "settings.json")


def _write_document(paths: SettingsPaths, document: object) -> None:
    paths.directory.mkdir(parents=True, exist_ok=True)
    paths.file.write_text(json.dumps(document), encoding="utf-8")


def test_default_paths_prefer_xdg_config_home() -> None:
    paths = SettingsPaths.default({"XDG_CONFIG_HOME": "/xdg", "HOME": "/home/frimm"})

    assert paths == SettingsPaths(
        directory=Path("/xdg/volna"), file=Path("/xdg/volna/settings.json")
    )


def test_default_paths_fall_back_to_home() -> None:
    paths = SettingsPaths.default({"HOME": "/home/frimm"})

    assert paths == SettingsPaths(
        directory=Path("/home/frimm/.config/volna"),
        file=Path("/home/frimm/.config/volna/settings.json"),
    )


def test_default_paths_are_none_without_xdg_or_home() -> None:
    assert SettingsPaths.default({}) is None


def test_default_paths_read_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    paths = SettingsPaths.default()

    assert paths == SettingsPaths(
        directory=tmp_path / "xdg" / "volna",
        file=tmp_path / "xdg" / "volna" / "settings.json",
    )

    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.delenv("HOME")

    assert SettingsPaths.default() is None


def test_missing_file_returns_defaults_without_creating_it(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    document = JsonViewSettingsStore(paths).load()

    assert document.view is None
    assert document.issues == ()
    assert not paths.directory.exists()


def test_round_trip_keeps_the_full_snapshot(tmp_path: Path) -> None:
    # Unsupported-by-V1 values must survive storage: presets and the file are
    # forward-compatible, normalization belongs to the tab layer.
    settings = ViewSettings(
        view_mode=ViewMode.COLUMNS,
        grouping=Grouping.NONE,
        sort_key=SortKey.NAME,
        reverse=False,
        folders_first=False,
        show_hidden=True,
        compact=True,
        zoom=85,
    )
    paths = _paths(tmp_path)

    assert JsonViewSettingsStore(paths).save(settings) is True

    document = JsonViewSettingsStore(paths).load()
    assert document.view == settings
    assert document.issues == ()

    text = paths.file.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == {
        "schema_version": SCHEMA_VERSION,
        "view": settings.to_mapping(),
    }


def test_save_creates_the_settings_directory(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    assert not paths.directory.exists()

    assert JsonViewSettingsStore(paths).save(ViewSettings()) is True

    assert paths.directory.is_dir()


def test_corrupt_json_degrades_and_is_preserved_on_next_save(tmp_path: Path) -> None:
    corrupt = b'{"schema_version": 1, "view": '
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    paths.file.write_bytes(corrupt)

    store = JsonViewSettingsStore(paths)
    document = store.load()

    assert document.view is None
    assert document.issues
    assert paths.file.read_bytes() == corrupt

    replacement = ViewSettings(sort_key=SortKey.NAME, zoom=80)
    assert store.save(replacement) is True

    backups = list(paths.directory.glob("settings.json.invalid-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == corrupt
    assert JsonViewSettingsStore(paths).load().view == replacement


@pytest.mark.parametrize("raw", ["null", "[]", '"text"', "42", "{oops"])
def test_non_object_document_is_an_issue(tmp_path: Path, raw: str) -> None:
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    paths.file.write_text(raw, encoding="utf-8")

    document = JsonViewSettingsStore(paths).load()

    assert document.view is None
    assert document.issues
    assert paths.file.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize(
    "document",
    [
        {"view": {}},
        {"schema_version": None, "view": {}},
        {"schema_version": True, "view": {}},
        {"schema_version": "1", "view": {}},
    ],
)
def test_missing_or_non_int_schema_version_is_an_issue(
    tmp_path: Path, document: object
) -> None:
    paths = _paths(tmp_path)
    _write_document(paths, document)

    result = JsonViewSettingsStore(paths).load()

    assert result.view is None
    assert result.issues


def test_newer_schema_degrades_to_defaults(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_document(
        paths, {"schema_version": SCHEMA_VERSION + 1, "view": {"sort_key": "name"}}
    )
    before = paths.file.read_bytes()

    document = JsonViewSettingsStore(paths).load()

    assert document.view is None
    assert document.issues
    assert paths.file.read_bytes() == before


def test_broken_field_falls_back_while_others_survive(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_document(
        paths,
        {
            "schema_version": SCHEMA_VERSION,
            "view": {
                "view_mode": "gallery",
                "grouping": "date",
                "sort_key": "name",
                "reverse": False,
                "show_hidden": "yes",
                "compact": True,
                "zoom": 999,
            },
        },
    )

    view = JsonViewSettingsStore(paths).load().view

    assert view == ViewSettings(
        view_mode=ViewMode.DETAILS,
        grouping=Grouping.DATE,
        sort_key=SortKey.NAME,
        reverse=False,
        show_hidden=False,
        compact=True,
        zoom=100,
    )


def test_save_is_atomic_and_leaves_no_temporary_files(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    assert JsonViewSettingsStore(paths).save(ViewSettings()) is True

    assert sorted(entry.name for entry in paths.directory.iterdir()) == [
        "settings.json"
    ]


def test_save_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _paths(tmp_path)
    store = JsonViewSettingsStore(paths)
    settings = ViewSettings(sort_key=SortKey.NAME)
    writes: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def counting_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        writes.append("write")
        return real_mkstemp(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(tempfile, "mkstemp", counting_mkstemp)

    assert store.save(settings) is True
    payload = paths.file.read_bytes()
    modified = paths.file.stat().st_mtime_ns
    time.sleep(0.02)

    assert store.save(settings) is True

    assert paths.file.read_bytes() == payload
    assert paths.file.stat().st_mtime_ns == modified
    assert writes == ["write"]


@pytest.mark.skipif(RUNNING_AS_ROOT, reason="root ignores directory permissions")
def test_read_only_directory_saves_nothing_but_still_loads(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    settings = ViewSettings(sort_key=SortKey.SIZE, zoom=70)
    assert JsonViewSettingsStore(paths).save(settings) is True
    before = paths.file.read_bytes()
    os.chmod(paths.directory, 0o500)

    try:
        assert JsonViewSettingsStore(paths).load().view == settings
        assert JsonViewSettingsStore(paths).save(ViewSettings()) is False
        assert paths.file.read_bytes() == before
    finally:
        os.chmod(paths.directory, 0o700)


def test_unreadable_file_reports_an_issue(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.file.mkdir(parents=True)

    document = JsonViewSettingsStore(paths).load()

    assert document.view is None
    assert document.issues


def test_memory_store_round_trip() -> None:
    initial = ViewSettings(sort_key=SortKey.NAME, show_hidden=True)
    store = MemoryViewSettingsStore(initial, issues=("note",))

    assert store.load().view == initial
    assert store.load().issues == ("note",)

    replacement = ViewSettings(zoom=10)
    assert store.save(replacement) is True
    assert store.load().view == replacement
    assert store.load().issues == ("note",)


def test_create_store_without_paths_returns_memory_store() -> None:
    store = create_store(None)

    assert isinstance(store, MemoryViewSettingsStore)
    assert store.load().issues
    assert store.save(ViewSettings(sort_key=SortKey.SIZE)) is True
    assert store.load().view == ViewSettings(sort_key=SortKey.SIZE)


def test_create_store_with_paths_returns_json_store(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    settings = ViewSettings(view_mode=ViewMode.ICONS, zoom=85)
    store = create_store(paths)

    assert isinstance(store, JsonViewSettingsStore)
    assert store.save(settings) is True
    assert JsonViewSettingsStore(paths).load().view == settings


# --- Known implementation bugs, kept as failing reproductions -----------------
# These tests state the contract from design/view-panel.md §5.1/§5.4;
# they fail until src/volna/display/store.py is fixed. Do not "fix" the tests.


def test_newer_schema_file_is_not_overwritten(tmp_path: Path) -> None:
    """§5.1: a newer-schema file is read-only; save() must not replace it."""
    paths = _paths(tmp_path)
    _write_document(
        paths, {"schema_version": SCHEMA_VERSION + 1, "view": {"sort_key": "name"}}
    )
    before = paths.file.read_bytes()
    store = JsonViewSettingsStore(paths)

    assert store.load().issues
    assert store.save(ViewSettings()) is False
    assert paths.file.read_bytes() == before


def test_invalid_utf8_degrades_to_defaults(tmp_path: Path) -> None:
    """§5.4: broken JSON / non-UTF-8 degrades to defaults, never raises."""
    paths = _paths(tmp_path)
    paths.directory.mkdir(parents=True)
    paths.file.write_bytes(b'{"schema_version": 1, "view": {"sort_key": "\xff"}}')

    document = JsonViewSettingsStore(paths).load()

    assert document.view is None
    assert document.issues
