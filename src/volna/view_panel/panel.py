"""The View panel: toolbar trigger, popover and composition of setting features.

The panel owns no state and knows no individual setting. It groups the
registered :class:`SettingFeature` classes by section, forwards their
declarative change dicts to ``update(**changes)`` and re-syncs the controls from
the active-tab snapshot. Adding a setting is a new module in ``settings/`` plus
one registry line — this file does not change.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ..display import ViewCapabilities, ViewSettings  # noqa: E402
from ..glyph import icon  # noqa: E402
from ..size import px  # noqa: E402
from .controls import footer, section, separator  # noqa: E402
from .settings import SETTING_FEATURES  # noqa: E402
from .settings.base import SettingFeature, SettingsSection  # noqa: E402

# The popover hangs 4 px below the trigger and starts at its left edge.
# GTK positions the popup when it is presented, so both values belong to the
# layout *before* the first show: a later change makes GTK re-present the open
# popup and the panel visibly jumps (design 02 §8: the popover appears at once,
# without a size animation).
_POPOVER_GAP = 4
_MAX_CONTENT_HEIGHT = 820


class ViewPanel:
    """Trigger button + popover composed from the registered setting features."""

    def __init__(
        self,
        *,
        settings: Callable[[], ViewSettings],
        update: Callable[..., bool],
        capabilities: ViewCapabilities,
        setting_features: Sequence[type[SettingFeature]] | None = None,
    ) -> None:
        self._settings = settings
        self._update = update
        self._capabilities = capabilities
        self._syncing = False

        factories = SETTING_FEATURES if setting_features is None else setting_features
        self._settings_features = [factory(self._on_change) for factory in factories]
        self._settings_features = [
            feature
            for feature in self._settings_features
            if feature.available(self._capabilities)
        ]

        self._popover = self._build_popover()
        self._button = self._build_trigger()
        self._button.set_popover(self._popover)
        self._popover.connect("show", self._on_show)
        self._popover.connect("closed", self._on_closed)
        self.sync()

    # -- public surface -------------------------------------------------

    def trigger(self) -> Gtk.MenuButton:
        return self._button

    @property
    def popover(self) -> Gtk.Popover:
        return self._popover

    def open(self) -> None:
        self._button.set_active(True)

    def close(self) -> None:
        self._button.set_active(False)

    def sync(self) -> None:
        """Reflect the current snapshot; never reports changes back to the window."""
        snapshot = self._settings()

        self._syncing = True
        try:
            for feature in self._settings_features:
                feature.sync(snapshot)
        finally:
            self._syncing = False

    # -- construction ---------------------------------------------------

    def _build_trigger(self) -> Gtk.MenuButton:
        button = Gtk.MenuButton()
        button.add_css_class("volna-view-trigger")
        button.add_css_class("volna-menu-button")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text("Вид")
        button.update_property([Gtk.AccessibleProperty.LABEL], ["Вид"])

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=px(6))
        row.add_css_class("volna-view")
        row.set_size_request(-1, px(28))
        row.append(icon("columns", px(16)))

        name = Gtk.Label(label="Вид")
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.add_css_class("volna-view-label")
        row.append(name)
        row.append(icon("down", px(16), dim=True))

        button.set_child(row)
        return button

    def _build_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("volna-view-popover")
        popover.set_has_arrow(False)
        popover.set_size_request(px(320), -1)
        # Left-align the content box with the trigger (GTK centres the popup on
        # its anchor otherwise) and keep the design's 4 px gap below it. Both
        # are part of the popup layout and stay constant, so the panel is
        # presented once, in its final place.
        popover.set_halign(Gtk.Align.START)
        popover.set_offset(0, _POPOVER_GAP)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.add_css_class("volna-view-body")
        for title, features in self._sections():
            container, body = section(title)
            for feature in features:
                body.append(feature.widget())
            content.append(container)
            content.append(separator())
        content.append(footer("Изменения применяются сразу"))

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(px(_MAX_CONTENT_HEIGHT))
        scroller.set_propagate_natural_height(True)
        scroller.set_child(content)
        popover.set_child(scroller)

        return popover

    def _sections(self) -> list[tuple[SettingsSection | str, list[SettingFeature]]]:
        """Group features by section, in first-seen order; the section is the title."""
        grouped: dict[SettingsSection | str, list[SettingFeature]] = {}
        for feature in self._settings_features:
            grouped.setdefault(feature.section, []).append(feature)

        return list(grouped.items())

    # -- popover lifecycle ----------------------------------------------

    def _on_show(self, *_args: object) -> None:
        # The tooltip would hang over the open panel (same as the main menu).
        self._button.set_tooltip_text(None)
        self.sync()

    def _on_closed(self, *_args: object) -> None:
        self._button.set_tooltip_text("Вид")
        # The panel can dismiss itself (a click outside it) and the trigger
        # keeps its pressed state until the next click — that click then only
        # clears the button instead of opening the panel. The trigger's state
        # follows the panel (design 05 §2: "active синхронизируется").
        self._button.set_active(False)

    # -- user input -----------------------------------------------------

    def _on_change(self, changes: dict[str, object]) -> None:
        if self._syncing:
            return

        self._update(**changes)
        self.sync()
