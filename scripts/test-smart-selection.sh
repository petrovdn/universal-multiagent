#!/bin/bash
# Скрипт для быстрого тестирования Smart Tool Selection

set -e

echo "🧪 Тестирование Smart Tool Selection"
echo "======================================"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка зависимостей
echo -e "\n${YELLOW}1. Проверка зависимостей...${NC}"
python3 -c "import openai; print('✅ OpenAI:', openai.__version__)" || { echo -e "${RED}❌ OpenAI не установлен${NC}"; exit 1; }
python3 -c "import yaml; print('✅ PyYAML установлен')" || { echo -e "${RED}❌ PyYAML не установлен${NC}"; exit 1; }
python3 -c "import numpy; print('✅ NumPy:', numpy.__version__)" || { echo -e "${RED}❌ NumPy не установлен${NC}"; exit 1; }

# Проверка API ключа
echo -e "\n${YELLOW}2. Проверка OpenAI API key...${NC}"
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}⚠️  OPENAI_API_KEY не установлен${NC}"
    echo "   Установите: export OPENAI_API_KEY='your-key'"
    read -p "   Продолжить без API key? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ OPENAI_API_KEY установлен${NC}"
fi

# Проверка skills
echo -e "\n${YELLOW}3. Проверка skills...${NC}"
python3 << 'PYTHON'
from src.core.skills.skill_loader import SkillLoader
from pathlib import Path

try:
    loader = SkillLoader()
    skills = loader.load_all_skills()
    print(f"✅ Загружено skills: {len(skills)}")
    for skill in skills:
        print(f"   - {skill.name}")
    if len(skills) == 0:
        print("⚠️  Skills не найдены. Убедитесь что skills/ директория существует.")
except Exception as e:
    print(f"❌ Ошибка загрузки skills: {e}")
PYTHON

# Запуск тестов
echo -e "\n${YELLOW}4. Запуск тестов...${NC}"

# Тесты без numpy (должны проходить везде)
echo -e "\n${YELLOW}4.1. Тесты SkillLoader...${NC}"
python3 -m pytest tests/test_skill_loader.py -v --tb=short || echo -e "${RED}❌ Тесты SkillLoader провалились${NC}"

# Тесты с numpy (могут падать в sandbox)
echo -e "\n${YELLOW}4.2. Тесты SmartToolSelector (требуют нормальное окружение)...${NC}"
python3 -m pytest tests/test_smart_tool_selector.py -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Тесты могут падать в sandbox окружении${NC}"

# Интеграционные тесты
echo -e "\n${YELLOW}4.3. Интеграционные тесты...${NC}"
python3 -m pytest tests/test_unified_engine_smart_selection.py -v --tb=short || echo -e "${RED}❌ Интеграционные тесты провалились${NC}"

# E2E тесты (без numpy-зависимых)
echo -e "\n${YELLOW}4.4. E2E тесты (slides workflow)...${NC}"
python3 -m pytest tests/test_e2e_slides_workflow.py::test_slides_workflow_selects_slides_skill tests/test_e2e_slides_workflow.py::test_slides_workflow_fallback_to_keyword_when_flag_disabled -v --tb=short || echo -e "${RED}❌ E2E тесты провалились${NC}"

# Проверка компонентов вручную
echo -e "\n${YELLOW}5. Проверка компонентов вручную...${NC}"

echo -e "\n${YELLOW}5.1. EmbeddingCache...${NC}"
python3 << 'PYTHON'
from src.core.tool_selection.embedding_cache import EmbeddingCache
from pathlib import Path
import tempfile

try:
    cache = EmbeddingCache(cache_dir=Path(tempfile.mkdtemp()))
    embedding = cache.get_embedding('test_tool', 'Test description')
    print(f"✅ Embedding создан, размер: {len(embedding)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
PYTHON

echo -e "\n${YELLOW}5.2. SkillSelector...${NC}"
python3 << 'PYTHON'
from src.core.skills.skill_loader import SkillLoader
from src.core.skills.skill_selector import SkillSelector
from pathlib import Path
import tempfile

try:
    loader = SkillLoader()
    skills = loader.load_all_skills()
    if skills:
        selector = SkillSelector(skills, cache_dir=Path(tempfile.mkdtemp()))
        selected = selector.select_skill('создай красивую презентацию')
        if selected:
            print(f"✅ Выбран skill: {selected.name}")
        else:
            print("⚠️  Skill не выбран (низкая similarity или нет релевантного skill)")
    else:
        print("⚠️  Skills не найдены")
except Exception as e:
    print(f"❌ Ошибка: {e}")
PYTHON

echo -e "\n${GREEN}✅ Тестирование завершено!${NC}"
echo -e "\n${YELLOW}Следующие шаги:${NC}"
echo "1. Запустите backend: python3 -m uvicorn src.api.server:app --reload"
echo "2. Включите флаг: export USE_SMART_TOOL_SELECTION=true"
echo "3. Протестируйте через UI или WebSocket"
echo ""
echo "Подробнее: см. TESTING_SMART_TOOL_SELECTION.md"
