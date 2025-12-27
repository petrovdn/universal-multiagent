# Быстрый старт

## 1. Установка зависимостей

### Автоматическая установка (рекомендуется)
```bash
./scripts/setup.sh
```

Этот скрипт:
- Создаст виртуальное окружение Python
- Установит все Python зависимости
- Установит MCP серверы через npm

### Ручная установка

**Backend:**
```bash
# Создайте виртуальное окружение (рекомендуется)
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

## 2. Установка MCP серверов

```bash
npm install -g @gongrzhe/server-gmail-autoauth-mcp
```

**Примечание**: Проект использует собственные MCP серверы для Calendar и Sheets, они запускаются автоматически при старте приложения.

## 3. Настройка Gmail MCP

1. Создайте OAuth 2.0 credentials в Google Cloud Console
2. Создайте файл `~/.gmail-mcp/gcp-oauth.keys.json`:

```bash
mkdir -p ~/.gmail-mcp
```

Скопируйте содержимое скачанного JSON файла в `~/.gmail-mcp/gcp-oauth.keys.json`:

```json
{
  "web": {
    "client_id": "ваш-client-id.apps.googleusercontent.com",
    "client_secret": "ваш-client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

## 4. Конфигурация приложения

Создайте `config/.env`:

```env
# Anthropic API
# At least one API key is required
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...

# Optional: Set default model (default: gpt-4o)
# DEFAULT_MODEL=gpt-4o

# Google OAuth (обязательно)
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# MCP настройки (используют stdio)
GMAIL_MCP_TRANSPORT=stdio
CALENDAR_MCP_TRANSPORT=stdio
SHEETS_MCP_TRANSPORT=stdio
```

## 5. Запуск

### Backend

**С виртуальным окружением:**
```bash
source venv/bin/activate
python3 src/main.py
```

**Или используйте скрипт:**
```bash
./scripts/run.sh
```

### Frontend (в другом терминале)
```bash
cd frontend
npm run dev
```

## 6. Аутентификация

1. Откройте http://localhost:8000/auth/login
2. Завершите OAuth процесс
3. Откройте http://localhost:5173 для использования приложения

## Готово!

Теперь вы можете общаться с агентом через веб-интерфейс. Все операции будут выполняться от вашего имени.

