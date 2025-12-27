# Быстрая настройка Railway

Пошаговая инструкция для первого деплоя на Railway.

## Шаг 1: Подготовка репозитория

```bash
# Убедитесь, что вы в production ветке
git checkout production

# Убедитесь, что все изменения закоммичены
git status

# Отправьте в GitHub
git push origin production
```

## Шаг 2: Создание проекта в Railway

1. Откройте [Railway](https://railway.app)
2. Нажмите "Start a New Project"
3. Выберите "Deploy from GitHub repo"
4. Авторизуйтесь через GitHub
5. Выберите ваш репозиторий
6. Выберите ветку `production`

## Шаг 3: Настройка переменных окружения

В Railway Dashboard:

1. Откройте ваш проект
2. Перейдите в "Variables"
3. Добавьте следующие переменные:

### Минимальный набор:

```
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
GOOGLE_OAUTH_CLIENT_ID=your-id
GOOGLE_OAUTH_CLIENT_SECRET=your-secret
APP_ENV=production
```

### После получения домена добавьте:

```
GOOGLE_OAUTH_REDIRECT_URI=https://your-app.railway.app/auth/callback
API_CORS_ORIGINS=https://your-app.railway.app
```

## Шаг 4: Получение домена

1. В Railway Dashboard откройте ваш сервис
2. Перейдите в "Settings" → "Networking"
3. Нажмите "Generate Domain"
4. Скопируйте домен (например: `your-app.up.railway.app`)

## Шаг 5: Обновление Google OAuth

1. Откройте [Google Cloud Console](https://console.cloud.google.com)
2. Перейдите в "APIs & Services" → "Credentials"
3. Откройте ваш OAuth 2.0 Client ID
4. В "Authorized redirect URIs" добавьте:
   ```
   https://your-app.railway.app/auth/callback
   ```
5. Сохраните изменения

## Шаг 6: Обновление переменных в Railway

Вернитесь в Railway и обновите переменные:

```
GOOGLE_OAUTH_REDIRECT_URI=https://your-app.railway.app/auth/callback
API_CORS_ORIGINS=https://your-app.railway.app
```

Railway автоматически перезапустит приложение.

## Шаг 7: Проверка

1. Откройте ваш домен в браузере
2. Проверьте health endpoint: `https://your-app.railway.app/api/health`
3. Должен вернуться JSON с `"status": "healthy"`

## Готово!

Ваше приложение задеплоено и готово к использованию.

## Следующие шаги

1. Настройте интеграции через веб-интерфейс
2. Проверьте логи в Railway Dashboard
3. Настройте мониторинг (опционально)

## Полезные команды

### Просмотр логов:
Railway Dashboard → Ваш сервис → "Deployments" → "View Logs"

### Перезапуск:
Railway Dashboard → Ваш сервис → "Settings" → "Restart"

### Обновление:
```bash
./scripts/sync-to-prod.sh
git push origin production
```

