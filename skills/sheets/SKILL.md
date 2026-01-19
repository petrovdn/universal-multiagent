---
name: sheets
description: >
  Работа с Google Sheets. Используй когда пользователь просит
  открыть таблицу, получить данные, создать таблицу, 
  записать данные, обновить ячейки.
metadata:
  type: domain
  version: "1.0"
  tools:
    - get_sheet_data
    - get_all_sheets_data
    - create_spreadsheet
    - add_rows
    - update_cells
    - format_cells
    - get_spreadsheet_info
---

## Когда активировать

Ключевые слова: "таблица", "spreadsheet", "excel", "данные", "ячейки"

Активируй этот skill когда пользователь:
- Просит открыть или показать таблицу
- Хочет получить данные из таблицы
- Просит создать новую таблицу
- Хочет записать или обновить данные

## Приоритетные инструменты

1. **`get_sheet_data`** — получить данные (для "покажи таблицу")
2. **`create_spreadsheet`** — создать новую таблицу
3. **`add_rows`** — добавить строки с данными
4. **`update_cells`** — обновить конкретные ячейки

## Workflow

### Прочитать таблицу
1. Если есть spreadsheet_id — используй `get_sheet_data`
2. Если нужны все листы — используй `get_all_sheets_data`
3. Укажи range для конкретного диапазона (например, "A1:D10")

### Создать таблицу
1. Используй `create_spreadsheet` с title
2. Получишь spreadsheet_id для дальнейшей работы

### Записать данные
1. Используй `add_rows` для добавления в конец
2. Используй `update_cells` для обновления конкретных ячеек
3. Формат values: [[row1_col1, row1_col2], [row2_col1, row2_col2]]
