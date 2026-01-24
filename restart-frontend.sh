#!/bin/bash
# Перезапуск frontend (Vite)

set -e
cd "$(dirname "$0")"

echo "🔄 Перезапуск frontend..."

# Остановка Vite / Node на 5173
pkill -f "vite" 2>/dev/null || true
pkill -f "node.*5173" 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 2

# Запуск из frontend/
echo "   Запуск Vite на http://localhost:5173 ..."
(cd frontend && nohup npm run dev > /tmp/frontend.log 2>&1 &)

# Ждём готовности
for i in $(seq 1 15); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null | grep -qE '^2|^3'; then
    echo "✅ Frontend перезапущен. Логи: /tmp/frontend.log"
    exit 0
  fi
  sleep 1
done

echo "❌ Frontend не ответил. Логи:"
tail -30 /tmp/frontend.log
exit 1
