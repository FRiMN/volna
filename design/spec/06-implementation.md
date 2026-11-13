# 06 · Реализация и контракт артефакта

## 1. Формат артефакта

Канонический макет — **один файл** [`design/artifacts/variant-c.html`](../artifacts/variant-c.html):

- один `index.html`-подобный документ: inline `<style>`, inline `<script>`, inline SVG-спрайт (`<symbol>`/`<use>`);
- **ноль внешних ресурсов**: никаких CDN, веб-шрифтов, картинок по URL, `@import`, fetch;
- окно 1440×900 внутри «сцены», масштабируется `transform: scale(var(--scale))`;
- только тёмная тема (light описан как референс, реализован в B);
- язык — русский; данные — демонстрационные из референса;
- работает при открытии файла напрямую (`file://`) и через HTTP.

Требования к производительности: без зависимостей, < 160 KB, без тяжёлых анимаций; перерисовка полосы — синхронная, на сотнях элементов.

## 2. Стек и структура

- HTML5, CSS3 (custom properties, flex/grid), ES5-совместимый JS (IIFE, без модулей/сборки).
- Секции файла (условно): `<style>` с токенами и компонентами → разметка окна → `<script>` с моделью `VIEWS`, рендерами и обработчиками.
- Никаких фреймворков; DOM создаётся императивно (`document.createElement`, `innerHTML` для статичных фрагментов).

## 3. Данные

```
VIEWS = {
  cache:     { label: '.cache',           path: '/home/frimm/.cache',     defaultSel: 'uv' },
  home:      { label: 'Домашняя папка',   path: '/home/frimm',            defaultSel: 'Видео' },
  downloads: { label: 'Загрузки',         path: '/home/frimm/Загрузки',   defaultSel: 'installer.AppImage' }
}
```

- Каждое представление содержит `groups[]` (5 групп дат для `cache`) c `items[]`.
- Элемент: `n` (имя), `s` (размер, «16,6 ГиБ»/«—»), `d` (дата отображения), `t` (сортировочный ключ `YYYYMMDDhhmm`), `c` (создан), `k` (`folder`/`file`), опционально `hidden`.
- Счётчики: «127 папок · 19 файлов (80,1 МиБ)»; свободное место «22,8 ГиБ»; устройство `sdc1`.
- Скрытые элементы добавляются динамически: `.gitignore` (группа 0), `.cache.lock` (группа 1).
- Пресеты: массив `{id,name,settings}`; built-in — константа `BUILTIN_PRESETS`; пользовательские — `localStorage['volna.presets.v1']` (JSON); снапшот настроек: `viewMode, grouping, sort, sortDir, showHidden, compact, zoom`. Перекрытие по имени (case-insensitive); при недоступном storage — память.

## 4. Ключевые id/классы (контракт DOM)

| id / класс | Роль |
|---|---|
| `#stage`, `#appWindow` | сцена и окно (масштаб, размеры, `is-compact`) |
| `#btnMenu`, `#btnBack`, `#btnFwd`, `#btnUp` | меню и навигация |
| `#btnView`, `#popView` | триггер и поповер «Вид» |
| `#viewZoom`, `#viewZoomValue` | слайдер масштаба и % |
| `#btnPresetSelect`, `#presetName`, `#presetList` | выбор пресета, текущее имя, инлайн-список |
| `#btnPresetSave` | кнопка сохранения пресета |
| `#presetModal`, `#presetNameInput`, `#presetExisting`, `#presetHint`, `#btnPresetCancel`, `#btnPresetConfirm` | диалог сохранения пресета |
| `#presetDeleteModal`, `#presetDeleteText`, `#btnPresetDeleteCancel`, `#btnPresetDeleteConfirm` | диалог удаления пресета |
| `.preset-item`, `.preset-apply`, `.preset-actions`, `.preset-act[data-preset-rename]`, `.preset-act[data-preset-delete]`, `.preset-rename-input` | строка списка пресетов, действия, инлайн-переименование |
| `#btnLocation`, `#locationLabel`, `#popLocation` | путь и dropdown |
| `#pathWidget`, `#pathAnchor`, `#btnPathEdit`, `#pathInput` | путь, редактирование |
| `#btnSettings`, `#popSettings` | настройки-сбросы |
| `#tabStrip` + `.tab[data-tab]` | табы `.cache`/`home`/`downloads` |
| `#railLeft`, `#railRight` + `.rail-btn[data-action]` | рейлы |
| `#leftPanel`, `#rightPanel`, `#rightTitle` | панели |
| `#placesSearch`, `#tree`/`#placesList` | поиск и дерево «Места» |
| `#filterInput`, `#filterClear`, `#editorCounts` | фильтр и счётчики |
| `#band`, `#bandInner`, `#bandEmpty`, `#bandNote` | полоса контента и состояния |
| `#detailBody`, `#detailActions`, `#btnOpen`, `#btnReveal` | инспектор и действия |
| `#bottomWindow`, `.bw-tab[data-btab]`, `#paneOps`, `#paneLog` | нижняя панель |
| `#statusText` | статус (role=status) |
| `#btnMin`, `#btnMax`, `#btnClose`, `#closedState`, `#btnReopen` | окно/состояние закрытия |
| `.band.is-icons` / `.is-details` / `.is-ungrouped` | режимы полосы |
| `.column`, `.col-head`, `.col-item` | «Столбцы» |
| `.icon-section`, `.icon-grid`, `.icon-tile` | «Значки» |
| `.details-head`, `.details-group`, `.dt-row` | «Подробности» |
| `.p-row`, `.p-row.is-group` | строки дерева |
| `.vp-*` | компоненты поповера «Вид» |
| `.preset-field`, `.preset-select`, `.preset-save`, `.preset-list`, `.preset-item`, `.preset-check` | пресеты в поповере |
| `.preset-modal`, `.preset-dialog`, `.preset-name-input`, `.preset-existing`, `.preset-hint`, `.preset-actions`, `.preset-btn` | диалог сохранения пресета |
| `.is-active`, `.is-current`, `.is-checked`, `.is-selected`, `.is-hidden`, `.is-scanning`, `.is-compact` | состояния |

Если имена классов меняются при переносе в продукт, семантика и структура компонентов должны сохраниться.

## 5. Рендер-модель

- `renderBand()` — диспетчер: `icons` → `renderIcons()`, `columns` + `grouping=none` → `renderColumnsUngrouped()`, `columns` → grouped columns, `details` → `renderDetailsView()`.
- `renderDetails()` — инспектор (не путать с режимом «Подробности»).
- `renderStatus()`, `renderTabs()`, `renderPlaces()`, `applyZoom()`, `syncViewPopover()` — вспомогательные.
- Пресеты: `allPresets()`, `applyPreset(id)`, `markPresetManual()`, `openPresetModal()`, `savePresetFromModal()`, `syncPresetLabel()`, `renderPresetList()`, `persistCustomPresets()`; `state.presetId`/`presetDirty`; localStorage-ключ `volna.presets.v1`. Переименование/удаление: `buildPresetRow()`, `beginPresetRename()`, `commitPresetRename()`, `cancelPresetRename()`, `openPresetDeleteConfirm()`, `deletePreset()`, `restorePresetRow()`.
- Общие хелперы: `visibleGroups()` (группы + скрытые), `sortedItems()`, `sizeBytes()` (парсинг русских единиц), `esc()` (экранирование), `ICON(name,size)`.
- Перерисовка полосы не должна сбрасывать скролл при клике выбора (точечное обновление классов), но может сбрасывать при смене режима/данных.
- `fit()` пересчитывает `--scale`; `applyZoom()` — `--col-w`, `--icon-size`, `--tile-icon`, значения слайдера.

## 6. CSS-архитектура

- Токены — в `:root`, никакого хардкода цветов в компонентах (кроме декоративных оттенков папок/теней).
- `--app-h: 900px`, `--left-w: 280px`, `--right-w: 300px`, `--bottom-h: 180px` (на window-элементе).
- BEM-подобные классы (`vp-row`, `dt-row`, `icon-tile`) без вложенности и без CSS-модулей.
- Стейт-классы на корне окна (`is-compact`, `is-icons` на `.band`) — предпочтительнее инлайновых стилей.
- Z-index — только из таблицы слоёв (см. [03-layout.md](03-layout.md#12-слои-z-index)).

## 7. QA-процесс

```bash
# 1) локальный сервер
cd design/artifacts && python3 -m http.server 8080

# 2) скриншоты рабочих состояний
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html"           design/screens/variant-c.png 1600 1000
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#view"      design/screens/variant-c-view.png
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#presets"   design/screens/variant-c-presets.png
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#presets-save" design/screens/variant-c-preset-save.png
# rename/delete/actions — через CDP (hover/click), см. скриншоты variant-c-preset*.png
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#icons"     design/screens/variant-c-icons.png
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#details"   design/screens/variant-c-details.png
design/tools/shot.sh "http://127.0.0.1:8080/variant-c.html#ungrouped" design/screens/variant-c-ungrouped.png

# 3) коллаж A/B/C
python3 design/tools/build_compare.py
```

`shot.sh` использует chromium headless с `--force-device-scale-factor=2` и `--virtual-time-budget=4000`; окно должно занимать 1440×900 внутри 1600×1000.

Перед сдачей: пройти [08-acceptance.md](08-acceptance.md), проверить отсутствие console errors, сверить попадание в 1440×900, отсутствие клиппинга/наложений.

## 8. Интеграция с OpenDesign

- Макет создавался в OpenDesign-проектах `volna-a-dolphin-breeze`, `volna-b-jetbrains-workbench`, `volna-c-hybrid`; текущие файлы скопированы в `design/artifacts/` как канон для репозитория.
- Превью OpenDesign (`http://127.0.0.1:7457/api/projects/<id>/raw/index.html`) живёт в рамках сессии демона; в репозитории источником истины считаются `design/artifacts/*.html`.
- Окружение/фикс free-tier OpenDesign — [`design/runtime-fix.md`](../runtime-fix.md).

## 9. Ограничения прототипа

| Ограничение | Причина/следствие |
|---|---|
| Нет реального файлового I/O | данные статичны; «Открыть»/«Показать в папке» — навигационные демо-действия |
| Закрытие окна = карточка «приложение закрыто» | демонстрация оконных контролов; в продукте — выход |
| Закрытие табов декоративное | close-иконка показывается, но не удаляет вкладку |
| «Сканирование…» — таймер | эмуляция статуса; в продукте — реальные операции |
| Свободное место/`sdc1` статичны | значение тома фиксировано для макета |
| «Подробности» не масштабируются | сохранён JetBrains-стандарт 24px строк; зум действует на иконки/колонки |
| Встроенные пресеты неизменяемы | переименование/удаление только для пользовательских; встроенный можно перекрыть сохранением под тем же именем |
| Светлая тема отсутствует в C | первичная тема тёмная; light — референс B |
| Нет сохранения состояния | при перезагрузке возвращаются дефолты; **исключение** — пользовательские пресеты сохраняются в `localStorage` |

## 10. Рекомендации по переносу в продукт

1. Сохранить 40/24/28-ритм и палитру как токены темы; не вводить третий серый.
2. «Вид» — поповер, а не модальное окно; изменения live.
3. Путь — в тулбаре с inline-редактированием; в статус-баре только статус + том/устройство.
4. Три режима — один диспетчер рендера; не дублировать контролы режимов в других местах.
5. Настройки отображения — единый state-объект; сохранение в профиль пользователя.
6. Статус — реальный канал событий (scan/transfer/ready), а не таймер.
7. Для доступности: сохранить роли/aria из макета, keyboard-only проход по всем интерактивным элементам.
8. Реализовать light-тему по референсу B, не изобретая новую палитру.
