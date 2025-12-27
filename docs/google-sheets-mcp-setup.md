# Google Sheets MCP Server Setup

Собственный MCP сервер для Google Sheets с OAuth2 авторизацией.

## Возможности

MCP сервер для Google Sheets поддерживает следующие операции:

### Работа с таблицами
- `sheets_list_spreadsheets` - Список недавних таблиц
- `sheets_get_spreadsheet_info` - Информация о таблице (листы, свойства)
- `sheets_create_spreadsheet` - Создание новой таблицы

### Чтение данных
- `sheets_read_range` - Чтение данных из диапазона ячеек
- `sheets_read_multiple_ranges` - Чтение нескольких диапазонов за раз
- `sheets_search` - Поиск значения в таблице

### Запись данных
- `sheets_write_range` - Запись данных в диапазон ячеек
- `sheets_append_rows` - Добавление строк в конец листа
- `sheets_clear_range` - Очистка диапазона ячеек

### Управление листами
- `sheets_add_sheet` - Добавление нового листа
- `sheets_delete_sheet` - Удаление листа
- `sheets_rename_sheet` - Переименование листа
- `sheets_copy_sheet` - Копирование листа

### Форматирование
- `sheets_format_cells` - Форматирование ячеек (жирный, курсив, цвета)
- `sheets_auto_resize_columns` - Автоматическая ширина колонок
- `sheets_merge_cells` - Объединение ячеек
- `sheets_unmerge_cells` - Разъединение ячеек

### Структурные операции
- `sheets_insert_rows` - Вставка строк
- `sheets_delete_rows` - Удаление строк
- `sheets_insert_columns` - Вставка колонок
- `sheets_delete_columns` - Удаление колонок
- `sheets_sort_range` - Сортировка данных

## Настройка Google Cloud Console

### 1. Создайте OAuth 2.0 Client ID

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите или создайте проект
3. Перейдите в **APIs & Services** → **Credentials**
4. Нажмите **Create Credentials** → **OAuth client ID**
5. Выберите тип **Web application**
6. Задайте имя (например, "Universal Multiagent")

### 2. Настройте Redirect URIs

Добавьте следующие Redirect URIs:

```
http://localhost:8000/api/integrations/google-sheets/callback
http://localhost:8000/api/integrations/google-calendar/callback
http://localhost:8000/api/integrations/gmail/callback
http://localhost:8000/auth/callback
```

### 3. Включите необходимые API

В разделе **APIs & Services** → **Library** включите:

- **Google Sheets API**
- **Google Drive API** (для создания таблиц и списка файлов)

### 4. Настройте OAuth Consent Screen

1. Перейдите в **APIs & Services** → **OAuth consent screen**
2. Выберите **External** (или Internal для организации)
3. Заполните обязательные поля:
   - App name
   - User support email
   - Developer contact email
4. Добавьте scopes:
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive.file`
5. Добавьте тестовых пользователей (если External и не verified)

## Использование

### Включение интеграции

1. Откройте приложение в браузере: `http://localhost:5173`
2. Нажмите на иконку **Настройки** (⚙️) в правом нижнем углу
3. Найдите переключатель **Google Sheets**
4. Включите его - откроется окно авторизации Google
5. Выберите аккаунт и разрешите доступ
6. После успешной авторизации переключатель станет активным

### Пример использования через агента

После включения интеграции вы можете попросить агента:

```
Создай новую таблицу "Бюджет на месяц" с листами "Январь", "Февраль", "Март"
```

```
Прочитай данные из таблицы https://docs.google.com/spreadsheets/d/xxx диапазон A1:D10
```

```
Найди в таблице все ячейки, содержащие слово "итого"
```

```
Добавь строку с данными ["Товар", "100", "шт", "1000"] в конец листа "Продажи"
```

## Файлы

- **MCP сервер**: `src/mcp_servers/google_sheets_server.py`
- **API роуты**: `src/api/integration_routes.py`
- **Токен**: `config/google_sheets_token.json` (создается автоматически после OAuth)
- **Скрипт запуска**: `scripts/start-sheets-mcp.sh`

## Устранение неполадок

### Ошибка "OAuth token not found"

Токен еще не создан. Включите интеграцию Google Sheets через интерфейс настроек.

### Ошибка "redirect_uri_mismatch"

Redirect URI не добавлен в Google Cloud Console. Добавьте:
```
http://localhost:8000/api/integrations/google-sheets/callback
```

### Ошибка "Access Not Configured"

Google Sheets API не включен в проекте. Включите его в Google Cloud Console:
1. APIs & Services → Library
2. Найдите "Google Sheets API"
3. Нажмите Enable

### Ошибка "App not verified"

Для тестирования добавьте свой email в тестовые пользователи:
1. APIs & Services → OAuth consent screen
2. Test users → Add users
3. Введите ваш email

## Безопасность

- OAuth токены хранятся локально в `config/google_sheets_token.json`
- Токены автоматически обновляются при истечении срока
- Для отключения интеграции используйте переключатель - токен будет удален
- Никакие данные не отправляются на внешние серверы кроме Google API

