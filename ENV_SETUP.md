# Настройка переменных окружения

Для production деплоя создайте файл `.env.example` на основе следующего шаблона:

```env
# API Keys (нужен хотя бы один)
ANTHROPIC_API_KEY=your-anthropic-api-key-here
OPENAI_API_KEY=your-openai-api-key-here

# Model settings
DEFAULT_MODEL=gpt-4o

# Google OAuth 2.0 (обязательно)
GOOGLE_OAUTH_CLIENT_ID=your-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# Application settings
APP_TIMEZONE=Europe/Moscow
APP_DEBUG=false
APP_LOG_LEVEL=INFO
APP_ENV=dev

# FastAPI settings
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:3001

# Session settings
SESSION_TIMEOUT_MINUTES=30
MAX_SESSIONS_PER_USER=10

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
MAX_API_CALLS_PER_MESSAGE=5

# MCP Endpoints
GMAIL_MCP_ENDPOINT=http://localhost:9001
GMAIL_MCP_TRANSPORT=stdio
CALENDAR_MCP_ENDPOINT=http://localhost:9002
CALENDAR_MCP_TRANSPORT=stdio
SHEETS_MCP_ENDPOINT=http://localhost:9003
SHEETS_MCP_TRANSPORT=stdio
WORKSPACE_MCP_ENDPOINT=http://localhost:9004
WORKSPACE_MCP_TRANSPORT=stdio

# Production settings (для Railway/deployment)
# DATA_DIR=/app/data  # Путь к volume для данных (автоматически определяется)
# APP_ENV=production   # Установите в production для использования volume paths
```

## Для Railway

В Railway Dashboard добавьте переменные окружения из этого шаблона, заменив значения на реальные.

Важно: После получения домена от Railway обновите:
- `GOOGLE_OAUTH_REDIRECT_URI` - должен указывать на ваш Railway домен
- `API_CORS_ORIGINS` - должен содержать ваш Railway домен

