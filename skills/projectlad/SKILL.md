---
name: projectlad
description: >
  Работа с Project Lad - системой управления проектами.
  Используй когда пользователь просит данные о проектах, работах,
  загрузке ресурсов, диаграмме Ганта.
metadata:
  type: domain
  version: "1.0"
  keywords:
    - PL
    - ПЛ
    - Project Lad
    - ProjectLad
    - проект лад
    - лад
    - проекты
    - портфель проектов
    - диаграмма ганта
    - гант
    - календарное планирование
    - график проекта
    - график
    - работы проекта
    - вехи
    - показатели
    - аналитика
  tools:
    - projectlad_list_projects
    - projectlad_get_project
    - projectlad_get_project_works
    - projectlad_get_milestones
    - projectlad_get_indicators
    - projectlad_get_indicator_analytics
---

## Когда активировать

Активируй этот skill когда пользователь:
- Упоминает "PL", "Project Lad", "проект лад"
- Просит данные о проектах, работах
- Хочет увидеть диаграмму Ганта
- Спрашивает о загрузке ресурсов
- Интересуется показателями проектов

## Приоритетные инструменты

1. **projectlad_list_projects** — список всех проектов
2. **projectlad_get_project_works** — работы проекта (для Ганта)
3. **projectlad_get_indicators** — показатели проекта

## Workflow

### Получить список проектов
1. Вызови projectlad_list_projects
2. Покажи пользователю список с названиями и ID

### Показать диаграмму Ганта
1. Вызови projectlad_list_projects чтобы получить project_id
2. Вызови projectlad_get_project_works с найденным project_id
3. Покажи работы с датами начала/конца

### Загрузка ресурсов
1. ОБЯЗАТЕЛЬНО: Нужны project_id И version_id
2. Если проект ВЛОЖЕННЫЙ (Children) - используй его ID, НЕ родителя
3. Пример: для "Atlas" используй ID вложенного проекта, не портфеля

## Важные замечания

⚠️ **Project Lad data != Google Drive files**
НЕ ищи проекты через search_drive - используй projectlad_* tools

⚠️ **Для вложенных проектов**
Всегда проверяй секцию "ВЛОЖЕННЫЕ ПРОЕКТЫ (Children)" в ответе
Используй project_id и version_id именно вложенного проекта, не родителя

⚠️ **Приоритет routing**
Если пользователь упоминает "PL" или "проект лад" - это ВСЕГДА Project Lad, не Google Drive
