"""Last-view persistence: one versioned JSON document in the XDG config dir.

The file holds only the display snapshot of the tab that was active when the
app closed. It is user data, so every failure degrades to defaults instead of
raising: the app must always start (AGENTS §14, §32).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .files import preserve_invalid, write_atomically
from .settings import ViewSettings

SCHEMA_VERSION = 1

_LOG = logging.getLogger("volna.display.store")

_READ_FAILED = "Не удалось прочитать настройки, используются значения по умолчанию"
_CORRUPT = "Файл настроек повреждён, используются значения по умолчанию"
_NEWER = "Настройки созданы более новой версией, используются значения по умолчанию"


@dataclass(frozen=True, slots=True)
class SettingsPaths:
    directory: Path
    file: Path

    @classmethod
    def default(cls, environ: Mapping[str, str] | None = None) -> SettingsPaths | None:
        """Resolve XDG paths; ``None`` when neither config dir nor home exists."""
        env = os.environ if environ is None else environ
        base = env.get("XDG_CONFIG_HOME")
        if base:
            directory = Path(base) / "volna"
        else:
            home = env.get("HOME")
            if not home:
                return None
            directory = Path(home) / ".config" / "volna"

        return cls(directory=directory, file=directory / "settings.json")


@dataclass(frozen=True, slots=True)
class SettingsDocument:
    view: ViewSettings | None = None
    issues: tuple[str, ...] = ()


class ViewSettingsStore(Protocol):
    def load(self) -> SettingsDocument: ...

    def save(self, view: ViewSettings) -> bool:
        """Persist ``view``; ``False`` means the caller stays in memory."""
        ...


class MemoryViewSettingsStore:
    """Fallback store for tests and environments without a config directory."""

    def __init__(
        self, view: ViewSettings | None = None, *, issues: tuple[str, ...] = ()
    ) -> None:
        self._view = view
        self._issues = issues

    def load(self) -> SettingsDocument:
        return SettingsDocument(self._view, self._issues)

    def save(self, view: ViewSettings) -> bool:
        self._view = view
        return True


class JsonViewSettingsStore:
    """Atomic JSON store; read/write failures become issues, never exceptions."""

    def __init__(self, paths: SettingsPaths) -> None:
        self._paths = paths
        self._last_payload: str | None = None
        self._discard_invalid_on_save = False
        self._read_only = False

    def load(self) -> SettingsDocument:
        try:
            text = self._paths.file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return SettingsDocument()
        except UnicodeDecodeError as exc:
            _LOG.warning("settings are not UTF-8 in %s: %s", self._paths.file, exc)
            self._discard_invalid_on_save = True
            return SettingsDocument(issues=(_CORRUPT,))
        except OSError as exc:
            _LOG.warning("cannot read %s: %s", self._paths.file, exc)
            return SettingsDocument(issues=(_READ_FAILED,))

        try:
            raw = json.loads(text)
        except (ValueError, UnicodeDecodeError) as exc:
            _LOG.warning("invalid settings JSON in %s: %s", self._paths.file, exc)
            self._discard_invalid_on_save = True
            return SettingsDocument(issues=(_CORRUPT,))

        return self._decode(raw)

    def save(self, view: ViewSettings) -> bool:
        if self._read_only:
            _LOG.warning("settings are read-only: %s", self._paths.file)
            return False

        payload = _encode(view)
        if payload == self._last_payload:
            return True

        try:
            self._paths.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            _LOG.warning("cannot create %s: %s", self._paths.directory, exc)
            return False

        try:
            self._preserve_invalid()
            self._write_atomically(payload)
        except OSError as exc:
            _LOG.warning("cannot write %s: %s", self._paths.file, exc)
            return False

        self._last_payload = payload
        self._discard_invalid_on_save = False
        return True

    def _decode(self, raw: object) -> SettingsDocument:
        if not isinstance(raw, Mapping):
            _LOG.warning("settings document is not an object: %s", self._paths.file)
            self._discard_invalid_on_save = True
            return SettingsDocument(issues=(_CORRUPT,))

        version = raw.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            _LOG.warning("settings without schema_version: %s", self._paths.file)
            self._discard_invalid_on_save = True
            return SettingsDocument(issues=(_CORRUPT,))

        if version > SCHEMA_VERSION:
            # Never overwrite a file written by a newer build.
            _LOG.warning("settings schema %s is newer than %s", version, SCHEMA_VERSION)
            self._read_only = True
            return SettingsDocument(issues=(_NEWER,))

        view_raw = raw.get("view")
        if not isinstance(view_raw, Mapping):
            return SettingsDocument()

        return SettingsDocument(view=ViewSettings.from_mapping(view_raw))

    def _write_atomically(self, payload: str) -> None:
        write_atomically(self._paths.directory, self._paths.file, payload)

    def _preserve_invalid(self) -> None:
        """Keep a corrupt file instead of silently overwriting user data."""
        if not self._discard_invalid_on_save:
            return

        backup = preserve_invalid(self._paths.file)
        if backup is not None:
            _LOG.warning("preserved invalid settings as %s", backup)


def create_store(paths: SettingsPaths | None) -> ViewSettingsStore:
    if paths is None:
        return MemoryViewSettingsStore(
            issues=("Каталог настроек недоступен, изменения не сохраняются",)
        )

    return JsonViewSettingsStore(paths)


def _encode(view: ViewSettings) -> str:
    document = {"schema_version": SCHEMA_VERSION, "view": view.to_mapping()}

    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
