# Google Workspace MCP Server Setup

Собственный MCP сервер для Google Workspace с OAuth2 авторизацией. Объединяет функциональность Google Drive, Google Docs и Google Sheets в единую интеграцию для работы с документами и файлами в выбранной рабочей папке.

## Возможности

MCP сервер для Google Workspace поддерживает следующие операции:

### Работа с файлами (Google Drive)
- `workspace_list_files` - Список файлов в рабочей папке
- `workspace_get_file_info` - Информация о файле (метаданные, тип, размер)
- `workspace_create_folder` - Создание подпапки в рабочей папке
- `workspace_delete_file` - Удаление файла или папки
- `workspace_move_file` - Перемещение файла в другую папку
- `workspace_search_files` - Поиск файлов по имени или содержимому

### Работа с документами (Google Docs)
- `docs_create` - Создание нового документа в рабочей папке
- `docs_read` - Чтение содержимого документа
- `docs_update` - Полная замена содержимого документа
- `docs_append` - Добавление текста в конец документа
- `docs_insert` - Вставка текста в определенную позицию
- `docs_format_text` - Форматирование текста (жирный, курсив, подчеркивание)

### Работа с таблицами (Google Sheets)
- `sheets_create_spreadsheet` - Создание новой таблицы в рабочей папке
- `sheets_read_range` - Чтение данных из диапазона ячеек
- `sheets_write_range` - Запись данных в диапазон ячеек
- `sheets_append_rows` - Добавление строк в конец листа
- `sheets_get_info` - Получение информации о таблице (листы, свойства)

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
http://localhost:8000/api/integrations/google-workspace/callback
http://localhost:8000/api/integrations/google-calendar/callback
http://localhost:8000/api/integrations/google-sheets/callback
http://localhost:8000/api/integrations/gmail/callback
http://localhost:8000/auth/callback
```

### 3. Включите необходимые API

В разделе **APIs & Services** → **Library** включите:

- **Google Drive API** (для работы с файлами и папками)
- **Google Docs API** (для работы с документами)
- **Google Sheets API** (для работы с таблицами)

### 4. Настройте OAuth Consent Screen

1. Перейдите в **APIs & Services** → **OAuth consent screen**
2. Выберите **External** (или Internal для организации)
3. Заполните обязательные поля:
   - App name
   - User support email
   - Developer contact email
4. Добавьте scopes:
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/spreadsheets`
5. Добавьте тестовых пользователей (если External и не verified)

## Использование

### Включение интеграции

1. Откройте приложение в браузере: `http://localhost:5173`
2. Нажмите на кнопку **Настройки** в верхней части интерфейса
3. Найдите переключатель **Google Workspace**
4. Включите его - откроется окно авторизации Google
5. Выберите аккаунт и разрешите доступ
6. После успешной авторизации откроется диалог выбора рабочей папки
7. Выберите существующую папку из списка или создайте новую
8. После выбора папки интеграция будет активна

### Выбор и смена рабочей папки

- В настройках отображается текущая рабочая папка
- Нажмите "Изменить папку" для смены без повторной авторизации
- Все операции агента будут выполняться только в выбранной папке

### Пример использования через агента

После настройки интеграции вы можете попросить агента:

```
Посмотри на документ с политикой написания писем, в соответствии с этой политикой 
напиши письма клиентам, которые есть в таблице Клиенты, результат (все письма) 
сохрани в текстовый документ "Письма клиентам". Содержание писем - индивидуальные 
поздравления с Новым годом
```

Агент выполнит следующие действия:
1. Список файлов в рабочей папке
2. Прочитает документ "Политика написания писем"
3. Прочитает данные из таблицы "Клиенты"
4. Сгенерирует персонализированные письма для каждого клиента
5. Создаст новый документ "Письма клиентам"
6. Запишет все письма в документ

Другие примеры:

```
Создай новую таблицу "Бюджет на месяц" с листами "Январь", "Февраль", "Март"
```

```
Прочитай документ "Отчет о продажах" и найди все упоминания суммы более 10000
```

```
Создай папку "Архив 2024" и перемести туда все файлы, созданные до 2024 года
```

## Файлы

- **MCP сервер**: `src/mcp_servers/google_workspace_server.py`
- **API роуты**: `src/api/integration_routes.py`
- **LangChain tools**: `src/mcp_tools/workspace_tools.py`
- **Agent**: `src/agents/workspace_agent.py`
- **Токен**: `config/google_workspace_token.json` (создается автоматически после OAuth)
- **Конфигурация**: `config/workspace_config.json` (хранит ID и имя рабочей папки)
- **Скрипт запуска**: `scripts/start-workspace-mcp.sh`
- **Frontend компоненты**: 
  - `frontend/src/components/WorkspaceFolderSelector.tsx` (диалог выбора папки)
  - `frontend/src/components/Header.tsx` (настройки интеграции)

## Устранение неполадок

### Ошибка "OAuth token not found"

Токен еще не создан. Включите интеграцию Google Workspace через интерфейс настроек.

### Ошибка "Workspace folder not configured"

После авторизации необходимо выбрать рабочую папку. Это можно сделать:
- Автоматически после OAuth (диалог откроется сам)
- Вручную в настройках, нажав "Изменить папку"

### Ошибка "redirect_uri_mismatch"

Redirect URI не добавлен в Google Cloud Console. Добавьте:
```
http://localhost:8000/api/integrations/google-workspace/callback
```

### Ошибка "Access Not Configured"

Необходимые API не включены в проекте. Включите их в Google Cloud Console:
1. APIs & Services → Library
2. Найдите и включите:
   - Google Drive API
   - Google Docs API
   - Google Sheets API

### Ошибка "App not verified"

Для тестирования добавьте свой email в тестовые пользователи:
1. APIs & Services → OAuth consent screen
2. Test users → Add users
3. Введите ваш email

### Агент не может найти файлы

Убедитесь, что:
- Рабочая папка выбрана и настроена
- Файлы находятся в рабочей папке (не в корне Drive)
- У вас есть доступ к файлам

## Безопасность

- OAuth токены хранятся локально в `config/google_workspace_token.json`
- Агент работает только в выбранной рабочей папке (не имеет доступа ко всему Drive)
- Конфигурация папки хранится в `config/workspace_config.json`
- Все операции логируются в audit.log
- Токены автоматически обновляются при истечении
- Для отключения интеграции используйте переключатель - токен и конфигурация будут удалены
- Никакие данные не отправляются на внешние серверы кроме Google API

## Архитектура

Интеграция состоит из следующих компонентов:

1. **MCP Server** (`google_workspace_server.py`) - обеспечивает взаимодействие с Google APIs
2. **LangChain Tools** (`workspace_tools.py`) - обертки для использования в агентах
3. **Workspace Agent** (`workspace_agent.py`) - специализированный агент для работы с документами
4. **API Routes** (`integration_routes.py`) - REST API для управления интеграцией
5. **Frontend UI** - интерфейс для настройки и выбора папки

Все файлы создаются и изменяются только в выбранной рабочей папке, что обеспечивает изоляцию и безопасность данных.

