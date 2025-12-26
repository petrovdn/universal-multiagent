# Руководство по деплою на Railway

Это руководство описывает процесс деплоя Universal Multi-Agent System на Railway.

## Предварительные требования

1. Аккаунт на [Railway](https://railway.app)
2. GitHub репозиторий с вашим проектом
3. Google Cloud Project с настроенным OAuth 2.0
4. API ключи (Anthropic или OpenAI)

## Подготовка проекта

### 1. Создание production ветки

```bash
# Переключитесь на main ветку
git checkout main

# Создайте production ветку
git checkout -b production

# Отправьте в репозиторий
git push origin production
```

### 2. Синхронизация изменений

Для переноса изменений из dev (main) в production используйте скрипт:

```bash
./scripts/sync-to-prod.sh
```

Этот скрипт:
- Переключается на main ветку
- Мержит изменения в production
- Показывает статус

## Настройка Railway

### 1. Создание проекта

1. Войдите в [Railway Dashboard](https://railway.app/dashboard)
2. Нажмите "New Project"
3. Выберите "Deploy from GitHub repo"
4. Выберите ваш репозиторий
5. Выберите ветку `production`

### 2. Настройка переменных окружения

В настройках проекта добавьте следующие переменные:

#### Обязательные переменные:

```env
# API Keys (нужен хотя бы один)
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=https://your-app.railway.app/auth/callback

# Production settings
APP_ENV=production
DATA_DIR=/app/data

# CORS (замените на ваш домен)
API_CORS_ORIGINS=https://your-app.railway.app
```

#### Опциональные переменные:

```env
# Model settings
DEFAULT_MODEL=gpt-4o

# Application settings
APP_TIMEZONE=Europe/Moscow
APP_LOG_LEVEL=INFO

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Настройка Volumes

Railway автоматически создаст volume для `/app/data`, где будут храниться:
- OAuth токены (`/app/data/tokens/`)
- Сессии (`/app/data/sessions/`)
- Логи (`/app/logs/`)

### 4. Настройка домена

1. В настройках сервиса перейдите в "Settings" → "Networking"
2. Нажмите "Generate Domain" или добавьте свой домен
3. Обновите `GOOGLE_OAUTH_REDIRECT_URI` с новым доменом

### 5. Обновление Google OAuth

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com)
2. Откройте ваш OAuth 2.0 Client
3. Добавьте ваш Railway домен в "Authorized redirect URIs":
   - `https://your-app.railway.app/auth/callback`

## Деплой

### Автоматический деплой

Railway автоматически деплоит при каждом push в ветку `production`:

```bash
# Синхронизируйте изменения
./scripts/sync-to-prod.sh

# Отправьте в репозиторий
git push origin production
```

### Проверка деплоя

1. В Railway Dashboard проверьте статус деплоя
2. Откройте ваш домен в браузере
3. Проверьте health endpoint: `https://your-app.railway.app/api/health`

## Локальное тестирование production образа

Перед деплоем можно протестировать образ локально:

```bash
# Соберите образ
./scripts/build-prod.sh

# Запустите локально
./scripts/test-prod-local.sh
```

## Troubleshooting

### Ошибка "Missing required configuration"

Убедитесь, что все обязательные переменные окружения установлены в Railway.

### Ошибка OAuth redirect

1. Проверьте, что `GOOGLE_OAUTH_REDIRECT_URI` соответствует домену Railway
2. Убедитесь, что домен добавлен в Google OAuth консоли

### Ошибка "Token not found"

Токены создаются автоматически при первой авторизации через OAuth. Убедитесь, что:
1. Volume настроен правильно
2. Приложение имеет права на запись в `/app/data`

### Проблемы с CORS

Убедитесь, что `API_CORS_ORIGINS` содержит ваш production домен.

### Логи

Просмотр логов в Railway:
1. Откройте сервис в Railway Dashboard
2. Перейдите в "Deployments"
3. Выберите последний деплой
4. Откройте "View Logs"

## Обновление приложения

1. Внесите изменения в `main` ветку
2. Протестируйте локально
3. Синхронизируйте в production:
   ```bash
   ./scripts/sync-to-prod.sh
   ```
4. Отправьте в репозиторий:
   ```bash
   git push origin production
   ```
5. Railway автоматически задеплоит новую версию

## Мониторинг

### Health Check

Railway автоматически проверяет health endpoint:
- URL: `/api/health`
- Интервал: каждые 30 секунд
- Timeout: 10 секунд

### Метрики

В Railway Dashboard доступны:
- CPU использование
- Memory использование
- Network traffic
- Request logs

## Безопасность

1. **Никогда не коммитьте** `.env` файлы или токены в Git
2. Используйте Railway Secrets для хранения чувствительных данных
3. Регулярно обновляйте зависимости
4. Используйте HTTPS (Railway предоставляет автоматически)

## Стоимость

Railway предоставляет:
- $5 бесплатных кредитов в месяц
- Pay-as-you-go после исчерпания лимита

Оценка стоимости для небольшого приложения: $5-15/месяц

## Дополнительные ресурсы

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
- [Troubleshooting Guide](docs/mcp-troubleshooting.md)

