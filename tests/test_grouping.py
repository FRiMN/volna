"""System acceptance for date grouping (design/grouping.md).

These tests drive the real ``MainWindow`` the way a user does: a temporary
listing with known modification times, then the «Вид» popover, mode switches
and restarts. Assertions are on user-visible captions, counts and rendered
names, not on the views' internal row objects, because the contract in
design/grouping.md §9 is about what the window shows.

The scenario fixtures (``_make_dated_listing``) use local-calendar timestamps
relative to the test run, so the expected captions are «Сегодня», «Вчера», the
weekday names of the two following days and «Неделю назад».
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from volna.core import ScanState  # noqa: E402
from volna.display import (  # noqa: E402
    DEFAULT_CAPABILITIES,
    MODE_ORDER,
    Grouping,
    JsonViewSettingsStore,
    MemoryViewSettingsStore,
    SettingsPaths,
    ViewCapabilities,
    ViewMode,
    ViewSettings,
)

# Localised weekday names of ``time.localtime(...).tm_wday``: the tests compute
# the expected caption from the timestamp instead of trusting the UI's mapping.
_WEEKDAYS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_DAY = 86_400.0


# -- GTK / window plumbing (patterns from tests/test_view_modes.py) ----------


def _walk(widget: object) -> Iterator[object]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: object, name: str) -> list[object]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _pump_until(condition, timeout: float = 5.0) -> bool:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return True
        time.sleep(0.01)
    return False


def _settle(seconds: float = 0.1) -> None:
    """Let GTK lay out the newly rendered/virtualized rows."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)


def _window(
    path: Path,
    *,
    settings: ViewSettings | None = None,
    capabilities: ViewCapabilities = DEFAULT_CAPABILITIES,
    store=None,
):
    from volna.window import MainWindow

    storage = store or MemoryViewSettingsStore()
    if settings is None:
        settings = storage.load().view or ViewSettings()

    return MainWindow(
        start_path=path,
        initial_settings=settings,
        settings_store=storage,
        capabilities=capabilities,
    )


def _close(window: object) -> None:
    window._on_close_request()
    window.destroy()


def _open_panel(window: object) -> object:
    window.present()
    panel = window._view_panel
    panel.open()
    assert _pump_until(lambda: panel.popover.get_visible()), "the popover did not open"

    return panel


def _control(root: object, text: str) -> object:
    """Find a labelled control (radio, checkbox, segmented button) by its text."""
    for widget in _walk(root):
        getter = getattr(widget, "get_label", None)
        if getter is not None and getter() == text:
            return widget
    raise AssertionError(f"control {text!r} not found")


def _ready(window: object) -> None:
    """Wait until the active tab has finished its scan (settings do not rescan)."""
    tab = window._active_tab
    assert _pump_until(lambda: tab.model.state is ScanState.READY), (
        f"the scan never finished: {tab.model.state}"
    )


def _visible_root(window: object) -> object:
    """The rendered widget of the active tab's visible mode."""
    tab = window._active_tab
    return tab.widget.get_visible_child() or tab.widget


def _mapped_texts(root: object, css_class: str) -> list[str]:
    """Non-empty texts of mapped widgets: virtualized pools are ignored."""
    texts = []
    for widget in _by_class(root, css_class):
        getter = getattr(widget, "get_text", None)
        if getter is None or not widget.get_mapped():
            continue
        text = getter()
        if text:
            texts.append(text)

    return texts


def _group_headers(window: object) -> list[tuple[str, str]]:
    """Visible date captions paired with their counts, in screen order."""
    headers: list[tuple[str, str]] = []
    for title in _by_class(_visible_root(window), "volna-group-title"):
        if not title.get_mapped():
            continue
        caption = title.get_text()
        if not caption:
            continue
        trailing = title.get_next_sibling()
        assert trailing is not None and (
            trailing.has_css_class("volna-group-stats")
            or trailing.has_css_class("volna-group-count")
        ), f"the caption {caption!r} has no summary next to it"
        headers.append((caption, trailing.get_text()))

    return headers


_MODE_NAME_CLASS = {
    ViewMode.DETAILS: "volna-dt-name",
    ViewMode.ICONS: "volna-icons-name",
    ViewMode.COLUMNS: "volna-col-name",
}


def _names(window: object, mode: ViewMode) -> list[str]:
    return _mapped_texts(_visible_root(window), _MODE_NAME_CLASS[mode])


def _wait_for_headers(window: object, expected: list[tuple[str, str]]) -> None:
    assert _pump_until(lambda: _group_headers(window) == expected), (
        f"captions never became {expected}: {_group_headers(window)}"
    )


def _wait_for_names(window: object, mode: ViewMode, *names: str) -> None:
    assert _pump_until(lambda: all(name in _names(window, mode) for name in names)), (
        f"{mode} never showed {names}: {_names(window, mode)}"
    )


def _wait_for_names_order(window: object, mode: ViewMode, expected: list[str]) -> None:
    assert _pump_until(lambda: _names(window, mode) == expected), (
        f"{mode} rows never became {expected}: {_names(window, mode)}"
    )


def _scroll_steps(adjustment) -> list[float]:
    """Scroll offsets covering the whole content of one axis, top to bottom."""
    lower = adjustment.get_lower()
    last = max(lower, adjustment.get_upper() - adjustment.get_page_size())
    if last <= lower:
        return [lower]

    return [lower + (last - lower) * share for share in (0.0, 0.5, 1.0)]


def _collect_listing(
    window: object, mode: ViewMode
) -> tuple[list[tuple[str, str]], list[str]]:
    """What the user can reach in this mode: scroll through the virtualized list.

    «Значки» and «Столбцы» materialize only visible rows/columns (the whole
    point of row-level virtualization), so a caption off screen has no widget
    yet. Scrolling the visible band to each position collects them in order;
    the position is restored afterwards so later assertions start at the top.
    """
    root = _visible_root(window)
    horizontal = root.get_hadjustment()
    vertical = root.get_vadjustment()
    headers: list[tuple[str, str]] = []
    names: list[str] = []

    _settle()
    try:
        for h_value in _scroll_steps(horizontal):
            for v_value in _scroll_steps(vertical):
                horizontal.set_value(h_value)
                vertical.set_value(v_value)
                _settle()

                for header in _group_headers(window):
                    if header not in headers:
                        headers.append(header)
                for name in _names(window, mode):
                    if name not in names:
                        names.append(name)
    finally:
        horizontal.set_value(horizontal.get_lower())
        vertical.set_value(vertical.get_lower())
        _settle()

    return headers, names


def _wait_for_mode_listing(
    window: object,
    mode: ViewMode,
    headers: list[tuple[str, str]],
    names: list[str],
) -> None:
    """Wait until the mode shows exactly ``headers`` and all ``names``."""
    collected_headers: list[tuple[str, str]] = []
    collected_names: list[str] = []
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        collected_headers, collected_names = _collect_listing(window, mode)
        if collected_headers == headers and set(names) <= set(collected_names):
            return
        _settle(0.05)

    raise AssertionError(
        f"{mode} never showed {headers} / {names}: "
        f"{collected_headers} / {collected_names}"
    )


# -- reference listing with known modification times ------------------------


def _local_midnight(now: float) -> float:
    local = time.localtime(now)
    return time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))


def _day_start(days_ago: int) -> float:
    """Local midnight ``days_ago`` calendar days back from the test run."""
    return _local_midnight(time.time()) - days_ago * _DAY


def _weekday(days_ago: int) -> str:
    # Noon keeps the timestamp inside the intended day even across a DST shift.
    timestamp = _day_start(days_ago) + 12 * 3_600
    return _WEEKDAYS[time.localtime(timestamp).tm_wday]


def _touch(path: Path, mtime: float) -> None:
    path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))


_DATED_GROUP_SIZES = [2, 1, 2, 1, 2]

_DATED_FILES = (
    # (file name, days ago, seconds within the day)
    ("today-new.txt", 0, 120),
    ("today-old.txt", 0, 60),
    ("yesterday.txt", 1, 0),
    ("twodays-a.txt", 2, 120),
    ("twodays-b.txt", 2, 60),
    ("threedays.txt", 3, 0),
    ("ten-a.txt", 10, 120),
    ("ten-b.txt", 10, 60),
)


def _make_dated_listing(root: Path) -> None:
    for name, days_ago, offset in _DATED_FILES:
        _touch(root / name, _day_start(days_ago) + 12 * 3_600 + offset)


def _files_in_summaries(headers: list[tuple[str, str]]) -> int:
    """The file counts the captions report, summed over the groups."""
    return sum(int(summary.split(" · ")[1].split()[0]) for _caption, summary in headers)


def _summary(files: int) -> str:
    """The caption summary for ``files`` single-byte entries in one group."""
    return f"0 папок · {files} файлов ({files} Б)"


def _column_captions() -> list[tuple[str, str]]:
    """«Столбцы» keep the compact count instead of the full summary."""
    return [
        (caption, str(size))
        for (caption, _summary), size in zip(
            _dated_captions(), _DATED_GROUP_SIZES, strict=True
        )
    ]


def _dated_captions() -> list[tuple[str, str]]:
    return [
        ("Сегодня", _summary(2)),
        ("Вчера", _summary(1)),
        (_weekday(2), _summary(2)),
        (_weekday(3), _summary(1)),
        ("Неделю назад", _summary(2)),
    ]


def _dated_names() -> list[str]:
    return [name for name, _days_ago, _offset in _DATED_FILES]


# The reference content set from design/content-spec.md / variant-c.html: the
# acceptance criterion fixes its group counts (Сегодня 3, Вчера 6, Среда 2,
# Вторник 1, Неделю назад 2). The weekday captions stay dynamic: they name the
# actual days 2 and 3 days before the run.
_REFERENCE_FILES = (
    ("starshp", 0),
    ("uv", 0),
    ("gh", 0),
    ("mc", 1),
    ("bookmarkrunner", 1),
    ("appstream", 1),
    ("kio_http", 1),
    ("mpv", 1),
    ("gstreamer-1.0", 1),
    ("electron", 2),
    ("pnpm", 2),
    ("gnome-calculator", 3),
    ("llmfit", 10),
    ("qtshadercache", 10),
)


def _make_reference_listing(root: Path) -> None:
    for index, (name, days_ago) in enumerate(_REFERENCE_FILES):
        _touch(root / name, _day_start(days_ago) + 12 * 3_600 + index * 60)


def _make_sorting_listing(root: Path) -> None:
    """One «Сегодня» group: a folder and two files with known values."""
    folder = root / "m-folder"
    folder.mkdir()
    (root / "a.txt").write_text("0123456789", encoding="utf-8")
    (root / "z.txt").write_text("0", encoding="utf-8")

    base = _day_start(0) + 3_600
    # The folder is the oldest entry: only `folders_first` can put it first.
    os.utime(folder, (base + 50, base + 50))
    os.utime(root / "a.txt", (base + 200, base + 200))
    os.utime(root / "z.txt", (base + 100, base + 100))


# -- 1. the grouped details listing -----------------------------------------


def test_details_shows_design_captions_in_order_with_counts(
    gtk_display, tmp_path: Path
) -> None:
    _make_dated_listing(tmp_path)
    expected = _dated_captions()

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_names(window, ViewMode.DETAILS, *_dated_names())

        assert _group_headers(window) == expected
        # The summary counts exactly the rows under the captions: the whole
        # listing is visible by default (no hidden files in this fixture).
        assert _files_in_summaries(expected) == len(_names(window, ViewMode.DETAILS))

        # «Без группировки»: one flat list, not a single caption.
        _control(panel.popover, "Без группировки").set_active(True)
        _wait_for_headers(window, [])
        assert _group_headers(window) == []
        _wait_for_names(window, ViewMode.DETAILS, *_dated_names())
    finally:
        _close(window)


def test_reference_content_set_matches_the_design_counts(
    gtk_display, tmp_path: Path
) -> None:
    """design/content-spec.md set: Сегодня 3, Вчера 6, Среда 2, Вторник 1, …

    «Среда»/«Вторник» in the mockup are the fixed sample content; the real
    captions name the actual weekdays, so the test recomputes them. The counts
    and the bucket order are the acceptance contract (grouping.md §9).
    """
    _make_reference_listing(tmp_path)
    expected = [
        ("Сегодня", _summary(3)),
        ("Вчера", _summary(6)),
        (_weekday(2), _summary(2)),
        (_weekday(3), _summary(1)),
        ("Неделю назад", _summary(2)),
    ]

    window = _window(tmp_path)
    try:
        _open_panel(window)
        _ready(window)
        _wait_for_mode_listing(
            window,
            ViewMode.DETAILS,
            expected,
            [name for name, _days_ago in _REFERENCE_FILES],
        )
    finally:
        _close(window)


# -- 2. all three modes -------------------------------------------------------


def test_every_mode_renders_and_drops_the_same_groups(
    gtk_display, tmp_path: Path
) -> None:
    _make_dated_listing(tmp_path)
    expected = _dated_captions()

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, expected)

        for mode in (ViewMode.DETAILS, ViewMode.ICONS, ViewMode.COLUMNS):
            _control(panel.popover, mode.label).set_active(True)
            headers = _column_captions() if mode is ViewMode.COLUMNS else expected
            _wait_for_mode_listing(window, mode, headers, _dated_names())
            assert window._active_tab.view_mode is mode

            _control(panel.popover, "Без группировки").set_active(True)
            _wait_for_mode_listing(window, mode, [], _dated_names())

            _control(panel.popover, "По дате изменения").set_active(True)
            headers = _column_captions() if mode is ViewMode.COLUMNS else expected
            _wait_for_mode_listing(window, mode, headers, _dated_names())
    finally:
        _close(window)


def test_switching_mode_keeps_the_grouping(gtk_display, tmp_path: Path) -> None:
    _make_dated_listing(tmp_path)
    expected = _dated_captions()

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, expected)

        _control(panel.popover, "Значки").set_active(True)
        _wait_for_mode_listing(window, ViewMode.ICONS, expected, _dated_names())
        _control(panel.popover, "Столбцы").set_active(True)
        _wait_for_mode_listing(
            window, ViewMode.COLUMNS, _column_captions(), _dated_names()
        )

        assert window._active_tab.view_settings.grouping is Grouping.DATE
    finally:
        _close(window)


# -- 3. the View panel section ------------------------------------------------


def test_view_panel_offers_grouping_between_mode_and_sorting(
    gtk_display, tmp_path: Path
) -> None:
    _make_dated_listing(tmp_path)

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)

        titles = _mapped_texts(panel.popover, "volna-view-section-title")
        assert titles == [
            "Режим просмотра",
            "Группировка",
            "Сортировка",
            "Параметры",
        ]

        radios = [
            widget.get_label() for widget in _by_class(panel.popover, "volna-radio")
        ]
        assert radios == [
            "Значки",
            "Столбцы",
            "Подробности",
            "По дате изменения",
            "Без группировки",
            "Дата изменения",
            "Размер",
            "Имя",
        ]

        # The choice the user sees reflected is the stored default.
        assert _control(panel.popover, "По дате изменения").get_active()
    finally:
        _close(window)


def test_grouping_change_applies_immediately_without_rescanning(
    gtk_display, tmp_path: Path
) -> None:
    _make_dated_listing(tmp_path)
    expected = _dated_captions()

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, expected)

        model = window._active_tab.model
        generation = model.generation
        state_before = model.state
        counters_before = model.counters()
        entries_before = len(model.entries())

        _control(panel.popover, "Без группировки").set_active(True)
        _wait_for_headers(window, [])

        assert model.generation == generation
        assert model.state is state_before
        assert model.counters() == counters_before
        assert len(model.entries()) == entries_before
        assert panel.popover.get_visible(), (
            "changing a setting must keep the popover open"
        )

        _control(panel.popover, "По дате изменения").set_active(True)
        _wait_for_headers(window, expected)
        assert model.generation == generation
        assert model.state is state_before
        assert model.counters() == counters_before
    finally:
        _close(window)


def test_a_new_tab_inherits_the_grouping_choice(gtk_display, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_dated_listing(first)
    _make_dated_listing(second)

    window = _window(first)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, _dated_captions())

        _control(panel.popover, "Без группировки").set_active(True)
        _wait_for_headers(window, [])
        first_tab = window._active_tab

        window._open_tab(second)
        second_tab = window._active_tab
        assert second_tab is not first_tab
        assert second_tab.view_settings.grouping is Grouping.NONE, (
            "a new tab must inherit the active tab's grouping"
        )

        _ready(window)
        _wait_for_headers(window, [])
        assert _group_headers(window) == []
        assert first_tab.view_settings.grouping is Grouping.NONE

        # Turning grouping back on applies to the new tab only.
        _control(panel.popover, "По дате изменения").set_active(True)
        _wait_for_headers(window, _dated_captions())
        assert second_tab.view_settings.grouping is Grouping.DATE
        assert first_tab.view_settings.grouping is Grouping.NONE
    finally:
        _close(window)


# -- 4. persistence -----------------------------------------------------------


def test_grouping_choice_survives_a_restart(gtk_display, tmp_path: Path) -> None:
    listing = tmp_path / "listing"
    listing.mkdir()
    _make_dated_listing(listing)
    paths = SettingsPaths(
        directory=tmp_path / "config", file=tmp_path / "config" / "settings.json"
    )

    first = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        panel = _open_panel(first)
        _ready(first)
        _wait_for_headers(first, _dated_captions())

        _control(panel.popover, "Без группировки").set_active(True)
        _wait_for_headers(first, [])
    finally:
        _close(first)

    assert paths.file.exists()
    assert JsonViewSettingsStore(paths).load().view.grouping is Grouping.NONE

    second = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        panel = _open_panel(second)
        _ready(second)
        assert second._active_tab.view_settings.grouping is Grouping.NONE
        _wait_for_headers(second, [])
        assert _control(panel.popover, "Без группировки").get_active()

        # Back on, persisted again.
        _control(panel.popover, "По дате изменения").set_active(True)
        _wait_for_headers(second, _dated_captions())
    finally:
        _close(second)

    assert JsonViewSettingsStore(paths).load().view.grouping is Grouping.DATE

    third = _window(listing, store=JsonViewSettingsStore(paths))
    try:
        _open_panel(third)
        _ready(third)
        assert third._active_tab.view_settings.grouping is Grouping.DATE
        _wait_for_headers(third, _dated_captions())
    finally:
        _close(third)


# -- 5. capability gate -------------------------------------------------------


def test_a_build_without_grouping_hides_it_and_shows_a_flat_listing(
    gtk_display, tmp_path: Path
) -> None:
    _make_dated_listing(tmp_path)
    capabilities = ViewCapabilities(
        modes=frozenset(MODE_ORDER),
        grouping=False,
        density=True,
        zoom_modes=frozenset(),
    )

    # A stored `date` must be normalized away on this build (grouping.md D8).
    window = _window(
        tmp_path,
        settings=ViewSettings(grouping=Grouping.DATE),
        capabilities=capabilities,
    )
    try:
        panel = _open_panel(window)

        titles = _mapped_texts(panel.popover, "volna-view-section-title")
        assert "Группировка" not in titles
        radios = [
            widget.get_label() for widget in _by_class(panel.popover, "volna-radio")
        ]
        assert "По дате изменения" not in radios
        assert "Без группировки" not in radios

        _ready(window)
        _wait_for_names(window, ViewMode.DETAILS, *_dated_names())
        assert window._active_tab.view_settings.grouping is Grouping.NONE
        assert _group_headers(window) == []
    finally:
        _close(window)


# -- 6. ordering inside the groups -------------------------------------------


def test_sort_key_changes_item_order_inside_groups_but_not_the_groups(
    gtk_display, tmp_path: Path
) -> None:
    _make_sorting_listing(tmp_path)
    today_only = [("Сегодня", "1 папок · 2 файлов (11 Б)")]

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, today_only)

        # Default: mtime descending, folders first — the folder leads even
        # though it is the oldest entry.
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "a.txt", "z.txt"])

        _control(panel.popover, "Имя").set_active(True)
        _control(panel.popover, "По убыванию").set_active(True)
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "z.txt", "a.txt"])

        _control(panel.popover, "По возрастанию").set_active(True)
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "a.txt", "z.txt"])

        _control(panel.popover, "Размер").set_active(True)
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "z.txt", "a.txt"])

        _control(panel.popover, "По убыванию").set_active(True)
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "a.txt", "z.txt"])

        assert _group_headers(window) == today_only, (
            "sorting must not change the groups themselves"
        )
    finally:
        _close(window)


def test_folders_first_applies_inside_a_group(gtk_display, tmp_path: Path) -> None:
    _make_sorting_listing(tmp_path)
    today_only = [("Сегодня", "1 папок · 2 файлов (11 Б)")]

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, today_only)

        _control(panel.popover, "Имя").set_active(True)
        _control(panel.popover, "По возрастанию").set_active(True)
        _wait_for_names_order(window, ViewMode.DETAILS, ["m-folder", "a.txt", "z.txt"])

        _control(panel.popover, "Папки перед файлами").set_active(False)
        _wait_for_names_order(window, ViewMode.DETAILS, ["a.txt", "m-folder", "z.txt"])
        assert _group_headers(window) == today_only
    finally:
        _close(window)


# -- 7. counts follow visibility ---------------------------------------------


def test_group_counts_follow_the_hidden_files_setting(
    gtk_display, tmp_path: Path
) -> None:
    base = _day_start(0) + 12 * 3_600
    _touch(tmp_path / "shown.txt", base + 60)
    _touch(tmp_path / ".hidden.txt", base + 120)
    _touch(tmp_path / "older.txt", _day_start(1) + 12 * 3_600)

    window = _window(tmp_path)
    try:
        panel = _open_panel(window)
        _ready(window)
        _wait_for_headers(window, [("Сегодня", _summary(1)), ("Вчера", _summary(1))])
        _wait_for_names(window, ViewMode.DETAILS, "shown.txt", "older.txt")
        assert ".hidden.txt" not in _names(window, ViewMode.DETAILS)

        _control(panel.popover, "Показывать скрытые файлы").set_active(True)
        _wait_for_headers(window, [("Сегодня", _summary(2)), ("Вчера", _summary(1))])
        _wait_for_names(window, ViewMode.DETAILS, ".hidden.txt")
        assert _files_in_summaries(_group_headers(window)) == len(
            _names(window, ViewMode.DETAILS)
        ), "each caption's file count must equal the rows rendered under it"

        _control(panel.popover, "Показывать скрытые файлы").set_active(False)
        _wait_for_headers(window, [("Сегодня", _summary(1)), ("Вчера", _summary(1))])
        assert _pump_until(
            lambda: ".hidden.txt" not in _names(window, ViewMode.DETAILS)
        ), "the hidden file must disappear with its count"
    finally:
        _close(window)
