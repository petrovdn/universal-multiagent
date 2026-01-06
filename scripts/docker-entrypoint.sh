#!/bin/bash
set -e

echo "=== Starting Universal Multi-Agent System ==="

# Создаем необходимые директории если их нет
mkdir -p /app/data/tokens
mkdir -p /app/data/sessions
mkdir -p /app/logs
mkdir -p /app/config

# Проверяем наличие переменных окружения
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: No API key set (ANTHROPIC_API_KEY or OPENAI_API_KEY)"
fi

if [ -z "$GOOGLE_OAUTH_CLIENT_ID" ] || [ -z "$GOOGLE_OAUTH_CLIENT_SECRET" ]; then
    echo "WARNING: Google OAuth credentials not set"
fi

# Запускаем приложение
# Railway предоставляет переменную $PORT, используем её или 8000 по умолчанию
PORT=${PORT:-8000}
echo "[DEBUG][HYP-A] Starting FastAPI server on port $PORT..."
exec python -m uvicorn src.api.server:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --log-level info
