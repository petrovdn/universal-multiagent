# Руководство по тестированию Python Code Execution Tool

## Пошаговая инструкция

### Шаг 1: Базовое тестирование инструмента

Запустите ручной тестовый скрипт, который проверит основную функциональность:

```bash
python3 test_code_execution_manual.py
```

Этот скрипт выполнит 8 тестов:
1. ✅ Простое выполнение кода
2. ✅ Выполнение с входными данными
3. ✅ Использование библиотеки math
4. ✅ Реалистичный сценарий конвертации валют
5. ✅ Операции со списками (формат таблицы)
6. ✅ Обработка timeout
7. ✅ Регистрация инструмента
8. ✅ Интеграция с SheetsAgent

**Ожидаемый результат**: Все тесты должны пройти успешно.

---

### Шаг 2: Тестирование через pytest (опционально)

Если у вас установлен pytest, можно запустить формальные unit-тесты:

```bash
# Установите pytest если его нет
pip install pytest pytest-asyncio

# Запустите тесты
pytest test_code_execution.py -v
```

---

### Шаг 3: Проверка интеграции с SheetsAgent

Убедитесь, что инструмент правильно загружается в SheetsAgent:

```bash
python3 -c "
from src.agents.sheets_agent import SheetsAgent
agent = SheetsAgent()
tools = agent.get_tools()
tool_names = [t.name for t in tools]
print(f'Total tools: {len(tools)}')
print(f'Tool names: {tool_names}')
assert 'execute_python_code' in tool_names, 'execute_python_code tool not found!'
print('✅ execute_python_code tool is available in SheetsAgent')
"
```

**Ожидаемый результат**: Должно вывести список инструментов, включая `execute_python_code`.

---

### Шаг 4: Тестирование через API (интеграционный тест)

Для полного тестирования нужно запустить сервер и протестировать через API:

#### 4.1. Запустите сервер

```bash
# Убедитесь, что зависимости установлены
pip install -r requirements.txt -r requirements-core.txt -r requirements-ai.txt

# Запустите сервер (если есть скрипт запуска)
python3 src/api/server.py
# или используйте ваш обычный способ запуска сервера
```

#### 4.2. Создайте тестовый запрос

Используйте ваше API или WebSocket для отправки запроса к SheetsAgent. Пример запроса:

```json
{
  "message": "У меня есть таблица [SPREADSHEET_ID] с ценами в долларах в колонке A (строки 2-4). Преобразуй их в рубли по курсу 95, добавь НДС 20%, округли до 2 знаков и запиши в колонку B",
  "agent": "SheetsAgent"
}
```

**Ожидаемое поведение**:
1. AI должен прочитать данные из таблицы
2. Сгенерировать Python код для преобразования
3. Вызвать `execute_python_code` с нужным кодом
4. Записать результаты обратно в таблицу

---

### Шаг 5: Тестирование реального сценария (с Google Sheets)

#### 5.1. Подготовьте тестовую таблицу

1. Создайте Google Sheets таблицу
2. В колонке A поместите тестовые цены (например: 10, 20, 30 в строках 2-4)
3. Оставьте колонку B пустой

#### 5.2. Отправьте запрос через интерфейс

Используйте ваш фронтенд или API для отправки запроса типа:

> "У меня в таблице [ID] в колонке A цены в долларах (строки 2-4). Преобразуй их в рубли по курсу 95, добавь НДС 20%, округли до 2 знаков и запиши в колонку B"

#### 5.3. Проверьте результат

Проверьте, что:
- ✅ Данные были прочитаны из колонки A
- ✅ Код был сгенерирован и выполнен
- ✅ Результаты записаны в колонку B
- ✅ Значения правильные (например, для 10 USD: 10 * 95 * 1.2 = 1140.0 RUB)

---

### Шаг 6: Тестирование edge cases

#### 6.1. Тест с пустыми данными

```python
# Запустите в Python консоли:
import asyncio
from src.mcp_tools.code_execution_tools import PythonCodeExecutionTool

tool = PythonCodeExecutionTool()

async def test():
    code = """
result = data.get('prices', [])
result = [p * 2 for p in result] if result else []
"""
    result = await tool._arun(code=code, input_data={})
    print(result)

asyncio.run(test())
```

#### 6.2. Тест с ошибкой в коде

```python
async def test():
    code = """
# Синтаксическая ошибка
result = [1, 2, 3
"""
    try:
        result = await tool._arun(code=code)
        print("❌ Should have failed")
    except Exception as e:
        print(f"✅ Correctly caught error: {e}")

asyncio.run(test())
```

#### 6.3. Тест с большими данными

```python
async def test():
    code = """
prices = data['prices']
result = [p * 2 for p in prices]
"""
    # Большой список данных
    input_data = {"prices": list(range(1000))}
    result = await tool._arun(code=code, input_data=input_data)
    print(f"✅ Processed {len(input_data['prices'])} items")

asyncio.run(test())
```

---

## Возможные проблемы и решения

### Проблема: ModuleNotFoundError при запуске тестов

**Решение**: Убедитесь, что все зависимости установлены:
```bash
pip install -r requirements.txt -r requirements-core.txt -r requirements-ai.txt
```

### Проблема: Tool не найден в SheetsAgent

**Решение**: Проверьте, что файл `src/mcp_tools/code_execution_tools.py` существует и правильно импортируется:
```bash
python3 -c "from src.mcp_tools.code_execution_tools import get_code_execution_tools; print(get_code_execution_tools())"
```

### Проблема: AI не использует execute_python_code

**Решение**: 
1. Проверьте, что системный промпт обновлен (раздел 9 в `SHEETS_AGENT_SYSTEM_PROMPT`)
2. Убедитесь, что инструмент доступен (проверьте через `agent.get_tools()`)
3. Попробуйте явно попросить AI использовать инструмент в запросе

---

## Чеклист успешного тестирования

- [ ] Все базовые тесты проходят (`test_code_execution_manual.py`)
- [ ] Инструмент доступен в SheetsAgent
- [ ] Может выполнять простой Python код
- [ ] Работает с входными данными через `data`
- [ ] Поддерживает библиотеки: math, datetime, json
- [ ] Корректно обрабатывает timeout
- [ ] Интегрирован в реальный workflow через API/интерфейс
- [ ] Работает с реальными Google Sheets данными
- [ ] Обрабатывает ошибки корректно

---

## Следующие шаги после успешного тестирования

1. Если все тесты прошли - можно вливать ветку в основную:
   ```bash
   git checkout production  # или main
   git merge feature/python-code-execution
   ```

2. Для production использования рекомендуется:
   - Добавить логирование выполняемого кода (для аудита)
   - Рассмотреть более строгую валидацию кода (AST parsing)
   - Добавить rate limiting для предотвращения злоупотреблений



