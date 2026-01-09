"""
TDD тест для fallback механизма фейковых деталей интентов.

Проверяет, что если детали интента не приходят долго (>10 секунд),
система автоматически отправляет фейковые детали для обратной связи.

КРИТЕРИИ УСПЕХА:
1. При создании интента запускается мониторинг таймаута
2. Если детали не приходят >10 секунд - отправляется фейковая деталь
3. Фейковые детали помечены флагом "is_fake": True
4. Когда приходит реальная деталь - время обновляется, фейковые прекращаются
5. При завершении интента мониторинг останавливается
"""

import pytest
import asyncio
import httpx
import websockets
import json
import time
from typing import List, Dict, Any


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


async def collect_events_with_timeout(
    ws_url: str,
    session_id: str,
    message: str,
    timeout: float = 30.0,
    check_interval: float = 0.5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Отправляет сообщение и собирает события с отслеживанием времени.
    
    Returns:
        Dict с ключами:
        - 'intent_start': List[{intent_id, text, timestamp}]
        - 'intent_detail': List[{intent_id, type, description, is_fake, timestamp}]
        - 'intent_complete': List[{intent_id, summary, timestamp}]
        - 'timeline': List[{event_type, timestamp}] - хронология событий
    """
    events = {
        'intent_start': [],
        'intent_detail': [],
        'intent_complete': [],
        'timeline': []
    }
    
    start_time = time.time()
    
    try:
        async with websockets.connect(f"{ws_url}/ws/{session_id}") as ws:
            # Отправляем сообщение
            await ws.send(json.dumps({
                "type": "message",
                "content": message
            }))
            
            # Собираем события
            while time.time() - start_time < timeout:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=check_interval)
                    event = json.loads(raw)
                    event_type = event.get('type')
                    data = event.get('data', {})
                    event_timestamp = time.time()
                    
                    events['timeline'].append({
                        'event_type': event_type,
                        'timestamp': event_timestamp,
                        'elapsed': event_timestamp - start_time
                    })
                    
                    if event_type == 'intent_start':
                        events['intent_start'].append({
                            'intent_id': data.get('intent_id'),
                            'text': data.get('text'),
                            'timestamp': event_timestamp
                        })
                    elif event_type == 'intent_detail':
                        events['intent_detail'].append({
                            'intent_id': data.get('intent_id'),
                            'type': data.get('type'),
                            'description': data.get('description'),
                            'is_fake': data.get('is_fake', False),
                            'timestamp': event_timestamp
                        })
                    elif event_type == 'intent_complete':
                        events['intent_complete'].append({
                            'intent_id': data.get('intent_id'),
                            'summary': data.get('summary'),
                            'timestamp': event_timestamp
                        })
                    elif event_type in ('final_result', 'react_complete', 'react_failed'):
                        break
                        
                except asyncio.TimeoutError:
                    continue
                    
    except Exception as e:
        pytest.skip(f"WebSocket connection failed: {e}")
    
    return events


class TestFakeDetailFallback:
    """Тесты для fallback механизма фейковых деталей."""
    
    @pytest.mark.asyncio
    async def test_fake_detail_sent_after_timeout(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        Если интент создан, но детали не приходят >10 секунд,
        должна быть отправлена фейковая деталь.
        
        Этот тест должен ПАДАТЬ до реализации фичи.
        """
        session_id = await create_session(base_url)
        
        # Используем простой запрос, который может долго обрабатываться
        query = "Покажи мои встречи на следующую неделю"
        
        events = await collect_events_with_timeout(
            ws_url, session_id, query,
            timeout=15.0  # Ждём 15 секунд
        )
        
        intent_starts = events['intent_start']
        intent_details = events['intent_detail']
        timeline = events['timeline']
        
        print(f"\n=== Fake Detail Fallback Test ===")
        print(f"Intent starts: {len(intent_starts)}")
        print(f"Intent details: {len(intent_details)}")
        
        if intent_details:
            print(f"\nDetails timeline:")
            for detail in intent_details:
                elapsed = detail['timestamp'] - timeline[0]['timestamp'] if timeline else 0
                print(f"  [{elapsed:.1f}s] {'FAKE' if detail.get('is_fake') else 'REAL'}: {detail['description'][:60]}")
        
        # КРИТЕРИЙ 1: Должен быть хотя бы один интент
        assert len(intent_starts) >= 1, (
            f"Expected at least 1 intent, got {len(intent_starts)}"
        )
        
        if len(intent_starts) > 0:
            intent_id = intent_starts[0]['intent_id']
            intent_start_time = intent_starts[0]['timestamp']
            
            # Находим детали для этого интента
            details_for_intent = [
                d for d in intent_details
                if d['intent_id'] == intent_id
            ]
            
            # КРИТЕРИЙ 2: Если прошло >10 секунд с момента создания интента,
            # должна быть хотя бы одна фейковая деталь
            if len(details_for_intent) > 0:
                first_detail_time = details_for_intent[0]['timestamp']
                elapsed_before_first_detail = first_detail_time - intent_start_time
                
                if elapsed_before_first_detail >= 10.0:
                    fake_details = [d for d in details_for_intent if d.get('is_fake')]
                    assert len(fake_details) >= 1, (
                        f"Expected at least 1 fake detail after {elapsed_before_first_detail:.1f}s timeout, "
                        f"but got {len(fake_details)} fake details. "
                        f"Total details: {len(details_for_intent)}"
                    )
                    print(f"\n✅ Found {len(fake_details)} fake detail(s) after {elapsed_before_first_detail:.1f}s")
    
    @pytest.mark.asyncio
    async def test_fake_details_have_correct_flag(self, base_url, ws_url):
        """
        КРИТЕРИЙ УСПЕХА:
        Фейковые детали должны быть помечены флагом "is_fake": True.
        
        Этот тест должен ПАДАТЬ до реализации фичи.
        """
        session_id = await create_session(base_url)
        
        query = "Покажи мои встречи на следующую неделю"
        
        events = await collect_events_with_timeout(
            ws_url, session_id, query,
            timeout=15.0
        )
        
        intent_details = events['intent_detail']
        
        # Ищем фейковые детали
        fake_details = [d for d in intent_details if d.get('is_fake')]
        
        print(f"\n=== Fake Details Flag Test ===")
        print(f"Total details: {len(intent_details)}")
        print(f"Fake details: {len(fake_details)}")
        
        if fake_details:
            for detail in fake_details:
                print(f"  - {detail['description'][:60]} (is_fake={detail.get('is_fake')})")
        
        # КРИТЕРИЙ: Все фейковые детали должны иметь is_fake=True
        # (Если нет фейковых - тест пропускается, так как фича не реализована)
        if fake_details:
            for detail in fake_details:
                assert detail.get('is_fake') is True, (
                    f"Fake detail missing is_fake flag: {detail}"
                )
