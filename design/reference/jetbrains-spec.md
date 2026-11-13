# JetBrains «New UI» — reference specification for the «Волна» file manager

> **Scope:** panel layout anatomy + general design language of JetBrains **New UI**
> (IntelliJ IDEA / PyCharm 2023.2 → 2025.x, Dark + Light themes).
> The client wants to **borrow the panel arrangement and the look**, not IDE functionality.
> Every layout metric below is expressed in **CSS px** (logical px), not device px.
>
> **Confidence legend**
> - **[V] Verified** — measured by pixel-analysis of official JetBrains screenshots (2×, 2068×1448 device px = 1034×724 CSS px) or read from official JetBrains source pages.
> - **[D] Documented** — stated in JetBrains UI Guidelines / IDE help (value taken from text, not measured).
> - **[A] Approximate** — reconstructed from community-documented values, visual proportion, or interpolation between measured landmarks. Safe to use, but do not market it as exact JetBrains value.
>
> Version note: the layout/metrics were measured on the official **2023.2-era** New UI capture, which JetBrains still ships unchanged in the 2026.3 docs (`new_ui_dark_theme.png` is byte-identical between 2023.2 and 2026.3 doc paths). 2025.1+ adds the optional **Islands** theme variant — see §5.

---

## 0. TL;DR for the designer

1. **Two surfaces, no more:** `#1e1f22` (editor/workspace) and `#2b2d30` (all chrome: toolbar, panels, stripes, status bar). Dark theme is built on exactly this pair; Light theme is `#ffffff` canvas + `#f7f8fa` chrome + a **dark `#27282d` window header** (default Light theme ships a dark toolbar — that is the single most recognizable JetBrains Light trait).
2. **40 px chrome rhythm:** main toolbar = 40, tool-window header row = 40, editor tab strip = 40, stripe width = 40. Data rows inside panels = **24**. Everything else is 1 px hairlines.
3. **The editor tab strip and the tool-window headers share one continuous 40 px band** across the window — a signature JetBrains arrangement (not a separate toolbar above the tabs).
4. **Vertical icon-only stripes** (40 px, 20 px icons) are the primary tool-window switcher; labels are hidden by default and appear as tooltips / optional names under icons.
5. **Accent blue is state only:** 2–3 px active-tab underline, focus, selection, links. Never decorative, never large fills.
6. **Outline two-tone icons**, neutral `#CED0D6`-on-dark stroke with a single accent-colored node; 16×16 grid (20×20 for stripe buttons), 1 px strokes.
7. **Flat, dense, calm:** no gradients, no shadows, no glass — depth comes exclusively from the two surface tones and 1 px dividers.
8. **Selection is a rounded 4 px full-row pill**, neutral `#43454a` when the panel is unfocused, blue-tinted when focused.
9. **Status bar = navigation + telemetry:** breadcrumb/navigation on the left, widgets (cursor pos, line separator, encoding, indent) on the right, 28 px tall.
10. For a file manager: keep the **3-column + bottom console + status bar** skeleton, 24 px rows, 40 px chrome, 4 px radii; move the *content* (files, transfer queue) into the IDE's slots, do **not** copy IDE metaphors (project tree = folder tree, editor tab = open folder/place tab, Git tool window = transfers/activity log).

---

## 1. Panel layout anatomy

### 1.1 Reference window (measured)

Official capture `new_ui_dark_theme.png`, 2068×1448 device px on a 2× display = **1034×724 CSS px** window.
Measured bands (native px / 2 = CSS px):

| # | Band | CSS height | Notes |
|---|------|-----------:|-------|
| 1 | **Main toolbar / window header** | **40** | measured 78–80 native px; contains macOS traffic lights (left, ~68 px inset), project widget, VCS widget, run widget + run/debug icons + kebab, then right cluster: user, search, settings |
| 2 | Divider under toolbar | **1** | `#1e1f22` (darker than both surfaces) |
| 3 | **Header band: tool-window headers + editor tab strip** | **40** | one continuous band across the window; tool-window part `#2b2d30`, editor/tab-strip part `#1e1f22` |
| 4 | Divider under header band | **1** | `#393b40` |
| 5 | **Workspace row**: left stripe + left tool window + editor + right stripe | **352** | content area; left tool window 300 wide, editor 654 wide incl. gutter |
| 6 | Divider above bottom tool window | **1** | `#1e1f22` |
| 7 | **Bottom tool window** (full width between stripes) | **259** | header row 40 + content ~219; in the captured window this is user-resized to ≈36 % of window height |
| 8 | Divider above status bar | **1** | `#1e1f22` |
| 9 | **Status bar** | **28** | measured 26.5–29 across captures → spec **28** |
| — | **Total** | **≈724** | 40+1+40+1+352+1+259+1+28 = 723 (+1 rounding) |

Horizontal metrics (CSS px): left stripe **40** · left tool window **300** (user-resized; docs default = 20 % of window width, min 200×500 **[D]**) · editor **654** · right stripe **40** · right tool window **300–400** when opened.

### 1.2 ASCII wireframe — full window with region sizes

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MAIN TOOLBAR / WINDOW HEADER                                                    40 px  │
│ (● ● ●) [intellij-samples ⌄]  [⑂ main ⌄]  ───────────  [UserTestData ⌄] ▶ 🐞 ⋮   👤 🔍 ⚙ │
├─────┬───────────────────┬──────────────────────────────────────────────────┬────────────┤
│  40 │ TOOL WINDOW HDR   │ TAB STRIP                                   40 px │   40 px    │
│  px │ ⌄ Project         │ [◉ AsyncSchedulerExample.java  ✕]                │  STRIPE    │
│  S  │                   │ ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔ 3 px #4276E8 underline  │  (vertical │
│  T  ├───────────────────┼──────────────────────────────────────────────────┤  tool      │
│  R  │ Project tree      │ EDITOR / WORKSPACE                         352 px │  windows)  │
│  I  │ ▸ debugging       │  gutter 40 │ content                         │            │
│  P  │ ▸ editing         │  12 ▶ │ public static void main(...)          │  🔔         │
│  E  │ ▸ flow            │  13   │   final var messageQueue = ...        │  🟣 AI      │
│     │ row 24 px         │  14   │   new Thread(() -> {                 │            │
│  ── │ indent 16 px      │       │ ...                                   │            │
│  ●  │                   │       │                                       │            │
│  20 │ 300 px            │ scrollbar 8 px                          scrollbar 8 px          │
├─────┴───────────────────┴──────────────────────────────────────────────────┴────────────┤
│ BOTTOM TOOL WINDOW — header 40 px:  [ Git ] [ Log ]      ← tabs     actions →  259 px    │
│ tool-window toolbar (search field + filters) ≈32 px                                     │
│ content ~219 px: table/list (no top border when scrolled to top)                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ STATUS BAR 28 px:  ‹ ava-samples › src › main › java › com › jetbrains › AsyncExample   │
│                    …         24:44   LF   UTF-8   4 spaces   ⌄                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Zooms — header, tab, stripe (px paddings)

**Tool-window header (40 px):**

```
┌──────────────────────────────────────────────────────────────────┐  40 px row
│ ⌄  Project                            [ ⟲ ]  [ ⋯ ]  [ — ]        │
│ ↑  ↑ title: Inter 13 semibold        ↑ 16×16 icons, 24×24 hit    │
│ │  8 px left padding                 8 px gaps, 8 px right pad   │
│ └─ view-options chevron (16×16), 4 px after title                │
└──────────────────────────────────────────────────────────────────┘
```
- Title left-aligned; **title-case** (not uppercase) **[D]**.
- Overflow: if the header is too narrow, action icons collapse under a trailing **`»` chevron** (toolbar overflow rule **[D]**).
- Planned actions: pin/collapse tool window, view options, hide, overflow. Pinning/floating is an IDE behavior — for the file manager keep the slots, drop the IDE semantics.
- Badges (e.g. "new changes") = small colored dot/badge over or next to the icon; the icon glyph itself never changes color for content updates **[D]**.

**Editor tab strip (40 px row) — 2023–2024 style:**

```
│ ◉  AsyncSchedulerExample.java   ✕ │  ✕
       ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
```
- Row height **40**; tab is full-height, **flat — no pill, background identical to the editor** (`#1e1f22`) **[V]**.
- Active state = **3 px accent underline** at the bottom of the tab (`#4276e8` in the 2023.2 capture; `#3574f0` family after the 2024 accent shift) **[V]**; the 1 px strip divider (`#393b40`) is replaced by the accent across the tab width.
- Label 13 px; active = primary text `#dfe1e5`, inactive = secondary `#9da0a8`; close ✕ 16×16 revealed on hover/active; file icon 16×16 left of the label.
- Tab min width ~80, typical 160–250, max ~300 before overflow **[A]**.
- Overflow: scrollbar, squeeze, or multi-row — user-selectable **[D]**.
- 2025 **Islands** changes the active tab to a rounded pill with background + border — see §5.

**Vertical tool-window stripe (40 × full height):**

```
┌────┐  40 px wide
│ 📁 │  selected tool window  (20×20 icon, 32×32 button, centered)
│    │
│ ⑂  │  other tool windows, 32 px pitch
│ 🔖 │
│    │
│ ⋯  │  "More tool windows" (ellipsis) lives at the bottom of the top group
│    │
│ ── │  separator between the vertical-tool-window group (top) and
│    │  horizontal-tool-window group (bottom) — drag icons across it
│ ⌨  │  32 px pitch for 20 px buttons: 6 px vertical gap
│ 👁 │
└────┘
```
- Icons in the **top part** open vertical (left/right) tool windows; icons in the **bottom part** open horizontal (bottom) tool windows **[D]**.
- Labels hidden by default (tooltip on hover); user can enable `Show Tool Window Names` (label 11–12 px under the icon) **[D]**.
- Badge = colored dot over icon; icon color unchanged **[D]**.

### 1.4 Region behavior rules (what to keep when adapting)

| Region | Behavior to borrow |
|---|---|
| Main toolbar | Widgets (project/VCS/run) instead of a classic menu bar; on Win/Linux the **hamburger ☰** replaces/merges the menu **[D]**. Right cluster: profile, search, settings. 1 px dividers separate widget groups. |
| Stripes | Never scroll, never take more than 40 px, icon-only; "More…" overflow at the bottom of each stripe; drag an icon across the splitter to move the tool window to another edge **[D]**. |
| Tool windows | Toggle on/off from stripes; header 40 px with title + actions + chevron; default width 20 % of window (min 200), bottom window default height 20 % (min 200) **[D]**; floating/pinned variants exist but are optional. |
| Tab strip | Sits in the same 40 px band as the panel headers; flat tabs; accent underline; overflow strategy is user-configurable. |
| Bottom tool window | Spans the **full width between the stripes** (it is not inside the editor column); own header row with tabs; its toolbar hides its border when content is scrolled to top **[D]**. |
| Status bar | Left: navigation/breadcrumb path. Right: small 16×16-icon widgets separated by 8–12 px: problems counter, cursor position (`24:44`), line separator (`LF`), encoding (`UTF-8`), indent (`4 spaces`), and a trailing screen-mode chevron. Height 28. |

---

## 2. Palette

All hex values below are the **New UI (2023.2+) palette**. Legacy Darcula (`#2B2B2B` editor, `#3C3F41` chrome) is a *different* system — do **not** mix it in.

### 2.1 Dark theme — primary roles

| Role | Hex | Confidence | Evidence / note |
|---|---|---|---|
| Main window / editor background ("canvas") | `#1E1F22` | **[V]** | dominant dark surface in official capture; also `EditorTabs.background` per Islands docs equals editor bg **[D]** |
| Chrome surface — main toolbar, tool-window panel, tool-window header, stripes, status bar | `#2B2D30` | **[V]** | dominant chrome surface (159k sampled pixels) |
| Divider / hairline on chrome | `#393B40` | **[V]** | 1 px line under the header band; standard `Component.borderColor` family |
| Divider that reads as a "gap" (toolbar↔content, stripe↔panel, panel↔bottom window, above status bar) | `#1E1F22` | **[V]** | 1 px lines measured between all major bands |
| Slightly darker chrome (editor-side chrome, drag ghosting) | `#26282D` | **[V]** | appears in editor tab strip / caret-row highlights in capture |
| Text — primary | `#DFE1E5` | **[V]** | glyph cores in headers/tabs (aliased to `#DFE1E5`) |
| Text — editor / code primary | `#BCBEC3` | **[V]** | editor foreground in Dartula-derived scheme |
| Text — secondary / inactive tab / status bar | `#9DA0A8` | **[V]** | status-bar text sampled ≈`#9DA0A7` (AA); canonical `#9DA0A8` **[V]** from icon palette tertiary dark |
| Text / icon — disabled | `#6F737A` | **[D]** | official icon palette "secondary stroke dark"; also used for disabled text |
| Icon stroke — primary | `#CED0D6` | **[D]** | official JetBrains icon palette: `#6C707E`→`#CED0D6` is the most-used pair |
| Icon stroke — secondary (chevrons, faint glyph) | `#6F737A` | **[D]** | official palette |
| Accent / primary action / link / focus | `#3574F0` (light-theme value) · `#548AF7` (dark-theme value) | **[D]** | official icon palette; in the 2023.2 capture the UI accent measures **`#4276E8`** **[V]** — see §2.4 |
| Accent — soft fill (info banner, selected node) | `#25324D` | **[D]** | official palette "blue soft dark" |
| Selection — current row, unfocused panel | `#43454A` | **[V]** | measured as a 24 px rounded row pill in Project tree and Git log |
| Selection — focused list/table area | `#1D2432` | **[V]** | measured in the focused Git log list area of the official capture; visually a very dark navy |
| Hover — row / toolbar button | `#393B40` – `#43454A` | **[A]** | not isolated in the capture (no hover state rendered); use `#393B40` for toolbar hover, `#43454A` for row hover |
| Scrollbar thumb / track | `#5B5D5F` thumb · `#3F4244` track/gutter | **[V]** | measured at panel scrollbars |
| Active tab underline | `#4276E8` (2023.2) / `#3574F0` (2024+) | **[V]/[D]** | measured 3 px underline |
| Reversed / on-accent text | `#FFFFFF` | **[D]** | inside filled blue buttons |
| Error | `#DB5C5C` | **[D]** | official palette dark |
| Warning | `#F2C55C` (status) · `#C77D55` (orange accent) | **[D]** | official palette dark |
| Success | `#57965C` | **[D]** | official palette dark |
| Purple (AI / special) | `#B589EC` | **[D]** | official palette dark |
| Inactive/dimmed overlay for unfocused window | alpha 0.44 over content | **[D]** | Islands spec `Island.inactiveAlpha` |

### 2.2 Light theme — primary roles

JetBrains Light is **not** an inverted dark theme: chrome uses a bluish off-white, canvas is pure white, and the **window header is dark by default**.

| Role | Hex | Confidence | Evidence / note |
|---|---|---|---|
| Window header / main toolbar (default **Light** theme) | `#27282D` | **[V]** | measured full-width band in both 2023.2 and 2026.3 Light captures; text on it is white |
| Window header (the optional **Light with Light Header** theme) | `#F7F8FA` | **[V]** | measured in `ij_new_ui_light_header_theme.png`; same layout, light chrome |
| Editor / canvas background | `#FFFFFF` | **[V]** | dominant light surface |
| Chrome surface — tool-window panels & headers, stripes, status bar | `#F7F8FA` | **[V]** | dominant light chrome surface |
| Divider / hairline | `#EBECF0` | **[V]** | 1 px line under toolbar; official light palette "disabled fill" family |
| Divider that reads as a gap | `#DFE1E5` | **[A]** | light counterpart of `#1E1F22` separators; verify against real product |
| Text — primary | `#000000` | **[V]** | glyph cores in light capture; JetBrains Light keeps near-black labels |
| Text — secondary | `#6D707D` | **[V]** | glyph cores; close to official icon light stroke `#6C707E` **[D]** |
| Icon stroke — primary / secondary | `#6C707E` / `#818594` | **[D]** | official icon palette light |
| Selection — current row, unfocused panel | `#DFE1E5` | **[V]** | measured selected row in Project tree |
| Selection — focused list area | `#E9EEF9` | **[V]** | measured light counterpart of the focused Git-log area |
| Selection — blue-tinted key (in-editor) | `#E8EFFC` | **[V]** | observed in light capture (`CompletionPopup.selectionBackground`-family) |
| Accent | `#4276E8` (2023.2 capture) / `#3574F0` (2024+ canonical) | **[V]/[D]** | official palette light blue = `#3574F0`; capture shows `#4276E8` |
| Accent soft fill | `#EDF3FF` / `#E7EFFD` | **[D]** | official palette light |
| Error / Warning / Success | `#DB3B4B` / `#FFAF0F` (status), `#E66D17` (orange) / `#208A3C` | **[D]** | official palette light |
| Scrollbar thumb | `#C4C4C4` / `#C6C6C8` | **[V]** | measured in light capture |

### 2.3 Semantic diffs / status colors (shared story)

New UI statuses are deliberately **muted** compared with Material apps: a small set of warm/cool accents on a neutral base.
`error #DB3B4B` (light) / `#DB5C5C` (dark), `success #208A3C` / `#57965C`, `warning #FFAF0F` / `#F2C55C`, `orange #E66D17` / `#C77D55`, `purple #834DF0` / `#B589EC`. Soft fills exist for each (`#FFF7F7`/`#402929`, `#F2FCF3`/`#253627`, `#FFFAEB`/`#3D3223`, `#FFF4EB`/`#45322B`, `#FAF5FF`/`#2F2936`) **[D]**.

### 2.4 Accent version drift (important when matching references)

The blue changed after the 2023.2 New UI launch:

* **2023.2–2023.3 captures:** UI accent measures **`#4276E8`** (active tab underline, selected-step highlights) **[V]**.
* **2024+ canonical:** **`#3574F0`** (light) / **`#548AF7`** (dark) — the official icon-palette values **[D]**, and what the current IDE uses.
* **Recommendation for «Волна»:** pick one and apply it everywhere. Use **`#3574F0` / `#548AF7`** (current canonical) unless you specifically want the 2023.2 screenshot look (`#4276E8`).

---

## 3. Typography

### 3.1 UI font

**Inter** is bundled and used for the whole UI on all OSs **[D]**. (Older builds referenced "JetBrains Sans"; current docs name **Inter** — the metrics are the same at 13 px.) Default UI size = **13 px**, and all other UI sizes are expressed as offsets from it **[D]**.

| Style | Implementation (guideline) | Size @ default 13 | Weight | Usage |
|---|---|---|---|---|
| H1 | `JBFont.h1().asBold()` | **18** (+5) | Bold | main page header |
| H2 | `JBFont.h2().asBold()` | **16** (+3) | Bold | small page header |
| Default | `JBFont.regular()` | **13** | Regular (400) | labels, inputs, links, trees, tables, tabs, buttons |
| Default semibold | `JBFont.regular().asBold()` | **13** | Semibold (600) | dialog/popup/notification/tool-window headers |
| Paragraph | default, line-height +3 | 13 / **16** lh | Regular | multiline description |
| Medium | `JBFont.medium()` | **12** (−1) | Regular | help text, status bar, secondary metadata |
| Medium semibold | `JBFont.medium().asBold()` | **12** | Semibold | group headers in popups |

Rules that carry the look: **title case** everywhere (never UPPERCASE section labels) **[D]**; one line height offset for body text (default +3); never hardcode font sizes — they are offsets from the user's default **[D]**.

### 3.2 Editor / monospace font

**JetBrains Mono**, default size = the editor default (13 px in practice), line height ≈ **1.2** → ~**22 px** measured line pitch in the official capture **[A: ratio; 22 px V-measured roughly]**.
Line numbers = default −1 (12 px), secondary color, right-aligned in a 40 px gutter **[A gutter width]**.
For the file manager this font is relevant for: file sizes, timestamps, hashes, transfer speeds — JetBrains Mono's tabular digits are a big part of the "technical tool" feel.

### 3.3 Type scale cheat-sheet (CSS)

```css
--font-ui: Inter, "JetBrains Sans", system-ui, sans-serif;
--font-mono: "JetBrains Mono", ui-monospace, monospace;
--ui-13: 13px/20px;   /* default UI */
--ui-12: 12px/18px;   /* medium / status / secondary */
--ui-16: 16px/24px;   /* H2 */
--ui-18: 18px/26px;   /* H1 */
--ui-header: 13px/20px 600;  /* tool window / dialog headers */
```

---

## 4. Component metrics

### 4.1 Heights (New UI, normal density)

| Component | Height | Confidence |
|---|---|---|
| Main toolbar / window header | **40** | [V] |
| Tool-window header row | **40** | [V] |
| Editor tab strip row | **40** | [V] |
| Tool-window stripe width | **40** | [V] |
| Bottom tool-window header/tab row | **40** | [V] |
| Tool-window toolbar row (inside a panel) | **32** | [A] (search field + filter row in capture) |
| Status bar | **28** (measured 26.5–29) | [V] |
| Tree / list / table row | **24** | [V] (measured 48 device px) |
| Section/group header row in a tree | **24** | [A] |
| Search field in tool-window toolbar | **24–26** | [A] |
| Input field (dialogs) | **28** | [A] |
| Default button | **32** | [A] |
| Small / toolbar icon button | **24** hit area, 16×16 icon | [A] |
| Stripe icon button | **32** hit area, 20×20 icon, 32 pitch | [A over V stripe width] |
| Scrollbar thumb width | **8** (overlay, no arrow buttons) | [V] |
| Splitter | 1 px visual, 4–6 px drag zone | [A] |

### 4.2 Spacing & padding system

| Item | Value | Confidence |
|---|---|---|
| Base spacing unit | **4 px** (all paddings are multiples: 4/8/12/16) | [A] |
| Tool-window header left padding | **8** | [V-ish: title starts ~8 px after edge] |
| Tool-window header right padding | **8** | [A] |
| Title → chevron gap | **4** | [A] |
| Action icon gap | **8** | [A] |
| Tree row indent per level | **16** | [A] |
| Tree chevron 16×16, 2 px from icon | — | [A] |
| Tab horizontal padding | **8–12** | [A] |
| Status bar horizontal padding | **8–12**, widget gap **8–12** | [A] |
| Tool-window content padding | **8** (lists go edge-to-edge; text blocks 12) | [A] |
| Banner / notification padding | **12** | [A] |

### 4.3 Radii, borders, focus

| Item | Value | Confidence |
|---|---|---|
| Control radius (buttons, inputs, search field) | **4** | [A] — New UI's standard small radius |
| Row selection radius | **4** (rounded full-row pill) | [V shape, A value] |
| Popup / tooltip / balloon radius | **8** | [A] |
| Panel/tool-window radius (pre-Islands) | **0** — panels are square, docked to the window edges | [V] |
| Islands (2025.1+) panel radius | **10** actual (`Island.arc = 20` at 2×), gutter **4** actual (`borderWidth = 5` − 1) | [D] |
| Borders | **1 px** everywhere; never 2 px except the accent underline (2–3 px) | [V] |
| Active-tab underline | **2–3 px** (measured 3) | [V] |
| Focus ring | **1 px** accent `#3574F0` + subtle 1 px inner offset; focus color is state, not decoration | [A] |
| Shadows | none on in-window surfaces; popups/balloons get a soft shadow only | [V visual] |
| Transparency / blur | none in normal UI | [V visual] |

### 4.4 Icons

| Item | Value | Confidence |
|---|---|---|
| Base icon grid | **16×16** (1 px strokes, aligned to whole px; outline style, rounded caps) | [D] |
| Tool-window/stripe icon | **20×20** (also provide a **16×16** variant) **[D]**, grey and monochromatic | [D] |
| Icon color, dark theme | primary `#CED0D6`, secondary `#6F737A`, disabled `#43454A` | [D] |
| Icon color, light theme | primary `#6C707E`, secondary `#818594`, disabled `#EBECF0` | [D] |
| Two-tone rule | one neutral stroke + at most **one** accent-colored node (e.g. blue dot, green arrow) | [D] |
| Chevrons | small 16×16 outline chevrons (`⌄`, `▸`, `»`), 1 px stroke, muted color; not filled triangles | [V visual] |
| Status badges | separate small colored circle (error/success/warning) — the glyph itself never changes color | [D] |
| File-type icons | 16×16, colored, but **desaturated** and small; the saturation budget of the UI is low | [A] |
| Arrow/chevron motion | static, no animation; chevron rotates only for disclosure | [A] |

### 4.5 State treatments

| State | Dark | Light | Confidence |
|---|---|---|---|
| Hover (row) | `#393B40` full-row (4 px radius) | `#ECEDF1` | [A] |
| Hover (icon button) | `#393B40` 24×24 rounded 4 px | `#DFE1E5`-ish | [A] |
| Selection, panel unfocused | `#43454A` full-row pill | `#DFE1E5` | [V] |
| Selection, panel focused | blue-tinted (`#1D2432` measured area, canonical `#2E436E` family) | `#E9EEF9` | [V] / [A canonical] |
| Active tab | 3 px accent underline; label primary | same | [V] |
| Inactive tab | no underline; label secondary | same | [V] |
| Disabled | text/icon `#6F737A` (dark) / `#A8ADBD` (light) | | [D] |
| Focus | 1 px accent border | same | [A] |

### 4.6 Compact mode & Zen mode

* **Compact mode** (View → Appearance → Compact Mode): reduced heights for toolbars and tool-window headers, scaled-down spacings/paddings, smaller icons and buttons **[D]**. Exact numbers are not published; proportionally ≈ **−20 %**: toolbar 32, header rows 32, stripe 32, rows 20, radius unchanged **[A]**. Implement it as a density token set, not as a second stylesheet.
* **Zen mode**: hides toolbars, stripes and status bar, leaving the editor alone — worth borrowing as a "focus mode" for the file manager (hide chrome, keep the content pane).

---

## 5. Islands theme (2025.1+) — the 2025 evolution

If the client references screenshots from **PyCharm/IDEA 2025.1+**, they are likely seeing **Islands** (Settings → Appearance → Theme: *Islands Dark / Islands Light*). Deltas from classic New UI **[D]**:

| Aspect | Classic New UI (2023–2024) | Islands (2025.1+) |
|---|---|---|
| Panels | Square, edge-to-edge, separated by 1 px lines | Rounded **10 px** "islands" floating on a slightly different main-window background |
| Gutters between panels | 1 px | **4 px** visible gap (`Island.borderWidth = 5` at 2× minus 1) |
| Sidebar/toolbar borders | 1 px hairlines (`#393b40` dark) | **Transparent** — `MainToolbar.borderColor`, `ToolWindow.Stripe.borderColor`, `StatusBar.borderColor` set to 100 % transparent |
| Tool-window background | `#2b2d30` (chrome tone) | Same as the **editor** background (or ±1 tone) |
| Main window background | `#1e1f22` | Dark: **lighter** than editor/panels; Light: **darker** (min contrast ratio 1.20:1) |
| Active editor tab | Accent **underline**, flat | **Rounded pill**: `EditorTabs.underlinedTabBackground` fill + `EditorTabs.underlinedBorderColor` border |
| Inactive window state | flat dimming | content under islands dimmed with alpha **0.44** |

**Recommendation for «Волна»:** choose **classic New UI** as the primary language (it is the most recognizable "JetBrains" and simpler to build: 1 px lines, square panels, 4 px controls). Treat Islands as an optional "2025 refresh" skin (10 px panels, 4 px gutters, pill tabs) — do not mix the two (a 10 px island inside a square panel reads as a bug).

---

## 6. JetBrains-signature details (what makes an interface unmistakably JetBrains)

1. **Two-tone surface system with zero decoration** — `#1e1f22` workspace vs `#2b2d30` chrome; no gradients, no shadows, no glass, no translucency. Depth is tone + 1 px line.
2. **Dark chrome over a bright canvas in the Light theme** — default `Light` ships a `#27282d` window header while the editor stays `#ffffff`. (A separate "Light with Light Header" theme exists.)
3. **40 px chrome rhythm** — main toolbar, panel headers and tab strip are all 40 px; 24 px data rows; every band separated by 1 px hairlines. The result looks engineered, not "branded".
4. **The continuous header band** — the editor tab strip and the tool-window headers occupy the same 40 px row across the window, so the chrome reads as one continuous horizontal strip.
5. **40 px icon-only vertical stripes** with 20 px two-tone outline icons — the primary navigation device; labels are hidden by default (tooltip / opt-in names). Badges are dots, not icon recolors.
6. **Flat tabs with a 3 px accent underline** (pre-Islands) — no pill, no rounded tab, no background on the active tab; the accent line alone signals the active tab.
7. **Widgetized main toolbar** — project switch, VCS branch switcher, run configuration as *composite widgets* with a chevron, not as plain icon buttons; hamburger ☰ on Windows/Linux **[D]**.
8. **Accent discipline** — `#3574f0`-family blue appears only as state (underline, focus, link, small selection tint). The palette's saturation budget is spent mostly on 16 px icons.
9. **Outline, two-tone icons on a 16 px grid** — `#6c707e` ↔ `#ced0d6` neutral stroke with a single colored node; statuses are separate colored badges.
10. **Selection as a rounded row-pill** — full-row highlight with 4 px radius, neutral grey when unfocused, blue-tinted when focused.
11. **Navigation moved into the status bar** (2023.2+) — breadcrumb path on the left, telemetry widgets (`24:44`, `LF`, `UTF-8`, `4 spaces`) on the right; the status bar is a real control surface, not decoration.
12. **Dense typography** — Inter 13 px everywhere, semibold only for headers, title case, no uppercase tracking; JetBrains Mono for all technical values.
13. **Tool-window chrome grammar** — title + disclosure chevron + right-aligned action icons + `»` overflow; content lists go edge-to-edge and their toolbar drops its border when scrolled to top **[D]**.
14. **Keyboard-first visual quietness** — no hover-lift, no animation, no e-commerce rounding; motion and decoration are removed so the data is the loudest thing on screen.

---

## 7. Do / Don't when adapting this language to a file manager

### Map IDE slots → file-manager slots (suggested)

| JetBrains New UI | «Волна» file manager |
|---|---|
| Main toolbar: project widget, VCS widget, run widget | Drive/location widget, breadcrumb-path widget, command/task widget (e.g. active transfer) |
| Left stripe + left tool window: Project tree | Left stripe + **folder tree / places / drives** (vertical tool window) |
| Editor tab strip | Tabs of **open folders / locations / search results** — same 40 px flat tab grammar |
| Editor canvas | **File list / details view** (table) — this is the "workspace", keep it `#1e1f22`/`#ffffff` |
| Right stripe + right tool window (Notifications, AI Assistant) | **Properties / preview / details / activity** panel |
| Bottom tool window: Git, Run, Problems, Terminal | **Transfer queue / operations / log / terminal** |
| Status bar widgets | Item count + selection size, free disk space, current path, zoom/density toggle, encoding for text preview |
| Tool-window header actions | Panel actions: filter, sort, view mode, pin, collapse, options |

### Do

- Keep the **exact skeleton**: 40 px toolbar → 40 px continuous header band → three columns (stripe+left panel / content / right panel+stripe) → full-width bottom panel → 28 px status bar.
- Use the **two-surface palette** and 1 px hairlines as the only separators; let the palette do the hierarchy work.
- Keep **24 px rows** and 40 px chrome on desktop; ship a **compact mode** token set (≈20 px rows / 32 px chrome) for laptops.
- Use **flat tabs with a 2–3 px accent underline** for open folders/locations; make overflow user-configurable (scroll / squeeze / wrap).
- Use **icon-only stripes** with tooltips and optional labels; put "More" (+) at the bottom of each stripe group.
- Use **4 px radii on controls, 4 px on row selection**, square panels (classic) — rounding is not the JetBrains signature.
- Put the **path/navigation in the status bar** (or, if usability demands it, at the top of the content area — see Don't) and **telemetry widgets on the right**.
- Keep icons **16 px, outline, two-tone, monochromatic** and desaturate file-type colors; statuses as small badges.
- Use **JetBrains Mono / tabular numbers** for sizes, dates, speeds, hashes — it is a huge part of the technical-tool feel.
- Design **empty, dense and ultra-dense** densities as tokens (24 / 20 / 16 px rows) — power users of file managers want density; JetBrains already has the vocabulary.

### Don't

- ❌ Don't add gradients, glass, blur, glow, drop shadows or "elevation" to in-window surfaces — that immediately stops reading as JetBrains.
- ❌ Don't make rows 32–40 px "for breathing room" (that is Finder/Chrome territory). JetBrains density = 24 px rows.
- ❌ Don't put persistent text labels under stripe icons by default (that is the VS Code activity-bar look); labels must be optional/tooltip.
- ❌ Don't use big rounded pill tabs with generous padding or macOS-style segmented tabs — JetBrains tabs are flat, dense and 40 px tall.
- ❌ Don't fill large areas with accent blue or turn selections into strong blue blocks; accent is state, small and local. (Focused blue tint is a *tint*, not a fill.)
- ❌ Don't use UPPERCASE or letter-spaced section headers — title case only.
- ❌ Don't use 8–12 px radii everywhere; only Islands panels (10 px) and popups (8 px) round, controls stay at 4 px.
- ❌ Don't mix dark chrome with light content *arbitrarily*: in JetBrains Light the dark header is deliberate and the canvas is pure white — pick one theme mode and respect its two-surface rule.
- ❌ Don't copy IDE functionality to justify the look (tool windows as editors, split editor, debugger semantics). Borrow the **arrangement and grammar**, not the product.
- ❌ Don't animate panels/tabs/hover lifts. Transitions, if any, should be ≤120 ms opacity/color only.
- ❌ Don't use a classic File/Edit/View menu bar on Windows/Linux; use the hamburger ☰ and composite widgets (JetBrains 2023+ pattern), or a `File` menu only if the client insists.
- ❌ Don't mix classic New UI (square panels, 1 px lines) with Islands (10 px panels, 4 px gutters, pill tabs) in one product. Pick one.

---

## 8. Sources

**Primary (official, used for verification)**

- New UI — IntelliJ IDEA Help: <https://www.jetbrains.com/help/idea/new-ui.html>
- User interface overview — IntelliJ Platform UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/ui-overview.html>
- Tool Window — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/tool-window.html>
- Toolbar — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/toolbar.html>
- Tabs — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/tabs.html>
- Typography — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/typography.html>
- Platform Theme Colors — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/platform-theme-colors.html>
- Window Sizes — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/window-sizes.html>
- Supporting Islands Theme — UI Guidelines: <https://plugins.jetbrains.com/docs/intellij/supporting-islands-theme.html>
- UI Guidelines index: <https://plugins.jetbrains.com/docs/intellij/ui-guidelines-welcome.html>
- New UI icon palette (official JetBrains repo skill doc, empirically derived from `expui` icon set): <https://github.com/JetBrains/intellij-community/blob/master/.agents/skills/icons/palette.md>
- Icon style guidelines: <https://plugins.jetbrains.com/docs/intellij/icons-style.html>
- IntelliJ-based theme JSON keys (e.g. `HighContrast.theme.json`, `Light.theme.json`): <https://github.com/JetBrains/intellij-community/tree/master/platform/platform-resources/src/themes>
- New UI Enhancements in IntelliJ IDEA 2023.1 — JetBrains blog: <https://blog.jetbrains.com/idea/2023/03/new-ui-enhancements-in-intellij-idea-2023-1/>

**Screenshot evidence (pixel-measured)**

- New UI Dark theme, official docs capture (2068×1448 @2×): <https://resources.jetbrains.com/help/img/idea/2026.3/new_ui_dark_theme.png>
- New UI Light theme (dark header), official docs capture: <https://resources.jetbrains.com/help/img/idea/2026.3/new_ui_light_theme.png>
- New UI Light with Light Header, official docs capture: <https://resources.jetbrains.com/help/img/idea/2026.3/ij_new_ui_light_header_theme.png>
- Older 2023.2 doc-path captures used as cross-check (identical layout/palette): `https://resources.jetbrains.com/help/img/idea/2023.2/new_ui_dark_theme.png` and `.../2023.2/new_ui_overview.png`

**Secondary (community, used only as cross-checks / for values marked [A])**

- Ferriswatch `palette/jetbrains/dark.rs` — community transcription of JetBrains theme JSON keys: <https://docs.rs/ferriswatch-core/0.4.5/src/ferriswatch_core/palette/jetbrains/dark.rs.html>

---

## 9. Verification method & evidence log

1. Downloaded the official New UI Dark/Light screenshots at 2× (2068×1448 device px = **1034×724 CSS px** window) and parsed them with PIL.
2. Confirmed the **2× scale** from invariants: tree row = 48 device px → 24 CSS px; stripe = 80 device px → 40 CSS px; traffic-light dots ≈ 14 device px.
3. Band detection (per-row modal color across a wide x-range) gave every horizontal region boundary and its height; 1 px lines were isolated from full-row uniform runs.
4. Role colors were sampled at interior points of each region (not edges) to avoid antialiasing, then cross-checked against the official icon palette for the same roles.
5. Accent under the active tab was isolated as a 6 device px (3 CSS px) `#4276E8` run spanning exactly the tab width.
6. Version drift was checked by comparing the 2023.2-path and 2026.3-path captures: byte-identical layout histogram, so the screenshots represent the same New UI build family (2023.2-era), while the accent hex in more recent product builds is `#3574F0`/`#548AF7` per the official palette.
7. Selection colors were located by bounding-box search of exact colors: `#43454a` (dark inactive row, 24 px) and `#1d2432`/`#e9eef9` (focused list area, light/dark counterparts).

### Known gaps / caveats

- **Not verified from the running IDE:** exact hover colors, toolbar button hit areas, input/button heights, compact-mode dimensions, icon stroke weight. These are marked **[A]** and should be tuned visually against the reference screenshots.
- The **tool-window header height** (40 px) and **tab strip height** (40 px) were measured on the macOS capture with a docked single tab; Windows/Linux may render the header band 1–2 px differently (window frame). Use 40 as the design value.
- The captured window's **bottom panel** is user-resized to ≈36 % height; the guideline default is **20 %** of window height (min 200 px) — use that for initial layout.
- **Islands** values (10 px radius, 4 px gutter, 0.44 inactive alpha) are from JetBrains' theme-conversion doc; they are theme **keys**, not a screenshot measurement.
- Darcula legacy (`#2B2B2B`/`#3C3F41`) is intentionally **not** part of this spec — it belongs to the pre-2022 UI and would make an adaptation look dated.
