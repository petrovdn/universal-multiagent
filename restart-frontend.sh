#!/bin/bash
# Команда для перезапуска фронтенда

# Останавливаем все процессы vite/node на порту 5173
pkill -9 -f "vite.*5173" || true
pkill -9 -f "node.*5173" || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

# Ждем 2 секунды
sleep 2

# Переходим в директорию проекта
cd "$(dirname "$0")/frontend"

# Запускаем фронтенд в фоновом режиме
echo "Запускаем фронтенд..."
nohup npm run dev > /tmp/frontend.log 2>&1 &

# Ждем немного для запуска
sleep 5

# Проверяем, что фронтенд запустился
for i in {1..10}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        break
    fi
    if [ $i -lt 10 ]; then
        sleep 1
    fi
done

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    # Получаем PID процесса
    PID=$(ps aux | grep '[n]ode.*5173\|[v]ite' | awk '{print $2}' | head -1)
    if [ -n "$PID" ]; then
        echo "✅ Фронтенд перезапущен. PID: $PID"
        echo "Логи: /tmp/frontend.log"
    else
        echo "✅ Фронтенд запущен и отвечает"
    fi
else
    echo "❌ Ошибка: фронтенд не запустился. Проверьте логи: /tmp/frontend.log"
    tail -20 /tmp/frontend.log
    exit 1
fi

