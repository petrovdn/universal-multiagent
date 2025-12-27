# Multi-stage build для production

# Stage 1: Frontend build
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Копируем package files сначала для кеширования слоев
COPY frontend/package.json frontend/package-lock.json ./

# Устанавливаем зависимости (включая dev для сборки)
RUN npm ci --legacy-peer-deps --no-audit --progress=false

# Копируем конфигурационные файлы
COPY frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html ./

# Копируем исходники frontend
COPY frontend/src ./src

# Собираем frontend
RUN npm run build

# Stage 2: Backend setup
FROM python:3.10-slim AS backend-setup

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip для лучшей производительности
RUN pip install --upgrade pip setuptools wheel

# Этап 1: Основные зависимости (быстрые, кешируются)
# Эти пакеты редко меняются и будут кешироваться Docker
COPY requirements-core.txt ./
RUN pip install --no-cache-dir --timeout=300 --retries=3 -r requirements-core.txt

# Этап 2: MCP зависимости (легкие, устанавливаются быстро)
COPY requirements-mcp.txt ./
RUN pip install --no-cache-dir --timeout=300 --retries=3 -r requirements-mcp.txt

# Этап 3: Google APIs (средние по размеру)
COPY requirements-google.txt ./
RUN pip install --no-cache-dir --timeout=300 --retries=3 -r requirements-google.txt

# Этап 4: AI Framework (самые тяжелые - в конце, больше времени)
COPY requirements-ai.txt ./
RUN pip install --no-cache-dir --timeout=600 --retries=5 -r requirements-ai.txt

# Stage 3: Final image
FROM python:3.10-slim

WORKDIR /app

# Устанавливаем только runtime зависимости
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем Python зависимости из backend-setup
COPY --from=backend-setup /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=backend-setup /usr/local/bin /usr/local/bin

# Копируем собранный frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Копируем исходный код backend
COPY src/ ./src/
COPY pyproject.toml ./

# Создаем директории для данных
RUN mkdir -p /app/data/tokens \
    /app/data/sessions \
    /app/logs \
    /app/config

# Копируем entrypoint скрипт
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_ENV=production \
    DATA_DIR=/app/data

# Expose порт
EXPOSE 8000

# Health check (увеличен start-period для запуска приложения)
# Railway использует свой healthcheck, но это для локального тестирования
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Entrypoint
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

