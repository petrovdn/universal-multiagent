# Руководство по настройке MCP серверов

Это руководство объясняет, как настроить и сконфигурировать MCP (Model Context Protocol) серверы для системы Google Workspace Multi-Agent.

## Обзор

Система использует собственные MCP серверы:
1. **Gmail MCP** - собственный сервер (`src/mcp_servers/gmail_server.py`)
2. **Google Calendar MCP** - собственный сервер (`src/mcp_servers/google_calendar_server.py`)
3. **Google Sheets MCP** - собственный сервер (`src/mcp_servers/google_sheets_server.py`)

Все серверы запускаются автоматически при старте приложения и используют stdio transport.

## Требования

- Python 3.10+ установлен
- Google Cloud Project с включенными API:
  - Gmail API
  - Google Calendar API
  - Google Sheets API
- OAuth 2.0 учетные данные (обязательно)

## 1. Настройка OAuth credentials

Все MCP серверы используют общие OAuth credentials из Google Cloud Console.

### Шаги настройки

1. Создайте Google Cloud Project (если еще не создан)
2. Включите необходимые API:
   - Gmail API
   - Google Calendar API
   - Google Sheets API
3. Создайте OAuth 2.0 учетные данные:
   - Перейдите в "APIs & Services" > "Credentials"
   - Нажмите "Create Credentials" > "OAuth client ID"
   - Тип приложения: **"Web application"**
   - Добавьте authorized redirect URI: `http://localhost:8000/auth/callback`
   - Скопируйте Client ID и Client Secret

4. Добавьте credentials в `config/.env`:

```env
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
```

## 2. Настройка MCP серверов

MCP серверы запускаются автоматически при старте приложения. Они находятся в:
- `src/mcp_servers/gmail_server.py` - Gmail MCP сервер
- `src/mcp_servers/google_calendar_server.py` - Calendar MCP сервер
- `src/mcp_servers/google_sheets_server.py` - Sheets MCP сервер

Все серверы используют stdio transport и запускаются как дочерние процессы приложения.

### Авторизация интеграций

После запуска приложения авторизуйте интеграции через веб-интерфейс:

1. Запустите приложение: `python src/main.py`
2. Откройте веб-интерфейс: http://localhost:5173
3. Перейдите в раздел настроек интеграций
4. Включите нужные интеграции:
   - Gmail: `/api/integrations/gmail/enable`
   - Google Calendar: `/api/integrations/google-calendar/enable`
   - Google Sheets: `/api/integrations/google-sheets/enable`
5. Завершите OAuth авторизацию для каждой интеграции

Токены будут сохранены в:
- `config/gmail_token.json`
- `config/google_calendar_token.json`
- `config/google_sheets_token.json`

## Конфигурация в приложении

Обновите `config/.env` с вашими настройками:

```env
# Google OAuth (обязательно)
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# MCP настройки (используют stdio, запускаются автоматически)
GMAIL_MCP_TRANSPORT=stdio
CALENDAR_MCP_TRANSPORT=stdio
SHEETS_MCP_TRANSPORT=stdio
```

**Важно**: MCP серверы запускаются автоматически при старте приложения как дочерние процессы. Они используют stdio transport для общения с основным приложением.

## Запуск приложения

Просто запустите приложение - все MCP серверы запустятся автоматически:

```bash
python src/main.py
```

Приложение автоматически:
1. Запустит все три MCP сервера (Gmail, Calendar, Sheets)
2. Подключится к ним через stdio transport
3. Обнаружит доступные инструменты

После запуска авторизуйте интеграции через веб-интерфейс приложения.

## Устранение неполадок

### Сервер не запускается

1. **Проверьте доступность портов:**
   ```bash
   lsof -i :9001
   lsof -i :9002
   lsof -i :9003
   ```

2. **Проверьте переменные окружения:**
   ```bash
   env | grep MCP
   ```

3. **Проверьте логи:**
   - Все MCP серверы: Проверьте логи приложения и вывод консоли
   - Проверьте файлы логов в директории `logs/`

### Ошибки аутентификации

1. **OAuth процесс не завершен:**
   - Перезапустите сервер
   - Завершите OAuth процесс в браузере
   - Проверьте, что redirect URI совпадает

2. **Неверные учетные данные:**
   - Проверьте client ID и secret
   - Убедитесь, что API включены в Google Cloud Console
   - Проверьте настройку OAuth consent screen

### Таймауты подключения

1. **Проверьте настройки файрвола**
2. **Проверьте endpoints в config/.env**
3. **Протестируйте с curl:**
   ```bash
   curl -v http://localhost:9001/health
   ```

### Ограничение скорости (Rate Limiting)

Если вы столкнулись с ограничением скорости:
- Реализуйте экспоненциальную задержку (уже в коде)
- Уменьшите количество одновременных запросов
- Проверьте квоты Google API в Cloud Console

## Проверка

Запустите скрипт проверки здоровья:

```bash
python scripts/check_mcp_servers.py
```

Это проверит все три MCP сервера и сообщит их статус.

## Следующие шаги

После запуска всех MCP серверов:
1. Проверьте конфигурацию в `config/.env`
2. Убедитесь, что серверы запущены (проверьте процессы)
3. Запустите приложение: `python src/main.py`
4. Приложение автоматически подключится к MCP серверам при старте

## Примечания

- **MCP серверы используют stdio transport**: Это означает, что они общаются через стандартный ввод/вывод, а не через HTTP
- **Все серверы запускаются автоматически**: Приложение автоматически запускает все три MCP сервера при старте
- **Интеграции настраиваются через веб-интерфейс**: После запуска авторизуйте интеграции через веб-интерфейс приложения
