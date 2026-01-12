#!/bin/bash
# Легкая версия скрипта перезапуска сервера
# Без проверки зависимостей, быстрый перезапуск

# Останавливаем все процессы uvicorn и освобождаем порт
pkill -9 -f "uvicorn.*server:app" || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Ждем 1 секунду (меньше чем в полной версии)
sleep 1

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Запускаем сервер в фоновом режиме (без проверки зависимостей)
echo "Запускаем сервер..."
nohup python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload > /tmp/server.log 2>&1 &

# Ждем немного для запуска
sleep 5

# Проверяем, что сервер запустился
for i in {1..5}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1 || curl -s http://localhost:8000/ > /dev/null 2>&1; then
        break
    fi
    if [ $i -lt 5 ]; then
        sleep 1
    fi
done

if curl -s http://localhost:8000/api/health > /dev/null 2>&1 || curl -s http://localhost:8000/ > /dev/null 2>&1; then
    # Получаем PID процесса
    PID=$(ps aux | grep '[u]vicorn.*server:app' | awk '{print $2}' | head -1)
    if [ -n "$PID" ]; then
        echo "✅ Сервер перезапущен. PID: $PID"
        echo "Логи: /tmp/server.log"
    else
        echo "✅ Сервер запущен и отвечает (PID не найден, возможно из-за --reload)"
    fi
else
    echo "❌ Ошибка: сервер не запустился. Проверьте логи: /tmp/server.log"
    tail -20 /tmp/server.log
    exit 1
fi
