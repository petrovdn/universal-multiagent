# Руководство по тестированию Smart Tool Selection через Backend

## 🚀 Быстрый старт

### Вариант 1: Автоматический скрипт (рекомендуется)

```bash
# Запустит backend с флагом и покажет инструкции
./scripts/test-backend-smart-selection.sh
```

### Вариант 2: Вручную

```bash
# Терминал 1: Запустите backend с флагом
export USE_SMART_TOOL_SELECTION=true
python3 -m uvicorn src.api.server:app --reload --port 8000

# Терминал 2: Протестируйте через WebSocket скрипт
python3 scripts/test-via-websocket.py "создай красивую презентацию"
```

## 🧪 Тестирование через WebSocket

### Использование готового скрипта

```bash
# Простой запрос
python3 scripts/test-via-websocket.py "создай красивую презентацию"

# Сложный запрос
python3 scripts/test-via-websocket.py "создай красивую презентацию про искусственный интеллект на 5 слайдов"
```

### Что проверяет скрипт:

1. ✅ Создание сессии
2. ✅ Подключение к WebSocket
3. ✅ Отправка запроса
4. ✅ Получение событий (thinking_started, tool_call, final_result)
5. ✅ Анализ выбранных инструментов

## 🖥️ Тестирование через UI (фронтенд)

### 1. Запустите backend с флагом

```bash
export USE_SMART_TOOL_SELECTION=true
python3 -m uvicorn src.api.server:app --reload --port 8000
```

### 2. Запустите фронтенд

```bash
cd frontend
npm run dev
# Откроется на http://localhost:5173 (или другой порт)
```

### 3. Тест-кейсы для проверки

#### Тест 1: Создание презентации (должен выбрать slides-formatting skill)

**Запрос:**
```
создай красивую презентацию про искусственный интеллект
```

**Что проверить:**
- В логах backend должно быть:
  ```
  [UnifiedReActEngine] Smart tool selection enabled with 1 skills
  [SkillSelector] Selected skill 'slides-formatting' with similarity 0.XX
  [SmartToolSelector] Selected 3 tools for query: создай красивую презентацию
  ```

- В промпте должны быть инструкции из skill (проверьте логи _think_and_plan)

#### Тест 2: Сравнение с keyword-based (без флага)

**Без флага:**
```bash
# Запустите без USE_SMART_TOOL_SELECTION
python3 -m uvicorn src.api.server:app --reload
```

**С флагом:**
```bash
export USE_SMART_TOOL_SELECTION=true
python3 -m uvicorn src.api.server:app --reload
```

**Сравните:**
- Какие инструменты выбраны
- Время ответа
- Качество ответа

#### Тест 3: Нерелевантный запрос

**Запрос:**
```
напиши стихотворение
```

**Ожидаемое поведение:**
- Skill не должен выбираться (низкая similarity)
- Или должен вернуть None если similarity < threshold

## 📊 Мониторинг и отладка

### Проверка логов backend

```bash
# В реальном времени
tail -f logs/*.log

# Или если логи в stdout
# (просто смотрите в терминал где запущен backend)
```

### Ключевые сообщения в логах

**При запуске:**
```
[UnifiedReActEngine] Smart tool selection enabled with 1 skills
```

**При обработке запроса:**
```
[SkillSelector] Selected skill 'slides-formatting' with similarity 0.85
[SmartToolSelector] Selected 3 tools for query: создай красивую презентацию
```

**В промпте (если включены debug логи):**
```
<skill_instructions>
АКТИВНЫЙ SKILL: slides-formatting
...
</skill_instructions>
```

### Проверка кэша embeddings

```bash
# Embeddings должны создаваться
ls -la data/tool_embeddings/

# Должны быть файлы:
# - create_presentation.json
# - create_slide.json
# - skill_slides-formatting.json
# - __query_*.json (для запросов пользователя)
```

### Проверка что feature flag работает

```bash
# Проверьте переменную окружения
echo $USE_SMART_TOOL_SELECTION
# Должно быть: true

# Или в логах при запуске:
# [UnifiedReActEngine] Smart tool selection enabled
```

## 🔍 Отладка проблем

### Проблема: Skill не выбирается

**Диагностика:**

```python
# Запустите в Python REPL
from src.core.skills.skill_loader import SkillLoader
from src.core.skills.skill_selector import SkillSelector
from pathlib import Path
import tempfile

loader = SkillLoader()
skills = loader.load_all_skills()
print(f"Skills загружены: {len(skills)}")

if skills:
    selector = SkillSelector(skills, cache_dir=Path(tempfile.mkdtemp()))
    
    # Проверяем similarity
    top_skills = selector.select_top_skills("создай презентацию", top_k=3)
    for skill, similarity in top_skills:
        print(f"{skill.name}: {similarity:.3f}")
    
    # Проверяем threshold
    selected = selector.select_skill("создай презентацию")
    print(f"Выбран skill: {selected.name if selected else None}")
```

**Возможные причины:**
- Низкая similarity (< threshold, по умолчанию 0.5)
- Embeddings не вычисляются (проблема с OpenAI API)
- Skill не загружен

### Проблема: Неправильные инструменты выбираются

**Диагностика:**

```python
from src.core.tool_selection.smart_selector import SmartToolSelector
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory

# Получаем все capabilities
registry = CapabilityRegistry()  # Нужна реальная инициализация
caps = registry.get_capabilities(categories=[CapabilityCategory.READ, CapabilityCategory.WRITE])

# Проверяем выбор
selector = SmartToolSelector(caps, cache_dir=Path("data/tool_embeddings"))
result = selector.select_tools("создай презентацию", max_tools=7)

for cap in result:
    print(f"{cap.name}: {cap.description[:50]}")
```

### Проблема: Backend не запускается

**Проверьте:**
1. Порт 8000 свободен: `lsof -i :8000`
2. Зависимости установлены: `pip install -r requirements.txt`
3. OPENAI_API_KEY установлен: `echo $OPENAI_API_KEY`
4. Логи ошибок в терминале

## 📝 Чеклист тестирования

### Базовое тестирование

- [ ] Backend запускается с `USE_SMART_TOOL_SELECTION=true`
- [ ] В логах есть сообщение "Smart tool selection enabled"
- [ ] Skills загружаются (проверьте количество в логах)
- [ ] Запрос "создай презентацию" выбирает slides-formatting skill
- [ ] Выбираются релевантные инструменты (create_presentation, create_slide)

### Расширенное тестирование

- [ ] Embeddings кэшируются (проверьте `data/tool_embeddings/`)
- [ ] Инструкции из skill включаются в промпт (проверьте логи)
- [ ] Fallback работает при ошибках (отключите OpenAI API key временно)
- [ ] Производительность приемлема (<200ms на выбор инструментов)

### Сравнительное тестирование

- [ ] Сравните результаты с флагом и без
- [ ] Проверьте что с флагом выбираются более релевантные инструменты
- [ ] Проверьте качество ответов (должны быть лучше с skill инструкциями)

## 🎯 Конкретные тест-кейсы

### Тест-кейс 1: Простая презентация

**Запрос:** "создай презентацию про ИИ"

**Ожидаемое:**
- Skill: slides-formatting
- Инструменты: create_presentation, create_slide, insert_slide_text
- В промпте: инструкции из slides-formatting SKILL.md

**Проверка:**
```bash
# В логах ищите:
grep "slides-formatting" logs/*.log
grep "create_presentation" logs/*.log
```

### Тест-кейс 2: Нерелевантный запрос

**Запрос:** "напиши стихотворение"

**Ожидаемое:**
- Skill: None (низкая similarity)
- Инструменты: общие или пусто
- Fallback на keyword-based если similarity низкая

### Тест-кейс 3: Сложный запрос

**Запрос:** "создай красивую презентацию на 5 слайдов про машинное обучение с графиками"

**Ожидаемое:**
- Skill: slides-formatting
- Инструменты: create_presentation, create_slide (4 раза), insert_slide_text, add_slide_image
- Инструкции из skill должны помочь правильно использовать инструменты

## 💡 Советы

1. **Начните с простого:** "создай презентацию" → проверьте что skill выбран
2. **Сравните результаты:** С флагом vs без флага
3. **Мониторьте логи:** Включите debug уровень для детальной информации
4. **Проверяйте кэш:** После первого запроса embeddings должны кэшироваться
5. **Тестируйте edge cases:** Пустые запросы, очень длинные запросы, нерелевантные

## 🚨 Частые проблемы

### Backend не видит флаг

```bash
# Убедитесь что флаг установлен ПЕРЕД запуском
export USE_SMART_TOOL_SELECTION=true
python3 -m uvicorn src.api.server:app --reload

# Или в config/.env
echo "USE_SMART_TOOL_SELECTION=true" >> config/.env
```

### Skills не загружаются

```bash
# Проверьте что skills/ директория существует
ls -la skills/

# Проверьте что SKILL.md есть
ls -la skills/slides-formatting/SKILL.md
```

### Embeddings не создаются

```bash
# Проверьте OpenAI API key
echo $OPENAI_API_KEY

# Проверьте что кэш директория создаётся
ls -la data/tool_embeddings/
```

## 📞 Следующие шаги

После успешного тестирования:

1. **Мониторинг в production:** Добавьте метрики для отслеживания
2. **Постепенный rollout:** Включите для небольшого % запросов
3. **Сбор feedback:** Сравните качество ответов с/без smart selection
4. **Оптимизация:** Настройте threshold, добавьте больше skills
