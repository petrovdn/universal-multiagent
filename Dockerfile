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

# Копируем requirements
COPY requirements.txt ./

# Устанавливаем Python зависимости с оптимизацией для Railway
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --timeout=300 --retries=3 -r requirements.txt

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

