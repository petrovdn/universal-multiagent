#!/bin/bash
# Перезапуск backend и frontend

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "🔄 Перезапуск backend и frontend..."
echo ""

bash "$ROOT/restart-server.sh"
echo ""

bash "$ROOT/restart-frontend.sh"
echo ""

echo "✅ Готово."
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
