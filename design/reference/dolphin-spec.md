# Dolphin reference spec — «Волна» ground truth

Visual spec of the KDE Dolphin reference capture in `reference/`. Implementation-ready: every number is
measured in **screenshot pixels** and every Russian UI label is transcribed verbatim.

**Sources**
| file | size | content |
|---|---|---|
| `Screenshot_20261113_183407.png` | 1532×931 | Dolphin main window, «Столбцы» view, sorted Size ↓, **no grouping** |
| `Screenshot_20261113_183441.png` | 1532×931 | same window, «Столбцы» view, **grouped by modification date** (`Сегодня`, `Вчера`, `Среда`, `Вторник`, `Неделю назад`) |
| `Screenshot_20261113_183418.png` | 774×492 | «Режим просмотра» settings dialog (mode=Столбцы, sort=По убыванию/Размер) |

**Method** — `design/reference/measure.py` (python3 + PIL/numpy). All geometry below is from pixel run-length
scans / colour-mask projections of the PNGs; colours are sampled RGB. The two main-window shots are the same
application state except grouping + sort, so all chrome numbers are shared. Round-trip reading: the dialog
snapshot corresponds to state **183407** (grouping checkbox is unchecked); **183441** is that same view after
enabling grouping and switching sort to modification date.

**Capture conventions / caveats**
- Screenshots are crops of a black (`#000000`) desktop with the window at **x=64, y=52**; window itself is **1404×803** (main) / **646×364** (dialog). Capture is 1:1 CSS px (crisp 1 px borders, ≈13 px UI font); no HiDPI scaling detected.
- Text uses **RGB subpixel antialiasing** (blue/orange fringes): sample glyph *cores*, not fringes.
- Brightest text pixel in all three shots is **#c5c9c5** (not Breeze Dark canonical #eff0f1): capture is ~18 % darker than stock Breeze Dark. For screenshot fidelity use the hex values verbatim.
- Values are ±1–2 px (antialiasing).

---

## 1. What the reference is, and why it is characteristic

A KDE Plasma 6 Dolphin file manager window (Russian locale, dark Breeze-derived theme) in its **«Столбцы» (Columns)**
view. Items flow **top-to-bottom in fixed-width columns** (not a row-major icon grid): sorted by size descending,
column 1 reads 16,6 ГиБ → 4,1 ГиБ → 3,4 ГиБ … 931,9 МиБ, then column 2 continues 848,5 МиБ → … → 94,9 МиБ.
With «Разбивать на группы в соответствии с режимом сортировки» the same view turns each date group into its own
**headed column** separated by 1px dividers — the signature state. Beside it: a Places sidebar with two stacked
scroll panels, a flat KDE toolbar with breadcrumb field, and the bottom filter + status row with zoom slider.

Characteristic "desktop file manager" material: dense 3-line item cells (icon left, name/size/date stack), a persistent Places rail, blue Breeze folder glyphs, and near-black low-chroma chrome with exactly one warm accent (device rows / clear button in salmon `#c4746e`).

---

## 2. Top-to-bottom window anatomy (main window, 1404×803 at 64,52)

| band | y (abs) | height | contents |
|---|---|---|---|
| window outline | 52 | 1 px `#444343` | rounded window corners, radius ≈5 px; no visible drop shadow on black desktop |
| titlebar | 53–88 | 36 | `#282727`; 16×16 window icon at x≈68–84; centred title; 5 window controls right |
| divider | 89 | 1 | `#4f504f` |
| toolbar row | 90–117 | 28 | nav buttons, 4 view-mode toggles, location field, 4 right icons; bg `#282727` |
| divider | 118 | 1 | `#4e4f4e` / `#4f504f` |
| chrome strip | 119–125 | 7 | `#282727` full-width band (lower toolbar margin) |
| divider | 126 | 1 | `#4f504f` |
| window-bg line | 127 | 1 | `#181616` |
| content | 128–853 | 726 | sidebar x=65–329 + right column x=330–1465 |

Right column (x=330–1465):

| band | y | height | contents |
|---|---|---|---|
| file view | 128–790 | 663 | 1px focus border `#8da4a8` (left/top) / `#8ba2a6` (right/bottom), fill `#0d0c0c` |
| gap | 791–792 | 2 | `#181616` |
| filter bar | 793–822 | 30 | bg `#181616`; field, filter glyph, clear button |
| divider | 822 | 1 | `#424241` |
| status bar | 823–853 | 31 | bg `#181616`; left item count, right `Масштаб:` slider + free-space bar |

### 2.1 Titlebar
- Title **`.cache — Dolphin`**, centred: text box x=714–817, y=62–74 (≈13 px, regular, `#c5c9c5`).
- Window icon 16×16 at x=68–84 (Dolphin blue folder mark).
- Right cluster, 5 controls at x-centres ≈1354, 1378, 1403, 1428, 1453, glyph y-centre 68, glyph colour `#b9bdb9`,
  pitches 25/25/25/25: glyphs measured as `?` help, double chevron `⌃⌃`, `⌄`, `⌃`, `✕` (KDE decoration order).

### 2.2 Toolbar (y 90–117, 28 px, bg `#282727`)
| element | measured box / centres |
|---|---|
| Back, Forward, Up buttons | 26×26, icon centres (86,104), (110,104), (132,104); forward is disabled → glyph `#5e5f5d` |
| vertical divider | 1 px at x=150, y≈94–113 |
| 4 view-mode toggles | 28 px pitch from x=160; icon centres (176.5,103.5), (204.5,103.5), (232.5,103.5), (260.5,103.5); 12×12 glyphs, `#c5c9c5` |
| checked toggle «Столбцы» | 26×26 at x=192–217, y=91–116; fill `#3c3b3b`, 1 px border `#575856`, radius 4 |
| location field | x=329–1342 (1013×30), y=89–118; fill `#0d0c0c`, 1 px border `#3d3e3e`, radius 6 |
| breadcrumb path | `/home/frimm/.cache/`; text starts x=339, glyph band y=98–109, 13 px, `#c5c9c5` |
| clear-path glyph | edit-clear (light filled pill with dark cut-out ✕) centred (1310,105) |
| path dropdown | chevron `⌄` centred (1333,105) |
| right toolbar icons | 4 glyph buttons, centres x≈1355.5 (`✓`), 1384.5 (`⊞+`), 1411.5 (`🔍`), 1443.5 (`☰`), y=105, `#c5c9c5` |

Toggle glyph shapes (12×12): ① 2×2 grid of squares; ② item-columns glyph — two rows of “square + 2 lines”
(**checked = current mode Столбцы**); ③ cascading/sitemap blocks; ④ lined document (details).

## 3. Places sidebar (x 65–329, 265 px)

Split into **two stacked scroll panels** with independent 24 px gutters + 6 px thumbs:
| panel | y-range | structure |
|---|---|---|
| A — folder tree | 128–≈399 | 12 rows, **22 px** pitch, first text centre y≈145.5; **zebra stripes** `#181616` / `#12120f` (22 px bands); thumb y=141–176 |
| B — Places | ≈403–853 | section headers + **26 px** rows; no zebra; thumb y=415–757 |

Shared gutter: list content x=65–304; separator line x=305 `#2a2828`; gutter x=306–329 `#181616`;
scrollbar thumb x=313–318 (6 px): fill `#363534`, 1 px edge `#5e5f5d`.

**Panel A rows** (chequered): dim chevron `>` at x=77–82 (`#3e3d3c`), 16×16 coloured symbolic icon at x≈91–107,
label x=111, 13 px `#c5c9c5`:
`Видео`, `Документы`, `Загрузки`, `Изображения`, `Музыка`, `Общедоступные`, `Рабочий стол`, `Шаблоны`,
`any-lim`, `audacity4`, `backup`, `barbaros` (top→bottom).

**Panel B** — 16×16 icons x=74–90, labels x=98, 13 px:
| y (text centre) | entry |
|---|---|
| 412–422 | section `Точки входа` (13 px `#7f807c`) |
| 443 | Домашняя папка |
| 467.5 | Рабочий стол |
| 495.5 | Документы |
| 521.5 | Загрузки |
| 547.5 | Музыка |
| 573 | Изображения |
| 599 | Видеофайлы |
| 625.5 | Корзина |
| 652–658 | section `В сети` |
| 680 | Сеть |
| 708–714 | section `Недавно изменённые` |
| 737 | Последние файлы |
| 763.5 | Последние расположения |
| 788–797 | section `Устройства` |
| 815.5 | `archive6` + usage bar y=824–826 |
| 841.5 | `Models` + usage bar y=850–852 |

Devices: label colour and bar **salmon `#c4746e`**; bar x=97–300 (204 px), 3 px tall, rounded, remaining track
`#3a3a39`; both disks are nearly full (archive6 fill to x=295, Models to x=290).

## 4. Main file view — «Столбцы», state A (sorted by size ↓, no grouping)

View box: **x=330–1465, y=128–790** (1136×663), 1 px focus border `#8da4a8`, fill `#0d0c0c`.
Content padding: first icon top y=146 → 17 px from view top; first icon left x=346 → 15 px from view left.

**Columns are content-sized and flow top-to-bottom.** Measured column starts (icon-left): 346, 572, 798, 1024, 1262
→ widths ≈226/226/226/238 px for the first four; 5th column is clipped by the viewport (its dates end with `…`).
Row pitch **106 px** (icon tops 146, 252, 358, 464, 570, 676) — 6 fully visible rows.

### 4.1 Item cell anatomy (the core unit)
```
[icon 86×78]  gap 10–11px  [name        ]   <- 13px #c5c9c5
 x=346+86=432             [size        ]   <- 13px #8d9090
                            [date        ]   <- 13px #8d9090
 cell height 106px (A) / 101px (B), no hover/selection state visible
```
| metric | value |
|---|---|
| folder icon | **86×78** at icon-left x=346; top y=146 (A) / y=175 (B) |
| icon shape | Breeze folder: back/tab panel **`#1e3545`** (top band 15 px, tab top edge y+0 running x+1…+35, then slope down to y+6 at x≈+44), 1 px lighter bevel `#4b5d6a` on that top edge; front panel **`#2d4f67`** from y+15 with ~5 px chamfer at its top-left; 1 px dark outline `#1d2e3a`; 1 px bottom edge `#29485d`/`#243f52` |
| text left | x=442 = icon-left + 96 (icon 86 + 10 gap) |
| name line | glyph band y=156–162, x-height 7 px → 13 px regular, `#c5c9c5` |
| size line | band y=172–180 (digit height 9 px) → 13 px, `#8d9090` |
| date line | band y=190–198 → 13 px, `#8d9090` |
| line pitch | **18 px** (156 → 172 → 190) |
| text-block offset | name baseline sits ~10 px below icon top; block is optically centred on icon |

### 4.2 State B (grouped by modification date)
Same view box and icon metrics, plus:
- **Group header zone** y=129–174 (46 px), no fill: header text 13 px `#7f807c`, band y=142–153, text starts at
  column start + 11–12 px (measured x = 342, 562, 792, 1027, 1261).
- Header labels, left→right: **`Сегодня`, `Вчера`, `Среда`, `Вторник`, `Неделю назад`**.
- **1 px column dividers `#292727`** at x=550, 781, 1015, 1249, running y=129–768 (they stop above the h-scrollbar zone).
  Measured column widths: 220, 231, 234, 234, 216+ (last clipped).
- First item icon top y=175; **row pitch 101 px**; text bands: name 182–194, size 201–209, date 219–229.
- Items are grouped by date and **within a group ordered by modification time ↓** (today: 15:21 → 03:11 → 02:56),
  even though the dialog snapshot shows sort = «По убыванию» / «Размер» — i.e. state B's sort dropdown is
  modification date (dialog not captured for that state).

### 4.3 Scrollbars
Thin overlay scrollbars, auto-hidden vertical:
- horizontal handle auto-positions at the bottom of the view: y=776–783 (**8 px** tall), rounded;
  A: x=339–516 (178 px wide); B: x=339–438 (100 px wide) — both start 8 px from view-left, fill `#3a3d3e`,
  1 px highlights `#596063` (top) / `#404445` (bottom); track transparent (`#0d0c0c`).
- no vertical scrollbar rendered in either shot (hover-only overlay).

## 5. Bottom bars

### 5.1 Filter bar (y 791–822)
| element | measurement |
|---|---|
| filter glyph | light "lock" glyph 10×12 at x=338–347, y=802–813, `#c5c9c5` |
| filter field | x=364–1431 (1068×29), y=793–821; fill `#0d0c0c`, 1 px border `#434342`, radius 6 |
| placeholder | `Фильтр...` x=372, band y=804–815, 13 px `#696a67` |
| clear-filter button | red ✕ 12×12 at x=1447–1458, y=802–813, `#c4746e` (outside the field, right-aligned) |
| divider | y=822 `#424241` |

### 5.2 Status bar (y 823–853)
- Left text `127 папок. 19 файлов (80,1 МиБ)` x=332, band y=834–846, 13 px `#c5c9c5`.
- Right cluster (all vertically centred at y≈839):
  - label `Масштаб:` x=1076–1135 (13 px `#c5c9c5`);
  - zoom slider groove x=1143–1258 (116×4, y=837–840, rounded); filled part x=1145–1179 **`#23333f`**;
    knob 14 px circle centred (1188.5, 838.5), fill `#282727`, 1 px ring `#545756`; empty groove `#2a2828`;
  - free-space bar x=1268–1338 (70×4, rounded) **`#23333f`**;
  - text `свободно 22,8 ГиБ` x=1348–1461, 13 px `#c5c9c5`.

## 6. «Режим просмотра» dialog (646×364 at 64,52)

| band | y | height | contents |
|---|---|---|---|
| outline | 52 | 1 | `#444343`, radius ≈5 |
| titlebar | 53–80 | **28** | `#282727`; icon 16×16 x≈70–85; title centred; 3 controls right |
| divider | 81 | 1 | `#4f504f` |
| content | 82–414 | 332 | bg `#181616` |

- Title **`Режим просмотра — Dolphin`**, text box x=296–477, y=62–74, 13–14 px `#c5c9c5`.
- Window controls: 3 glyphs at x≈642–651, 668–677, 691–698, y=62–70, `#b9bdb9` (chevrons + ✕).
- Layout grid: **labels right-aligned to x=276**, controls start x=285; content left margin 65, right 708.

### 6.1 Controls
| row | control | box | text / state |
|---|---|---|---|
| y=92–121 | label `Режим просмотра:` | x=160–276 | 13–14 px `#c5c9c5` |
| | combo «Столбцы» | x=285–396, 112×30 | 12×12 view icon at x≈289–298, text `Столбцы` x≈303, `⌄` at x≈385 |
| y=130–159 | label `Сортировка:` | x=199–275 | |
| | combo «По убыванию» | x=285–421, 136×30 | text x≈292, `⌄` at x≈412 |
| | combo «Размер» | x=432–606, 175×30 | text x≈438, `⌄` at x≈597 |

Combos: fill `#282727`, 1 px border `#575856`, radius ≈4, height 30; row pitch 38 px (10 px gap between rows).

### 6.2 Checkbox block
- Section label **`Параметры режима просмотра:`** right-aligned x=76–276, band y=192–203.
- Checkbox indicator **16×16** at x=286–301, radius ≈2; rows pitch **28 px**, box tops y=188, 216, 244, 272, 300;
  labels x=309, 13–14 px `#c5c9c5`, text bands ≈y 191–203 / 220–231 / 247–259 / 275–287 / 303–315.

| # | state | label (exact) |
|---|---|---|
| 1 | ☑ | `Показывать папки перед файлами` |
| 2 | ☑ | `Миниатюры вместо значков` |
| 3 | ☐ | `Разбивать на группы в соответствии с режимом сортировки` |
| 4 | ☑ | `Показывать скрытые файлы` |
| 5 | ☐ | `Показывать скрытые объекты в конце` |

Checked: fill `#1f2931`, border `#2d4f67`, check mark `#c5c9c5` (AA `#a8adab`).
Unchecked: fill `#0d0c0c`, border `#4e4d4c`.

### 6.3 Expander + buttons
- Expander row y≈349–360: chevron `>` x=83–88 (`#c5c9c5`), text **`Дополнительные сведения`** x=99–271, 13 px `#c5c9c5`.
- Button row y=372–403 (**32 px** tall), right-aligned, gaps 8–9 px, right margin 11 px:

| button | x | w | fill | border | text |
|---|---|---|---|---|---|
| `OK` (default, check glyph) | 409–491 | 83 | `#292f34` | `#455661` (blue-grey accent) | `OK` `#c5c9c5` |
| `Применить` (disabled) | 500–606 | 107 | `#262525` | `#363535` | `#757575` |
| `Отмена` (✕-in-circle glyph) | 616–697 | 82 | `#282727` | `#575856` | `#c5c9c5` |

## 7. Design tokens (sampled hex)

`≈` = sampled at antialiased edges / downscaled text; use as-is for screenshot-faithful HTML.

| role | value | where used |
|---|---|---|
| desktop | `#000000` | capture backdrop (not part of window) |
| window outline | `#444343` | 1 px frame of both windows |
| window / base bg | `#181616` | sidebar, filter bar, status bar, dialog body, inter-panel gaps |
| chrome bg | `#282727` | titlebar, toolbar, chrome strip, combos, normal buttons |
| chrome divider light | `#4f504f` / `#4e4f4e` | toolbar↔titlebar, toolbar↔content, dialog titlebar |
| chrome strip | `#282727` (7 px) | full-width band y=119–125 |
| window-bg hairline | `#181616` | 1 px y=127 before content |
| view bg | `#0d0c0c` | file view, location field, filter field, unchecked checkbox |
| view focus border | `#8da4a8` top/left, `#8ba2a6` right/bottom | 1 px around file view |
| primary text | `#c5c9c5` ≈ | titles, item names, path, status, labels, check marks |
| secondary text | `#8d9090` ≈ | item size/date lines, status secondary |
| muted text / group headers / section headers | `#7f807c` | «Сегодня»…, «Точки входа», «В сети», «Недавно изменённые», «Устройства» |
| disabled glyph | `#5e5f5d` | disabled back/forward, scroll-thumb edge |
| dim chevron (tree) | `#3e3d3c` | sidebar expand `>` |
| checked toggle fill | `#3c3b3b` | active view-mode button |
| checked toggle border | `#575856` | active view-mode button, combo/button borders |
| zebra row A | `#181616` | folder-tree even rows |
| zebra row B | `#12120f` | folder-tree odd rows (subtle stripe) |
| sidebar gutter separator | `#2a2828` | 1 px x=305 |
| scrollbar thumb | `#363534` (+`#5e5f5d` edge) | sidebar thumb 6 px |
| h-scrollbar thumb | `#3a3d3e` (+`#596063`/`#404445`) | bottom overlay scrollbar |
| row divider | `#424241` | filter↔status |
| field border | `#434342` | filter field |
| location field border | `#3d3e3e` (inner `#333232`) | breadcrumb field |
| folder body | `#2d4f67` | front panel of Breeze folder icon |
| folder back/tab | `#1e3545` | top band of Breeze folder icon |
| folder outline | `#1d2e3a`; bevel `#4b5d6a`; bottom `#29485d`/`#243f52` | icon edges |
| column divider (grouped) | `#292727` | 1 px between group columns |
| device text + usage bar | `#c4746e` | `archive6`, `Models`, filter clear ✕ |
| device bar track | `#3a3a39` | remaining disk usage |
| accent (filled sliders) | `#23333f` | zoom-slider filled groove, free-space bar |
| slider empty groove | `#2a2828`; knob `#282727` + ring `#545756` | zoom slider |
| placeholder text | `#696a67` | `Фильтр...` |
| checkbox checked fill | `#1f2931`; border `#2d4f67` | checked boxes |
| checkbox unchecked border | `#4e4d4c` | unchecked boxes |
| button default | fill `#292f34`, border `#455661` | `OK` |
| button disabled | fill `#262525`, border `#363535`, text `#757575` | `Применить` |
| window-control glyph | `#b9bdb9` | titlebar `? ⌃⌄ ✕` |

**Palette summary:** near-black neutrals (`#000`→`#0d0c0c`→`#181616`→`#282727`), two text greys (`#c5c9c5`/`#8d9090`), one muted grey (`#7f807c`), one steel-blue icon family (`#1e3545`/`#2d4f67`), one desaturated blue accent (`#23333f`/`#455661`), one warm salmon accent (`#c4746e`). **No bright Breeze blue (#3daee9) appears anywhere.**

## 8. Typography

Font stack suggestion: `"Noto Sans", "Cantarell", "DejaVu Sans", system-ui, sans-serif` (KDE default = Noto Sans; all text regular 400, no bold anywhere).

| element | px | weight | line-height | colour |
|---|---|---|---|---|
| window title (main + dialog) | 13–14 | 400 | ~18 | `#c5c9c5` |
| breadcrumb path | 13 | 400 | — | `#c5c9c5` |
| item name | 13 | 400 | 18 | `#c5c9c5` |
| item size / date | 13 | 400 | 18 | `#8d9090` |
| group header (dates) | 13 | 400 | — | `#7f807c` |
| sidebar tree labels | 13 | 400 | 22 row | `#c5c9c5` |
| sidebar section headers | 13 | 400 | 26 row | `#7f807c` |
| Places labels | 13 | 400 | 26 row | `#c5c9c5` |
| device labels | 13 | 400 | 26 row | `#c4746e` |
| filter placeholder | 13 | 400 | — | `#696a67` |
| status bar / slider labels | 13 | 400 | — | `#c5c9c5` |
| dialog labels / checkboxes | 13–14 | 400 | 28 row | `#c5c9c5` |
| dialog combo text | 13–14 | 400 | 30 box | `#c5c9c5` |
| dialog buttons | 13 | 400 | 32 box | `#c5c9c5` |

Measured glyph heights: x-height 7 px, digits 9 px, cap+descender 12–13 px → base UI font ≈13 px (10 pt at 96 dpi), one font everywhere.

## 9. Item inventory — state A (`183407`)

Sort: size ↓, column-major (down col 1, then col 2 …). Values transcribed from the capture.

| # | col | name | size | date |
|---|---|---|---|---|
| 1 | 1 | `uv` | 16,6 ГиБ | Сегодня в 03:11 |
| 2 | 1 | `pip` | 4,1 ГиБ | 21.09.2025 в 10:45 |
| 3 | 1 | `JetBrains` | 3,4 ГиБ | 14.02.2026 в 18:46 |
| 4 | 1 | `thumbnails` | 1,9 ГиБ | 30.09.2026 в 16:42 |
| 5 | 1 | `ms-playwright` | 1,4 ГиБ | 18.10.2025 в 10:16 |
| 6 | 1 | `mozilla` | 931,9 МиБ | 20.04.2022 в 10:05 |
| 7 | 2 | `trivy` | 848,5 МиБ | 12.12.2025 в 05:01 |
| 8 | 2 | `debuginfod_client` | 548,9 МиБ | 09.02.2026 в 03:30 |
| 9 | 2 | `electron` | 212,9 МиБ | 11.11.2026 в 09:40 |
| 10 | 2 | `tracker3` | 202,1 МиБ | 28.07.2025 в 23:33 |
| 11 | 2 | `discover` | 100,9 МиБ | 09.02.2026 в 02:01 |
| 12 | 2 | `node-gyp` | 94,9 МиБ | 08.08.2025 в 17:25 |
| 13 | 3 | `puppeteer` | 73,1 МиБ | 04.08.2026 в 20:40 |
| 14 | 3 | `Homebrew` | 66,6 МиБ | 23.09.2026 в 19:11 |
| 15 | 3 | `appstream` | 66,2 МиБ | Вчера в 13:21 |
| 16 | 3 | `ccache` | 64,9 МиБ | 12.08.2025 в 18:29 |
| 17 | 3 | `opencode` | 59,4 МиБ | 16.09.2026 в 21:30 |
| 18 | 3 | `systemsettings` | 53,8 МиБ | 09.02.2026 в 00:10 |
| 19 | 4 | `kio_http` | 50,8 МиБ | Вчера в 08:19 |
| 20 | 4 | `nvidia` | 46,4 МиБ | 26.07.2025 в 14:46 |
| 21 | 4 | `huggingface` | 39,7 МиБ | 29.10.2026 в 03:43 |
| 22 | 4 | `mintinstall` | 37,2 МиБ | 09.02.2026 в 17:23 |
| 23 | 4 | `ffmpeg-static-nodejs` | 28,0 МиБ | 04.08.2026 в 20:40 |
| 24 | 4 | `konsole` | 27,1 МиБ | 14.02.2026 в 03:55 |
| 25 | 5 | `plasmashell` | 24,1 МиБ | 09.02.2026 в 01:3… (clipped) |
| 26 | 5 | `gnome-software` | 21,9 МиБ | 01.09.2025 в 16:5… (clipped) |
| 27 | 5 | `selenium` | 17,4 МиБ | 29.12.2025 в 14:2… (clipped) |
| 28 | 5 | `pnpm` | 12,8 МиБ | 11.11.2026 в 07:4… (clipped) |
| 29 | 5 | `onyx` | 8,2 МиБ | 27.02.2026 в 12:5… (clipped) |
| 30 | 5 | `flatpak` | 7,6 МиБ | 08.08.2025 в 03:4… (clipped) |

All 30 items are folders (folder glyph). Status line reports the folder as a whole:
`127 папок. 19 файлов (80,1 МиБ)`; free space `свободно 22,8 ГиБ`.

## 10. Item inventory — state B (`183441`, grouped)

Group columns left→right, items top→bottom within each:

| group header | items (name · size · date) |
|---|---|
| `Сегодня` | `starshp` · 0 Б · Сегодня в 15:21 · `uv` · 16,6 ГиБ · Сегодня в 03:11 · `gh` · 5,9 КиБ · Сегодня в 02:56 |
| `Вчера` | `mc` · 35 Б · Вчера в 15:06 · `bookmarkrunner` · 0 Б · Вчера в 14:52 · `appstream` · 66,2 МиБ · Вчера в 13:21 · `kio_http` · 50,8 МиБ · Вчера в 08:19 · `mpv` · 1,3 МиБ · Вчера в 07:03 · `gstreamer-1.0` · 1,7 МиБ · Вчера в 07:01 |
| `Среда` | `electron` · 212,9 МиБ · 11.11.2026 в 09:40 · `pnpm` · 12,8 МиБ · 11.11.2026 в 07:49 |
| `Вторник` | `gnome-calculator` · 1,9 КиБ · 10.11.2026 в 20:00 |
| `Неделю назад` | `llmfit` · 0 Б · 03.11.2026 в 17:0… (clipped) · `qtshadercache-x8…` · 746,2 КиБ · 02.11.2026 в 01:2… (clipped) |

Chrome, sidebar, filter and status text are byte-identical to state A, including
`127 папок. 19 файлов (80,1 МиБ)` and `свободно 22,8 ГиБ`.

## 11. Signature details (do not lose in variants)

1. **3-line item cell, icon-left** — 86×78 Breeze folder + name/size/date stack, 18 px lines; icon dominates, size/date are greyed.
2. **Column-major flow** — items fill a column top→bottom then wrap; content-width columns (226–238 px) distinguish «Столбцы» from the icon grid.
3. **Date-grouped columns** — muted 13 px captions (`Сегодня`, `Вчера`, `Среда`, …) in a 46 px band, 1 px `#292727` rules between columns.
4. **Breeze folder icons** — two-tone steel-blue (`#1e3545` tab over `#2d4f67` body), 1 px dark outline, light bevel on the tab; flat, no gradients.
5. **KDE titlebar + flat toolbar** — centred title, mono-line controls right; one 28 px flat toolbar (nav / checked toggle / rounded breadcrumb / icon cluster).
6. **Places sidebar, two stacked panels** — zebra-striped folder tree (22 px rows, chevrons) above Places rail with quiet captions (26 px rows), 6 px rounded thumb in 24 px gutter.
7. **Bottom filter + status row** — rounded `Фильтр...` field with red ✕ clear, then `N папок. M файлов (…)` left and `Масштаб:` slider + blue free-space bar + `свободно …` right.
8. **Low-chroma chrome, two accents** — salmon `#c4746e` (devices, clear ✕) and dark desaturated blue `#23333f`/`#455661` (sliders, default-button ring, checkbox ring).

## 12. Preserve vs modernize

**Preserve (identity)**
- Column-major «Столбцы» layout math (content-sized columns, top-to-bottom order, ~101–106 px item cells).
- The 3-line cell and icon-left hierarchy, 18 px line rhythm.
- Date-group columns with muted captions + 1 px rules; exact Russian group words.
- Places rail structure (tree + Places sections + devices with usage bars) and its 22/26 px row cadence.
- Bottom filter/status/zoom strip, because it is what makes the window feel like a file manager.
- Flat, borderless chrome on near-black neutrals; the two accent colours.

**Modernize (safe to change)**
- Text contrast: lift `#8d9090`/`#7f807c` toward ≥4.5:1 — the capture is ~18 % darker than stock Breeze Dark (canonical `#eff0f1`).
- Titlebar controls: replace the 5 mono-line glyphs with a coherent minimize/maximize/close set; keep the centred title.
- Rounder geometry: field/button radius 6→8 px, toggle 4→6 px (keep 1 px borders).
- Missing states: design hover/focus/selection explicitly (`#262525`-family row hover, `#2d4f67`-family selection, 1 px `#455661` focus ring).
- Icon: allow an SVG folder in the same two-tone palette; keep 86×78 at this density.
- Density: express the spec on a 4-px base grid (22/26/28/30/32/36 px bands, 18 px text line-height, 10–11 px icon-text gap).

---

*Measurement helper: `design/reference/measure.py` (re-runnable: `python3 design/reference/measure.py`).*
