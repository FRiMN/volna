"""Shared pytest setup: a private Xvfb for GTK4 widget tests.

Widget tests need a display; CI and this development box have no session one.
The fixture starts a private Xvfb, initializes GTK once per module and skips
cleanly when Xvfb or GTK4 is unavailable.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import sys
import time
from array import array
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def gtk_display() -> Iterator[None]:
    process, display = _start_xvfb()
    previous = {
        name: os.environ.get(name)
        for name in ("DISPLAY", "GDK_BACKEND", "GSK_RENDERER")
    }
    os.environ["DISPLAY"] = display
    os.environ["GDK_BACKEND"] = "x11"
    os.environ["GSK_RENDERER"] = "cairo"

    try:
        import gi

        try:
            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib, Gtk
        except (ImportError, ValueError) as exc:
            pytest.skip(f"GTK4 is not available: {exc}")

        try:
            Gtk.init()
        except GLib.Error as exc:
            pytest.skip(f"cannot initialize GTK4: {exc}")

        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        process.terminate()
        process.wait(5)


def _free_display() -> int | None:
    for number in range(100, 140):
        if not Path(f"/tmp/.X11-unix/X{number}").exists():
            return number
    return None


def _start_xvfb() -> tuple[subprocess.Popen, str]:
    if shutil.which("Xvfb") is None:
        pytest.skip("Xvfb is not installed")

    number = _free_display()
    if number is None:
        pytest.skip("no free X display")

    process = subprocess.Popen(
        ["Xvfb", f":{number}", "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    socket = Path(f"/tmp/.X11-unix/X{number}")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if socket.exists():
            return process, f":{number}"
        if process.poll() is not None:
            break
        time.sleep(0.05)

    process.terminate()
    process.wait(5)
    pytest.skip("Xvfb did not start")


class _XImage(ctypes.Structure):
    """The X11 image header ``XGetImage`` returns."""

    _fields_ = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("xoffset", ctypes.c_int),
        ("format", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("byte_order", ctypes.c_int),
        ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int),
        ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int),
        ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong),
        ("blue_mask", ctypes.c_ulong),
        ("obdata", ctypes.c_void_p),
    ]


def _x11_library() -> ctypes.CDLL:
    path = ctypes.util.find_library("X11")
    if path is None:
        pytest.skip("libX11 is not installed")

    x11 = ctypes.CDLL(path)
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XGetImage.restype = ctypes.POINTER(_XImage)
    x11.XGetImage.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulong,
        ctypes.c_int,
    ]
    return x11


Colour = tuple[int, int, int]
"""An RGB colour of the screen, as the X11 readback reports it."""


def _read_colours(
    x11: ctypes.CDLL,
    surface: object,
    x: int,
    y: int,
    width: int,
    height: int,
) -> Counter[Colour]:
    """The colours of a rectangle of an X11 drawable."""
    import gi

    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11

    display = x11.XOpenDisplay(None)
    if not display:
        pytest.skip("cannot open the X display")

    try:
        xid = GdkX11.X11Surface.get_xid(surface)
        image = x11.XGetImage(display, xid, x, y, width, height, 0xFFFFFFFF, 2)
        if not image:
            pytest.skip("XGetImage failed")

        header = image.contents
        raw = ctypes.string_at(header.data, header.bytes_per_line * header.height)

        def shift(mask: int) -> int:
            return (mask & -mask).bit_length() - 1

        red_shift = shift(header.red_mask)
        green_shift = shift(header.green_mask)
        blue_shift = shift(header.blue_mask)
        if header.bits_per_pixel != 32:
            pytest.skip(
                f"unsupported pixel format: {header.bits_per_pixel} bits per pixel"
            )

        # The pixels are words in the order of the image; the machine may
        # read them the other way round.
        pixels = array("I")
        for row in range(header.height):
            start = row * header.bytes_per_line
            pixels.frombytes(raw[start : start + header.width * 4])
        if (header.byte_order == 0) != (sys.byteorder == "little"):
            pixels.byteswap()

        colours: Counter[Colour] = Counter()
        for pixel in pixels:
            colours[
                (
                    (pixel & header.red_mask) >> red_shift,
                    (pixel & header.green_mask) >> green_shift,
                    (pixel & header.blue_mask) >> blue_shift,
                )
            ] += 1
        return colours
    finally:
        x11.XCloseDisplay(display)


@pytest.fixture(scope="session")
def x11_pixels(gtk_display) -> Iterator[Callable[[object], Counter[Colour]]]:
    """Read the colours an X11 drawable actually shows.

    A colour only exists in the cascade of the stylesheet, so a widget test
    cannot see it: the rule that paints it may be anywhere, and the widget's
    own class says nothing about the result. Under Xvfb every surface is a
    real X11 window, so the pixels can be read back with ``XGetImage`` — the
    only check that sees what the user sees.
    """
    x11 = _x11_library()

    def read(surface: object) -> Counter[Colour]:
        return _read_colours(
            x11, surface, 0, 0, surface.get_width(), surface.get_height()
        )

    yield read


@pytest.fixture(scope="session")
def x11_region(
    gtk_display,
) -> Iterator[Callable[[object, int, int, int, int], Counter[Colour]]]:
    """Read the colours of one rectangle of an X11 drawable.

    The window shows the whole app, so a check about one pane needs the pane's
    own rectangle, not the colours of every pixel on the screen.
    """
    x11 = _x11_library()

    def read(
        surface: object, x: int, y: int, width: int, height: int
    ) -> Counter[Colour]:
        return _read_colours(x11, surface, x, y, width, height)

    yield read


@pytest.fixture
def project_theme(gtk_display) -> Iterator[Callable[[], None]]:
    """Put ``theme.css`` on the display for one test.

    The application's stylesheet is loaded by ``volna.main`` at start-up; a
    widget test has to do it itself, or the widgets are painted by the GTK
    theme alone. The provider is taken off the display afterwards, so the next
    test starts from the same state as this one did.
    """
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
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
