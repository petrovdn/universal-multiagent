# Google Calendar MCP Server Setup Guide

Собственный MCP сервер для Google Calendar без Composio. Поддерживает OAuth2 авторизацию через интерфейс приложения.

## Возможности

Google Calendar MCP сервер предоставляет следующие инструменты:

### Просмотр календарей
- `list_calendars` - Список всех доступных календарей

### Просмотр событий
- `list_events` - Список событий за период времени
- `get_event` - Получение деталей конкретного события

### Управление событиями
- `create_event` - Создание нового события
- `update_event` - Обновление существующего события
- `delete_event` - Удаление события
- `quick_add_event` - Быстрое создание события на естественном языке

## Быстрый старт

### 1. Настройка Google Cloud Console

**ВАЖНО**: Для работы Google Calendar необходимо добавить redirect URI в Google Cloud Console!

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите ваш проект
3. Перейдите в **APIs & Services** → **Credentials**
4. Найдите ваш OAuth 2.0 Client ID и нажмите на него для редактирования
5. В разделе **Authorized redirect URIs** добавьте:
   - `http://localhost:8000/api/integrations/google-calendar/callback`
6. Нажмите **Save**

> **Примечание**: Если у вас уже добавлен redirect URI для Gmail (`http://localhost:8000/api/integrations/gmail/callback`), просто добавьте еще один URI для Calendar рядом с ним.

### 2. Включение Google Calendar API

1. В Google Cloud Console перейдите в **APIs & Services** → **Library**
2. Найдите "Google Calendar API" и включите его

### 3. Настройка переменных окружения

Убедитесь, что у вас настроены переменные окружения (если еще не настроены):

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

Эти переменные должны быть уже настроены, если вы настроили Gmail интеграцию.

### 4. Подключение Google Calendar

1. Откройте приложение в браузере: `http://localhost:5173`
2. Нажмите на иконку настроек (⚙️) в правом нижнем углу
3. В разделе "Интеграции" включите переключатель **Google Calendar**
4. Откроется окно OAuth авторизации Google
5. Разрешите доступ к Google Calendar
6. После успешной авторизации Calendar готов к работе!

## OAuth Scopes

Сервер запрашивает следующие разрешения:

- `https://www.googleapis.com/auth/calendar` - Полный доступ к календарю (чтение, создание, редактирование, удаление событий)

## Устранение неполадок

### Ошибка "redirect_uri_mismatch"

Если вы видите ошибку `Error 400: redirect_uri_mismatch`, это означает, что redirect URI для Calendar не добавлен в Google Cloud Console.

**Решение:**
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services** → **Credentials**
3. Откройте ваш OAuth 2.0 Client ID
4. В разделе **Authorized redirect URIs** добавьте:
   ```
   http://localhost:8000/api/integrations/google-calendar/callback
   ```
5. Нажмите **Save**
6. Попробуйте подключить Calendar снова

### Ошибка "Token expired"

Если токен истек, просто переподключите интеграцию через интерфейс приложения. Система автоматически запросит новый токен.

### Ошибка "API not enabled"

Убедитесь, что Google Calendar API включен в Google Cloud Console:
1. **APIs & Services** → **Library**
2. Найдите "Google Calendar API"
3. Нажмите **Enable**

## Примеры использования

### Просмотр календарей
```
"Покажи все мои календари"
```

### Просмотр событий
```
"Покажи события на завтра"
"Какие у меня встречи на следующей неделе?"
"Покажи события за последние 3 дня"
```

### Создание события
```
"Создай встречу 'Встреча с командой' завтра в 14:00"
"Добавь событие 'День рождения' на 15 декабря"
```

### Быстрое создание события
```
"Добавь встречу завтра в 15:00"
"Встреча с клиентом в понедельник в 10 утра"
```

### Управление событиями
```
"Обнови название события с ID 'xxx' на 'Новая встреча'"
"Удали событие с ID 'xxx'"
```

## Токен

Токен OAuth сохраняется в файле `config/google_calendar_token.json`. Этот файл автоматически создается при первой авторизации.

**Важно**: Не коммитьте файл `config/google_calendar_token.json` в git! Он содержит ваши персональные токены доступа.

## Архитектура

Calendar MCP сервер работает аналогично Gmail MCP серверу:

1. При запуске приложения подключается MCP сервер Calendar
2. При первой попытке использования запрашивается OAuth авторизация
3. После авторизации токен сохраняется локально
4. Все последующие запросы используют сохраненный токен
5. Токен автоматически обновляется при истечении срока действия

