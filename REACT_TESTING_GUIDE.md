# Руководство по тестированию ReAct Orchestrator

## Способы переключения режимов

### 1. Через Frontend UI

1. Откройте приложение в браузере
2. В правом верхнем углу найдите выпадающий список режимов выполнения
3. Выберите один из режимов:
   - **Агент** (`instant`) - прямое выполнение без планирования
   - **План** (`approval`) - планирование с подтверждением
   - **ReAct** (`react`) - адаптивный ReAct режим ⭐ НОВЫЙ

### 2. Через API запрос

#### Создание сессии с ReAct режимом:

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "execution_mode": "react",
    "model_name": "claude-sonnet-4-5"
  }'
```

#### Отправка сообщения с ReAct режимом:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Создай таблицу с тестовыми данными",
    "session_id": "your-session-id",
    "execution_mode": "react"
  }'
```

### 3. Через Python скрипт

Используйте готовый тестовый скрипт:

```bash
python test_react_orchestrator.py
```

Или создайте свой:

```python
import asyncio
from src.api.session_manager import get_session_manager
from src.api.websocket_manager import get_websocket_manager
from src.core.react_orchestrator import ReActOrchestrator

async def test():
    session_manager = get_session_manager()
    ws_manager = get_websocket_manager()
    
    # Создать сессию с ReAct режимом
    session_id = session_manager.create_session(execution_mode="react")
    context = session_manager.get_session(session_id)
    
    # Создать orchestrator
    orchestrator = ReActOrchestrator(
        ws_manager=ws_manager,
        session_id=session_id
    )
    
    # Выполнить задачу
    result = await orchestrator.execute(
        user_request="Ваша задача здесь",
        context=context,
        file_ids=[]
    )
    
    print(f"Результат: {result}")

asyncio.run(test())
```

## Тестирование

### Тест 1: Простая задача

**Задача:** "Создай таблицу с названием 'Тест' и добавь одну строку"

**Ожидаемое поведение:**
1. ReAct цикл начнется
2. Агент проанализирует задачу (THINK)
3. Выберет инструмент `create_spreadsheet` (PLAN)
4. Выполнит создание таблицы (ACT)
5. Проанализирует результат (OBSERVE)
6. Если успешно - завершит, если ошибка - попробует альтернативу (ADAPT)

**Проверка:**
- В логах должны быть события: `react_start`, `react_thinking`, `react_action`, `react_observation`
- Если успешно: `react_complete`
- Если ошибка: `react_failed` с описанием проблемы

### Тест 2: Задача с ошибкой (для проверки адаптации)

**Задача:** "Найди файл с названием 'НесуществующийФайл.xlsx' и открой его"

**Ожидаемое поведение:**
1. Агент попытается найти файл
2. Получит ошибку "файл не найден"
3. Проанализирует ошибку
4. Попробует альтернативный подход (например, спросить у пользователя или создать файл)
5. Если альтернатив нет - вернет graceful failure с отчетом

**Проверка:**
- Должно быть событие `react_adapting` с описанием альтернативы
- В reasoning trail должны быть шаги адаптации

### Тест 3: Сложная многошаговая задача

**Задача:** "Создай таблицу, добавь в неё данные, затем отправь письмо с ссылкой на таблицу"

**Ожидаемое поведение:**
1. Агент разобьет задачу на шаги
2. Выполнит каждый шаг с анализом результата
3. Адаптирует стратегию если что-то не работает
4. Завершит все шаги или вернет отчет о проблемах

**Проверка:**
- Должно быть несколько итераций ReAct цикла
- Reasoning trail должен показывать прогресс
- Финальный результат должен содержать все выполненные действия

## Мониторинг выполнения

### WebSocket события

Подключитесь к WebSocket и слушайте события:

```javascript
// В браузере (консоль)
const ws = new WebSocket('ws://localhost:8000/ws/{session_id}');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type.startsWith('react_')) {
    console.log('ReAct событие:', data);
  }
};
```

### События для отслеживания:

- `react_start` - начало выполнения
- `react_thinking` - агент думает (содержит `thought` и `iteration`)
- `react_action` - выбрано действие (содержит `action`, `tool`, `params`)
- `react_observation` - результат действия (содержит `result`)
- `react_adapting` - адаптация стратегии (содержит `reason`, `new_strategy`)
- `react_complete` - успешное завершение (содержит `result`, `trail`)
- `react_failed` - неудача (содержит `reason`, `tried`)

### Логи

Проверьте логи приложения:

```bash
tail -f logs/app.log | grep ReActOrchestrator
```

Или в коде:

```python
from src.utils.logging_config import get_logger
logger = get_logger(__name__)
logger.info("Проверка логов")
```

## Отличия от StepOrchestrator

| Характеристика | StepOrchestrator | ReActOrchestrator |
|----------------|------------------|-------------------|
| Планирование | Создает план заранее | Планирует на каждом шаге |
| Выполнение | Линейное, по плану | Адаптивное, с анализом |
| Обработка ошибок | Останавливается или продолжает | Пробует альтернативы |
| Reasoning | Минимальный | Полный trail мышления |
| Адаптация | Нет | Да, на каждом шаге |

## Типичные проблемы и решения

### Проблема: ReAct режим не активируется

**Решение:**
1. Проверьте, что `context.execution_mode == "react"`
2. Убедитесь, что задача классифицирована как "complex" (не "simple")
3. Проверьте логи на наличие ошибок инициализации

### Проблема: Слишком много итераций

**Решение:**
- По умолчанию максимум 10 итераций
- Можно изменить в `ReActState.max_iterations`
- Проверьте, не зацикливается ли агент

### Проблема: Не видно reasoning trail

**Решение:**
- Проверьте WebSocket подключение
- Убедитесь, что фронтенд обрабатывает события `react_*`
- Проверьте логи на наличие событий

## Дополнительные настройки

### Изменение максимального количества итераций

В `src/core/react_orchestrator.py`:

```python
state = ReActState(goal=user_request)
state.max_iterations = 15  # Изменить лимит
```

### Настройка анализа результатов

В `src/core/result_analyzer.py` можно настроить:
- Пороги для quick analysis
- Промпты для LLM анализа
- Критерии успеха/неудачи

## Примеры использования

См. файл `test_react_orchestrator.py` для готовых примеров тестирования.

