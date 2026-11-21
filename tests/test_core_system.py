"""System test: build a real tree and scan it through the public core API."""

import time

from volna.core import Counters, DirModel, ScanState, SortKey


def test_system_listing_matches_filesystem(tmp_path) -> None:
    (tmp_path / "dir_a").mkdir()
    (tmp_path / "dir_b").mkdir()
    (tmp_path / "file_1.txt").write_text("12345")
    (tmp_path / "file_2.txt").write_text("123")
    (tmp_path / "file_3.txt").write_text("")

    model = DirModel(sort_key=SortKey.NAME, reverse=False)
    model.scan(str(tmp_path))

    assert [entry.name for entry in model.entries()] == [
        "dir_a",
        "dir_b",
        "file_1.txt",
        "file_2.txt",
        "file_3.txt",
    ]
    assert model.counters() == Counters(folders=2, files=3, total_size=8)
    assert model.state is ScanState.READY


def test_system_large_directory_scan_is_complete(tmp_path) -> None:
    count = 1500
    for index in range(count):
        (tmp_path / f"file_{index:05d}.txt").write_text("x")

    model = DirModel(sort_key=SortKey.NAME)
    started = time.monotonic()
    model.scan(str(tmp_path))
    elapsed = time.monotonic() - started

    assert len(model.entries()) == count
    assert model.counters().files == count
    assert elapsed < 10.0
