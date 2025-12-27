# Gmail MCP Server Setup Guide

Собственный MCP сервер для Gmail без Composio. Поддерживает OAuth2 авторизацию через интерфейс приложения.

## Возможности

Gmail MCP сервер предоставляет следующие инструменты:

### Чтение писем
- `gmail_list_messages` - Список писем из входящих или по метке
- `gmail_get_message` - Получение полного содержимого письма
- `gmail_search` - Поиск по Gmail синтаксису (from:, subject:, is:unread, newer_than: и т.д.)
- `gmail_get_thread` - Получение цепочки писем (conversation)
- `gmail_list_labels` - Список всех меток/папок
- `gmail_get_unread_count` - Количество непрочитанных писем
- `gmail_get_important_emails` - Важные/помеченные/непрочитанные письма
- `gmail_get_profile` - Информация о профиле пользователя

### Отправка писем
- `gmail_send_email` - Отправка нового письма
- `gmail_reply` - Ответ на письмо (с поддержкой reply all)
- `gmail_forward` - Пересылка письма
- `gmail_create_draft` - Создание черновика

### Управление письмами
- `gmail_mark_read` - Пометить как прочитанное
- `gmail_mark_unread` - Пометить как непрочитанное
- `gmail_star_message` - Добавить/убрать звёздочку
- `gmail_archive_message` - Архивировать
- `gmail_trash_message` - Удалить в корзину
- `gmail_add_label` - Добавить метку
- `gmail_remove_label` - Убрать метку

## Быстрый старт

### 1. Настройка Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Gmail API:
   - Перейдите в APIs & Services → Library
   - Найдите "Gmail API" и включите его
4. Создайте OAuth2 credentials:
   - APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: **Web application**
   - Authorized redirect URIs:
     - `http://localhost:8000/api/integrations/gmail/callback`
5. Скопируйте Client ID и Client Secret

### 2. Настройка переменных окружения

Добавьте в `config/.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### 3. Подключение Gmail

1. Откройте приложение в браузере: `http://localhost:5173`
2. Нажмите на иконку настроек (⚙️) в правом нижнем углу
3. В разделе "Интеграции" включите переключатель **Gmail**
4. Откроется окно OAuth авторизации Google
5. Разрешите доступ к Gmail
6. После успешной авторизации Gmail готов к работе!

## OAuth Scopes

Сервер запрашивает следующие разрешения:

- `gmail.readonly` - Чтение писем
- `gmail.send` - Отправка писем  
- `gmail.modify` - Изменение меток, архивация
- `gmail.compose` - Создание черновиков
- `gmail.labels` - Управление метками

## Примеры использования

### Просмотр последних писем
```
"Покажи последние 5 писем из входящих"
```

### Поиск писем
```
"Найди письма от boss@company.com за последние 3 дня"
"Покажи непрочитанные письма"
"Найди письма с темой 'отчёт'"
```

### Отправка письма
```
"Напиши письмо на email@example.com с темой 'Привет' и текстом 'Как дела?'"
```

### Ответ на письмо
```
"Ответь на последнее письмо от John: 'Спасибо за информацию!'"
```

### Управление письмами
```
"Пометь это письмо как прочитанное"
"Архивируй все письма от newsletter@spam.com"
```

## Gmail Search Syntax

Поддерживается полный синтаксис поиска Gmail:

| Оператор | Описание | Пример |
|----------|----------|--------|
| `from:` | От кого | `from:example@gmail.com` |
| `to:` | Кому | `to:me@gmail.com` |
| `subject:` | Тема | `subject:meeting` |
| `is:` | Статус | `is:unread`, `is:starred`, `is:important` |
| `has:` | Содержит | `has:attachment` |
| `newer_than:` | Новее чем | `newer_than:3d`, `newer_than:1w` |
| `older_than:` | Старше чем | `older_than:1m` |
| `after:` | После даты | `after:2024/01/01` |
| `before:` | До даты | `before:2024/12/31` |
| `label:` | По метке | `label:work` |

## Запуск MCP сервера вручную

Если нужно запустить сервер отдельно:

```bash
# Из корня проекта
./scripts/start-gmail-mcp.sh

# Или напрямую
python -m src.mcp_servers.gmail_server --token-path config/gmail_token.json
```

## Структура токена

После авторизации токен сохраняется в `config/gmail_token.json`:

```json
{
  "token": "access_token_here",
  "refresh_token": "refresh_token_here",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly", ...]
}
```

## Отключение Gmail

1. Выключите переключатель Gmail в настройках
2. Токен будет удалён
3. Для повторного подключения снова включите переключатель

## Troubleshooting

### "OAuth token not found"
Включите Gmail интеграцию через настройки приложения.

### "Insufficient Permission"
Убедитесь что Gmail API включён в Google Cloud Console и OAuth credentials имеют правильные redirect URIs.

### "Token has been expired or revoked"
Отключите и снова включите Gmail интеграцию для получения нового токена.

### Письма не отправляются
Проверьте что scope `gmail.send` присутствует в токене. Может потребоваться переавторизация.

## Безопасность

- Токены хранятся локально в `config/gmail_token.json`
- Токены автоматически обновляются при истечении
- Рекомендуется добавить `config/*.json` в `.gitignore`
- Используйте test mode в Google Cloud Console для разработки

