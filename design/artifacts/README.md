# Артефакты дизайна

Три самодостаточных HTML-макета (inline CSS/JS/SVG, без внешних ресурсов, окно 1440×900, русская UI):

| Файл | Вариант | Роль |
|---|---|---|
| [`variant-c.html`](variant-c.html) | **C — Dolphin × JetBrains** | **Канон.** Все три режима просмотра, группировка, «Вид», путь с редактированием, статус-бар со статусом и `sdc1` |
| [`variant-b.html`](variant-b.html) | B — JetBrains Workbench | Референс панельной грамматики, поповеров и светлой темы |
| [`variant-a.html`](variant-a.html) | A — Dolphin Breeze | Референс верности Dolphin: «Столбцы», палитра Breeze, диалог «Режим просмотра» |

## Открыть

```bash
cd design/artifacts
python3 -m http.server 8080
# http://localhost:8080/variant-c.html
```

Состояния канонического макета: `#view`, `#presets`, `#presets-save`, `#icons`, `#details`, `#ungrouped`, `#icons-ungrouped`.

## Происхождение

Макеты сгенерированы в OpenDesign и доведены итерациями по фидбеку:

- проекты OpenDesign: `volna-a-dolphin-breeze`, `volna-b-jetbrains-workbench`, `volna-c-hybrid`;
- предыдущие итерации сохранены в [`design/backups/`](../backups/);
- скриншоты состояний — в [`design/screens/`](../screens/);
- спецификация — в [`design/spec/`](../spec/README.md).

Артефакты в этом каталоге — источник истины для репозитория; превью OpenDesign живёт в рамках сессии демона и не является долговременным хранилищем.
