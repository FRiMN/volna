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
import time
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
        import gi

        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11

        display = x11.XOpenDisplay(None)
        if not display:
            pytest.skip("cannot open the X display")

        try:
            xid = GdkX11.X11Surface.get_xid(surface)
            width = surface.get_width()
            height = surface.get_height()
            image = x11.XGetImage(display, xid, 0, 0, width, height, 0xFFFFFFFF, 2)
            if not image:
                pytest.skip("XGetImage failed")

            header = image.contents
            raw = ctypes.string_at(header.data, header.bytes_per_line * header.height)

            def shift(mask: int) -> int:
                return (mask & -mask).bit_length() - 1

            red_shift = shift(header.red_mask)
            green_shift = shift(header.green_mask)
            blue_shift = shift(header.blue_mask)
            step = header.bits_per_pixel // 8

            colours: Counter[tuple[int, int, int]] = Counter()
            for y in range(header.height):
                row = raw[y * header.bytes_per_line :]
                for x in range(header.width):
                    offset = x * step
                    pixel = int.from_bytes(row[offset : offset + step], "little")
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

    yield read
