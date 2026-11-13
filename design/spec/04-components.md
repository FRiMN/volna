# 04 · Компоненты

Все компоненты — часть одного окна 1440×900. Состояния: `default`, `hover`, `active/pressed`, `focus-visible`, `selected`, `disabled`, `empty`. Фокус — 1px accent ring с offset 1px (внутри скруглений — offset −1px).

## 1. Тулбар (40px, chrome)

| Элемент | Размер | Стиль/состояния |
|---|---|---|
| Меню ☰ | 40×40 | иконка 20, hover `#393b40`, radius 4 |
| Назад/вперёд/вверх | 24×24 | иконки 16; disabled — `#6f737a`, без hover |
| Separator | 1×20 | `--divider-line`, отступы 6px |
| «Вид» widget | 28px высота, padding 0 8 | иконка 16 + label 13 + шеврон 16; hover `#393b40`; `aria-haspopup`, `aria-expanded` |
| Path widget | flex, 28px | иконка папки 16, путь 13 (truncate), шеврон; hover; клик — dropdown |
| Path edit | 24×24 | карандаш 16, title «Изменить путь» |
| Path input (режим редактирования) | 24px высота, mono 12 | select-all, accent-border при фокусе; Enter/Blur/Esc |
| Spacer | flex | не даёт правой группе двигаться |
| Настройки ⚙ | 24×24 | поповер: «Сбросить масштаб», «Очистить фильтр», «Сбросить сортировку» |
| Window controls | 40×40 | свернуть/развернуть/закрыть; close hover `#db5c5c` |

## 2. Поповер «Вид» (display settings)

Анатомия:

```
┌ Вид ─────────────────────────── 320px ┐
│ Режим просмотра                       │
│  ○ Значки                             │
│  ● Столбцы                            │
│  ○ Подробности                        │
│ ─────────────────────────────────────  │
│ Группировка                           │
│  ● По дате изменения                  │
│  ○ Без группировки                    │
│ ─────────────────────────────────────  │
│ Сортировка                            │
│  ● Дата изменения                     │
│  ○ Размер                             │
│  ○ Имя                                │
│  [ По убыванию | По возрастанию ]     │
│ ─────────────────────────────────────  │
│ Параметры                             │
│  ☐ Показывать скрытые файлы           │
│  ☐ Плотная раскладка                  │
│ ─────────────────────────────────────  │
│ Масштаб   ──────●──────  100%         │
│ ─────────────────────────────────────  │
│ Изменения применяются сразу            │
└────────────────────────────────────────┘
```

| Часть | Метрики |
|---|---|
| Header | 13px/600 primary, margin-bottom 6 |
| Section | padding 8 0; между секциями 1px `#393b40` |
| Section title | 11px/600 secondary, `letter-spacing .02em`, title case |
| Row | 26px, padding 0 4, radius 4, hover `#393b40`; label 13 primary |
| Radio | 14px, border 1.5px `#6f737a`; selected — accent border + 5px dot accent |
| Checkbox | 14px, border 1.5px `#6f737a`, radius 3; checked — accent fill + 10px check icon белый |
| Segmented | контейнер `#1e1f22`, 1px border, radius 6, padding 2, gap 2; кнопка 24px, radius 4; active `#393b40` + primary text; inactive secondary |
| Zoom | слайдер 96×14 (трек 4), thumb 10 accent; проценты mono 12, min-width 38, right |
| Footer | 11px muted, border-top 1px, margin-top 6, padding-top 8 |
| Поведение | открытие/закрытие, `aria-expanded`, весь поповер скроллится при max-height 820 |

Все изменения применяются сразу, без кнопки «Применить».

## 3. Рейлы (tool windows)

- Ширина 40, фон chrome, padding 4 0; кнопки 32×32, radius 4, иконки 20.
- `hover` `#393b40`; `is-active` — фон `#43454a` + иконка primary; без подписей (только `title`).
- Левый: Места (active), Файлы, Закладки, Недавние, Устройства, Сеть, separator, Корзина.
- Правый: Сведения (active), Предпросмотр. Терминала и настроек в рейлах нет.
- Клик переключает содержимое панели; повторный клик по активному — допустимо оставить как действие «показать панель», но не создавать дубль контрола.

## 4. Header band

- Левый заголовок: шеврон 16 + title 13/600 + действия 24×24 (refresh, «…», hide), padding 0 8.
- Табы: 40px, max-width 220, padding 0 10, gap 6, label 13, иконка 16; inactive secondary, active primary + 3px accent underline по низу; close 16×16 появляется на hover/active, hover-фон `#4a4d52`.
- Правый заголовок: title 13/600 + «…» + hide; same metrics.
- Фон панельных заголовков chrome, таб-стрипа canvas; снизу 1px `#393b40`.

## 5. Левая панель «Места»

- Панельный тулбар 32: поле поиска 24 (иконка 16, placeholder «Поиск…», радиус 4, focus — accent border), кнопки фильтра/сортировки 24.
- Дерево: `p-row` 24px, margin 0 4, padding 0 4, radius 4; twisty 16, indent 16/уровень, иконка 16, label 13, sub 11 mono muted.
- Секции (`p-row.is-group`): 12px/600 secondary.
- Устройства: label + usage-bar 3px высотой (track `#3c3f44`, fill `#db5c5c`), отступ 10 справа.
- Выбор: `is-selected` → `#43454a`; hover `#393b40`; фокус — accent ring.
- Empty state поиска: 12px secondary; скролл вертикальный 8px.
- Никаких дублирующихся локаций; «Домашняя папка» встречается один раз.

## 6. Редактор

### 6.1 Тулбар редактора (32px)

- Поле фильтра: 200×24, фон `#26282d`, border `#393b40`, радиус 4; funnel 16 secondary; placeholder «Фильтр…» 12 muted; clear 16×16.
- Separator, spacer, счётчики 11 muted («127 папок · 19 файлов (80,1 МиБ)»).
- Никаких кнопок видов/сортировки — они в «Вид».

### 6.2 Полоса контента (`.band`, 576px)

Общие состояния: пусто (`Нет совпадений` + «Попробуйте изменить запрос») по центру; заметка `bandNote` снизу; скролл-бары 8px overlay.

#### «Столбцы» (grouped)

- Контейнер `band-inner`: flex, `width: max-content`, горизонтальный скролл.
- Колонка: width `--col-w` (236 по умолчанию; зум 200–280), вертикальная граница 1px `#393b40`; header 28px: label 12/600 secondary + count 11 mono muted (справа), клик сворачивает группу (aria-expanded); свёрнутая — заголовок + «N объектов» muted.
- Item: 62px (плотная — 54), padding 6 8, margin-bottom 2, radius 4, flex: иконка 48 (плотная 40; зум 40–56) + 3-строчный текст (name 12.5 primary, size/date 11 mono muted, межстрочный 1–1.25), gap 8–10.
- Hover — `#393b40`; selected — `#1d2432`; focus — accent ring; hidden-элемент — приглушённые иконка/текст.
- Групповые headers — по одной колонке на дату («Сегодня», «Вчера», «Среда», «Вторник», «Неделю назад»).

#### «Значки» (grouped)

- Секции по датам: header 28px (label 12/600 secondary + count 11 mono muted, border-bottom), затем grid.
- Grid: `repeat(auto-fill, minmax(150px, 178px))`, gap 6, padding 0 0 6; выравнивание `space-between`.
- Плитка: min-height 150 (плотная 132), padding 10 8 8, radius 6, центр; иконка 48–72 (зум), имя 12.5 до 2 строк (`line-clamp:2`), size/date 11 mono muted; hover `#393b40`; selected `#1d2432`; hidden — приглушение.
- Вертикальный скролл всей полосы.

#### «Подробности» (grouped)

- Sticky header 28px: grid `minmax(0,1fr) 96px 168px 76px`, gap 12, padding 0 14; заголовки «Имя / Размер / Изменён / Тип» 11/600 secondary, размер/дата right-aligned; border-bottom.
- Групповая строка 28px: label 12/600 secondary + count 11 mono muted; фон `#26282d`, линии сверху/снизу.
- Строка 24px: иконка 16 + name 12.5 primary; size/date 12 mono secondary (right); type 12 secondary; hover `#393b40`; selected `#1d2432`; hidden — приглушение; focus — accent ring.
- Вертикальный скролл.

#### Без группировки

- «Значки» и «Подробности» — те же компоненты без заголовков групп, единым списком/сеткой.
- «Столбцы» — безголовые колонки: content-sized (min-width 190), по 6 строк на колонку, горизонтальный скролл; порядок — сортировка, затем заполнение колонки сверху вниз (column-major).

## 7. Правая панель «Сведения»

- Заголовок в header band: «Сведения» 13/600 + «…» (показать в дереве / скрыть панель) + hide.
- Тело (скролл вертикальный): карточка (иконка 64, имя 16/600, тип 12 secondary) в `#26282d`, radius 4; метаданные: строки 24px (label 11 secondary слева, value 13 primary/mono справа; path переносится mono 12); секции «Доступ» (владелец/группа/остальные → чтение/запись) и «Содержимое» (Папок 127 / Файлов 19) — заголовки 12/600 secondary.
- Действия снизу: `Открыть` (accent, 32px, radius 4, white) и `Показать в папке` (ghost, border `#393b40`, 32px); gap 8, padding 12, border-top.
- Empty state: «Объект не выбран» + подсказка.
- Выбранный объект может быть файлом — тип/права меняются.

## 8. Bottom window

- Шапка 40: табы «Операции»/«Журнал» (40px, padding 0 12, active primary + 3px underline), справа «—» и «…».
- Контент 140, padding 10 12: строки операций 24px (иконка 16, name 13, progress 4px радиус 2, %, скорость mono 12, статус); журнал — mono 12, время в начале строки.
- Прогресс: track `#393b40`, fill accent (в работе) / success (готово) / muted (очередь); width по проценту.
- Свёрнуто: 40px, остаётся только шапка; меню «…» — «Очистить завершённые» (disabled, если нет завершённых).

## 9. Status bar

- 28px, chrome, padding 0 8, gap 12, left/right.
- Слева: `sb-status` 12px secondary (`Готово.`) / muted (`Сканирование…`); `role="status"`, `aria-live="polite"`.
- Справа: `свободно 22,8 ГиБ` с иконкой диска 14, разделитель «·», `sdc1` (mono 12).
- Ни зума, ни пути, ни режима просмотра, ни счётчиков.

## 10. Поповеры действий

- Общий стиль: min-width 190, padding 4, radius 8, фон chrome, border `#393b40`, тень `0 8px 24px rgba(0,0,0,.45)`, z-index 40.
- Пункт: высота 26, padding 0 8, radius 4, label 13, hover `#393b40`; check-иконка 16 accent/primary.
- Позиции: вниз от триггера (`top: calc(100% + 4px)`), вверх (`.up`), вправо (`.to-right`).
- Закрытие: клик вне, Esc, выбор пункта; у триггера `aria-expanded`.
- Настройки (⚙): «Сбросить масштаб», «Очистить фильтр», «Сбросить сортировку»; после действия — закрыть поповер.

## 11. Состояние «приложение закрыто» (прототип)

Отдельная карточка вне окна (фон затемнён): заголовок «Волна» 18/600, описание 13 secondary, primary-кнопка «Открыть Волну». В реальном приложении не нужно (закрытие = выход), оставлено для демонстрации оконных контролов.
