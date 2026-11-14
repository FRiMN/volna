import os
import threading

import pytest

from volna.core.scanner import DirScanner, Phase, ScanError, iter_batches


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
