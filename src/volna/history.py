"""Per-tab back/forward history of visited directories.

Pure list-and-cursor policy over ``pathlib.Path``: no GTK and no filesystem
reads, so the navigation rules are unit-tested without a display. Each tab owns
one instance and only mirrors ``current`` into its path widget and listing.
"""

from __future__ import annotations

from pathlib import Path


class NavigationHistory:
    """Visited directories of one tab with a cursor for back/forward.

    The history always holds at least the start path, so ``current`` is total.
    Visiting drops the forward branch, like a browser: going back and then to a
    new directory forgets where the back button could have led.
    """

    def __init__(self, start: Path) -> None:
        self._entries: list[Path] = [start]
        self._index = 0

    @property
    def current(self) -> Path:
        """Directory the tab shows now."""
        return self._entries[self._index]

    @property
    def can_back(self) -> bool:
        """Whether an earlier directory is remembered."""
        return self._index > 0

    @property
    def can_forward(self) -> bool:
        """Whether ``back`` left a directory that can be returned to."""
        return self._index < len(self._entries) - 1

    @property
    def can_up(self) -> bool:
        """Whether the current directory has a parent (false only at a root)."""
        return self.current.parent != self.current

    def visit(self, path: Path) -> Path:
        """Make ``path`` the current directory and return it.

        Visiting the current directory changes nothing: the forward branch is
        kept, so re-opening the shown directory costs no way forward.
        """
        if path == self.current:
            return self.current

        del self._entries[self._index + 1 :]
        self._entries.append(path)
        self._index = len(self._entries) - 1

        return self.current

    def back(self) -> Path | None:
        """Step to the previously visited directory; ``None`` if there is none."""
        if not self.can_back:
            return None

        self._index -= 1

        return self.current

    def forward(self) -> Path | None:
        """Step to the directory ``back`` left; ``None`` if there is none."""
        if not self.can_forward:
            return None

        self._index += 1

        return self.current

    def up(self) -> Path | None:
        """Visit the parent directory; ``None`` at a filesystem root.

        ``up`` is an ordinary visit, so a following ``back`` returns to the
        child directory.
        """
        if not self.can_up:
            return None

        return self.visit(self.current.parent)
