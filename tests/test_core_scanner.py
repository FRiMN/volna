import os
import threading

import pytest

from volna.core.scanner import (
    DirScanner,
    Phase,
    ScanError,
    iter_batches,
    iter_dirents,
    iter_stats,
)
from volna.core.statpool import StatPool


def test_iter_batches_reads_dirents(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    os.symlink(tmp_path / "a.txt", tmp_path / "link")

    batches = list(iter_batches(str(tmp_path), generation=7, need_stats=False))

    assert batches
    assert all(batch.generation == 7 for batch in batches)
    assert all(batch.phase is Phase.DIRENT for batch in batches)
    kinds = {entry.name: entry.kind for batch in batches for entry in batch.entries}
    assert kinds["sub"].value == "dir"
    assert kinds["a.txt"].value == "file"
    assert kinds["link"].value == "symlink"


def test_stats_phase_fills_size_and_mtime(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("hello")

    batches = list(iter_batches(str(tmp_path), generation=1))

    assert any(batch.phase is Phase.STATS for batch in batches)
    entries = {entry.name: entry for batch in batches for entry in batch.entries}
    assert entries["a.txt"].size == 5
    assert entries["a.txt"].mtime is not None


def test_missing_directory_raises(tmp_path) -> None:
    with pytest.raises(ScanError):
        list(iter_batches(str(tmp_path / "missing"), generation=1))


def test_cancel_stops_before_first_batch(tmp_path) -> None:
    for index in range(20):
        (tmp_path / f"f{index}.txt").write_text("")
    cancel = threading.Event()
    cancel.set()

    batches = list(
        iter_batches(str(tmp_path), generation=1, cancel=cancel, batch_size=4)
    )

    assert batches == []


def test_scanner_scan_emits_batches(tmp_path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b.txt").write_text("hi")
    seen = []

    DirScanner().scan(str(tmp_path), generation=3, emit=seen.append)

    assert seen
    assert all(batch.generation == 3 for batch in seen)
    names = {entry.name for batch in seen for entry in batch.entries}
    assert names == {"a", "b.txt"}


def test_scanner_start_runs_on_thread(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("")
    seen = []
    finished = threading.Event()
    scanner = DirScanner()

    scanner.start(
        str(tmp_path),
        generation=5,
        emit=seen.append,
        on_done=finished.set,
    )

    assert finished.wait(5.0), "scan did not finish"
    assert seen
    assert all(batch.generation == 5 for batch in seen)


def test_iter_dirents_yields_only_dirents(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()

    batches = list(iter_dirents(str(tmp_path), generation=4))

    assert batches
    assert all(batch.generation == 4 for batch in batches)
    assert all(batch.phase is Phase.DIRENT for batch in batches)
    entries = [entry for batch in batches for entry in batch.entries]
    assert {entry.name for entry in entries} == {"a.txt", "sub"}
    assert all(entry.size is None and entry.mtime is None for entry in entries)


def test_iter_dirents_chunks_by_batch_size(tmp_path) -> None:
    for index in range(5):
        (tmp_path / f"f{index}.txt").write_text("")

    batches = list(iter_dirents(str(tmp_path), generation=1, batch_size=2))

    assert [len(batch.entries) for batch in batches] == [2, 2, 1]


def test_iter_dirents_stops_on_cancel(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("")
    cancel = threading.Event()
    cancel.set()

    assert list(iter_dirents(str(tmp_path), generation=1, cancel=cancel)) == []


def test_iter_dirents_missing_directory_raises(tmp_path) -> None:
    with pytest.raises(ScanError):
        list(iter_dirents(str(tmp_path / "missing"), generation=1))


def test_iter_stats_fills_size_and_mtime(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("hi")
    entries = [
        entry
        for batch in iter_dirents(str(tmp_path), generation=2)
        for entry in batch.entries
    ]

    batches = list(iter_stats(entries, generation=2))

    assert batches
    assert all(batch.phase is Phase.STATS for batch in batches)
    assert all(batch.generation == 2 for batch in batches)
    assert {entry.name: entry.size for entry in entries} == {"a.txt": 5, "b.txt": 2}
    assert all(entry.mtime is not None for entry in entries)


def test_iter_stats_chunks_by_chunk_size(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    entries = [
        entry
        for batch in iter_dirents(str(tmp_path), generation=1)
        for entry in batch.entries
    ]

    batches = list(iter_stats(entries, generation=1, chunk_size=1))

    assert [len(batch.entries) for batch in batches] == [1, 1]


def test_iter_stats_stops_on_cancel(tmp_path) -> None:
    for index in range(3):
        (tmp_path / f"f{index}.txt").write_text("")
    entries = [
        entry
        for batch in iter_dirents(str(tmp_path), generation=1)
        for entry in batch.entries
    ]
    cancel = threading.Event()
    batches = iter_stats(entries, generation=1, chunk_size=1, cancel=cancel)

    assert next(batches).phase is Phase.STATS
    cancel.set()

    assert list(batches) == []


def test_iter_stats_leaves_caller_pool_open(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("x")
    entries = [
        entry
        for batch in iter_dirents(str(tmp_path), generation=1)
        for entry in batch.entries
    ]
    pool = StatPool()
    try:
        list(iter_stats(entries, generation=1, stat_pool=pool))

        assert pool.stat_batch([entries[0].path])[0].ok
    finally:
        pool.close()


def test_iter_batches_composes_phases_in_order(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()

    batches = list(iter_batches(str(tmp_path), generation=3))

    phases = [batch.phase for batch in batches]
    first_stats = phases.index(Phase.STATS)
    assert all(phase is Phase.DIRENT for phase in phases[:first_stats])
    assert all(phase is Phase.STATS for phase in phases[first_stats:])

    dirent_entries = {
        id(entry)
        for batch in batches
        if batch.phase is Phase.DIRENT
        for entry in batch.entries
    }
    stats_entries = {
        id(entry)
        for batch in batches
        if batch.phase is Phase.STATS
        for entry in batch.entries
    }
    assert stats_entries == dirent_entries
