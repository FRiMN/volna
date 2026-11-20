"""Atomic file writes shared by the display stores (pure, no GTK).

A store never leaves a half-written document: the payload goes to a temporary
file in the same directory, is fsynced and then renamed over the target.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def write_atomically(directory: Path, target: Path, payload: str) -> None:
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=".tmp", dir=directory
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, target)
    finally:
        tmp_path.unlink(missing_ok=True)

    fsync_directory(directory)


def preserve_invalid(target: Path) -> Path | None:
    """Move an unreadable document aside instead of overwriting user data.

    Returns the backup path, or ``None`` when there is nothing to keep or the
    move failed (a disk-level failure: the caller then keeps the original).
    """
    if not target.exists():
        return None

    backup = target.with_name(f"{target.name}.invalid-{int(time.time())}")
    try:
        os.replace(target, backup)
    except OSError:  # pragma: no cover - defensive, disk-level failure
        return None

    return backup


def fsync_directory(directory: Path) -> None:
    """Best effort: not every platform/filesystem allows fsync on a directory."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:  # pragma: no cover - platform dependent
        return

    try:
        os.fsync(descriptor)
    except OSError:  # pragma: no cover - platform dependent
        pass
    finally:
        os.close(descriptor)
