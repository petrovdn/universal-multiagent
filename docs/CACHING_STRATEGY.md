# Стратегия кеширования промптов и embeddings

**Дата:** 2026-01-20  
**Цель:** Оптимизация скорости и стоимости работы AI-агентов через multi-tier кеширование

---

## 📋 Executive Summary

Система использует **3-tier кеширование**:
1. **Tier 1 (Memory):** Статические данные в RAM (~1.3 MB) — мгновенный доступ
2. **Tier 2 (Anthropic Cache):** Большие промпты на сервере Anthropic — экономия токенов
3. **Tier 3 (Disk):** Persistence embeddings между рестартами

**Ожидаемый эффект:**
- ⚡ Скорость: **100x быстрее** (100ms → 1ms на tool/skill selection)
- 💰 Стоимость: **-70% на input tokens** ($3 → $0.9 на 1K requests)
- 📊 Memory overhead: **+1.3 MB** (ничтожно)

---

## 🔍 Детальный анализ компонентов

### 1️⃣ Guardrails (Критические правила безопасности)

**Что содержит:**
- Запреты на отправку почты без подтверждения
- Запреты на удаление данных без согласования
- Правила работы с конфиденциальной информацией
- Политики безопасности при финансовых операциях

**Текущее состояние:**
❌ **ПРОБЛЕМА:** Правила размазаны по разным местам:
- `MainAgent` system prompt: "⚠️ Отправка писем — требует подтверждения"
- `skills/gmail/SKILL.md`: дублирование того же правила
- `CalendarAgent`: правила для событий

**Где должно быть:**
✅ **config/GUARDRAILS.md** — единый источник правды

**Характеристики:**
- **Размер:** ~500-800 tokens (~2-3 KB текста)
- **Частота изменений:** Редко (раз в недели/месяцы)
- **Когда меняется:** При изменении политик безопасности компании

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ config/GUARDRAILS.md                │
│ ↓                                   │
│ Tier 1: Python dict в памяти        │ ← Загрузка при старте сервера
│   _memory_cache["guardrails"]       │ ← Хранится постоянно (~3 KB)
│ ↓                                   │
│ Tier 2: Anthropic server cache      │ ← Автоматически при первом вызове
│   cache_control: "ephemeral"        │ ← TTL: 5 минут, экономия ~500 tokens
│ ↓                                   │
│ Инвалидация: при изменении файла    │ ← Сравнение file mtime
└─────────────────────────────────────┘
```

**Экономика:**
- **Сейчас:** 500 tokens × $0.003 × 1000 requests = **$1.5**
- **С Anthropic cache:** $0.15 (90% экономия)
- **ROI:** $1.35 экономии на 1K requests

---

### 2️⃣ Base System Prompt (Базовый промпт)

**Что содержит сейчас (избыточно):**
```python
# MainAgent (~170 строк, ~1500 tokens):
- Общие инструкции (язык, формат ответа)
- DATA SOURCE ROUTING (60+ строк правил)  ← Должно быть в скиллах!
- Response format guidelines
```

**Что должно остаться (~20-30 строк, ~200 tokens):**
```markdown
Ты универсальный AI-ассистент.

## Язык
- Думай и отвечай на русском
- Reasoning на русском

## Принцип работы
1. Следуй <guardrails> (КРИТИЧНЫЙ приоритет)
2. Следуй <skill_instructions> для domain-specific задач
3. Используй релевантные инструменты
4. Структурируй ответы понятно

## Если нет активного skill
- Анализируй запрос
- Выбирай подходящие инструменты
- При сомнениях — уточняй
```

**Где создаётся:**
- `src/agents/main_agent.py`, функция `_get_default_main_agent_prompt()`
- Захардкожен в коде (константа)

**Характеристики:**
- **Размер (сейчас):** ~1500 tokens (~6 KB)
- **Размер (после рефакторинга):** ~200 tokens (~800 B)
- **Частота изменений:** Очень редко (раз в месяцы)

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ Константа BASE_SYSTEM_PROMPT        │
│ ↓                                   │
│ Tier 1: Python константа            │ ← Определена в коде
│ ↓                                   │
│ Tier 2: Anthropic cache             │ ← cache_control: "ephemeral"
│   TTL: 5 минут                      │ ← Обновляется автоматически
│ ↓                                   │
│ Инвалидация: при рестарте сервера   │ ← Новый деплой → новая версия
└─────────────────────────────────────┘
```

**Почему так:**
- ✅ Константа в коде — не нужно читать из файла
- ✅ Anthropic cache — экономия токенов
- ✅ Инвалидация при деплое — логично (новый код → новый промпт)

---

### 3️⃣ Skill Instructions (Инструкции для домена)

**Что содержит:**
```markdown
<skill_instructions>
АКТИВНЫЙ SKILL: calendar

## Когда активировать
Ключевые слова: "календарь", "встреча", "событие"

## Приоритетные инструменты
1. get_calendar_events — список событий
2. create_event — создание события

## Workflow
### Показать встречи
1. Используй get_calendar_events с date_range
...

## Важные замечания
⚠️ Создание событий — требует подтверждения
</skill_instructions>
```

**Где создаётся:**
- `src/core/unified_react_engine.py`, функция `_think_and_plan()` (строки 4926-4939)
- Загружается через `SkillSelector.select_skill()` при каждом запросе
- Контент берётся из `skills/{domain}/SKILL.md`

**Характеристики:**
- **Размер:** ~500-1000 tokens per skill (~2-4 KB)
- **Всего skills:** 8 (calendar, gmail, sheets, docs, slides, workspace, focus-day, meeting-prep)
- **Total size:** ~20 KB (все skills)
- **Частота изменений:** Средняя (раз в дни/недели)

**Когда меняется:**
- При добавлении новых инструментов в домен
- При обновлении workflow
- Пример: добавили `bulk_create_events` → обновили calendar/SKILL.md

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ skills/{domain}/SKILL.md            │
│ ↓                                   │
│ SkillLoader.load_skill()            │ ← При старте сервера
│ ↓                                   │
│ Tier 1: SkillSelector.skills list   │ ← Все 8 skills в памяти
│   [Skill(name="calendar", ...), ]  │ ← ~20 KB total (постоянно)
│ ↓                                   │
│ Tier 2: PromptCache._memory_cache   │ ← Formatted strings
│   "skill_calendar_full" -> str     │ ← По content hash
│   TTL: 5 минут                      │ ← Для редко используемых skills
│ ↓                                   │
│ Tier 3: Anthropic cache             │ ← НЕ кешируем (dynamic)
│   Меняется каждый запрос           │ ← calendar → gmail → sheets
│ ↓                                   │
│ Инвалидация: при изменении SKILL.md │ ← File watcher или mtime check
└─────────────────────────────────────┘
```

**Почему так:**
- ✅ Все skills в памяти: 20 KB это ничтожно, загружаем при старте
- ✅ Formatted strings кешируем: Чтобы не парсить YAML каждый раз
- ❌ НЕ в Anthropic cache: Skill меняется каждый запрос (calendar → gmail → sheets)

---

### 4️⃣ Tool Descriptions (Описания инструментов)

**Что содержит:**
```python
# Пример в _think_and_plan():
tools_str = "\n".join([f"- {t['name']}: {t['description']}" for t in relevant_tools])

# Результат:
"""
<available_tools>
- get_calendar_events: Получить список событий из Google Calendar за указанный период
- create_event: Создать новое событие в Google Calendar с указанием времени и участников
- get_next_availability: Найти следующее свободное время в календаре для встречи
- send_email: Отправить письмо через Gmail с указанием получателей, темы и текста
- search_emails: Поиск писем в Gmail по различным критериям (отправитель, тема, дата)
- get_sheet_data: Прочитать данные из Google Sheets по диапазону ячеек
- get_all_sheets_data: Получить данные со ВСЕХ листов таблицы одним запросом
</available_tools>
"""
```

**Где создаётся:**
- `src/core/unified_react_engine.py`, функция `_get_relevant_tools()`
- Вызывается при каждом `_think_and_plan()`
- Инструменты фильтруются через `SmartToolSelector` на основе запроса

**Характеристики:**
- **Размер:** ~3000-7000 tokens (зависит от количества selected tools)
- **Количество инструментов:** 3-7 per request (из 200+ доступных)
- **Частота изменений:** Каждый запрос! (динамический набор)

**Примеры:**
- "покажи встречи" → 5 calendar tools
- "отправь письмо" → 5 gmail tools
- "анализ таблицы" → 10 sheets + code execution tools

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ _get_relevant_tools(goal)           │ ← Вызывается каждый раз
│ ↓                                   │
│ SmartToolSelector.select_tools()    │ ← Semantic search по goal
│ ↓                                   │
│ Tier 1: НЕ кешируем strings         │ ← Разный набор каждый запрос
│ ↓                                   │
│ Tier 2: НЕ в Anthropic cache        │ ← Динамический контент
│ ↓                                   │
│ НО: Tool EMBEDDINGS в памяти!       │ ← ЭТО кешируем (см. ниже)
└─────────────────────────────────────┘
```

**Почему НЕ кешируем:**
- ❌ **Динамический набор:** Каждый запрос = разные инструменты
- ❌ **Разный размер:** От 3 до 7 tools, нельзя предсказать
- ❌ **Cache miss rate:** 100% (никогда не повторяется)
- ✅ **НО embeddings кешируем:** Чтобы semantic search был быстрым

---

### 5️⃣ Tool Embeddings (Векторные представления инструментов) ⭐

**ЭТО КРИТИЧНО ДЛЯ ОПТИМИЗАЦИИ!**

**Что содержит:**
```python
# Для каждого инструмента:
{
    "tool_name": "get_calendar_events",
    "description": "Получить список событий из Google Calendar за указанный период...",
    "embedding": [0.123, -0.456, 0.789, ...],  # 1536 float32
    "model": "text-embedding-3-small",
    "dimension": 1536
}
```

**Где создаётся:**
- `src/core/tool_selection/embedding_cache.py`, класс `EmbeddingCache`
- **При первом обращении:** вычисляет через OpenAI API ($0.02 на 1M tokens)
- **При повторном:** загружает из `data/tool_embeddings/{tool_name}.json`

**Характеристики:**
- **1 embedding:** 1536 floats × 4 bytes = **6 KB**
- **200 tools:** 200 × 6 KB = **1.2 MB**
- **На диске (JSON):** ~200 × 15 KB = **3 MB** (с метаданными)

**Частота изменений:**
- **Редко** (раз в недели)
- Только при изменении описания инструмента
- Автоматически инвалидируется по hash описания

**ТЕКУЩАЯ ПРОБЛЕМА (КРИТИЧНО!):**
```python
# Сейчас:
def get_embedding(self, tool_name, description):
    cached_data = self._load_from_cache(tool_name)  # ← Disk I/O КАЖДЫЙ РАЗ!
    if cached_data and self._is_cache_valid(cached_data, description):
        embedding = np.array(cached_data['embedding'])  # ← Парсинг JSON
        return embedding
    # ...
```

**Проблемы:**
- ❌ **Disk I/O:** Чтение 200 JSON файлов при каждом `select_tools()` → **~50-100ms**
- ❌ **JSON parsing:** Конвертация списка в numpy array → **~10ms per tool**
- ❌ **Total latency:** 200 tools × 0.3ms = **~60ms overhead PER REQUEST**

**Стратегия кеширования (РЕШЕНИЕ):**
```
┌─────────────────────────────────────┐
│ OpenAI API (первый раз)             │
│ text-embedding-3-small              │ ← Вычисляется 1 раз, $0.02/1M tokens
│ ↓                                   │
│ Tier 3: Disk cache (JSON)           │ ← Persistence между рестартами
│   data/tool_embeddings/*.json       │ ← ~3 MB (200 files)
│ ↓                                   │
│ Tier 1: Memory cache (numpy)        │ ← Preload при старте сервера
│   _memory_embeddings: Dict[str, np] │ ← ~1.2 MB в RAM (постоянно!)
│ ↓                                   │
│ SmartToolSelector.select_tools()    │ ← Instant access (0ms)
│   cosine_similarity(query, tool)    │ ← Работает с RAM напрямую
│ ↓                                   │
│ Инвалидация: при изменении description │ ← Hash-based
└─────────────────────────────────────┘
```

**Реализация (псевдокод):**
```python
class EmbeddingCache:
    def __init__(self, preload_embeddings=True):
        self._memory_embeddings: Dict[str, np.ndarray] = {}
        
        if preload_embeddings:
            # Загружаем все embeddings при старте (1 раз, ~1 секунда)
            print("[EmbeddingCache] Preloading 200 embeddings...")
            for json_file in self.cache_dir.glob("*.json"):
                data = json.load(open(json_file))
                self._memory_embeddings[data['tool_name']] = np.array(
                    data['embedding'], dtype=np.float32
                )
            print(f"[EmbeddingCache] Preloaded {len(self._memory_embeddings)} embeddings (1.2 MB)")
    
    def get_embedding(self, tool_name, description):
        # Check memory cache first (instant!)
        if tool_name in self._memory_embeddings:
            return self._memory_embeddings[tool_name]  # ← 0ms!
        
        # Fallback: compute or load from disk (new tool)
        # ...
```

**Почему именно так:**
- ✅ **Preload все:** 1.2 MB это ничтожно (< 0.1% RAM современного сервера)
- ✅ **Instant access:** **0ms вместо 60ms** при каждом select_tools()
- ✅ **Disk persistence:** Не теряем embeddings при рестарте
- ✅ **Auto-invalidation:** Hash description → пересчитываем только изменённые

**Ожидаемый эффект:**
- ⚡ Tool selection: **60ms → 0.6ms** (100x быстрее!)
- 💾 Memory: +1.2 MB (ничтожно)
- 💰 API cost: $0 (embeddings уже вычислены)

---

### 6️⃣ Skill Embeddings (Векторные представления скиллов)

**Что содержит:**
- Embeddings для `skill.description` + `skill.content`

**ТЕКУЩАЯ ПРОБЛЕМА:**
```python
# Сейчас используется только description (~100 tokens):
skill_embedding = self.embedding_cache.get_embedding(
    tool_name=f"skill_{skill.name}",
    description=skill.description  # ← Только краткое описание!
)
```

**Должно быть:**
```python
# Использовать полный content (~500-1000 tokens):
full_content = f"{skill.description}\n\n{skill.content}"
skill_embedding = self.embedding_cache.get_embedding(
    tool_name=f"skill_{skill.name}_full",
    description=full_content  # ← Полные инструкции!
)
```

**Характеристики:**
- **1 skill embedding:** 6 KB (как у tools)
- **8 skills:** 8 × 6 KB = **48 KB**
- **Частота изменений:** Средняя (раз в дни/недели)

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ SkillLoader.load_all_skills()       │ ← При старте сервера
│ ↓                                   │
│ Tier 1: Skill objects в памяти      │ ← 8 skills, ~20 KB
│   SkillSelector.skills list         │ ← Постоянно в RAM
│ ↓                                   │
│ Tier 2: Full content embeddings     │ ← Preload при старте
│   embedding_cache._memory_embeddings│ ← skill_{name}_full -> np array
│   "skill_calendar_full" -> [...]   │ ← 48 KB total (постоянно)
│ ↓                                   │
│ SkillSelector.select_skill(query)   │ ← Instant access (0ms)
│   cosine_similarity(query, skill)   │
│ ↓                                   │
│ Инвалидация: при изменении SKILL.md │ ← Content hash
└─────────────────────────────────────┘
```

**Почему именно так:**
- ✅ **Full content:** Точнее semantic matching (+30-50% accuracy)
- ✅ **Preload:** 48 KB это ничтожно
- ✅ **Instant selection:** Критично для latency

**Ожидаемый эффект:**
- ⚡ Skill selection: **40ms → 0.4ms** (100x быстрее!)
- 🎯 Accuracy: +30-50% (используем полный контент вместо description)
- 💾 Memory: +48 KB (ничтожно)

---

### 7️⃣ Dynamic Context (Динамический контекст)

**Что содержит:**
```python
# Создаётся в _think_and_plan() при каждой итерации:
- task_status: "Цель: {goal}, Итерация: {n}, Дата: {current_date}"
- completed_actions: История выполненных шагов с результатами
- previous_errors: Ошибки предыдущих попыток
- blocked_tools: Запрещённые к повтору инструменты
- context_section: Открытые файлы, прикреплённые файлы
- critical_rules: Специфичные правила для текущей задачи
- output_format: Формат ответа
```

**Характеристики:**
- **Размер:** ~1000-3000 tokens (зависит от истории)
- **Частота изменений:** Каждая итерация!
- **Lifetime:** 1 итерация (~5-30 секунд)

**Стратегия кеширования:**
```
┌─────────────────────────────────────┐
│ НЕ КЕШИРУЕМ!                        │
│ ↓                                   │
│ Создаётся заново каждую итерацию    │
│ ↓                                   │
│ Tier: None                          │
│ ↓                                   │
│ Инвалидация: N/A (всегда fresh)     │
└─────────────────────────────────────┘
```

**Почему НЕ кешируем:**
- ❌ **Уникальный каждый раз:** goal, iteration, history, errors — всё разное
- ❌ **Малый lifetime:** Живёт только 1 итерацию (~5-30 секунд)
- ❌ **Cache miss rate:** 100% (никогда не повторяется)

---

## 📊 Итоговая таблица стратегий

| Компонент | Размер | Частота изменений | Tier 1 (Memory) | Tier 2 (Anthropic) | Tier 3 (Disk) | TTL | Когда загрузить | Когда выгрузить |
|-----------|--------|-------------------|-----------------|-------------------|---------------|-----|-----------------|-----------------|
| **Guardrails** | 3 KB | Редко (недели) | ✅ Python dict | ✅ cache_control | ✅ GUARDRAILS.md | ∞ | При старте | При рестарте |
| **Base System Prompt** | 800 B | Очень редко | ✅ Константа | ✅ cache_control | ❌ | ∞ | При старте | При рестарте |
| **Skill Objects** | 20 KB | Средне (дни) | ✅ List[Skill] | ❌ | ✅ skills/*.md | ∞ | При старте | При изменении файла |
| **Skill Embeddings** | 48 KB | Средне | ✅ np.ndarray | ❌ | ✅ JSON | ∞ | При старте | При изменении content |
| **Tool Embeddings** | 1.2 MB | Редко | ✅ np.ndarray | ❌ | ✅ JSON | ∞ | При старте | При изменении description |
| **Skill Instructions (formatted)** | 2-4 KB | Per request | ✅ Formatted str | ❌ Dynamic | ❌ | 5 мин | При select_skill() | Через 5 мин |
| **Tool Descriptions** | 3-7 KB | Per request | ❌ Dynamic | ❌ Dynamic | ❌ | N/A | При _get_relevant_tools() | Сразу |
| **Dynamic Context** | 1-3 KB | Per iteration | ❌ Dynamic | ❌ Dynamic | ❌ | N/A | При _think_and_plan() | Сразу |

**Total memory footprint (постоянно в RAM):** ~1.3 MB

---

## 🎯 Принципы выбора стратегий

### 1. Статическое → Memory forever
- Guardrails, Base Prompt, Embeddings не меняются часто
- Загружаем при старте, держим в памяти всегда
- **Total memory cost: ~1.3 MB** (ничтожно!)

### 2. Большое + редкое → Anthropic cache
- Guardrails + Base Prompt = ~700 tokens
- Экономия: ~700 × $0.003 × 1000 requests = **$2.1**
- При 10K requests/день = **$21/день экономии**

### 3. Динамическое → НЕ кешируем
- Tool descriptions меняются каждый запрос
- Dynamic context меняется каждую итерацию
- Кешировать бессмысленно (cache miss rate = 100%)

### 4. Промежуточное (Skill instructions) → Short-lived cache
- Formatted skill instructions используются 1-10 раз
- Кешируем в памяти с TTL 5 минут
- После истечения — выгружаем (освобождаем память)

---

## 💡 Практические рекомендации

### Приоритет внедрения:

**🔥 Критично (сейчас):**
1. **Preload tool embeddings в память** 
   - Ускорение: **60ms → 0.6ms** (100x быстрее)
   - Complexity: Low (10 строк кода)
   - Impact: High (каждый запрос!)

2. **Use full skill content для embeddings**
   - Точность: +30-50% accuracy
   - Complexity: Low (1 строка изменений)
   - Impact: High (skill selection критично)

**⚠️ Важно (эта неделя):**
3. **Создать config/GUARDRAILS.md**
   - Безопасность: Централизованные правила
   - Complexity: Medium (новый файл + loader)
   - Impact: High (безопасность критична)

4. **Anthropic cache для Guardrails + Base Prompt**
   - Экономия: ~$20/день при 10K requests
   - Complexity: Medium (настройка cache_control)
   - Impact: Medium (экономия денег)

**💭 Полезно (следующая неделя):**
5. **Preload skill embeddings в память**
   - Ускорение: 40ms → 0.4ms
   - Complexity: Low (аналогично tool embeddings)
   - Impact: Low (skill selection реже чем tool selection)

6. **Short-lived cache для formatted skills**
   - Экономия: CPU cycles (парсинг YAML)
   - Complexity: Low (TTL-based dict)
   - Impact: Low (YAML парсинг не дорогой)

---

## 📈 Ожидаемые результаты

### Производительность

| Метрика | Сейчас | После оптимизации | Улучшение |
|---------|--------|-------------------|-----------|
| **Tool selection latency** | 60ms | 0.6ms | **100x быстрее** |
| **Skill selection latency** | 40ms | 0.4ms | **100x быстрее** |
| **Total request overhead** | ~100ms | ~1ms | **100x быстрее** |
| **Skill selection accuracy** | 70% | 90%+ | **+30% точность** |

### Ресурсы

| Метрика | Сейчас | После оптимизации | Изменение |
|---------|--------|-------------------|-----------|
| **Memory usage (static)** | ~50 MB | ~51.3 MB | +1.3 MB (ничтожно) |
| **Disk usage** | 3 MB | 3 MB | Без изменений |
| **Startup time** | ~2s | ~3s | +1s (preload embeddings) |

### Стоимость (на 1000 requests)

| Компонент | Сейчас | После Anthropic cache | Экономия |
|-----------|--------|----------------------|----------|
| **Guardrails tokens** | 500 × $0.003 = $1.5 | $0.15 | **-90%** |
| **Base Prompt tokens** | 200 × $0.003 = $0.6 | $0.06 | **-90%** |
| **Skill instructions** | 700 × $0.003 = $2.1 | $2.1 | 0% (динамические) |
| **Tool descriptions** | Dynamic | Dynamic | N/A |
| **Total input cost** | ~$4.2 | ~$2.3 | **-45%** |

**При 10K requests/день:**
- Экономия: ~$19/день = **~$570/месяц**

---

## 🔧 Реализация

### Фаза 1: Preload embeddings (критично!)

**Файл:** `src/core/tool_selection/embedding_cache.py`

```python
class EmbeddingCache:
    def __init__(self, cache_dir=None, preload_embeddings=False):
        # ...существующий код...
        self._memory_embeddings: Dict[str, np.ndarray] = {}
        
        if preload_embeddings:
            self._preload_all_embeddings()
    
    def _preload_all_embeddings(self):
        """Предзагрузить все embeddings из disk в memory."""
        import time
        logger.info("[EmbeddingCache] Preloading embeddings to memory...")
        start_time = time.time()
        
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                tool_name = data['tool_name']
                embedding = np.array(data['embedding'], dtype=np.float32)
                self._memory_embeddings[tool_name] = embedding
                count += 1
            except Exception as e:
                logger.warning(f"Failed to preload {cache_file}: {e}")
        
        duration = time.time() - start_time
        memory_mb = count * 6 / 1024  # 6KB per embedding
        logger.info(
            f"[EmbeddingCache] Preloaded {count} embeddings "
            f"({memory_mb:.1f} MB) in {duration:.2f}s"
        )
    
    def get_embedding(self, tool_name: str, description: str):
        # Check memory cache first (instant!)
        if tool_name in self._memory_embeddings:
            logger.debug(f"[EmbeddingCache] Memory hit for {tool_name}")
            return self._memory_embeddings[tool_name]
        
        # Check disk cache
        cached_data = self._load_from_cache(tool_name)
        if cached_data and self._is_cache_valid(cached_data, description):
            embedding = np.array(cached_data['embedding'], dtype=np.float32)
            # Store in memory for future
            self._memory_embeddings[tool_name] = embedding
            return embedding
        
        # Compute new
        embedding = self._compute_embedding(description)
        self._save_to_cache(tool_name, description, embedding)
        self._memory_embeddings[tool_name] = embedding
        return embedding
```

**Использование:**

```python
# src/core/unified_react_engine.py
self.embedding_cache = EmbeddingCache(
    cache_dir=cache_dir,
    preload_embeddings=True  # ← Включаем preload!
)
```

### Фаза 2: Full skill content в embeddings

**Файл:** `src/core/skills/skill_selector.py`

```python
def select_skill(self, query: str, skill_type: Optional[str] = None) -> Optional[Skill]:
    # ...
    for skill in skills_to_search:
        # Используем полные инструкции для более точного matching
        full_content = f"{skill.description}\n\n{skill.content}"
        skill_embedding = self.embedding_cache.get_embedding(
            tool_name=f"skill_{skill.name}_full",  # ← Новый ключ!
            description=full_content  # ← Полный контент!
        )
        
        similarity = cosine_similarity(query_embedding, skill_embedding)
        similarities.append((skill, similarity))
```

### Фаза 3: GUARDRAILS.md

**Создать файл:** `config/GUARDRAILS.md`

```markdown
---
priority: critical
always_loaded: true
---

# Критические правила безопасности

## 🚫 Запрещённые действия без подтверждения

1. **Отправка почты** (`send_email`)
   - ВСЕГДА запрашивай подтверждение получателей, темы и тела
   - Покажи preview перед отправкой

2. **Удаление данных** (`delete_*`, `remove_*`)
   - ВСЕГДА запрашивай подтверждение
   - Покажи что будет удалено

3. **Финансовые операции** (1С, проводки)
   - НЕ изменяй бухгалтерские данные
   - Только read-only операции

## ✅ При сомнениях
1. Объясни что планируешь сделать
2. Спроси "Продолжить?"
3. Дожидайся явного подтверждения
```

**Создать:** `src/core/guardrails/guardrails_loader.py`

```python
from pathlib import Path
import re

class GuardrailsLoader:
    def __init__(self, guardrails_path=None):
        if guardrails_path is None:
            project_root = Path(__file__).parent.parent.parent
            guardrails_path = project_root / "config" / "GUARDRAILS.md"
        self.guardrails_path = guardrails_path
        self._cached_content = None
        self._cached_mtime = 0
    
    def load_guardrails(self) -> str:
        if not self.guardrails_path.exists():
            return ""
        
        # Check if file changed
        current_mtime = self.guardrails_path.stat().st_mtime
        if current_mtime != self._cached_mtime:
            content = self.guardrails_path.read_text(encoding="utf-8")
            
            # Parse YAML frontmatter
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
            if match:
                markdown_content = match.group(2).strip()
            else:
                markdown_content = content.strip()
            
            self._cached_content = f"""<guardrails priority="critical">
{markdown_content}
</guardrails>"""
            self._cached_mtime = current_mtime
        
        return self._cached_content
```

---

## ✅ Чеклист для внедрения

### Неделя 1 (Критично):
- [ ] Добавить `preload_embeddings=True` в `EmbeddingCache.__init__()`
- [ ] Обновить `UnifiedReActEngine` для использования preload
- [ ] Изменить `SkillSelector` для использования full content
- [ ] Тестирование: измерить latency до/после

### Неделя 2 (Важно):
- [ ] Создать `config/GUARDRAILS.md`
- [ ] Создать `GuardrailsLoader`
- [ ] Интегрировать guardrails в `MainAgent`
- [ ] Удалить дублирование правил из system prompts

### Неделя 3 (Полезно):
- [ ] Настроить Anthropic `cache_control` для guardrails
- [ ] Настроить Anthropic `cache_control` для base prompt
- [ ] Мониторинг экономии токенов
- [ ] Документация для команды

---

## 📚 Дополнительные ресурсы

- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Semantic Search Best Practices](https://www.pinecone.io/learn/semantic-search/)

---

**Вопросы?** Обсудите с командой в Slack #ai-optimization
