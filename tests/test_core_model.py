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


def test_ingest_then_finish_builds_sorted_listing() -> None:
    model = DirModel(sort_key=SortKey.MTIME, reverse=True)
    generation = model.begin_scan("/d")

    sub = make("sub", kind=Kind.DIR)
    file = make("a.txt")
    model.ingest(Batch(generation, Phase.DIRENT, [sub, file]))
    assert model.counters() == Counters(folders=1, files=1, total_size=0)

    file.size = 5
    file.mtime = 999_999.0
    model.ingest(Batch(generation, Phase.STATS, [file]))
    assert model.counters() == Counters(folders=1, files=1, total_size=5)

    model.finish_scan(generation)

    assert model.state is ScanState.READY
    assert [entry.name for entry in model.entries()] == ["sub", "a.txt"]


def test_stale_generation_is_ignored() -> None:
    model = DirModel()
    first = model.begin_scan("/a")
    second = model.begin_scan("/b")

    assert second == first + 1
    model.ingest(Batch(first, Phase.DIRENT, [make("old.txt")]))

    assert model.entries() == []


def test_events_fire_in_order() -> None:
    model = DirModel()
    seen = []
    model.subscribe(
        Event.SCAN_STATE, lambda state, _gen: seen.append(("state", state.value))
    )
    model.subscribe(Event.ORDER_CHANGED, lambda _gen: seen.append(("order", None)))
    model.subscribe(
        Event.COUNTERS_CHANGED,
        lambda counters, _gen: seen.append(("counters", counters.files)),
    )

    generation = model.begin_scan("/d")
    model.ingest(Batch(generation, Phase.DIRENT, [make("a.txt")]))
    model.finish_scan(generation)

    values = [item[0] for item in seen]
    assert values[0] == "state"
    assert "order" in values
    assert "counters" in values
    assert values[-1] == "state"


def test_groups_bucket_entries() -> None:
    now = 1_700_000_000.0
    today = day_start(now)
    model = DirModel(now=lambda: now)
    generation = model.begin_scan("/d")
    model.ingest(
        Batch(
            generation,
            Phase.DIRENT,
            [
                make("today", mtime=today + 10),
                make("yesterday", mtime=today - 10),
                make("old", mtime=today - 8 * 86_400),
                make("unknown"),
            ],
        )
    )

    groups = {
        group.bucket: [entry.name for entry in group.entries]
        for group in model.groups()
    }

    assert groups[GroupBucket.TODAY] == ["today"]
    assert groups[GroupBucket.YESTERDAY] == ["yesterday"]
    assert groups[GroupBucket.OLDER] == ["old"]
    assert groups[GroupBucket.UNKNOWN] == ["unknown"]


def test_scan_reads_real_directory(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "sub").mkdir()
    model = DirModel(sort_key=SortKey.NAME, reverse=False)

    model.scan(str(tmp_path))

    assert model.state is ScanState.READY
    assert [entry.name for entry in model.entries()] == ["sub", "a.txt", "b.txt"]
    assert model.counters() == Counters(folders=1, files=2, total_size=5)


def test_scan_of_missing_path_sets_error(tmp_path) -> None:
    model = DirModel()

    model.scan(str(tmp_path / "missing"))

    assert model.state is ScanState.ERROR
    assert model.entries() == []


def test_groups_split_this_week_per_calendar_day() -> None:
    now = 1_700_000_000.0
    today = day_start(now)
    model = DirModel(now=lambda: now)
    generation = model.begin_scan("/d")
    model.ingest(
        Batch(
            generation,
            Phase.DIRENT,
            [
                make("today", mtime=today + 10),
                make("yesterday", mtime=today - 10),
                make("two-days", mtime=day_start(today - 2 * 86_400)),
                make("three-days", mtime=day_start(today - 3 * 86_400)),
                make("old", mtime=today - 8 * 86_400),
                make("unknown"),
            ],
        )
    )

    groups = model.groups()

    assert [group.bucket for group in groups] == [
        GroupBucket.TODAY,
        GroupBucket.YESTERDAY,
        GroupBucket.THIS_WEEK,
        GroupBucket.THIS_WEEK,
        GroupBucket.OLDER,
        GroupBucket.UNKNOWN,
    ]
    assert [group.day for group in groups[:2]] == [None, None]
    assert groups[2].day == day_start(today - 2 * 86_400)
    assert groups[3].day == day_start(today - 3 * 86_400)
    assert groups[4].day is None
    assert [entry.name for entry in groups[2].entries] == ["two-days"]
    assert [entry.name for entry in groups[3].entries] == ["three-days"]


def test_groups_keep_the_sort_order_inside_every_group() -> None:
    now = 1_700_000_000.0
    today = day_start(now)
    model = DirModel(sort_key=SortKey.NAME, reverse=False, now=lambda: now)
    generation = model.begin_scan("/d")
    model.ingest(
        Batch(
            generation,
            Phase.DIRENT,
            [
                make("b", mtime=today - 2 * 86_400),
                make("a", mtime=today - 2 * 86_400),
                make("c", mtime=today - 3 * 86_400),
            ],
        )
    )

    groups = model.groups()

    assert [[entry.name for entry in group.entries] for group in groups] == [
        ["a", "b"],
        ["c"],
    ]
    assert [group.day for group in groups] == [
        day_start(today - 2 * 86_400),
        day_start(today - 3 * 86_400),
    ]
