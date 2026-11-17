"""Grouped «Значки»: date captions over virtualized tile rows.

Widget-level tests of :class:`~volna.views.icons.IconsView` (design/grouping.md
D6): a grouped render builds caption rows plus tile bands, the band size follows
the allocated width, resizing re-chunks the rows, and the flat listing keeps the
old ``GtkGridView`` path. The view is driven directly here — the tab wiring is
covered by the system tests in ``tests/test_view_modes.py`` — under the shared
Xvfb display from ``tests/conftest.py``.

GTK and ``volna.views`` are imported inside the tests, not at module level: the
display is set up by the session fixture (see ``tests/test_view_modes.py``).
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

pytest.importorskip("gi")

from volna.size import px  # noqa: E402

# The metric contract from design/grouping.md D6: tiles are ``px(150)`` wide
# with a ``px(6)`` gap, and a band holds as many as fit.
_TILE_MIN = px(150)
_GAP = px(6)


def _walk(widget: Any) -> Iterator[Any]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _walk(child)
        child = child.get_next_sibling()


def _by_class(root: Any, name: str) -> list[Any]:
    return [widget for widget in _walk(root) if widget.has_css_class(name)]


def _texts(root: Any, name: str) -> list[str]:
    return [label.get_text() for label in _by_class(root, name)]


def _pump(seconds: float = 0.2) -> None:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)


def _pump_until(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        _pump(0.02)

    return False


def _items(count: int, prefix: str = "file") -> tuple[Any, ...]:
    from volna.views.item import ListingItem

    return tuple(
        ListingItem(
            f"{prefix}{index:03d}.txt",
            f"/tmp/{prefix}{index:03d}.txt",
            "1 КиБ",
            "01.01.2026 00:00",
            False,
        )
        for index in range(count)
    )


def _band_count(width: int) -> int:
    """Tiles per band: the metric contract, restated as a packing invariant."""
    return max(1, (width + _GAP) // (_TILE_MIN + _GAP))


def _fits(width: int, count: int) -> bool:
    """``count`` tiles fit into ``width`` and one more tile does not."""
    step = _TILE_MIN + _GAP
    return count * step <= width + _GAP < (count + 1) * step


def _rows(view: Any) -> list[Any]:
    return [view.store.get_item(index) for index in range(view.store.get_n_items())]


def _captions(view: Any) -> list[Any]:
    from volna.views.icons import HeaderRow

    return [row for row in _rows(view) if isinstance(row, HeaderRow)]


def _bands(view: Any) -> list[Any]:
    from volna.views.icons import TileRow

    return [row for row in _rows(view) if isinstance(row, TileRow)]


def _tile_named(view: Any, name: str) -> Any:
    for tile in _by_class(view.widget, "volna-icons-tile"):
        if _texts(tile, "volna-icons-name") == [name]:
            return tile

    raise AssertionError(f"tile {name!r} is not on screen")


def _settle(view: Any) -> None:
    """Let GTK allocate the visible presentation and run width re-chunking."""
    _pump_until(
        lambda: view._list.get_width() > 0 or view._scroller.get_child() is view._grid
    )
    _pump(0.4)


@dataclass
class _Harness:
    window: Any
    view: Any
    activated: list[Any] = field(default_factory=list)

    def render(self, sections: tuple[Any, ...]) -> None:
        self.view.render(sections)
        _settle(self.view)

    def resize(self, width: int, height: int = 600) -> None:
        self.window.set_default_size(width, height)
        _pump(0.5)

    def close(self) -> None:
        self.window.destroy()


@contextmanager
def _opened_view(*, width: int = 900, height: int = 900) -> Iterator[_Harness]:
    """A presented ``IconsView``; GTK objects never outlive the session Xvfb."""
    from gi.repository import Gtk

    from volna.views.icons import IconsView

    window = Gtk.Window()
    window.set_default_size(width, height)
    activated: list[Any] = []
    view = IconsView(on_activate=activated.append)
    window.set_child(view.widget)
    window.present()
    _pump(0.3)

    harness = _Harness(window=window, view=view, activated=activated)
    try:
        yield harness
    finally:
        harness.close()


@contextmanager
def _project_theme() -> Iterator[None]:
    """Load ``theme.css`` for one test and take it off the display afterwards.

    The grouped band is width-driven only because the theme relaxes the tile's
    ``min-width`` inside ``.volna-icons-band`` (design/grouping.md D6/D9); this
    test file is the place that guards that contract.
    """
    from pathlib import Path

    from gi.repository import Gdk, Gtk

    css = (Path(__file__).resolve().parents[1] / "src/volna/theme.css").read_text(
        encoding="utf-8"
    )
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    try:
        yield
    finally:
        Gtk.StyleContext.remove_provider_for_display(display, provider)


# -- grouped structure --------------------------------------------------------


def test_grouped_render_builds_caption_rows_and_tile_bands(gtk_display) -> None:
    from volna.views.base import Section

    first = _items(7, "today")
    second = _items(2, "yday")

    with _opened_view() as harness:
        harness.render(
            (
                Section(items=first, header="Сегодня", stats="7 файлов (7 Б)"),
                Section(items=second, header="Вчера", stats="2 файлов (2 Б)"),
            )
        )

        captions = _captions(harness.view)
        bands = _bands(harness.view)
        assert [caption.label for caption in captions] == ["Сегодня", "Вчера"]
        assert [caption.stats for caption in captions] == [
            "7 файлов (7 Б)",
            "2 файлов (2 Б)",
        ]
        assert [item.name for band in bands for item in band.items] == [
            item.name for item in (*first, *second)
        ]

        # What the user sees: one caption per section, with the title and the
        # group summary (folder/file counts and size, like the editor header).
        _pump_until(lambda: _texts(harness.view.widget, "volna-group-title") != [])
        assert _texts(harness.view.widget, "volna-group-title") == ["Сегодня", "Вчера"]
        assert _texts(harness.view.widget, "volna-group-stats") == [
            "7 файлов (7 Б)",
            "2 файлов (2 Б)",
        ]
        assert len(_by_class(harness.view.widget, "volna-icons-head")) == 2
        assert "today000.txt" in _texts(harness.view.widget, "volna-icons-name")


def test_caption_summary_comes_from_the_section(gtk_display) -> None:
    from volna.views.base import Section

    summaries = ("2 файлов (2 Б)", "3 папок · 1 файлов (9 Б)")

    with _opened_view() as harness:
        harness.render(
            tuple(
                Section(
                    items=_items(2, f"g{index}"), header=f"Группа {index}", stats=text
                )
                for index, text in enumerate(summaries)
            )
        )

        _pump_until(lambda: _texts(harness.view.widget, "volna-group-stats") != [])
        assert _texts(harness.view.widget, "volna-group-stats") == list(summaries)
        assert [caption.stats for caption in _captions(harness.view)] == list(summaries)


def test_tiles_per_band_follow_the_band_width(gtk_display) -> None:
    from volna.views.base import Section

    with _opened_view() as harness:
        harness.render((Section(items=_items(30), header="Сегодня"),))

        width = harness.view._list.get_width()
        count = _band_count(width)
        assert _fits(width, count)

        bands = _bands(harness.view)
        assert len(bands) == -(-30 // count)
        assert all(1 <= len(band.items) <= count for band in bands)


def test_a_short_band_keeps_the_design_tile_width(gtk_display) -> None:
    """A band with fewer tiles than fits must not stretch them across the band.

    The mockup's grid columns are 150..178 px and the leftover width stays to
    the right; stretching two tiles over a 1400 px band would not read as the
    design's icon grid (design/grouping.md D6).
    """
    from volna.size import px
    from volna.views.base import Section

    with _opened_view(width=1400) as harness:
        harness.render((Section(items=_items(2), header="Сегодня"),))

        def laid_out() -> bool:
            tiles = _by_class(harness.view.widget, "volna-icons-tile")
            return len(tiles) == 2 and all(tile.get_width() > 0 for tile in tiles)

        assert _pump_until(laid_out)
        tiles = _by_class(harness.view.widget, "volna-icons-tile")
        widths = [tile.get_width() for tile in tiles]

        assert all(px(150) - 1 <= width <= px(178) for width in widths), widths
        assert sum(widths) + _GAP < harness.view._list.get_width(), (
            "a two-tile band filled the whole width instead of keeping tile width"
        )


def test_narrower_band_rechunks_the_tile_rows(gtk_display) -> None:
    from volna.views.base import Section

    with _opened_view() as harness:
        harness.render((Section(items=_items(30), header="Сегодня"),))

        wide = harness.view._list.get_width()
        wide_count = _band_count(wide)
        wide_bands = len(_bands(harness.view))

        harness.resize(420)

        def rechunked() -> bool:
            width = harness.view._list.get_width()
            return 0 < width < wide and _band_count(width) < wide_count

        assert _pump_until(rechunked)
        narrow = harness.view._list.get_width()
        narrow_count = _band_count(narrow)
        assert _fits(narrow, narrow_count)
        assert narrow_count < wide_count
        assert len(_bands(harness.view)) == -(-30 // narrow_count)
        assert len(_bands(harness.view)) > wide_bands
        assert all(len(band.items) <= narrow_count for band in _bands(harness.view))


def test_large_listing_stays_row_level(gtk_display) -> None:
    """Virtualization is per tile band: the store holds rows, not 2000 tiles."""
    from volna.views.base import Section

    with _opened_view() as harness:
        harness.render((Section(items=_items(2000), header="Сегодня"),))

        width = harness.view._list.get_width()
        count = _band_count(width)
        expected_rows = 1 + -(-2000 // count)
        assert harness.view.store.get_n_items() == expected_rows
        assert expected_rows < 2000


# -- flat listing -------------------------------------------------------------


def test_flat_section_keeps_the_grid_view(gtk_display) -> None:
    from volna.views.base import Section

    items = _items(4)

    with _opened_view() as harness:
        harness.render((Section(items=items),))

        assert harness.view._scroller.get_child() is harness.view._grid
        assert _rows(harness.view) == list(items)
        _pump_until(
            lambda: (
                _texts(harness.view.widget, "volna-icons-name")
                == [item.name for item in items]
            )
        )
        assert _texts(harness.view.widget, "volna-icons-name") == [
            item.name for item in items
        ]
        assert _texts(harness.view.widget, "volna-group-title") == []


def test_flat_after_grouped_drops_the_captions(gtk_display) -> None:
    from volna.views.base import Section

    with _opened_view() as harness:
        harness.render((Section(items=_items(3, "grouped"), header="Сегодня"),))
        harness.render((Section(items=_items(2, "flat")),))

        assert harness.view._scroller.get_child() is harness.view._grid
        assert _captions(harness.view) == []
        _pump_until(
            lambda: (
                _texts(harness.view.widget, "volna-icons-name")
                == ["flat000.txt", "flat001.txt"]
            )
        )
        assert _texts(harness.view.widget, "volna-icons-name") == [
            "flat000.txt",
            "flat001.txt",
        ]
        assert _texts(harness.view.widget, "volna-group-title") == []


def test_narrow_band_clips_tiles_instead_of_squeezing_them(gtk_display) -> None:
    """A band narrower than its tiles must not allocate a tile below its padding.

    The ListView allocates the previous rows once more between a resize and the
    idle re-chunk. Squeezing the overflowing tiles to zero width made GTK
    allocate their padded children with negative sizes (``GtkImage ... with
    width -14``); the band now clips them at their design width instead.
    """
    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    from volna.views.icons import TileBand, _make_tile

    criticals: list[str] = []

    def on_log(_domain: str, _level: int, message: str, _data) -> None:
        criticals.append(message)

    handler = GLib.log_set_handler(
        "Gtk",
        GLib.LogLevelFlags.LEVEL_WARNING | GLib.LogLevelFlags.LEVEL_CRITICAL,
        on_log,
        None,
    )
    try:
        with _project_theme():
            band = TileBand(tile_width=_TILE_MIN)
            for _ in range(2):
                band.append(_make_tile())

            window = Gtk.Window()
            window.set_default_size(100, 200)
            window.set_child(band)
            window.present()
            _pump(0.4)
            window.destroy()
            _pump(0.1)
    finally:
        GLib.log_remove_handler("Gtk", handler)

    assert criticals == []


# -- activation and scroll ----------------------------------------------------


def test_double_click_on_a_tile_opens_its_item(gtk_display) -> None:
    from gi.repository import Gtk

    from volna.views.base import Section

    items = _items(5)

    with _opened_view() as harness:
        harness.render((Section(items=items, header="Сегодня"),))

        tile = _tile_named(harness.view, items[2].name)
        controllers = tile.observe_controllers()
        clicks = [
            controllers.get_item(index)
            for index in range(controllers.get_n_items())
            if isinstance(controllers.get_item(index), Gtk.GestureClick)
        ]
        assert len(clicks) == 1, "a tile must carry the double-click handler"

        clicks[0].emit("pressed", 2, 0.0, 0.0)

        assert harness.activated == [items[2]]


def test_reading_position_survives_a_rechunk(gtk_display) -> None:
    from volna.views.base import Section
    from volna.views.icons import TileRow

    items = _items(400)

    with _opened_view() as harness:
        harness.render((Section(items=items, header="Сегодня"),))

        adjustment = harness.view._scroller.get_vadjustment()
        adjustment.set_value(3000)
        _pump(0.3)
        anchor = harness.view._first_visible_item()
        assert anchor is not None
        assert anchor is not items[0]

        harness.resize(420)

        def rechunked() -> bool:
            width = harness.view._list.get_width()
            if not width > 0:
                return False

            expected = 1 + -(-len(items) // _band_count(width))
            return harness.view.store.get_n_items() == expected

        assert _pump_until(rechunked)

        # Re-chunking changes the packing, so the anchor can stop being the
        # first tile of its row; the contract is that its row becomes the top
        # row of the viewport instead of the scroll jumping elsewhere.
        anchor_row = harness.view._row_position(anchor)

        def anchored() -> bool:
            row = harness.view._top_row()
            return isinstance(row, TileRow) and row.position == anchor_row

        assert _pump_until(anchored), "the reading position was not preserved"
        assert anchor in harness.view._top_row().items
        assert adjustment.get_value() > 0


def test_theme_lets_the_window_shrink_and_rechunk_the_bands(gtk_display) -> None:
    """The grouped band must not freeze the window's minimum width.

    A tile carries ``.volna-icons-tile`` with a design min-width; if it counted
    towards the row's minimum, the ``ListView`` (and the window) would stop
    shrinking at the current band, so the width-driven re-chunk would never run
    on a narrower window. ``theme.css`` relaxes it inside ``.volna-icons-band``.
    """
    from volna.views.base import Section

    items = _items(40)

    with _project_theme(), _opened_view(width=1240, height=800) as harness:
        harness.render((Section(items=items, header="Сегодня"),))

        wide_width = harness.view._list.get_width()
        wide_columns = _band_count(wide_width)
        wide_bands = len(_bands(harness.view))

        # The minimum width follows the chunks, so narrow like a drag: each
        # step re-chunks and lowers the minimum for the next step.
        for _ in range(3):
            harness.window.set_default_size(520, 800)
            _pump(0.8)

        narrow_width = harness.view._list.get_width()
        assert narrow_width < wide_width, "the window did not shrink"
        assert _band_count(narrow_width) < wide_columns, "the bands did not re-chunk"
        assert len(_bands(harness.view)) > wide_bands
        assert len(_bands(harness.view)) == -(-len(items) // _band_count(narrow_width))


def test_grouped_render_before_the_window_is_shown_still_chunks(gtk_display) -> None:
    """A render before the first allocation must not keep single-tile bands."""
    from gi.repository import Gtk

    from volna.views.base import Section
    from volna.views.icons import IconsView

    items = _items(12)
    view = IconsView(on_activate=lambda item: None)
    view.render((Section(items=items, header="Сегодня"),))
    assert [len(band.items) for band in _bands(view)] == [1] * len(items)

    window = Gtk.Window()
    window.set_default_size(900, 900)
    window.set_child(view.widget)
    window.present()
    try:
        assert _pump_until(lambda: view.store.get_n_items() < len(items) + 1)
        width = view._list.get_width()
        assert len(_bands(view)) == -(-len(items) // _band_count(width))
        assert len(_bands(view)[0].items) > 1
    finally:
        window.destroy()


# -- teardown -----------------------------------------------------------------

# A band parents its tiles by hand (``set_parent``); GtkWidget releases no
# children of a custom widget, so a disposed band has to unparent them itself.
# When it does not, GTK finalizes it "with children left" — the warning the user
# sees on every group toggle — and leaks the tiles. The warning is written to
# stderr by C, so the scenarios run in a child interpreter: PyGObject does not
# dispatch GObject's ``dispose`` to Python and offers no practical in-process
# hook.
_LIFECYCLE_SCRIPT = """
import gc
import time
import weakref

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

Gtk.init()

from volna.size import px
from volna.views.base import Section
from volna.views.icons import IconsView, TileBand, TileRow
from volna.views.item import ListingItem


def pump(seconds=0.3):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)


def pump_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        pump(0.02)

    return False


def items(prefix, count):
    return tuple(
        ListingItem(
            f"{prefix}{index}.txt",
            f"/tmp/{prefix}{index}.txt",
            "1 КиБ",
            "01.01.2026 00:00",
            False,
        )
        for index in range(count)
    )


def sections(*, collapsed):
    return (
        Section(
            items=items("today", 8),
            header="Сегодня",
            key="today",
            collapsed=collapsed,
        ),
        Section(items=items("yesterday", 5), header="Вчера", key="yesterday"),
    )


def materialised_bands():
    \"\"\"Bands on screen that still show their tiles.\"\"\"
    count = 0
    child = view._list.get_first_child()
    while child is not None:
        box = child.get_first_child()
        row = getattr(box, "icon_row", None)
        band = box.get_first_child() if box is not None else None
        if child.get_mapped() and isinstance(row, TileRow):
            if band is not None and band.get_first_child() is not None:
                count += 1

        child = child.get_next_sibling()

    return count


class CountedTile(Gtk.Box):
    \"\"\"A tile with a Python-subclass wrapper, kept alive with its GObject.\"\"\"

    __gtype_name__ = "VolnaCountedTile"


# 1. A band discarded without ever being rooted: GtkWidget unroots a widget only
#    if it had a root, so unroot alone would never release such a band's tiles.
orphan = TileBand(tile_width=px(150))
tiles = [CountedTile(), CountedTile()]
gone = [weakref.ref(tile) for tile in tiles]
for tile in tiles:
    orphan.append(tile)

del tile, tiles, orphan
gc.collect()
assert all(ref() is None for ref in gone), "the never-rooted band leaked its tiles"
print("ORPHAN TORN DOWN", flush=True)

# 2. What a group toggle does: the tab renders the sections again, the rows are
#    rebuilt and the bands of the previous render are discarded.
window = Gtk.Window()
window.set_default_size(900, 900)
view = IconsView(on_activate=lambda item: None)
window.set_child(view.widget)
window.present()
pump(0.4)

view.render(sections(collapsed=False))
assert pump_until(lambda: materialised_bands() > 0), "no tile bands on screen"

for _ in range(3):
    view.render(sections(collapsed=True))
    pump(0.3)
    view.render(sections(collapsed=False))
    pump(0.3)

assert pump_until(lambda: materialised_bands() > 0), "the toggles lost the bands"
print("TOGGLES DONE", flush=True)

window.destroy()
pump(0.4)
view = None
gc.collect()
pump(0.3)
"""


def test_discarded_bands_leave_no_children_behind(gtk_display) -> None:
    """A discarded band must release its hand-parented tiles.

    Both paths are covered: a group toggle discards the bands of the rebuilt
    rows, and a band can be dropped before it is ever rooted (GtkWidget then
    never unroots it). Either way, GTK finalizes a band "with children left" —
    the warning reported on every group toggle — and the tiles of every
    discarded row stay alive.
    """
    result = subprocess.run(
        [sys.executable, "-c", _LIFECYCLE_SCRIPT],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "ORPHAN TORN DOWN" in result.stdout, result.stderr
    assert "TOGGLES DONE" in result.stdout, result.stderr
    assert "still has children left" not in result.stderr, result.stderr
