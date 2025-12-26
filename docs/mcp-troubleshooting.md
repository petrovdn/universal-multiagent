# Устранение проблем с MCP серверами

**Примечание**: Проект использует собственные MCP серверы для Gmail, Calendar и Sheets. Они запускаются автоматически при старте приложения.

## Проблема: OAuth credentials не найдены

### Решение

Убедитесь, что OAuth credentials настроены в `config/.env`:

```env
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
```

**Важно**: Используйте OAuth 2.0 Client ID типа "Web application" из Google Cloud Console.

## Проблема: Интеграции не авторизованы

### Решение

Авторизуйте интеграции через веб-интерфейс приложения:

1. Откройте веб-интерфейс приложения
2. Перейдите в раздел настроек интеграций
3. Включите нужные интеграции (Gmail, Calendar, Sheets)
4. Завершите OAuth авторизацию

Токены будут сохранены в:
- `config/gmail_token.json`
- `config/google_calendar_token.json`
- `config/google_sheets_token.json`

## Проблема: Сервер запускается, но приложение не подключается

### Решение

1. **Проверьте transport**: Убедитесь, что в `config/.env` указан `stdio`:
   ```env
   GMAIL_MCP_TRANSPORT=stdio
   CALENDAR_MCP_TRANSPORT=stdio
   SHEETS_MCP_TRANSPORT=stdio
   ```

2. **Проверьте логи**: Приложение автоматически запускает MCP серверы. Проверьте логи на наличие ошибок.

3. **Проверьте OAuth credentials**: Убедитесь, что они корректны в `config/.env`

## Проблема: Python не найден

### Решение

Установите Python 3.10 или выше:
```bash
# macOS (через Homebrew)
brew install python@3.10

# Или скачайте с https://www.python.org/
```

Проверьте установку:
```bash
python3 --version
```

## Проблема: Зависимости не установлены

### Решение

Установите все зависимости:
```bash
pip install -r requirements.txt
```

## Автоматический запуск

Приложение автоматически запускает MCP серверы при старте. Убедитесь, что:

1. ✅ Python 3.10+ установлен
2. ✅ Зависимости установлены: `pip install -r requirements.txt`
3. ✅ OAuth credentials настроены в `config/.env`
4. ✅ Интеграции авторизованы через веб-интерфейс

Затем просто запустите:
```bash
python src/main.py
```

Приложение автоматически запустит все MCP серверы (Gmail, Calendar, Sheets) и подключится к ним.



