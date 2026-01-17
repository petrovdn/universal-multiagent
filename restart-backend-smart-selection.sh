#!/bin/bash
# Перезапуск backend с USE_SMART_TOOL_SELECTION=true

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 Перезапуск backend с Smart Tool Selection${NC}"
echo "=============================================="

# Останавливаем существующий backend
echo -e "\n${YELLOW}1. Остановка существующего backend...${NC}"
pkill -f "uvicorn.*server:app" 2>/dev/null && sleep 1 || echo "   Backend не запущен"

# Проверяем что порт свободен
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}⚠️  Порт 8000 всё ещё занят. Принудительное освобождение...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Включаем smart tool selection
export USE_SMART_TOOL_SELECTION=true
echo -e "\n${GREEN}✅ USE_SMART_TOOL_SELECTION=true${NC}"

# Проверяем OpenAI API key (используем тот же что для обычных моделей)
echo -e "\n${YELLOW}2. Проверка OpenAI API key...${NC}"
python3 << 'PYTHON'
import os
import sys
from pathlib import Path

# Используем config_loader чтобы получить ключ так же как это делает backend
try:
    from src.utils.config_loader import get_config
    config = get_config()
    api_key = getattr(config, 'openai_api_key', None) or os.environ.get('OPENAI_API_KEY')
    
    if api_key and api_key.strip():
        print(f"✅ OpenAI API key найден (используется тот же что для обычных моделей)")
        # Устанавливаем в окружение для текущей сессии если ещё не установлен
        if not os.environ.get('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = api_key
    else:
        print("⚠️  OpenAI API key не найден")
        print("   Smart tool selection требует OpenAI API key для embeddings")
        print("   Установите в config/.env: OPENAI_API_KEY=your-key")
        print("   Или через переменную окружения: export OPENAI_API_KEY='your-key'")
except Exception as e:
    print(f"⚠️  Ошибка проверки config: {e}")
    print("   Backend попытается загрузить ключ сам при запуске")
PYTHON

# Проверяем skills
echo -e "\n${YELLOW}3. Проверка skills...${NC}"
python3 << 'PYTHON'
from src.core.skills.skill_loader import SkillLoader

loader = SkillLoader()
skills = loader.load_all_skills()
print(f"✅ Загружено skills: {len(skills)}")
for skill in skills:
    print(f"   - {skill.name}")
if len(skills) == 0:
    print("⚠️  Skills не найдены, но backend запустится")
PYTHON

# Запускаем backend
echo -e "\n${YELLOW}4. Запуск backend с USE_SMART_TOOL_SELECTION=true...${NC}"
echo -e "${GREEN}Backend запускается на http://localhost:8000${NC}"
echo -e "${BLUE}Логи в реальном времени ниже...${NC}"
echo ""
echo -e "${YELLOW}Для остановки: Ctrl+C${NC}"
echo ""

# Запускаем в foreground чтобы видеть логи
exec python3 -m uvicorn src.api.server:app --reload --port 8000
