#!/bin/bash
# Команда для перезапуска backend и frontend

echo "🔄 Перезапуск всех сервисов..."

# Запускаем скрипты перезапуска
echo ""
echo "📦 Перезапуск backend..."
bash "$(dirname "$0")/restart-server.sh"

echo ""
echo "🎨 Перезапуск frontend..."
bash "$(dirname "$0")/restart-frontend.sh"

echo ""
echo "✅ Все сервисы перезапущены!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"




