"""Entry — one directory record as read from the OS (no GTK imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(Enum):
    """Entry kind, taken from ``dirent.d_type`` without an extra stat."""

    DIR = "dir"
    FILE = "file"
    SYMLINK = "symlink"
    OTHER = "other"


@dataclass(slots=True)
class Entry:
    """A directory entry with precomputed sort keys.

    ``size`` and ``mtime`` stay ``None`` until the stat phase fills them in.
    """

    name: str
    path: str
    kind: Kind
    size: int | None = None
    mtime: float | None = None
    name_key: str = field(init=False)

    def __post_init__(self) -> None:
        self.name_key = self.name.casefold()

    @property
    def is_dir(self) -> bool:
        return self.kind is Kind.DIR

    @property
    def is_hidden(self) -> bool:
        """Whether the name follows the hidden-entry (dotfile) convention."""
        return self.name.startswith(".")
