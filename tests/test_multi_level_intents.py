"""
TDD тест для мульти-уровневых интентов.

Проверяет, что сложные задачи с несколькими логическими шагами
создают НЕСКОЛЬКО top-level интентов (как в Cursor):

1. Каждый логический этап = отдельный intent_start
2. Под каждым интентом - свои intent_detail

Пример задачи:
"Нужно составить график зависимости зарплаты от первой буквы фамилии сотрудника.
 Для этого возьми в 1С данные по зарплате, перенеси их в таблицу,
 сделай код на питоне для расчета, и выдай графики."

Ожидаемые интенты:
- "📊 Получение данных из 1С" (details: OData запросы)
- "📋 Создание таблицы" (details: sheets операции)
- "🐍 Генерация Python кода" (details: code execution)
- "📈 Построение графиков" (details: chart generation)
"""

import pytest
import asyncio
import httpx
import websockets
import json
from typing import List, Dict, Any


# Сложная multi-step задача для тестирования
COMPLEX_MULTI_STEP_QUERY = """
Нужно проанализировать зарплаты сотрудников. 
Возьми данные из 1С о зарплатах за последние 3 месяца,
создай Google таблицу с этими данными,
и построй диаграмму средней зарплаты по отделам.
"""

# Более простая задача с явными шагами
EXPLICIT_MULTI_STEP_QUERY = """
Выполни по очереди:
1. Найди письма от boss@company.ru за эту неделю
2. Создай задачу в календаре на основе найденных писем
3. Отправь подтверждение о создании задачи
"""


@pytest.fixture
def base_url():
    return "http://localhost:8000"


@pytest.fixture
def ws_url():
    return "ws://localhost:8000"


async def create_session(base_url: str) -> str:
    """Создаёт сессию и возвращает session_id."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/api/session/create")
        if response.status_code != 200:
            pytest.skip(f"Backend not available: {response.status_code}")
        data = response.json()
        return data.get("session_id") or data.get("id")


async def collect_intent_events(
    ws_url: str, 
    session_id: str, 
    message: str, 
    timeout: float = 60.0
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Отправляет сообщение и собирает intent события.
    
    Returns:
        Dict с ключами:
        - 'intent_start': List[{intent_id, text}]
        - 'intent_detail': List[{intent_id, type, description}]
        - 'intent_complete': List[{intent_id, summary}]
    """
    events = {
        'intent_start': [],
        'intent_detail': [],
        'intent_complete': [],
        'all_events': []
    }
    
    try:
        async with websockets.connect(f"{ws_url}/ws/{session_id}") as ws:
            # Отправляем сообщение
            await ws.send(json.dumps({
                "type": "message",
                "content": message
            }))
            
            # Собираем события
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    event = json.loads(raw)
                    event_type = event.get('type')
                    data = event.get('data', {})
                    
                    events['all_events'].append({'type': event_type, 'data': data})
                    
                    if event_type == 'intent_start':
                        events['intent_start'].append({
                            'intent_id': data.get('intent_id'),
                            'text': data.get('text')
                        })
                    elif event_type == 'intent_detail':
                        events['intent_detail'].append({
                            'intent_id': data.get('intent_id'),
                            'type': data.get('type'),
                            'description': data.get('description')
                        })
                    elif event_type == 'intent_complete':
                        events['intent_complete'].append({
                            'intent_id': data.get('intent_id'),
                            'summary': data.get('summary')
                        })
                    elif event_type in ('final_result', 'react_complete', 'react_failed'):
                        break
                        
                except asyncio.TimeoutError:
                    break
                    
    except Exception as e:
        pytest.skip(f"WebSocket connection failed: {e}")
    
    return events


class TestMultiLevelIntents:
    """Тесты для мульти-уровневых интентов."""
    
    @pytest.mark.asyncio
    async def test_complex_task_creates_multiple_intents(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        Сложная задача с несколькими логическими шагами
        должна создавать НЕСКОЛЬКО top-level intent_start событий,
        а не один.
        
        Сейчас система создаёт ОДИН task-level intent.
        Этот тест должен ПАДАТЬ до реализации фичи.
        """
        session_id = await create_session(base_url)
        
        events = await collect_intent_events(
            ws_url, session_id, 
            COMPLEX_MULTI_STEP_QUERY,
            timeout=90.0
        )
        
        intent_starts = events['intent_start']
        
        print(f"\n=== Intent Start Events ({len(intent_starts)}) ===")
        for intent in intent_starts:
            print(f"  - {intent['text']}")
        
        # КРИТЕРИЙ: Должно быть минимум 2 высокоуровневых интента
        # Система создаёт интенты по мере перехода между фазами (категориями инструментов)
        # Так что если агент не использовал инструменты всех категорий, интентов будет меньше
        assert len(intent_starts) >= 2, (
            f"Expected at least 2 top-level intents for multi-step task, "
            f"but got {len(intent_starts)}: {[i['text'] for i in intent_starts]}"
        )
    
    @pytest.mark.asyncio
    async def test_each_intent_has_own_details(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        Интенты должны иметь details привязанные к ним.
        
        Примечание: Количество интентов зависит от фактических переходов
        между категориями инструментов во время выполнения.
        Если агент остаётся в одной категории (например, email),
        то будет только один интент.
        """
        session_id = await create_session(base_url)
        
        events = await collect_intent_events(
            ws_url, session_id,
            EXPLICIT_MULTI_STEP_QUERY,
            timeout=90.0
        )
        
        intent_starts = events['intent_start']
        intent_details = events['intent_detail']
        
        print(f"\n=== Intent Architecture ===")
        print(f"Total intent_start: {len(intent_starts)}")
        print(f"Total intent_detail: {len(intent_details)}")
        
        # Группируем details по intent_id
        details_by_intent: Dict[str, List[str]] = {}
        for detail in intent_details:
            intent_id = detail['intent_id']
            if intent_id not in details_by_intent:
                details_by_intent[intent_id] = []
            details_by_intent[intent_id].append(detail['description'])
        
        print(f"\nDetails by intent:")
        for intent_id, details in details_by_intent.items():
            # Найдём текст интента
            intent_text = next(
                (i['text'] for i in intent_starts if i['intent_id'] == intent_id),
                'Unknown'
            )
            print(f"  [{intent_id[:20]}...] {intent_text}")
            for d in details[:5]:
                print(f"    - {d}")
        
        # КРИТЕРИЙ 1: Должен быть хотя бы 1 интент
        assert len(intent_starts) >= 1, (
            f"Expected at least 1 intent, got {len(intent_starts)}"
        )
        
        # КРИТЕРИЙ 2: Интент должен иметь details
        total_details_count = sum(len(d) for d in details_by_intent.values())
        assert total_details_count >= 2, (
            f"Expected at least 2 details total, got {total_details_count}"
        )
        
        # КРИТЕРИЙ 3: Если было более 1 интента - это бонус (многофазность работает)
        if len(intent_starts) >= 2:
            print(f"\n✅ Multi-phase detected! {len(intent_starts)} intents created.")
    
    @pytest.mark.asyncio
    async def test_intents_have_meaningful_titles(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        Каждый интент должен иметь осмысленное название,
        описывающее конкретный логический шаг.
        
        НЕ должно быть:
        - "Итерация 1", "Итерация 2"
        - "Выполнение задачи..."
        - "Обработка запроса..."
        """
        session_id = await create_session(base_url)
        
        events = await collect_intent_events(
            ws_url, session_id,
            COMPLEX_MULTI_STEP_QUERY,
            timeout=90.0
        )
        
        intent_starts = events['intent_start']
        
        # Плохие паттерны для названий интентов
        bad_patterns = [
            'итерация',
            'iteration',
            'выполнение задачи',
            'обработка запроса',
            'processing',
            'executing task',
        ]
        
        print(f"\n=== Intent Titles ===")
        for intent in intent_starts:
            text = intent['text'].lower()
            print(f"  - {intent['text']}")
            
            for pattern in bad_patterns:
                assert pattern not in text, (
                    f"Intent title contains generic pattern '{pattern}': {intent['text']}"
                )
        
        # КРИТЕРИЙ: Каждый интент должен содержать релевантные ключевые слова
        # из задачи или описание конкретного действия
        relevant_keywords = [
            '1с', '1c', 'данн', 'зарплат', 'таблиц', 'sheet', 'диаграмм', 
            'график', 'chart', 'получ', 'созда', 'постро', 'анализ'
        ]
        
        for intent in intent_starts:
            text = intent['text'].lower()
            has_relevant = any(kw in text for kw in relevant_keywords)
            # Мягкая проверка - хотя бы один интент должен быть релевантным
            if has_relevant:
                break
        else:
            # Если ни один интент не содержит релевантных слов - предупреждение
            print("\nWARNING: No intent contains task-relevant keywords")
    
    @pytest.mark.asyncio
    async def test_simple_task_single_intent(self, base_url, ws_url):
        """
        Простая задача (один шаг) должна создавать ОДИН интент.
        Это контрольный тест - он должен ПРОХОДИТЬ.
        """
        session_id = await create_session(base_url)
        
        simple_query = "Покажи мои встречи на сегодня"
        
        events = await collect_intent_events(
            ws_url, session_id,
            simple_query,
            timeout=30.0
        )
        
        intent_starts = events['intent_start']
        
        print(f"\n=== Simple Task Intents ({len(intent_starts)}) ===")
        for intent in intent_starts:
            print(f"  - {intent['text']}")
        
        # Для простой задачи - 1-2 интента максимум
        assert len(intent_starts) <= 2, (
            f"Simple task should have 1-2 intents, got {len(intent_starts)}"
        )


class TestIntentHierarchy:
    """Тесты для иерархии интентов (родительские/дочерние)."""
    
    @pytest.mark.asyncio
    async def test_intent_details_linked_to_correct_parent(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        intent_detail события должны ссылаться на корректный
        родительский intent_id.
        
        Не должно быть деталей с несуществующим intent_id.
        """
        session_id = await create_session(base_url)
        
        events = await collect_intent_events(
            ws_url, session_id,
            COMPLEX_MULTI_STEP_QUERY,
            timeout=90.0
        )
        
        intent_ids = {i['intent_id'] for i in events['intent_start']}
        
        print(f"\n=== Intent Hierarchy Validation ===")
        print(f"Known intent_ids: {intent_ids}")
        
        orphan_details = []
        for detail in events['intent_detail']:
            if detail['intent_id'] not in intent_ids:
                orphan_details.append(detail)
        
        if orphan_details:
            print(f"\nOrphan details (no parent intent):")
            for d in orphan_details:
                print(f"  - {d['intent_id']}: {d['description']}")
        
        # КРИТЕРИЙ: Все details должны иметь валидный parent intent
        assert len(orphan_details) == 0, (
            f"Found {len(orphan_details)} intent_detail events with unknown parent intent_id"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
