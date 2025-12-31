# Включение Google APIs для Google Workspace

Для работы интеграции Google Workspace необходимо включить три API в Google Cloud Console.

## Необходимые API

1. **Google Drive API** - для работы с файлами и папками
2. **Google Docs API** - для работы с документами
3. **Google Sheets API** - для работы с таблицами

## Инструкция по включению

### Способ 1: Быстрое включение (рекомендуется)

1. Перейдите по прямой ссылке на каждый API:
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
   - [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)

2. На каждой странице:
   - Убедитесь, что выбран правильный проект (номер проекта: 271246391378)
   - Нажмите кнопку **ENABLE** (Включить)

### Способ 2: Через библиотеку APIs

1. Перейдите в [Google Cloud Console - APIs Library](https://console.cloud.google.com/apis/library)

2. Убедитесь, что выбран правильный проект (в верхней части страницы)

3. Для каждого API:
   - Используйте поиск, чтобы найти API:
     - Найдите "Google Drive API"
     - Найдите "Google Docs API"
     - Найдите "Google Sheets API"
   - Откройте страницу API
   - Нажмите кнопку **ENABLE** (Включить)

## Проверка включенных API

После включения можно проверить список включенных API:

1. Перейдите в [APIs & Services → Enabled APIs](https://console.cloud.google.com/apis/dashboard)
2. Убедитесь, что в списке есть:
   - ✅ Google Drive API
   - ✅ Google Docs API  
   - ✅ Google Sheets API

## После включения

После включения всех трех API:

1. Подождите 1-2 минуты (изменения применяются не мгновенно)
2. Обновите страницу приложения (F5 или Ctrl+R)
3. Попробуйте снова выбрать рабочую папку в настройках Google Workspace

## Если API уже включены, но ошибка остается

1. Проверьте, что вы используете правильный проект Google Cloud
2. Проверьте, что OAuth Client ID создан в том же проекте
3. Убедитесь, что прошло достаточно времени после включения API (1-2 минуты)
4. Попробуйте очистить кеш браузера



