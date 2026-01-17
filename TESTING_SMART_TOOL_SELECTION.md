# Руководство по тестированию Smart Tool Selection

## 🎯 Обзор

Smart Tool Selection с RAG и Skills реализован и готов к тестированию. Это руководство поможет протестировать функциональность в реальном окружении.

## 📋 Подготовка

### 1. Убедитесь что зависимости установлены

```bash
pip install -r requirements.txt
# Особенно важно:
# - openai>=1.50.0 (для embeddings)
# - PyYAML>=6.0.0 (для SKILL.md)
# - numpy>=1.24.0 (для cosine similarity)
```

### 2. Настройте OpenAI API Key

```bash
# В config/.env или через переменную окружения
export OPENAI_API_KEY="your-key-here"
```

### 3. Проверьте что skills загружаются

```bash
python3 -c "
from src.core.skills.skill_loader import SkillLoader
from pathlib import Path

loader = SkillLoader()
skills = loader.load_all_skills()
print(f'✅ Загружено skills: {len(skills)}')
for skill in skills:
    print(f'  - {skill.name}')
"
```

## 🧪 Варианты тестирования

### Вариант 1: Локальное тестирование (рекомендуется сначала)

**Запуск всех unit тестов:**

```bash
# Тесты без numpy (должны проходить везде)
python3 -m pytest tests/test_skill_loader.py -v

# Тесты с numpy (требуют нормальное окружение, не sandbox)
python3 -m pytest tests/test_embedding_cache.py tests/test_smart_tool_selector.py tests/test_skill_selector.py -v

# Интеграционные тесты
python3 -m pytest tests/test_unified_engine_smart_selection.py -v

# E2E тесты (без numpy-зависимых)
python3 -m pytest tests/test_e2e_slides_workflow.py::test_slides_workflow_selects_slides_skill -v
```

**Проверка работы компонентов вручную:**

```bash
# 1. Проверка EmbeddingCache
python3 -c "
from src.core.tool_selection.embedding_cache import EmbeddingCache
from pathlib import Path
import tempfile

cache = EmbeddingCache(cache_dir=Path(tempfile.mkdtemp()))
embedding = cache.get_embedding('test_tool', 'Test description')
print(f'✅ Embedding создан, размер: {len(embedding)}')
"

# 2. Проверка SmartToolSelector
python3 -c "
from src.core.tool_selection.smart_selector import SmartToolSelector
from src.core.action_provider import ActionCapability, CapabilityCategory, ProviderType
from pathlib import Path
import tempfile

caps = [
    ActionCapability(
        name='create_presentation',
        description='Создать презентацию',
        category=CapabilityCategory.WRITE,
        provider_type=ProviderType.MCP_TOOL,
        input_schema={},
        service='slides'
    )
]

selector = SmartToolSelector(caps, cache_dir=Path(tempfile.mkdtemp()))
result = selector.select_tools('создай презентацию', max_tools=5)
print(f'✅ Выбрано инструментов: {len(result)}')
for tool in result:
    print(f'  - {tool.name}')
"

# 3. Проверка SkillSelector
python3 -c "
from src.core.skills.skill_loader import SkillLoader
from src.core.skills.skill_selector import SkillSelector
from pathlib import Path
import tempfile

loader = SkillLoader()
skills = loader.load_all_skills()
if skills:
    selector = SkillSelector(skills, cache_dir=Path(tempfile.mkdtemp()))
    selected = selector.select_skill('создай красивую презентацию')
    if selected:
        print(f'✅ Выбран skill: {selected.name}')
        print(f'   Описание: {selected.description[:100]}...')
    else:
        print('⚠️ Skill не выбран (низкая similarity)')
else:
    print('⚠️ Skills не найдены')
"
```

### Вариант 2: Тестирование через реальный backend

**1. Запустите backend:**

```bash
# В одном терминале
python3 -m uvicorn src.api.server:app --reload --port 8000
```

**2. Включите smart tool selection:**

```bash
# В другом терминале или в config/.env
export USE_SMART_TOOL_SELECTION=true
```

**3. Протестируйте через WebSocket:**

```bash
# Используйте существующий E2E тест
python3 -m pytest tests/test_e2e_websocket.py -v -s

# Или создайте простой тест-скрипт
python3 << 'EOF'
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/test-session"
    async with websockets.connect(uri) as ws:
        # Отправляем запрос о презентации
        await ws.send(json.dumps({
            "type": "message",
            "content": "создай красивую презентацию про искусственный интеллект"
        }))
        
        # Слушаем события
        async for message in ws:
            data = json.loads(message)
            print(f"Event: {data.get('type')}")
            if data.get('type') == 'final_result':
                print(f"✅ Получен результат: {data.get('data', {}).get('content', '')[:100]}")
                break

asyncio.run(test())
EOF
```

### Вариант 3: Постепенный rollout с мониторингом

**1. Включите для тестовой сессии:**

```bash
# Только для одной сессии
USE_SMART_TOOL_SELECTION=true python3 -m uvicorn src.api.server:app --reload
```

**2. Проверьте логи:**

```bash
# Ищите в логах:
grep "Smart tool selection" logs/*.log
grep "Selected skill" logs/*.log
grep "SmartToolSelector" logs/*.log
```

**3. Сравните результаты:**

- **С флагом:** Запрос "создай презентацию" → должен выбрать slides-formatting skill
- **Без флага:** Тот же запрос → keyword-based selection

## 🔍 Что проверять

### 1. Правильность выбора инструментов

**Тест-кейсы:**

| Запрос | Ожидаемые инструменты | Skill |
|--------|----------------------|-------|
| "создай красивую презентацию" | create_presentation, create_slide, insert_slide_text | slides-formatting |
| "проанализируй таблицу" | sheets_read_range, get_sheet_data | (нет skill) |
| "выгрузи зарплату из 1С" | onec_get_salary_by_employee_month | (нет skill) |

**Как проверить:**

```python
# В логах или через debug
# Должно быть:
# [SmartToolSelector] Selected 3 tools for query: создай красивую презентацию
# [SkillSelector] Selected skill 'slides-formatting' with similarity 0.85
```

### 2. Качество embeddings

**Проверка кэша:**

```bash
# Embeddings должны кэшироваться
ls -la data/tool_embeddings/
# Должны быть файлы: create_presentation.json, skill_slides-formatting.json, etc.
```

**Проверка similarity:**

```python
# Высокая similarity для релевантных запросов (>0.7)
# Низкая similarity для нерелевантных (<0.3)
```

### 3. Инструкции из skill в промпте

**Проверка через логи:**

```bash
# В логах _think_and_plan должен быть:
# <skill_instructions>
# АКТИВНЫЙ SKILL: slides-formatting
# ...
# </skill_instructions>
```

### 4. Производительность

**Метрики:**

- Первый запрос: может быть медленнее (вычисление embeddings)
- Последующие запросы: должны быть быстрее (кэш)
- Время выбора инструментов: <100ms (с кэшем)

## 🐛 Отладка проблем

### Проблема: Skill не выбирается

**Диагностика:**

```python
from src.core.skills.skill_selector import SkillSelector
from src.core.skills.skill_loader import SkillLoader

loader = SkillLoader()
skills = loader.load_all_skills()
selector = SkillSelector(skills)

# Проверяем similarity
top_skills = selector.select_top_skills("создай презентацию", top_k=3)
for skill, similarity in top_skills:
    print(f"{skill.name}: {similarity:.3f}")

# Если similarity низкая - проверьте embeddings
```

### Проблема: Неправильные инструменты выбираются

**Диагностика:**

```python
from src.core.tool_selection.smart_selector import SmartToolSelector

# Проверяем какие инструменты выбираются
selector = SmartToolSelector(capabilities, cache_dir=...)
result = selector.select_tools("создай презентацию", max_tools=7)

for cap in result:
    print(f"{cap.name}: {cap.description[:50]}")
```

### Проблема: Segmentation fault с numpy

**Решение:**

Это проблема sandbox окружения. В нормальном окружении должно работать. Если проблема сохраняется:

```bash
# Проверьте версию numpy
python3 -c "import numpy; print(numpy.__version__)"

# Попробуйте переустановить
pip install --upgrade numpy
```

## 📊 Метрики успеха

### Критерии для включения в production:

1. ✅ **Точность выбора:** >80% релевантных инструментов для типичных запросов
2. ✅ **Производительность:** <200ms на выбор инструментов (с кэшем)
3. ✅ **Fallback работает:** При ошибках автоматический откат на keyword-based
4. ✅ **Skills загружаются:** Все skills из `skills/` директории загружаются корректно

### Мониторинг:

```python
# Добавьте метрики в код:
logger.info(f"[Metrics] Tool selection time: {elapsed_ms}ms")
logger.info(f"[Metrics] Selected {len(tools)} tools, skill: {skill.name if skill else None}")
logger.info(f"[Metrics] Similarity: {similarity:.3f}")
```

## 🚀 Рекомендуемый порядок тестирования

1. **Локально (unit тесты):**
   ```bash
   python3 -m pytest tests/test_skill_loader.py tests/test_unified_engine_smart_selection.py -v
   ```

2. **Локально (компоненты):**
   ```bash
   # Проверьте каждый компонент отдельно (см. Вариант 1)
   ```

3. **Локально (интеграция):**
   ```bash
   USE_SMART_TOOL_SELECTION=true python3 -m pytest tests/test_e2e_slides_workflow.py -v
   ```

4. **Через реальный backend:**
   ```bash
   # Запустите backend с флагом и протестируйте через UI или WebSocket
   ```

5. **Production (постепенный rollout):**
   ```bash
   # Включите для небольшого % запросов
   # Мониторьте метрики
   # Постепенно увеличивайте %
   ```

## 📝 Чеклист перед production

- [ ] Все unit тесты проходят
- [ ] Embeddings кэшируются корректно
- [ ] Skills загружаются из `skills/` директории
- [ ] Feature flag работает (включение/выключение)
- [ ] Fallback на keyword-based работает при ошибках
- [ ] Производительность приемлема (<200ms)
- [ ] Логи содержат достаточно информации для отладки
- [ ] Тестировано на реальных запросах (презентации, таблицы, etc.)

## 💡 Советы

1. **Начните с простых запросов:** "создай презентацию" → проверьте что skill выбран
2. **Сравните результаты:** С флагом vs без флага
3. **Мониторьте кэш:** Embeddings должны кэшироваться после первого запроса
4. **Проверяйте логи:** Включите debug логи для детальной информации
5. **Тестируйте edge cases:** Пустые запросы, нерелевантные запросы, ошибки API

## 🔗 Полезные команды

```bash
# Очистить кэш embeddings (для тестирования с нуля)
rm -rf data/tool_embeddings/*

# Проверить что skills загружаются
python3 -c "from src.core.skills.skill_loader import SkillLoader; print([s.name for s in SkillLoader().load_all_skills()])"

# Проверить feature flag
python3 -c "import os; print('USE_SMART_TOOL_SELECTION:', os.getenv('USE_SMART_TOOL_SELECTION', 'not set'))"
```
