"""User presets persistence: ``presets.json`` next to ``settings.json``.

Same contract as the last-view store: a failure never raises, it degrades to
an issue message, a memory fallback or a read-only file. A malformed entry is
skipped, and the original file is kept as ``*.invalid-*`` before the next save.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from .files import preserve_invalid, write_atomically
from .presets import MAX_NAME_LENGTH, Preset, PresetError, clean_name
from .settings import ViewSettings
from .store import SettingsPaths

SCHEMA_VERSION = 1
PRESETS_FILE_NAME = "presets.json"

_LOG = logging.getLogger("volna.display.presets_store")

_READ_FAILED = "Не удалось прочитать пресеты, используются встроенные"
_CORRUPT = "Файл пресетов повреждён, пользовательские пресеты не загружены"
_SKIPPED = "Часть пресетов повреждена и пропущена"
_NEWER = "Пресеты созданы более новой версией, изменения не сохраняются"


@dataclass(frozen=True, slots=True)
class PresetDocument:
    presets: tuple[Preset, ...] = ()
    issues: tuple[str, ...] = ()


class PresetStore(Protocol):
    def load(self) -> PresetDocument: ...

    def save(self, presets: Sequence[Preset]) -> bool:
        """Persist the custom presets; ``False`` means the caller keeps them in memory."""
        ...


class MemoryPresetStore:
    """Fallback for tests and for hosts without a config directory."""

    def __init__(self, presets: Sequence[Preset] = ()) -> None:
        self._presets = tuple(presets)

    def load(self) -> PresetDocument:
        return PresetDocument(self._presets)

    def save(self, presets: Sequence[Preset]) -> bool:
        self._presets = tuple(presets)
        return True


class JsonPresetStore:
    """Atomic JSON store; read/write failures become issues, never exceptions."""

    def __init__(self, paths: SettingsPaths) -> None:
        self._directory = paths.directory
        self._file = paths.directory / PRESETS_FILE_NAME
        self._last_payload: str | None = None
        self._discard_invalid_on_save = False
        self._read_only = False

    def load(self) -> PresetDocument:
        try:
            text = self._file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return PresetDocument()
        except UnicodeDecodeError as exc:
            _LOG.warning("presets are not UTF-8 in %s: %s", self._file, exc)
            self._discard_invalid_on_save = True
            return PresetDocument(issues=(_CORRUPT,))
        except OSError as exc:
            _LOG.warning("cannot read %s: %s", self._file, exc)
            return PresetDocument(issues=(_READ_FAILED,))

        try:
            raw = json.loads(text)
        except ValueError as exc:
            _LOG.warning("invalid presets JSON in %s: %s", self._file, exc)
            self._discard_invalid_on_save = True
            return PresetDocument(issues=(_CORRUPT,))

        return self._decode(raw)

    def save(self, presets: Sequence[Preset]) -> bool:
        if self._read_only:
            _LOG.warning("presets are read-only: %s", self._file)
            return False

        payload = _encode(presets)
        if payload == self._last_payload:
            return True

        try:
            self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            _LOG.warning("cannot create %s: %s", self._directory, exc)
            return False

        try:
            self._preserve_invalid()
            write_atomically(self._directory, self._file, payload)
        except OSError as exc:
            _LOG.warning("cannot write %s: %s", self._file, exc)
            return False

        self._last_payload = payload
        self._discard_invalid_on_save = False
        return True

    def _decode(self, raw: object) -> PresetDocument:
        if not isinstance(raw, Mapping):
            _LOG.warning("presets document is not an object: %s", self._file)
            self._discard_invalid_on_save = True
            return PresetDocument(issues=(_CORRUPT,))

        version = raw.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            _LOG.warning("presets without schema_version: %s", self._file)
            self._discard_invalid_on_save = True
            return PresetDocument(issues=(_CORRUPT,))

        if version > SCHEMA_VERSION:
            # Never overwrite a file written by a newer build.
            _LOG.warning("presets schema %s is newer than %s", version, SCHEMA_VERSION)
            self._read_only = True
            return PresetDocument(issues=(_NEWER,))

        entries = raw.get("presets", [])
        if not isinstance(entries, list):
            self._discard_invalid_on_save = True
            return PresetDocument(issues=(_CORRUPT,))

        presets, skipped = _decode_entries(entries)
        if skipped:
            _LOG.warning("skipped %s invalid preset(s) in %s", skipped, self._file)
            self._discard_invalid_on_save = True
            return PresetDocument(presets=presets, issues=(_SKIPPED,))

        return PresetDocument(presets=presets)

    def _preserve_invalid(self) -> None:
        if not self._discard_invalid_on_save:
            return

        backup = preserve_invalid(self._file)
        if backup is not None:
            _LOG.warning("preserved invalid presets as %s", backup)


def create_preset_store(paths: SettingsPaths | None) -> PresetStore:
    """The file store, or memory when no config directory exists."""
    if paths is None:
        return MemoryPresetStore()

    return JsonPresetStore(paths)


def _decode_entries(entries: list[object]) -> tuple[tuple[Preset, ...], int]:
    presets: list[Preset] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    skipped = 0

    for entry in entries:
        preset = _decode_entry(entry)
        if preset is None or preset.id in seen_ids:
            skipped += 1
            continue

        key = preset.name.casefold()
        if key in seen_names:
            skipped += 1
            continue

        seen_ids.add(preset.id)
        seen_names.add(key)
        presets.append(preset)

    return tuple(presets), skipped


def _decode_entry(entry: object) -> Preset | None:
    if not isinstance(entry, Mapping):
        return None

    preset_id = entry.get("id")
    raw_name = entry.get("name")
    settings = entry.get("settings")
    if not isinstance(preset_id, str) or not preset_id.startswith("custom-"):
        return None
    if len(preset_id) > 64 or not isinstance(raw_name, str):
        return None
    if not isinstance(settings, Mapping):
        return None

    try:
        name = clean_name(raw_name)
    except PresetError:
        return None

    return Preset(preset_id, name, ViewSettings.from_mapping(settings))


def _encode(presets: Sequence[Preset]) -> str:
    document = {
        "schema_version": SCHEMA_VERSION,
        "presets": [
            {
                "id": preset.id,
                "name": preset.name[:MAX_NAME_LENGTH],
                "settings": preset.settings.to_mapping(),
            }
            for preset in presets
            if not preset.builtin
        ],
    }

    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
