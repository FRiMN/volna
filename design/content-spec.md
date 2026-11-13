# «Волна» — file manager — shared content spec

> Working name of the app: **Волна** (`volna`). All variants show the SAME screen content so they can be compared as design directions, not as different features.
> Locale: Russian. Platform: Linux desktop app window. Design canvas: 1440×900 (window inside a neutral studio backdrop).

## 1. Window

- Title: `.cache — Волна`
- Path: `/home/frimm/.cache/`
- Window = desktop app chrome + 4 regions: titlebar, toolbar, body (sidebar + content), footer (filter + status).

## 2. Toolbar (left → right)

| group | items |
|---|---|
| Navigation | Назад (back), Вперёд (forward), Вверх (up) |
| View modes | Значки (icons), **Столбцы (columns) — ACTIVE**, Подробности (details) |
| Panes | Разделить вид (split view), Новая вкладка (new tab) |
| Location | breadcrumb field `/home/frimm/.cache/` with a dropdown chevron on the right edge |
| Actions | Принять/перейти (✓), Поиск (magnifier), Меню (hamburger ☰) |

Reference detail: the active view-mode button («Столбцы») has a blue/accent highlight; toolbar icons are flat symbolic 22–24 px.

## 3. Sidebar (left, scrollable, section headers + rows)

Sections in this order (headers are dimmer, smaller):

1. *(unnumbered home-subfolder list, expandable rows with `>` chevrons)*: Видео, Документы, Загрузки, Изображения, Музыка, Общедоступные, Рабочий стол, Шаблоны, any-limb, audacity4, backup, barbaros
2. **Точки входа**: Домашняя папка, Рабочий стол, Документы, Загрузки, Музыка, Изображения, Видеофайлы, Корзина
3. **В сети**: Сеть
4. **Недавно изменённые**: Последние файлы, Последние расположения
5. **Устройства**: archive6 (usage bar ≈ 90 %, red), Models (usage bar ≈ 85 %, red)

Sidebar rows: symbolic 16 px icon + label, row height ~26 px, selected/hover tint. Sidebar has its own vertical scrollbar.

## 4. Main area — the signature Dolphin «Столбцы» (Columns) view

A horizontally scrollable band of **columns grouped by modification date**, each column separated by a vertical rule, each item = large folder icon on the left + a 3-line text stack on the right (name / size / modified date). Column headers (group titles) are at the top of the band.

Primary state (grouped by date — use this one in all variants):

| Column header | Items (name — size — modified) |
|---|---|
| Сегодня | starshp — 0 Б — Сегодня в 15:21 · uv — 16,6 ГиБ — Сегодня в 03:11 · gh — 5,9 КиБ — Сегодня в 02:56 |
| Вчера | mc — 35 Б — Вчера в 15:06 · bookmarkrunner — 0 Б — Вчера в 14:52 · appstream — 66,2 МиБ — Вчера в 13:21 · kio_http — 50,8 МиБ — Вчера в 08:19 · mpv — 1,3 МиБ — Вчера в 07:03 · gstreamer-1.0 — 1,7 МиБ — Вчера в 07:01 |
| Среда | electron — 212,9 МиБ — 11.11.2026 в 09:40 · pnpm — 12,8 МиБ — 11.11.2026 в 07:49 |
| Вторник | gnome-calculator — 1,9 КиБ — 10.11.2026 в 20:00 |
| Неделю назад | llmfit — 0 Б — 03.11.2026 в 17:01 · qtshadercache-x86… — 746,2 КиБ — 02.11.2026 в 01:22 |

Secondary state (ungrouped, sorted by size descending — optional "alternate state" toggle inside a variant):
uv 16,6 ГиБ · pip 4,1 ГиБ · JetBrains 3,4 ГиБ · thumbnails 1,9 ГиБ · ms-playwright 1,4 ГиБ · mozilla 931,9 МиБ · trivy 848,5 МиБ · debuginfod_client 548,9 МиБ · electron 212,9 МиБ · tracker3 202,1 МиБ · discover 100,9 МиБ · node-gyp 94,9 МиБ · puppeteer 73,1 МиБ · Homebrew 66,6 МиБ · appstream 66,2 МиБ · ccache 64,9 МиБ · opencode 59,4 МиБ · systemsettings 53,8 МиБ · kio_http 50,8 МиБ · nvidia 46,4 МиБ · huggingface 39,7 МиБ · mintinstall 37,2 МиБ · ffmpeg-static-nodejs 28,0 МиБ · konsole 27,1 МиБ · plasmashell 24,1 МиБ · gnome-software 21,9 МиБ · selenium 17,4 МиБ · pnpm 12,8 МиБ · onyx 8,2 МиБ · flatpak 7,6 МиБ — plus dates as in the reference.

Horizontal scrollbar below the columns band.

## 5. Footer

- Filter row: funnel icon + placeholder `Фильтр...` in a full-width rounded field + clear (×) button on the right.
- Status bar left: `127 папок. 19 файлов (80,1 МиБ)`
- Status bar right: `Масштаб:` + slider | free-space indicator bar + `свободно 22,8 ГиБ`

## 6. Secondary screen (variant A / C): «Режим просмотра» dialog

- Title: `Режим просмотра — Волна` (reference: `— Dolphin`)
- Row: `Режим просмотра:` [combo «Столбцы» with view icon]
- Row: `Сортировка:` [combo «По убыванию»] [combo «Размер»]
- Group label: `Параметры режима просмотра:`
- Checkboxes: `Показывать папки перед файлами` ✓, `Миниатюры вместо значков` ✓, `Разбивать на группы в соответствии с режимом сортировки` ☐, `Показывать скрытые файлы` ✓, `Показывать скрытые объекты в конце` ☐
- Expanding row: `› Дополнительные сведения`
- Buttons: `✓ OK` (primary), `✓ Применить` (disabled), `⊗ Отмена`

## 7. Shared content rules for all variants

- No lorem ipsum, no placeholder folders: use exactly the names/sizes/dates above.
- Russian UI copy everywhere (including tooltips where used).
- Same window title and path in every variant.
- Difference between variants = chrome, panel arrangement, density, palette, typography, icon language — NOT content.
- Folder icons: variant A keeps a Breeze-like blue folder; variants B/C may use a JetBrains-flavoured folder/«папка» icon but must stay blue-family so the screen reads as a file manager.
- All chrome icons: inline SVG (no icon fonts, no external assets, no CDN). Self-contained single-file HTML.
