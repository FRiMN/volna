# Summary

The «Вид» panel had two defects, both reproduced and measured on a real XFCE/X11 session:

- it appeared in two phases — GTK positions a popup when it is presented, and the offset was computed in the `show` handler, i.e. after that, so the panel showed up centred on the trigger and was re-presented 146 px to the left (`map 0×0 → alloc 490×508`);
- after closing, the next click on the trigger did nothing — GTK builds the popup surface around the drop shadow, and the shadow's transparent margins covered the trigger completely, so the click never reached the widget (open → close → nothing → open, repeating).

Both are fixed: the panel is presented once, where it stays, and the trigger stays fully clickable.

# Root cause

**Flicker.** `ViewPanel._on_show()` computed the alignment offset (`(size_request − trigger_width) // 2`) and applied it with `Gtk.Popover.set_offset()`. GTK positions the popup in `gtk_popover_show()`/`gtk_popover_map()`, which run *before* the user handler of the `show` signal; the offset therefore triggered `gtk_widget_queue_resize()` and a second presentation of an already mapped popup. Measured: `map 0×0 @(24,9)` → `show, offset (146,4)` → `alloc 490×508 @(170,13)`.

**Lost click.** A CSS `box-shadow` on the popover's contents is not only painted: GTK adds the blur as transparent margins of the *popup surface*. With `0 12px 32px` the surface grew by 45 px per side (33 px on top), and the trigger button lay entirely inside it. The click was delivered to the popup surface, not to the button, so the button never toggled. The trigger's `active` state was never out of sync with the panel — the click itself was lost. A minimal GTK reproducer without the shadow does not lose the click, which confirms the coupling.

# Impact

- every second click on «Вид» was swallowed (open → close → nothing → open), which made the panel feel broken;
- the panel visibly jumped from the centre of the trigger to its final position on every open;
- the trigger button was hidden behind the shadow margin of the open panel.

# Changes

- `src/volna/view_panel/panel.py`
  - the geometry is part of the popup layout from the start: `set_halign(Gtk.Align.START)` aligns the content box with the trigger's left edge (GTK centres the popup otherwise), `set_offset(0, 4)` keeps the design's gap; both are set at construction and never touched while the panel is open;
  - `_on_show()` no longer changes the geometry — only the tooltip and the snapshot sync;
  - `_on_closed()` restores the tooltip and syncs the trigger's state with the panel (`active` follows the panel, design 05 §2).
- `src/volna/theme.css` — the panel's drop shadow is now `0 2px 4px rgba(0,0,0,.45)`: the blur stays inside the 4 px gap, so the popup surface starts at the trigger's bottom edge and the button stays fully clickable.
- `design/spec/02-design-tokens.md`, `design/spec/03-layout.md`, `design/view-panel.md` — the shadow deviation and the positioning mechanism are recorded with the reason.
- `tests/test_view_panel.py` — three regression tests (see below) plus the X11 helpers they need.

# Tests

- `test_popover_is_left_aligned_with_the_trigger` — the content box starts at the trigger's left edge; the layout (`halign`, `offset`) is constant.
- `test_the_popover_surface_does_not_cover_the_trigger` — the popup surface starts at the trigger's bottom edge and no lower than the 4 px gap (the root cause of the lost click).
- `test_the_panel_is_not_moved_after_it_is_shown` — the surface keeps the position it was presented with (the flicker).
- `test_the_trigger_state_follows_the_panel` — `active` describes the panel.

All three fail on the previous code and pass on the fixed one. Full suite: `243 passed` (`uv run pytest`), `ruff check`/`ruff format --check` clean.

Verified manually on the real session (XFCE/X11, `xfwm4`): the click sequence is now open → close → open → close; Escape, an outside click and hovering (with the tooltip visible) behave as before.

# Trade-offs / residual risk

- The panel's drop shadow is smaller than the mock's (`0 2px 4px` instead of `0 12px 32px`). In GTK the blur is part of the popup surface, so a large blur cannot coexist with a 4 px gap: the surface would cover the trigger and eat its clicks. The deviation is documented in the design specs; if the visual weight of the shadow matters more, the gap has to grow instead — that is a design decision, not a bug fix.
- The click that *closes* the panel (a click outside it) is still consumed by the popover's grab — standard GTK behaviour for `autohide` popovers, unchanged by this PR.
- The lost click could not be reproduced on the Xvfb display the test suite uses (no window manager), so the regression is covered by the geometry assertions instead of an end-to-end click test.
- OWASP analysis is intentionally deferred for this PR (no security surface: CSS and widget geometry only).

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
