# Быстрый старт MCP серверов

Краткое руководство по быстрой настройке и запуску MCP серверов.

## Предварительные требования

1. **Python 3.10+** установлен
2. **Google Cloud Project** с включенными API (Gmail, Calendar, Sheets)
3. **OAuth 2.0 credentials** созданы в Google Cloud Console

**Примечание**: Проект использует собственные MCP серверы для Gmail, Calendar и Sheets. Внешние зависимости не требуются.

## Шаг 1: Настройка OAuth credentials

1. Создайте OAuth 2.0 credentials в Google Cloud Console
2. Добавьте credentials в `config/.env`:

```env
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
```

## Шаг 2: Запуск приложения

Приложение автоматически запустит все MCP серверы при старте. Убедитесь, что:

1. OAuth credentials настроены в `config/.env`
2. Все зависимости установлены: `pip install -r requirements.txt`

Запустите приложение:
```bash
python src/main.py
```

MCP серверы (Gmail, Calendar, Sheets) запустятся автоматически и будут доступны через stdio transport.

## Проверка

После запуска приложения проверьте логи - должны быть сообщения о успешном подключении к MCP серверам:

```
✅ Connected to gmail MCP server
✅ Connected to calendar MCP server
✅ Connected to sheets MCP server
```

## Шаг 3: Авторизация интеграций

После запуска приложения авторизуйте интеграции через веб-интерфейс:

1. Откройте веб-интерфейс приложения
2. Перейдите в раздел настроек интеграций
3. Включите нужные интеграции (Gmail, Calendar, Sheets)
4. Завершите OAuth авторизацию для каждой интеграции

Токены будут сохранены в:
- `config/gmail_token.json`
- `config/google_calendar_token.json`
- `config/google_sheets_token.json`

## Устранение проблем

### MCP серверы не запускаются

Проверьте:
1. Python установлен: `python3 --version` (требуется 3.10+)
2. Зависимости установлены: `pip install -r requirements.txt`
3. OAuth credentials настроены в `config/.env`

### Инструменты не обнаружены

Если инструменты не обнаружены после подключения:
1. Проверьте, что интеграции авторизованы (токены существуют)
2. Проверьте логи приложения на наличие ошибок
3. Убедитесь, что OAuth credentials корректны

## Дополнительная информация

Подробные инструкции см. в [mcp-setup.md](mcp-setup.md)



