#!/bin/bash
# Скрипт для тестирования Smart Tool Selection через реальный backend

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Тестирование Smart Tool Selection через Backend${NC}"
echo "=================================================="

# Проверка что backend не запущен
echo -e "\n${YELLOW}1. Проверка порта 8000...${NC}"
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}⚠️  Порт 8000 уже занят. Остановите существующий backend или используйте другой порт.${NC}"
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ Порт 8000 свободен${NC}"
fi

# Проверка переменных окружения
echo -e "\n${YELLOW}2. Настройка окружения...${NC}"
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}⚠️  OPENAI_API_KEY не установлен${NC}"
    echo "   Установите: export OPENAI_API_KEY='your-key'"
    exit 1
else
    echo -e "${GREEN}✅ OPENAI_API_KEY установлен${NC}"
fi

# Включаем smart tool selection
export USE_SMART_TOOL_SELECTION=true
echo -e "${GREEN}✅ USE_SMART_TOOL_SELECTION=true${NC}"

# Проверка skills
echo -e "\n${YELLOW}3. Проверка skills...${NC}"
python3 << 'PYTHON'
from src.core.skills.skill_loader import SkillLoader

loader = SkillLoader()
skills = loader.load_all_skills()
print(f"✅ Загружено skills: {len(skills)}")
for skill in skills:
    print(f"   - {skill.name}")
if len(skills) == 0:
    print("⚠️  Skills не найдены!")
    exit(1)
PYTHON

# Запуск backend
echo -e "\n${YELLOW}4. Запуск backend с USE_SMART_TOOL_SELECTION=true...${NC}"
echo -e "${BLUE}Backend будет запущен в фоне.${NC}"
echo -e "${BLUE}Логи: смотрите в терминале или в logs/ директории${NC}"
echo ""
echo -e "${YELLOW}Для остановки: нажмите Ctrl+C или выполните: pkill -f 'uvicorn.*server:app'${NC}"
echo ""

# Запускаем backend в фоне
python3 -m uvicorn src.api.server:app --reload --port 8000 > /tmp/backend-smart-selection.log 2>&1 &
BACKEND_PID=$!

# Ждём запуска
echo "Ожидание запуска backend..."
sleep 3

# Проверка что backend запустился
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend не запустился. Проверьте логи:${NC}"
    cat /tmp/backend-smart-selection.log
    exit 1
fi

# Проверка доступности
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend запущен и доступен на http://localhost:8000${NC}"
else
    echo -e "${YELLOW}⚠️  Backend запущен, но /health не отвечает. Проверьте логи.${NC}"
fi

echo ""
echo -e "${GREEN}=================================================="
echo -e "Backend запущен с Smart Tool Selection!"
echo -e "==================================================${NC}"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Откройте фронтенд: http://localhost:5173 (или ваш порт)"
echo "2. Отправьте запрос: 'создай красивую презентацию про ИИ'"
echo "3. Проверьте логи на наличие:"
echo "   - [UnifiedReActEngine] Smart tool selection enabled"
echo "   - [SkillSelector] Selected skill 'slides-formatting'"
echo "   - [SmartToolSelector] Selected X tools"
echo ""
echo -e "${YELLOW}Или протестируйте через curl:${NC}"
echo 'curl -X POST http://localhost:8000/api/sessions/test-session/message \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{"content": "создай красивую презентацию"}'"'"''
echo ""
echo -e "${YELLOW}Логи backend:${NC}"
echo "tail -f /tmp/backend-smart-selection.log"
echo ""
echo -e "${YELLOW}Для остановки backend:${NC}"
echo "kill $BACKEND_PID"
echo ""

# Ждём завершения или прерывания
trap "echo ''; echo 'Остановка backend...'; kill $BACKEND_PID 2>/dev/null; exit" INT TERM

# Показываем последние строки логов
echo -e "${BLUE}Последние строки логов:${NC}"
tail -20 /tmp/backend-smart-selection.log

echo ""
echo -e "${YELLOW}Нажмите Ctrl+C для остановки backend${NC}"
wait $BACKEND_PID
