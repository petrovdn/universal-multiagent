# Настройка файла gcp-oauth.keys.json для Gmail MCP

## Точное расположение файла

Gmail MCP сервер ищет файл `gcp-oauth.keys.json` в следующих местах (в порядке приоритета):

1. **Текущая директория** (где запускается команда)
2. **`~/.gmail-mcp/gcp-oauth.keys.json`** (рекомендуется)

## Рекомендуемый способ

Создайте файл в домашней директории:

```bash
# 1. Создайте директорию (если еще не создана)
mkdir -p ~/.gmail-mcp

# 2. Создайте файл gcp-oauth.keys.json
nano ~/.gmail-mcp/gcp-oauth.keys.json
# или
code ~/.gmail-mcp/gcp-oauth.keys.json
```

## Формат файла

Скопируйте содержимое скачанного JSON файла из Google Cloud Console и преобразуйте в нужный формат:

```json
{
  "web": {
    "client_id": "ваш-client-id.apps.googleusercontent.com",
    "client_secret": "ваш-client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

**Важно**: 
- Используйте ключ `"web"`, даже если создавали "Desktop app" credentials
- Убедитесь, что JSON валиден (проверьте запятые, кавычки)

## Проверка

После создания файла проверьте:

```bash
# Проверьте, что файл существует
ls -la ~/.gmail-mcp/gcp-oauth.keys.json

# Проверьте содержимое (будьте осторожны - не показывайте секреты публично!)
cat ~/.gmail-mcp/gcp-oauth.keys.json | jq . 2>/dev/null || cat ~/.gmail-mcp/gcp-oauth.keys.json
```

## Альтернативный вариант

Если хотите использовать текущую директорию проекта:

```bash
# В корне проекта
cp путь/к/скачанному-файлу.json gcp-oauth.keys.json
```

Но это менее удобно, так как файл должен быть в директории, где запускается сервер.

## Безопасность

⚠️ **Важно**: 
- Файл содержит секретные ключи
- Добавьте в `.gitignore`: `gcp-oauth.keys.json` и `~/.gmail-mcp/`
- Не коммитьте этот файл в git
- Не делитесь содержимым файла

## Полный путь для macOS

На macOS полный путь будет:
```
/Users/ваше-имя-пользователя/.gmail-mcp/gcp-oauth.keys.json
```

Для текущего пользователя:
```
/Users/Dima/.gmail-mcp/gcp-oauth.keys.json
```



