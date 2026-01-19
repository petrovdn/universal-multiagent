---
name: workspace
description: >
  Работа с файлами в Google Drive. Используй когда пользователь
  ищет файл, хочет список файлов, или нужно найти документ
  по названию.
metadata:
  type: domain
  version: "1.0"
  tools:
    - search_files
    - list_files
    - get_file_info
    - open_file
    - find_and_open_file
---

## Когда активировать

Ключевые слова: "файл", "найди", "открой", "диск", "drive"

Активируй этот skill когда пользователь:
- Ищет файл по названию
- Просит показать файлы в папке
- Хочет найти документ/таблицу/презентацию

## Приоритетные инструменты

1. **`search_files`** — поиск по названию и типу
2. **`find_and_open_file`** — найти и сразу получить содержимое
3. **`list_files`** — список файлов в папке

## Workflow

### Найти файл
1. Используй `search_files` с query
2. Для фильтра по типу: mime_type (presentation, spreadsheet, document)
3. Получишь список с file_id для дальнейшей работы
