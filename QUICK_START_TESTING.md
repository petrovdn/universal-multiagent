# Быстрый старт тестирования Smart Tool Selection

## 🚀 Два способа запуска backend

### 1. С Smart Tool Selection (RAG + Skills)

```bash
./restart-backend-smart-selection.sh
```

**Что делает:**
- ✅ Останавливает существующий backend
- ✅ Устанавливает `USE_SMART_TOOL_SELECTION=true`
- ✅ Проверяет skills
- ✅ Запускает backend с smart selection

**Используется:**
- Semantic search для выбора инструментов
- Skills для специализированных workflow
- Embeddings для релевантности

### 2. Без Smart Tool Selection (Keyword-based)

```bash
./restart-backend-keyword.sh
```

**Что делает:**
- ✅ Останавливает существующий backend
- ✅ Убирает `USE_SMART_TOOL_SELECTION` (если был)
- ✅ Запускает backend в legacy режиме

**Используется:**
- Keyword matching для выбора инструментов
- Старая логика из `_get_relevant_tools`

## 🧪 Тестирование

### Через WebSocket скрипт

```bash
# В другом терминале
python3 scripts/test-via-websocket.py "создай красивую презентацию"
```

### Через UI

1. Запустите backend (один из скриптов выше)
2. Запустите фронтенд:
   ```bash
   cd frontend && npm run dev
   ```
3. Отправьте запрос: "создай красивую презентацию про ИИ"

## 📊 Сравнение результатов

### С Smart Tool Selection

**Запрос:** "создай красивую презентацию"

**В логах:**
```
[UnifiedReActEngine] Smart tool selection enabled with 1 skills
[SkillSelector] Selected skill 'slides-formatting' with similarity 0.85
[SmartToolSelector] Selected 3 tools for query: создай красивую презентацию
```

**Выбранные инструменты:**
- create_presentation
- create_slide
- insert_slide_text

**В промпте:** Инструкции из slides-formatting SKILL.md

### Без Smart Tool Selection (Keyword-based)

**Запрос:** "создай красивую презентацию"

**В логах:**
```
[UnifiedReActEngine] Initialized for session ...
```

**Выбранные инструменты:**
- Зависит от keyword matching в `_get_relevant_tools`
- Может быть больше инструментов (до 7)

**В промпте:** Нет skill инструкций

## 🔍 Что проверять

### 1. Логи при запуске

**С флагом:**
```
[UnifiedReActEngine] Smart tool selection enabled with 1 skills
```

**Без флага:**
```
[UnifiedReActEngine] Initialized for session ...
(нет сообщения о smart selection)
```

### 2. Логи при обработке запроса

**С флагом:**
```
[SkillSelector] Selected skill 'slides-formatting' with similarity 0.XX
[SmartToolSelector] Selected X tools for query: ...
```

**Без флага:**
```
(нет сообщений о skill selector)
```

### 3. Кэш embeddings

**С флагом:**
```bash
ls -la data/tool_embeddings/
# Должны быть файлы: create_presentation.json, skill_slides-formatting.json
```

**Без флага:**
```bash
ls -la data/tool_embeddings/
# Директория может не создаваться или быть пустой
```

## 💡 Советы

1. **Начните с keyword-based:** Проверьте что всё работает как раньше
2. **Переключитесь на smart selection:** Сравните результаты
3. **Проверьте логи:** Убедитесь что skill выбирается
4. **Сравните качество:** Ответы должны быть лучше с skill инструкциями

## 🐛 Отладка

### Backend не запускается

```bash
# Проверьте порт
lsof -i :8000

# Принудительно освободите
lsof -ti:8000 | xargs kill -9
```

### Флаг не работает

```bash
# Проверьте что флаг установлен
echo $USE_SMART_TOOL_SELECTION

# В логах должно быть:
# [UnifiedReActEngine] Smart tool selection enabled
```

### Skills не загружаются

```bash
# Проверьте директорию
ls -la skills/

# Проверьте вручную
python3 -c "from src.core.skills.skill_loader import SkillLoader; print(len(SkillLoader().load_all_skills()))"
```
