"""Application entry point for Volna."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gdk, GLib, Graphene, Gtk  # noqa: E402

APP_ID = "io.github.frimn.volna"


class VolnaApplication(Gtk.Application):
    def __init__(self, *, screenshot: str | None = None) -> None:
        super().__init__(application_id=APP_ID)
        self.screenshot = screenshot
        self.window = None
        self.set_accels_for_action("win.new-tab", ["<Control>t"])
        self.set_accels_for_action("win.close-tab", ["<Control>w"])
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)

    def _on_startup(self, _application: Gtk.Application) -> None:
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)

        css = resources.files("volna").joinpath("theme.css").read_text(encoding="utf-8")
        provider = Gtk.CssProvider()
        try:
            provider.load_from_string(css)
        except AttributeError:  # GTK < 4.12
            provider.load_from_data(css.encode("utf-8"))

        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _on_activate(self, _application: Gtk.Application) -> None:
        from .window import MainWindow

        self.window = MainWindow(application=self)
        self.window.present()
        if self.screenshot:
            GLib.timeout_add(700, self._capture)

    def _capture(self) -> bool:
        content = self.window.get_child()
        width = content.get_width()
        height = content.get_height()
        paintable = Gtk.WidgetPaintable.new(content)
        snapshot = Gtk.Snapshot.new()
        paintable.snapshot(snapshot, width, height)
        node = snapshot.to_node()
        renderer = self.window.get_native().get_renderer()
        viewport = Graphene.Rect().init(0, 0, width, height)
        texture = renderer.render_texture(node, viewport)
        texture.save_to_png(str(Path(self.screenshot).expanduser()))
        self.quit()
        return False


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    screenshot = None
    if "--screenshot" in args:
        index = args.index("--screenshot")
        if index + 1 >= len(args):
            raise SystemExit("--screenshot requires a path")
        screenshot = args[index + 1]
        del args[index : index + 2]
    application = VolnaApplication(screenshot=screenshot)
    return application.run(args)
