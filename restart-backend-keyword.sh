#!/bin/bash
# Перезапуск backend БЕЗ Smart Tool Selection (keyword-based)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 Перезапуск backend с Keyword-based Selection${NC}"
echo "=================================================="

# Останавливаем существующий backend
echo -e "\n${YELLOW}1. Остановка существующего backend...${NC}"
pkill -f "uvicorn.*server:app" 2>/dev/null && sleep 1 || echo "   Backend не запущен"

# Проверяем что порт свободен
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}⚠️  Порт 8000 всё ещё занят. Принудительное освобождение...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Выключаем smart tool selection (если был установлен)
unset USE_SMART_TOOL_SELECTION
echo -e "\n${GREEN}✅ USE_SMART_TOOL_SELECTION не установлен (keyword-based mode)${NC}"

# Запускаем backend
echo -e "\n${YELLOW}2. Запуск backend в keyword-based режиме...${NC}"
echo -e "${GREEN}Backend запускается на http://localhost:8000${NC}"
echo -e "${BLUE}Используется keyword-based tool selection (legacy)${NC}"
echo ""
echo -e "${YELLOW}Для остановки: Ctrl+C${NC}"
echo ""

# Запускаем в foreground чтобы видеть логи
exec python3 -m uvicorn src.api.server:app --reload --port 8000
