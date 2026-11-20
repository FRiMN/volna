from volna.core.entry import Entry, Kind
from volna.core.order import SortKey, sort_entries


def make(
    name: str,
    *,
    kind: Kind = Kind.FILE,
    size: int | None = None,
    mtime: float | None = None,
) -> Entry:
    return Entry(name=name, path=f"/d/{name}", kind=kind, size=size, mtime=mtime)


def test_name_key_is_casefolded() -> None:
    assert make("README.md").name_key == "readme.md"


def test_sort_by_name_folders_first_and_case_insensitive() -> None:
    entries = [make("b.txt"), make("A", kind=Kind.DIR), make("a.txt")]

    sort_entries(entries, key=SortKey.NAME)

    assert [entry.name for entry in entries] == ["A", "a.txt", "b.txt"]


def test_sort_by_name_desc_keeps_folders_first() -> None:
    entries = [make("a"), make("B", kind=Kind.DIR), make("c")]

    sort_entries(entries, key=SortKey.NAME, reverse=True)

    assert [entry.name for entry in entries] == ["B", "c", "a"]


def test_sort_by_size_puts_missing_and_zero_last() -> None:
    entries = [make("a", size=10), make("b", size=0), make("c"), make("d", size=20)]

    sort_entries(entries, key=SortKey.SIZE)

    assert [entry.name for entry in entries] == ["a", "d", "b", "c"]


def test_sort_by_size_desc() -> None:
    entries = [make("a", size=10), make("b", size=20)]

    sort_entries(entries, key=SortKey.SIZE, reverse=True)

    assert [entry.name for entry in entries] == ["b", "a"]


def test_sort_by_mtime_missing_last() -> None:
    entries = [make("a", mtime=100.0), make("b"), make("c", mtime=200.0)]

    sort_entries(entries, key=SortKey.MTIME)

    assert [entry.name for entry in entries] == ["a", "c", "b"]


def test_sort_by_mtime_desc() -> None:
    entries = [make("a", mtime=100.0), make("b", mtime=200.0)]

    sort_entries(entries, key=SortKey.MTIME, reverse=True)

    assert [entry.name for entry in entries] == ["b", "a"]


def test_sort_by_name_without_folders_first_mixes_kinds() -> None:
    entries = [make("c.txt"), make("A", kind=Kind.DIR), make("b.txt")]

    sort_entries(entries, key=SortKey.NAME, folders_first=False)

    assert [entry.name for entry in entries] == ["A", "b.txt", "c.txt"]


def test_sort_by_size_without_folders_first_mixes_kinds() -> None:
    entries = [
        make("docs", kind=Kind.DIR),
        make("big", size=20),
        make("small", size=10),
    ]

    sort_entries(entries, key=SortKey.SIZE, folders_first=False)

    # A directory has no size, so it is missing and stays last in both directions.
    assert [entry.name for entry in entries] == ["small", "big", "docs"]


def test_sort_by_mtime_without_folders_first_mixes_kinds() -> None:
    entries = [
        make("dir", kind=Kind.DIR, mtime=200.0),
        make("a", mtime=100.0),
        make("c", mtime=300.0),
    ]

    sort_entries(entries, key=SortKey.MTIME, folders_first=False)

    assert [entry.name for entry in entries] == ["a", "dir", "c"]
