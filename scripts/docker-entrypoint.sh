#!/bin/bash
set -e

# #region agent log - DEBUG INSTRUMENTATION
echo "[DEBUG][HYP-D] Entrypoint started at $(date)"
echo "[DEBUG][HYP-D] Current directory: $(pwd)"
echo "[DEBUG][HYP-D] PORT env variable: ${PORT:-not set}"
echo "[DEBUG][HYP-E] Checking critical files..."
ls -la /app/ 2>&1 | head -20
echo "[DEBUG][HYP-E] Checking src directory..."
ls -la /app/src/ 2>&1 | head -10 || echo "[DEBUG][HYP-E] ERROR: /app/src/ not found!"
echo "[DEBUG][HYP-E] Checking pyproject.toml..."
ls -la /app/pyproject.toml 2>&1 || echo "[DEBUG][HYP-E] ERROR: pyproject.toml not found!"
# #endregion

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

# #region agent log - DEBUG INSTRUMENTATION
echo "[DEBUG][HYP-B] Testing Python imports..."
python -c "print('[DEBUG][HYP-B] Python works'); import sys; print(f'[DEBUG][HYP-B] Python path: {sys.path[:3]}')" 2>&1
python -c "from fastapi import FastAPI; print('[DEBUG][HYP-B] FastAPI import OK')" 2>&1 || echo "[DEBUG][HYP-B] ERROR: FastAPI import failed!"
python -c "from src.api.server import app; print('[DEBUG][HYP-B] Server import OK')" 2>&1 || echo "[DEBUG][HYP-B] ERROR: Server import failed!"
# #endregion

# Запускаем приложение
# Railway предоставляет переменную $PORT, используем её или 8000 по умолчанию
PORT=${PORT:-8000}
echo "[DEBUG][HYP-A] Starting FastAPI server on port $PORT..."
exec python -m uvicorn src.api.server:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --log-level info

