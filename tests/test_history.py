"""Per-tab navigation history: back/forward bounds, truncation and ``up``."""

from pathlib import Path

from volna.history import NavigationHistory


def test_initial_state_is_the_start_directory_only() -> None:
    history = NavigationHistory(Path("/home/nik"))

    assert history.current == Path("/home/nik")
    assert not history.can_back
    assert not history.can_forward
    assert history.can_up
    assert history.back() is None
    assert history.forward() is None


def test_visit_appends_and_makes_the_path_current() -> None:
    history = NavigationHistory(Path("/a"))

    assert history.visit(Path("/b")) == Path("/b")
    assert history.current == Path("/b")
    assert history.can_back
    assert not history.can_forward


def test_visit_after_back_truncates_the_forward_branch() -> None:
    history = NavigationHistory(Path("/a"))
    history.visit(Path("/b"))
    history.visit(Path("/c"))
    assert history.back() == Path("/b")

    assert history.visit(Path("/d")) == Path("/d")
    assert history.current == Path("/d")
    assert not history.can_forward
    assert history.back() == Path("/b")


def test_visiting_current_path_keeps_the_forward_branch() -> None:
    history = NavigationHistory(Path("/a"))
    history.visit(Path("/b"))
    history.back()

    assert history.visit(Path("/a")) == Path("/a")
    assert history.can_forward
    assert history.forward() == Path("/b")


def test_visiting_current_path_adds_no_duplicate_entry() -> None:
    history = NavigationHistory(Path("/a"))
    history.visit(Path("/b"))
    history.back()
    history.visit(Path("/a"))
    history.visit(Path("/a"))

    assert history.forward() == Path("/b")
    assert history.back() == Path("/a")
    assert not history.can_back


def test_back_and_forward_walk_the_recorded_paths() -> None:
    history = NavigationHistory(Path("/a"))
    history.visit(Path("/b"))
    history.visit(Path("/c"))

    assert history.back() == Path("/b")
    assert history.back() == Path("/a")
    assert not history.can_back
    assert history.back() is None

    assert history.forward() == Path("/b")
    assert history.forward() == Path("/c")
    assert not history.can_forward
    assert history.forward() is None


def test_up_records_parent_so_back_returns_to_the_child() -> None:
    child = Path("/home/nik/volna")
    history = NavigationHistory(child)

    assert history.up() == Path("/home/nik")
    assert history.current == Path("/home/nik")
    assert history.back() == child
    assert history.forward() == Path("/home/nik")


def test_up_at_filesystem_root_is_unavailable() -> None:
    history = NavigationHistory(Path("/"))

    assert not history.can_up
    assert history.up() is None
    assert history.current == Path("/")
    assert not history.can_back
    assert not history.can_forward


def test_up_from_one_level_below_root_reaches_root() -> None:
    history = NavigationHistory(Path("/etc"))

    assert history.can_up
    assert history.up() == Path("/")
    assert not history.can_up
