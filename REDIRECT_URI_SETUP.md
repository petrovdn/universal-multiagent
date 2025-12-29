# Настройка Redirect URIs в Google Cloud Console

Чтобы все интеграции работали корректно, добавьте следующие Redirect URIs в Google Cloud Console:

## Список всех Redirect URIs

```
http://localhost:8000/api/integrations/google-workspace/callback
http://localhost:8000/api/integrations/google-calendar/callback
http://localhost:8000/api/integrations/google-sheets/callback
http://localhost:8000/api/integrations/gmail/callback
http://localhost:8000/auth/callback
```

## Инструкция по добавлению

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите ваш проект
3. Перейдите в **APIs & Services** → **Credentials**
4. Найдите ваш **OAuth 2.0 Client ID** (тип Web application)
5. Нажмите на него для редактирования
6. В разделе **Authorized redirect URIs** нажмите **+ ADD URI**
7. Добавьте каждый URI из списка выше (по одному)
8. Нажмите **SAVE**

## Проверка

После сохранения проверьте, что все URIs добавлены. Они должны отображаться в списке.

## Важно

- URIs должны быть добавлены точно как указано (с http://localhost:8000)
- Если вы используете другой порт или домен, замените localhost:8000 на соответствующий
- После добавления URIs изменения применяются сразу, перезагрузка не требуется

## Если ошибка все еще возникает

1. Убедитесь, что вы используете правильный OAuth Client ID в настройках приложения
2. Проверьте, что все URIs добавлены точно (включая слеши и регистр)
3. Подождите несколько секунд после сохранения (изменения могут применяться с небольшой задержкой)
4. Очистите кеш браузера и попробуйте снова



