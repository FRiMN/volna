# Summary

Implements design/view-modes.md: the two missing listing modes, «Столбцы» and «Значки», and the separation of all three modes so that a future fourth one is one module plus one registry line.

The listing data is unchanged — a mode is a difference in widget layout, not in data. The tab owns the dispatch, the View panel gains a «Режим просмотра» radio group, and the mode survives a restart through the already-persisted `view_mode` field (no schema change).

# Root cause

Not a defect fix — a feature. The design groundwork (2026-11-16, `docs(view): design the listing view modes and their separation`) found that the domain layer was already mode-ready (`ViewMode`, `ViewSettings.view_mode`, `preferred_mode()`, `schema_version = 1` with `view_mode` persisted), while the app had exactly one renderer (`DetailsView`) hard-wired into `DirectoryTab` with `Row` living inside it, and no UI to choose a mode. The `V1_CAPABILITIES.modes = {DETAILS}` gate silently normalized every stored mode back to «Подробности».

# Impact

- Users get two new ways to see the same listing: a tile grid («Значки») and horizontally scrolling columns («Столбцы»), both per-tab, inheriting on new tabs, persisted on close like the other display settings.
- Switching a mode is a display change: no rescan, no «Сканирование…», `generation` untouched, counters unchanged.
- The window never resizes because of a mode: the listing scrolls inside the band (measured on GTK 4.14.5 under Xvfb, all modes stay exactly 1800×1125).
- No security surface added: rendering, wheel handling and static SVG/CSS assets only; config parsing is unchanged.

# Changes

- `src/volna/views/` — restructured into one module per mode behind a shared contract:
  - `base.py` — `ListingView` (widget / render / apply / reset_scroll) and `Section` (the seam for future date grouping: the tab always builds one unnamed section today);
  - `item.py` — `ListingItem`, the shared item model (moved out of `details.py`, previously `Row`);
  - `registry.py` — `MODE_VIEWS` / `VIEWS_BY_MODE`, the only list of modes (explicit tuple, no importlib);
  - `details.py` — adapted to the contract, visually unchanged;
  - `icons.py` — `Gtk.GridView` tile grid; the grid's default 7-column cap is lifted, the tile width drives the count;
  - `columns.py` — a horizontal `Gtk.ListView` whose model holds *columns* (chunks of 6), so GTK virtualizes whole columns; double click opens a folder.
- `src/volna/tab.py` — the mode dispatch: a `Gtk.Stack` with one view per available mode, exactly one visible; switching clears the outgoing view (it must not hold the old listing), resets the new one's scroll and re-renders from the model.
- `src/volna/view_panel/settings/view_mode.py` — new setting feature: a radio group built from `ViewCapabilities.modes`, labels and order from `display` (`mode.label`, `MODE_ORDER`); hidden entirely when only one mode is available.
- `src/volna/display/settings.py` — `ViewMode.label`, `MODE_ORDER`, `DEFAULT_CAPABILITIES` (renamed from `V1_CAPABILITIES`) now offering all three modes; `MODE_PREFERENCE` still drives the fallback for a stored mode this build cannot render.
- `src/volna/main.py`, `src/volna/window.py` — follow the rename; the GTK version gate proved unnecessary (horizontal `Gtk.ListView` and `GridView:min/max-columns` exist since 4.0 — verified against the GTK sources), so the minimum stays «GTK 4».
- `src/volna/icons/50,60,75/` — glyph variants for tile and column icons (`px(40)/px(48)/px(60)`); vector copies with a different declared size.
- `src/volna/theme.css` — tile/column metrics from the mockup across wide/compact/density; scrolled windows paint the editor canvas (previously they fell back to the default light background under the tab content).
- `tests/test_icons.py` — the centering budget scales with the declared size: glyph geometry is size-independent, so an absolute pixel budget judged the same artwork stricter the bigger the icon.
- `tests/test_view_modes.py` — new: registry contract, labels/order, panel section presence/absence, per-tab modes, inheritance, persistence across restart, unavailable modes not offered, activation through the grid, wheel panning.
- `tests/test_view_panel.py`, `tests/test_view_settings.py`, `tests/test_window.py` — follow the rename and the dispatcher (`_views[ViewMode.DETAILS]` instead of the former single `_view`).
- `design/view-modes.md` — implementation status, measured facts (horizontal ListView behavior, GridView column fitting, two-line label clamp, wheel behavior), acceptance checklist.

# Tests

- 258 passed, 3 deselected (`uv run pytest`); `ruff check` / `ruff format --check` clean.
- New suite `tests/test_view_modes.py` (13 tests): registry covers every `ViewMode` with unique classes; the panel section lists the available modes in mockup order and disappears with one mode; switching through the real window shows the same names in every mode without a rescan; modes are per-tab and inherited; the mode survives a restart; unavailable modes are neither offered nor created; double click in «Значки» opens a folder.
- Wheel (follow-up commit): either wheel axis pans «Столбцы» horizontally via a `Gtk.EventControllerScroll` in the capture phase (the scrolled window's own bubble-phase handler would otherwise consume the event), clamped to the range, the vertical axis untouched.
- Verified end-to-end under Xvfb with real X11 wheel events (XTest): four notches moved `hadjustment` 0 → 250 while `vadjustment` stayed 0 even though the vertical range overflowed (617 > 372).
- Visual check: screenshots of all three modes in the running app (Xvfb, theme loaded, 1800×1125) compared against the mockup's ungrouped states.

# Trade-offs / residual risk

- Flat modes only: the mockup's signature «columns grouped by date» requires date grouping, which the owner deferred to the next iteration; the `Section` seam is already in the contract, so no rework is expected there.
- The wheel never scrolls the columns vertically (by design, either axis pans horizontally); in a very short window the six rows are reached with the vertical scrollbar instead.
- Column width relies on the design's minimum widths in CSS plus a name character budget (`max_width_chars`), because GTK CSS has no `max-width`; an unusually long unbreakable token still ellipsizes as designed.
- Icon sizes 50/60/75 are generated copies of the 16 px geometry (size-independent viewBox); the icon test suite guards declared size, ink bounds and optical centering for every size.
- The 100k-entry non-functional test (mode switch under ~200 ms) is still an open acceptance item in design/view-modes.md §9; the view clears the outgoing mode's store, so memory does not accumulate across switches, but the timing measurement is not automated yet.
- OWASP analysis is intentionally deferred for this PR per the owner's request (no security surface: rendering, wheel handling and static assets only; config parsing unchanged).

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
