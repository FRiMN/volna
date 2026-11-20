"""Preset dialogs: save, rename, delete (design/spec/04 §2.2–2.3, 05 §18.6).

Each dialog is its own small modal window, not an overlay inside the main one:
a whole-window overlay with a dimmed backdrop made GTK re-snapshot the entire
main window on every open and close, which on a large window is a visible
stall before the panel comes back. A window repaints only its own card.

A dialog only collects a name or a confirmation; the validation text it shows
comes from the callback, so the rules stay in the model (``display.presets``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ..display.presets import MAX_NAME_LENGTH, PresetError, clean_name  # noqa: E402
from ..size import px  # noqa: E402


def _button(text: str, css: str) -> Gtk.Button:
    button = Gtk.Button(label=text)
    button.add_css_class("volna-preset-dialog-button")
    button.add_css_class(css)
    return button


def _card(parent: Gtk.Window) -> tuple[Gtk.Window, Gtk.Box]:
    """The dialog's own window and the card filling it."""
    window = Gtk.Window()
    window.set_transient_for(parent)
    window.set_modal(True)
    window.set_decorated(False)
    window.set_resizable(False)
    window.set_destroy_with_parent(True)
    window.add_css_class("volna-preset-dialog-window")
    window.set_visible(False)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("volna-preset-dialog")
    window.set_child(card)
    return window, card


def _escape_cancels(widget: Gtk.Widget, on_cancel: Callable[[], None]) -> None:
    keys = Gtk.EventControllerKey()

    def pressed(
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            on_cancel()
            return True
        return False

    keys.connect("key-pressed", pressed)
    widget.add_controller(keys)


class _NameDialog:
    """Shared anatomy of a name prompt: title, entry, hint, Cancel/Confirm.

    Subclasses supply the words and the hint; ``on_save`` returning an error
    text keeps the dialog open and shows that text, so validation never closes
    the dialog on the user.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        *,
        title: str,
        confirm_label: str,
        with_existing: bool,
        default_hint: str | None,
    ) -> None:
        self._on_save: Callable[[str], str | None] | None = None
        self._on_done: Callable[[], None] | None = None
        self._error: str | None = None
        self._default_hint = default_hint
        self._original = ""
        self._root, card = _card(parent)

        heading = Gtk.Label(label=title)
        heading.set_halign(Gtk.Align.START)
        heading.add_css_class("volna-preset-dialog-title")
        card.append(heading)

        caption = Gtk.Label(label="Название пресета")
        caption.set_halign(Gtk.Align.START)
        caption.add_css_class("volna-preset-dialog-label")
        card.append(caption)

        self._entry = Gtk.Entry()
        self._entry.add_css_class("volna-preset-dialog-entry")
        self._entry.set_max_length(MAX_NAME_LENGTH)
        self._entry.connect("changed", self._on_changed)
        self._entry.connect("activate", lambda _e: self._confirm())
        _escape_cancels(self._entry, self.cancel)
        card.append(self._entry)

        self._existing: Gtk.Box | None = None
        self._existing_name_list: list[str] = []
        if with_existing:
            existing_caption = Gtk.Label(label="Или выберите существующий")
            existing_caption.set_halign(Gtk.Align.START)
            existing_caption.add_css_class("volna-preset-dialog-label")
            card.append(existing_caption)

            self._existing = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            self._existing.add_css_class("volna-preset-list")
            # The design caps this list (04 §2.2, max-height 144 px); without
            # the cap a library of presets made the dialog taller than the
            # screen and pushed its buttons out of reach.
            self._existing_scroller = Gtk.ScrolledWindow()
            self._existing_scroller.add_css_class("volna-preset-list-scroller")
            self._existing_scroller.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
            )
            self._existing_scroller.set_propagate_natural_height(True)
            self._existing_scroller.set_max_content_height(px(144))
            self._existing_scroller.set_child(self._existing)
            card.append(self._existing_scroller)

        self._hint = Gtk.Label()
        self._hint.set_halign(Gtk.Align.START)
        self._hint.set_wrap(True)
        self._hint.add_css_class("volna-preset-hint")
        self._hint.set_visible(default_hint is not None)
        if default_hint is not None:
            self._hint.set_text(default_hint)
        card.append(self._hint)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        self._cancel_button = _button("Отмена", "is-cancel")
        self._cancel_button.connect("clicked", lambda _b: self.cancel())
        self._confirm_button = _button(confirm_label, "is-primary")
        self._confirm_button.connect("clicked", lambda _b: self._confirm())
        buttons.append(self._cancel_button)
        buttons.append(self._confirm_button)
        card.append(buttons)

        _escape_cancels(card, self.cancel)
        _escape_cancels(self._root, self.cancel)

    # -- public surface ---------------------------------------------------

    @property
    def widget(self) -> Gtk.Widget:
        """The card; tests and the window walk it, never the window node."""
        return self._root.get_child()

    @property
    def is_open(self) -> bool:
        return self._root.get_visible()

    def close(self) -> None:
        if not self._root.get_visible():
            return

        self._on_save = None
        done = self._on_done
        self._on_done = None
        # The owner brings the panel back while this window still covers it,
        # so the panel is on screen the moment the dialog disappears.
        if done is not None:
            done()
        self._root.set_visible(False)

    def cancel(self) -> None:
        self.close()

    # -- subclass hooks ---------------------------------------------------

    def _can_confirm(self, typed: str) -> bool:
        return bool(typed)

    def _hint_for(self, typed: str) -> tuple[str | None, bool]:
        """The hint text and whether it is a warning."""
        if self._error is not None:
            return self._error, True

        return None, False

    # -- internals --------------------------------------------------------

    def _open(
        self,
        suggested: str,
        on_save: Callable[[str], str | None],
        on_done: Callable[[], None],
        *,
        existing: Sequence[str] = (),
    ) -> None:
        self._on_save = on_save
        self._on_done = on_done
        self._error = None
        self._entry.set_text(suggested)
        self._rebuild_existing(existing)
        self._refresh()
        self._root.present()
        # A mapped window is required before focus can land in the entry.
        GLib.idle_add(lambda: self._entry.grab_focus() and False)
        self._entry.select_region(0, -1)

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        # Typing supersedes a rejected name: the error is about the old text.
        self._error = None
        self._refresh()

    def _rebuild_existing(self, names: Sequence[str]) -> None:
        if self._existing is None:
            return

        child = self._existing.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._existing.remove(child)
            child = following

        self._existing_name_list = list(names)
        for name in names:
            row = Gtk.Button()
            row.add_css_class("volna-preset-existing-row")
            row.set_halign(Gtk.Align.FILL)

            text = Gtk.Label(label=name)
            text.set_xalign(0)
            text.set_halign(Gtk.Align.START)
            text.set_hexpand(True)
            row.set_child(text)

            row.connect("clicked", self._pick_existing, name)
            self._existing.append(row)

    def _pick_existing(self, _button: Gtk.Button, name: str) -> None:
        self._entry.set_text(name)
        self._entry.grab_focus()
        self._entry.select_region(0, -1)

    def _existing_names(self) -> list[str]:
        return list(self._existing_name_list)

    def _typed_name(self) -> str:
        return self._entry.get_text().strip()

    def _refresh(self) -> None:
        typed = self._typed_name()
        self._confirm_button.set_sensitive(self._can_confirm(typed))

        text, warning = self._hint_for(typed)
        self._hint.set_text(text or "")
        self._hint.set_visible(bool(text))
        self._hint.remove_css_class("is-warning")
        if warning:
            self._hint.add_css_class("is-warning")

    def _confirm(self) -> None:
        if self._on_save is None:
            return

        try:
            name = clean_name(self._entry.get_text())
        except PresetError:
            self._refresh()
            return

        error = self._on_save(name)
        if error is None:
            self.close()
            return

        self._error = error
        self._refresh()


class SaveDialog(_NameDialog):
    """Name entry + list of existing presets; Enter saves, Esc cancels."""

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            parent,
            title="Сохранить пресет",
            confirm_label="Сохранить",
            with_existing=True,
            default_hint="Новый пресет будет добавлен в список",
        )

    def open(
        self,
        suggested: str,
        existing: Sequence[str],
        on_save: Callable[[str], str | None],
        on_done: Callable[[], None],
    ) -> None:
        """Show the dialog; ``on_save`` returns an error text or ``None`` (saved)."""
        self._open(suggested, on_save, on_done, existing=existing)

    def _hint_for(self, typed: str) -> tuple[str | None, bool]:
        if self._error is not None:
            return super()._hint_for(typed)

        if typed and any(
            name.casefold() == typed.casefold() for name in self._existing_names()
        ):
            return "Пресет с таким именем будет перезаписан", True

        return self._default_hint, False


class RenameDialog(_NameDialog):
    """Renames one custom preset; the list of presets is not needed here."""

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            parent,
            title="Переименовать пресет",
            confirm_label="Переименовать",
            with_existing=False,
            default_hint=None,
        )

    def open(
        self,
        current: str,
        on_save: Callable[[str], str | None],
        on_done: Callable[[], None],
    ) -> None:
        """``on_save`` returns an error text or ``None`` (renamed)."""
        self._original = current.strip()
        self._open(current, on_save, on_done)

    def _can_confirm(self, typed: str) -> bool:
        # Confirming an unchanged name would write nothing, so it stays disabled.
        return bool(typed) and typed != self._original


class DeleteDialog:
    """Confirmation with Cancel focused by default; Esc and Cancel dismiss it."""

    def __init__(self, parent: Gtk.Window) -> None:
        self._on_confirm: Callable[[], None] | None = None
        self._on_done: Callable[[], None] | None = None
        self._root, card = _card(parent)

        title = Gtk.Label(label="Удалить пресет?")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("volna-preset-dialog-title")
        card.append(title)

        self._text = Gtk.Label()
        self._text.set_halign(Gtk.Align.START)
        self._text.set_wrap(True)
        self._text.set_xalign(0)
        self._text.add_css_class("volna-preset-dialog-text")
        card.append(self._text)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        self._cancel_button = _button("Отмена", "is-cancel")
        self._cancel_button.connect("clicked", lambda _b: self.cancel())
        self._delete_button = _button("Удалить", "is-danger")
        self._delete_button.connect("clicked", lambda _b: self._confirm())
        buttons.append(self._cancel_button)
        buttons.append(self._delete_button)
        card.append(buttons)

        _escape_cancels(card, self.cancel)
        _escape_cancels(self._root, self.cancel)

        # Enter confirms (design 04 §2.3), while keyboard focus stays on «Отмена»
        # so Space and Esc back out: without a default widget Enter activated the
        # focused button — it cancelled the deletion the user had just asked for.
        self._root.set_default_widget(self._delete_button)

    @property
    def widget(self) -> Gtk.Widget:
        """The card; tests and the window walk it, never the window node."""
        return self._root.get_child()

    @property
    def is_open(self) -> bool:
        return self._root.get_visible()

    def open(
        self,
        name: str,
        on_confirm: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        """``on_confirm`` runs only on «Удалить»; ``on_done`` after any close."""
        self._on_confirm = on_confirm
        self._on_done = on_done
        self._text.set_text(
            f"Пресет «{name}» будет удалён. Это действие нельзя отменить."
        )
        self._root.present()
        # Enter must confirm the deletion (design 04 §2.3), and GTK4 Enter
        # activates the *focused* button — activate_default() follows the focus
        # too. So the destructive button takes the focus while it is open; Esc
        # and «Отмена» are the ways out, and the dialog is a confirmation the
        # user opened deliberately.
        GLib.idle_add(lambda: self._delete_button.grab_focus() and False)

    def close(self) -> None:
        if not self._root.get_visible():
            return

        self._on_confirm = None
        done = self._on_done
        self._on_done = None
        if done is not None:
            done()
        self._root.set_visible(False)

    def cancel(self) -> None:
        self.close()

    def _confirm(self) -> None:
        callback = self._on_confirm
        self._on_confirm = None
        self.close()
        if callback is not None:
            callback()


__all__ = ["DeleteDialog", "RenameDialog", "SaveDialog"]
