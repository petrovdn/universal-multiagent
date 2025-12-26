# Руководство по настройке Google аутентификации

Это руководство объясняет, как настроить Google Cloud аутентификацию для мультиагентной системы. Система использует только OAuth 2.0, все операции выполняются от имени аутентифицированного пользователя.

## Обзор

Система использует OAuth 2.0 для аутентификации:
- Все операции выполняются от имени пользователя, который прошел аутентификацию
- Пользователь предоставляет согласие на доступ к своим данным (Gmail, Calendar, Sheets)
- Токены автоматически обновляются при необходимости

## Требования

- Аккаунт Google Cloud
- Доступ для создания проектов и учетных данных
- Google аккаунт пользователя для аутентификации

## Шаг 1: Создание Google Cloud проекта

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Нажмите "Select a project" > "New Project"
3. Введите имя проекта: `multi-agent-workspace`
4. Нажмите "Create"
5. Дождитесь создания проекта (может занять несколько секунд)

## Шаг 2: Включение необходимых API

Включите следующие API в вашем проекте:

1. **Gmail API**
   - Перейдите в "APIs & Services" > "Library"
   - Найдите "Gmail API"
   - Нажмите "Enable"

2. **Google Calendar API**
   - Найдите "Google Calendar API"
   - Нажмите "Enable"

3. **Google Sheets API**
   - Найдите "Google Sheets API"
   - Нажмите "Enable"

## Шаг 3: Создание OAuth 2.0 учетных данных

### 3.1 Настройка OAuth Consent Screen

1. Перейдите в "APIs & Services" > "OAuth consent screen"
2. Выберите "External" (если у вас нет Google Workspace)
3. Нажмите "Create"
4. Заполните форму:
   - **App name**: `Multi-Agent Workspace Assistant`
   - **User support email**: Ваш email
   - **Developer contact**: Ваш email
5. Нажмите "Save and Continue"
6. Добавьте scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/spreadsheets`
7. Нажмите "Save and Continue"
8. Добавьте тестовых пользователей (если в режиме тестирования)
9. Нажмите "Save and Continue"
10. Просмотрите и нажмите "Back to Dashboard"

### 3.2 Создание OAuth Client ID

1. Перейдите в "APIs & Services" > "Credentials"
2. Нажмите "Create Credentials" > "OAuth client ID"
3. Выберите тип приложения: **"Web application"**
4. Введите имя: `multi-agent-web-client`
5. Добавьте authorized redirect URIs:
   - `http://localhost:8000/auth/callback`
   - `http://localhost:5173/auth/callback` (для frontend)
6. Нажмите "Create"
7. **Сохраните Client ID и Client Secret** (они вам понадобятся)

## Шаг 4: Конфигурация приложения

Обновите `config/.env` с вашими OAuth учетными данными:
```env
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
```

## Шаг 5: Лучшие практики безопасности

### 5.1 Защита учетных данных

1. **Никогда не коммитьте учетные данные в git:**
   - Добавьте в `.gitignore`:
     ```
     config/.env
     config/token.json
     ```

2. **Используйте переменные окружения в production:**
   - Установите через платформу развертывания (Heroku, AWS и т.д.)
   - Используйте управление секретами (AWS Secrets Manager, Google Secret Manager)

3. **Регулярно ротируйте учетные данные:**
   - OAuth секреты: каждые 180 дней
   - Токены пользователей автоматически обновляются системой

### 5.2 Ограничение scopes

Запрашивайте только минимально необходимые scopes:
- `gmail.readonly` вместо `gmail` (если достаточно доступа только для чтения)
- `calendar` вместо `calendar.events` (если не нужен полный доступ к календарю)

### 5.3 Мониторинг использования

1. Включите Cloud Logging
2. Настройте алерты для:
   - Необычного использования API
   - Неудачных попыток аутентификации
   - Ошибок ограничения скорости

## Шаг 6: Тестирование аутентификации

### Тест OAuth процесса

1. Запустите приложение
2. Перейдите на `/auth/login`
3. Завершите OAuth процесс согласия
4. Проверьте, что токен сохранен

## Устранение неполадок

### Проблемы с OAuth

**Ошибка: "redirect_uri_mismatch"**
- Проверьте, что redirect URI в OAuth client совпадает точно
- Проверьте наличие завершающих слэшей
- Убедитесь, что протокол (http/https) совпадает

**Ошибка: "access_denied"**
- Пользователь мог отклонить согласие
- Проверьте конфигурацию OAuth consent screen
- Убедитесь, что тестовые пользователи добавлены (если в режиме тестирования)

### Проблемы с квотами API

**Ошибка: "Quota exceeded"**
- Проверьте квоты API в Cloud Console
- Реализуйте ограничение скорости
- Запросите увеличение квоты при необходимости

## Следующие шаги

После настройки аутентификации:
1. Запустите приложение: `python src/main.py`
2. Откройте в браузере: `http://localhost:8000/auth/login`
3. Завершите OAuth процесс согласия
4. После успешной аутентификации вы будете перенаправлены на frontend
5. Теперь все операции будут выполняться от вашего имени

## Важные замечания

- **Все операции выполняются от имени пользователя**: Система работает с вашими данными (ваш Gmail, ваш Calendar, ваши Sheets)
- **Токены автоматически обновляются**: Система автоматически обновляет истекшие токены
- **Безопасность**: Токены хранятся локально в `config/token.json` (не коммитьте этот файл!)
- **Выход из системы**: Используйте `/auth/logout` для отзыва токенов

## Ссылки

- [OAuth 2.0 for Web Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
