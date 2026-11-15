"""Hidden-entry visibility and runtime ordering on DirModel.

Pure tests: no display and no GTK. The scan-based test at the end drives the
public ``DirModel`` API over a real directory so the behavior can be read as a
system contract rather than an implementation detail.
"""

import time

import pytest

from volna.core.entry import Entry, Kind
from volna.core.model import Counters, DirModel, Event, ScanState
from volna.core.order import GroupBucket, SortKey, day_start
from volna.core.scanner import Batch, Phase


def make(
    name: str,
    *,
    kind: Kind = Kind.FILE,
    size: int | None = None,
    mtime: float | None = None,
) -> Entry:
    return Entry(name=name, path=f"/d/{name}", kind=kind, size=size, mtime=mtime)


def start(model: DirModel) -> int:
    return model.begin_scan("/d")


def ingest(model: DirModel, entries: list[Entry], phase: Phase = Phase.DIRENT) -> None:
    model.ingest(Batch(model.generation, phase, entries))


class Recorder:
    """Collect the events a subscriber would receive."""

    def __init__(self, model: DirModel) -> None:
        self.order: list[int] = []
        self.counters: list[tuple[Counters, int]] = []
        model.subscribe(Event.ORDER_CHANGED, self._on_order)
        model.subscribe(Event.COUNTERS_CHANGED, self._on_counters)

    def _on_order(self, generation: int) -> None:
        self.order.append(generation)

    def _on_counters(self, counters: Counters, generation: int) -> None:
        self.counters.append((counters, generation))


# -- Entry.is_hidden ----------------------------------------------------


def test_entry_is_hidden_follows_the_dotfile_convention() -> None:
    assert make(".gitignore").is_hidden
    assert make(".config", kind=Kind.DIR).is_hidden
    assert make("...").is_hidden
    assert not make("readme.md").is_hidden
    assert not make("hidden", kind=Kind.DIR).is_hidden


def test_hidden_entry_keeps_its_casefolded_sort_key() -> None:
    assert make(".README").name_key == ".readme"


# -- default behavior ---------------------------------------------------


def test_default_model_keeps_showing_hidden_entries() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False)
    generation = start(model)
    visible = make("a.txt", size=10)
    hidden = make(".env", size=7)
    ingest(model, [visible, hidden])
    ingest(model, [visible, hidden], Phase.STATS)
    model.finish_scan(generation)

    assert [entry.name for entry in model.entries()] == [".env", "a.txt"]
    assert model.counters() == Counters(folders=0, files=2, total_size=17)


# -- filtering ----------------------------------------------------------


def test_entries_exclude_hidden_entries_when_disabled() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)
    ingest(model, [make("beta.txt"), make(".gamma"), make("alpha", kind=Kind.DIR)])
    model.finish_scan(generation)

    assert [entry.name for entry in model.entries()] == ["alpha", "beta.txt"]


def test_counters_ignore_hidden_directories_and_files() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)
    hidden_dir = make(".cache", kind=Kind.DIR)
    visible_dir = make("docs", kind=Kind.DIR)
    hidden_file = make(".env", size=5)
    visible_file = make("a.txt", size=12)
    ingest(model, [hidden_dir, visible_dir, hidden_file, visible_file])
    ingest(model, [hidden_file, visible_file], Phase.STATS)
    model.finish_scan(generation)

    assert model.counters() == Counters(folders=1, files=1, total_size=12)


def test_groups_skip_hidden_entries() -> None:
    now = 1_700_000_000.0
    today = day_start(now)
    model = DirModel(show_hidden=False, now=lambda: now)
    generation = start(model)
    ingest(
        model,
        [
            make("visible.txt", mtime=today + 10),
            make(".today", mtime=today + 5),
            make(".yesterday", mtime=today - 10),
        ],
    )
    model.finish_scan(generation)

    groups = model.groups()

    assert [group.bucket for group in groups] == [GroupBucket.TODAY]
    assert [entry.name for entry in groups[0].entries] == ["visible.txt"]


# -- set_show_hidden ----------------------------------------------------


def test_toggle_show_hidden_recounts_without_rescanning() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)
    visible = make("a.txt", size=12)
    hidden = make(".env", size=5)
    ingest(model, [visible, hidden])
    ingest(model, [visible, hidden], Phase.STATS)
    model.finish_scan(generation)

    assert model.counters() == Counters(folders=0, files=1, total_size=12)

    assert model.set_show_hidden(True) is True

    assert model.generation == generation
    assert model.state is ScanState.READY
    assert model.path == "/d"
    assert model.counters() == Counters(folders=0, files=2, total_size=17)
    assert {entry.name for entry in model.entries()} == {".env", "a.txt"}


def test_set_show_hidden_guard_returns_false_without_events() -> None:
    model = DirModel(show_hidden=False)
    start(model)
    recorder = Recorder(model)

    assert model.set_show_hidden(False) is False

    assert recorder.order == []
    assert recorder.counters == []


def test_set_show_hidden_announces_counters_and_order() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)
    entries = [make("a.txt", size=12), make(".env", size=5)]
    ingest(model, entries)
    ingest(model, entries, Phase.STATS)
    model.finish_scan(generation)
    recorder = Recorder(model)

    assert model.set_show_hidden(True) is True

    assert recorder.counters == [
        (Counters(folders=0, files=2, total_size=17), generation)
    ]
    assert recorder.order == [generation]


def test_set_show_hidden_before_a_scan_is_safe() -> None:
    model = DirModel()

    assert model.set_show_hidden(False) is True
    assert model.entries() == []
    assert model.counters() == Counters()

    generation = start(model)
    entries = [make("a.txt", size=1), make(".env", size=2)]
    ingest(model, entries)
    ingest(model, entries, Phase.STATS)
    model.finish_scan(generation)

    assert model.counters() == Counters(folders=0, files=1, total_size=1)


def test_toggling_visibility_while_scanning_keeps_counters_consistent() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)

    visible_one = make("a", size=10)
    hidden_one = make(".h1", size=1)
    ingest(model, [visible_one, hidden_one])
    ingest(model, [visible_one, hidden_one], Phase.STATS)
    assert model.counters() == Counters(folders=0, files=1, total_size=10)

    model.set_show_hidden(True)
    assert model.counters() == Counters(folders=0, files=2, total_size=11)

    visible_two = make("b", size=20)
    hidden_two = make(".h2", size=2)
    ingest(model, [visible_two, hidden_two])
    ingest(model, [visible_two, hidden_two], Phase.STATS)
    assert model.counters() == Counters(folders=0, files=4, total_size=33)

    model.set_show_hidden(False)
    assert model.counters() == Counters(folders=0, files=2, total_size=30)
    assert model.generation == generation


# -- set_folders_first --------------------------------------------------


def test_set_folders_first_guard_returns_false_without_events() -> None:
    model = DirModel(folders_first=True)
    start(model)
    recorder = Recorder(model)

    assert model.set_folders_first(True) is False

    assert recorder.order == []
    assert recorder.counters == []


def test_set_folders_first_mixes_loaded_entries_without_scanning() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, folders_first=True)
    generation = start(model)
    ingest(
        model,
        [make("z.txt"), make("A", kind=Kind.DIR), make("b.txt")],
    )
    model.finish_scan(generation)
    recorder = Recorder(model)

    assert [entry.name for entry in model.entries()] == ["A", "b.txt", "z.txt"]
    assert model.set_folders_first(False) is True

    assert [entry.name for entry in model.entries()] == ["A", "b.txt", "z.txt"]
    assert model.generation == generation
    assert model.state is ScanState.READY
    assert recorder.order == [generation]
    assert recorder.counters == []


def test_set_folders_first_changes_the_visible_order() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False)
    generation = start(model)
    ingest(model, [make("zzz", kind=Kind.DIR), make("aaa.txt")])
    model.finish_scan(generation)

    model.set_folders_first(False)

    assert [entry.name for entry in model.entries()] == ["aaa.txt", "zzz"]


# -- set_order ----------------------------------------------------------


def test_set_order_guard_returns_false_without_events() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False)
    start(model)
    recorder = Recorder(model)

    assert model.set_order(sort_key=SortKey.NAME, reverse=False) is False

    assert recorder.order == []
    assert recorder.counters == []


def test_set_order_resorts_loaded_entries_without_scanning() -> None:
    model = DirModel(sort_key=SortKey.MTIME, reverse=True)
    generation = start(model)
    ingest(
        model,
        [make("a", mtime=100.0), make("c", mtime=300.0), make("b", mtime=200.0)],
    )
    model.finish_scan(generation)
    recorder = Recorder(model)

    assert model.set_order(sort_key=SortKey.NAME, reverse=False) is True

    assert [entry.name for entry in model.entries()] == ["a", "b", "c"]
    assert model.generation == generation
    assert model.state is ScanState.READY
    assert recorder.order == [generation]
    assert recorder.counters == []


@pytest.mark.parametrize(
    ("reverse", "expected"),
    [
        (False, ["A", "b.txt", "z.txt"]),
        (True, ["A", "z.txt", "b.txt"]),
    ],
)
def test_set_order_keeps_folders_first(reverse: bool, expected: list[str]) -> None:
    model = DirModel(sort_key=SortKey.MTIME, reverse=True)
    generation = start(model)
    ingest(
        model,
        [make("z.txt", size=10), make("A", kind=Kind.DIR), make("b.txt", size=20)],
    )
    model.finish_scan(generation)

    model.set_order(sort_key=SortKey.NAME, reverse=reverse)

    assert [entry.name for entry in model.entries()] == expected


@pytest.mark.parametrize(
    ("sort_key", "reverse", "expected"),
    [
        (SortKey.SIZE, False, ["docs", "small", "big", "unknown"]),
        (SortKey.SIZE, True, ["docs", "big", "small", "unknown"]),
        (SortKey.MTIME, False, ["docs", "small", "big", "unknown"]),
        (SortKey.MTIME, True, ["docs", "big", "small", "unknown"]),
    ],
)
def test_set_order_applies_key_and_direction(
    sort_key: SortKey, reverse: bool, expected: list[str]
) -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False)
    generation = start(model)
    ingest(
        model,
        [
            make("big", size=20, mtime=300.0),
            make("small", size=10, mtime=100.0),
            make("unknown"),
            make("docs", kind=Kind.DIR),
        ],
    )
    model.finish_scan(generation)

    model.set_order(sort_key=sort_key, reverse=reverse)

    assert [entry.name for entry in model.entries()] == expected


def test_set_order_keeps_hidden_entries_for_a_later_toggle() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = start(model)
    ingest(model, [make("b"), make(".c"), make("a")])
    model.finish_scan(generation)

    model.set_order(sort_key=SortKey.NAME, reverse=True)
    assert [entry.name for entry in model.entries()] == ["b", "a"]

    model.set_show_hidden(True)
    assert [entry.name for entry in model.entries()] == ["b", "a", ".c"]


def test_visibility_and_order_changes_do_not_touch_scan_metadata() -> None:
    model = DirModel(sort_key=SortKey.MTIME, reverse=True)
    generation = start(model)
    ingest(model, [make("a.txt", size=1), make(".env", size=2)])
    model.finish_scan(generation)

    model.set_order(sort_key=SortKey.SIZE, reverse=False)
    model.set_show_hidden(False)
    model.set_show_hidden(True)

    assert model.generation == generation
    assert model.state is ScanState.READY
    assert model.path == "/d"


# -- system check over a real directory ---------------------------------


def test_system_scan_follows_the_visibility_policy(tmp_path) -> None:
    (tmp_path / ".gitignore").write_text("x", encoding="utf-8")
    (tmp_path / ".cache-dir").mkdir()
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=False)
    generation = model.scan(str(tmp_path))

    assert model.state is ScanState.READY
    assert model.generation == generation
    assert [entry.name for entry in model.entries()] == ["docs", "a.txt"]
    assert model.counters() == Counters(folders=1, files=1, total_size=5)

    assert model.set_show_hidden(True) is True

    assert model.state is ScanState.READY
    assert model.generation == generation
    assert [entry.name for entry in model.entries()] == [
        ".cache-dir",
        "docs",
        ".gitignore",
        "a.txt",
    ]
    assert model.counters() == Counters(folders=2, files=2, total_size=6)


@pytest.mark.slow
def test_toggle_show_hidden_is_a_single_linear_pass() -> None:
    model = DirModel(sort_key=SortKey.NAME, reverse=False, show_hidden=True)
    generation = start(model)
    entries = [make(f"f{index:06d}") for index in range(20_000)]
    entries += [make(f".h{index:06d}", size=1) for index in range(5_000)]
    ingest(model, entries)
    model.finish_scan(generation)

    started = time.perf_counter()
    assert model.set_show_hidden(False) is True
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"visibility toggle took {elapsed:.3f}s"
    assert model.counters() == Counters(folders=0, files=20_000, total_size=0)
