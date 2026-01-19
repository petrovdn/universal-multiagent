---
name: docs
description: >
  Работа с Google Docs. Используй когда пользователь просит
  открыть документ, прочитать текст, создать документ,
  отредактировать или отформатировать.
metadata:
  type: domain
  version: "1.0"
  tools:
    - read_document
    - create_document
    - update_document
    - append_to_document
    - format_document_text
    - format_document_paragraph
---

## Когда активировать

Ключевые слова: "документ", "doc", "текст", "файл", "прочитать"

Активируй этот skill когда пользователь:
- Просит открыть или прочитать документ
- Хочет создать новый документ
- Просит отредактировать документ
- Хочет отформатировать текст

## Приоритетные инструменты

1. **`read_document`** — прочитать содержимое
2. **`create_document`** — создать новый документ
3. **`append_to_document`** — добавить текст в конец
4. **`update_document`** — заменить текст

## Workflow

### Прочитать документ
1. Если есть document_id — используй `read_document`
2. Если нужно найти — сначала `search_files` из workspace

### Создать документ
1. Используй `create_document` с title и content
2. Получишь document_id для дальнейшей работы
