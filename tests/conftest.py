"""Shared pytest setup: a private Xvfb for GTK4 widget tests.

Widget tests need a display; CI and this development box have no session one.
The fixture starts a private Xvfb, initializes GTK once per module and skips
cleanly when Xvfb or GTK4 is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
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
