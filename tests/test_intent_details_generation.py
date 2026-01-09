"""
Test that backend generates sufficient intent_start and intent_detail events
for complex tasks like scheduling meetings.

This test connects directly to the WebSocket and counts all events,
bypassing the frontend to verify backend behavior.
"""
import pytest
import asyncio
import json
import httpx
import websockets
from typing import List, Dict, Any


class IntentEventCollector:
    """Collects intent events from WebSocket."""
    
    def __init__(self):
        self.intent_starts: List[Dict[str, Any]] = []
        self.intent_details: List[Dict[str, Any]] = []
        self.intent_completes: List[Dict[str, Any]] = []
        self.all_events: List[Dict[str, Any]] = []
        self.final_result: str = ""
        self.is_complete = False
    
    def process_event(self, event: Dict[str, Any]):
        """Process a single WebSocket event."""
        self.all_events.append(event)
        event_type = event.get("type")
        data = event.get("data", event)
        
        if event_type == "intent_start":
            self.intent_starts.append(data)
            print(f"  📋 INTENT_START: {data.get('text', data.get('intent', 'unknown'))[:60]}")
        
        elif event_type == "intent_detail":
            self.intent_details.append(data)
            print(f"    ➡️ INTENT_DETAIL: {data.get('description', 'unknown')[:60]}")
        
        elif event_type == "intent_complete":
            self.intent_completes.append(data)
            print(f"  ✅ INTENT_COMPLETE: {data.get('summary', 'done')[:60]}")
        
        elif event_type == "final_result_complete":
            self.final_result = data.get("content", "")
            self.is_complete = True
            print(f"  🏁 FINAL_RESULT: {self.final_result[:100]}...")
        
        elif event_type == "react_complete":
            self.is_complete = True
            print(f"  🏁 REACT_COMPLETE")
        
        elif event_type == "react_failed":
            self.is_complete = True
            print(f"  ❌ REACT_FAILED: {data.get('reason', 'unknown')}")
        
        elif event_type == "message_complete":
            self.is_complete = True


@pytest.mark.asyncio
async def test_meeting_scheduling_generates_multiple_intents():
    """
    Test that scheduling a meeting generates multiple intent_start and intent_detail events.
    
    Expected flow:
    1. intent_start: "Определяю участников" or similar
    2. intent_detail: "Получаю календарь участника X"
    3. intent_detail: "Ищу свободные слоты"
    4. intent_start: "Создаю встречу" or similar
    5. intent_detail: "Отправляю приглашение"
    6. intent_complete
    
    Minimum expected:
    - At least 2 intent_start events (analysis + action)
    - At least 2 intent_detail events (calendar check + slot finding)
    """
    BASE_URL = "http://localhost:8000"
    
    # 1. Create session
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/session/create")
        if response.status_code != 200:
            pytest.skip(f"Backend not available: {response.status_code}")
        
        session_data = response.json()
        session_id = session_data.get("session_id")
        assert session_id, "No session_id returned"
        print(f"\n✅ Session created: {session_id}")
    
    # 2. Connect to WebSocket
    collector = IntentEventCollector()
    ws_url = f"ws://localhost:8000/ws/{session_id}"
    
    print(f"\n📡 Connecting to WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ WebSocket connected")
            
            # 3. Send message
            message = "создай встречу с bsn@lad24.ru на 2 часа"
            await ws.send(json.dumps({
                "type": "message",
                "content": message,
                "mode": "agent"
            }))
            print(f"\n📤 Sent message: {message}")
            print("\n📥 Receiving events:")
            
            # 4. Collect events with timeout
            try:
                async with asyncio.timeout(120):  # 2 minutes timeout
                    while not collector.is_complete:
                        try:
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            event = json.loads(raw_msg)
                            collector.process_event(event)
                        except asyncio.TimeoutError:
                            print("⚠️ Timeout waiting for event, checking if complete...")
                            if collector.is_complete:
                                break
                            continue
            except asyncio.TimeoutError:
                print("⚠️ Overall timeout reached")
    
    except Exception as e:
        pytest.skip(f"WebSocket connection failed: {e}")
    
    # 5. Report results
    print("\n" + "="*60)
    print("📊 RESULTS:")
    print("="*60)
    print(f"Total events received: {len(collector.all_events)}")
    print(f"intent_start events: {len(collector.intent_starts)}")
    print(f"intent_detail events: {len(collector.intent_details)}")
    print(f"intent_complete events: {len(collector.intent_completes)}")
    
    # Print all intent texts
    print("\n📋 Intent sequence:")
    for i, intent in enumerate(collector.intent_starts, 1):
        text = intent.get('text', intent.get('intent', 'unknown'))
        print(f"  {i}. {text}")
    
    print("\n➡️ Intent details:")
    for i, detail in enumerate(collector.intent_details, 1):
        desc = detail.get('description', 'unknown')
        print(f"  {i}. {desc}")
    
    # 6. Assertions
    print("\n" + "="*60)
    print("🔍 ASSERTIONS:")
    print("="*60)
    
    # Must have at least 2 intent_start events
    assert len(collector.intent_starts) >= 2, \
        f"Expected at least 2 intent_start events, got {len(collector.intent_starts)}"
    print("✅ At least 2 intent_start events")
    
    # Must have at least 2 intent_detail events  
    assert len(collector.intent_details) >= 2, \
        f"Expected at least 2 intent_detail events, got {len(collector.intent_details)}. " \
        f"Backend should send details like 'Получаю календарь', 'Ищу слоты' etc."
    print("✅ At least 2 intent_detail events")
    
    # Must complete
    assert collector.is_complete, "Execution did not complete"
    print("✅ Execution completed")
    
    print("\n✅ All assertions passed!")


@pytest.mark.asyncio  
async def test_intent_details_contain_meaningful_descriptions():
    """
    Test that intent_detail events contain meaningful descriptions,
    not generic placeholders.
    """
    BASE_URL = "http://localhost:8000"
    
    # Create session
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/session/create")
        if response.status_code != 200:
            pytest.skip(f"Backend not available: {response.status_code}")
        
        session_data = response.json()
        session_id = session_data.get("session_id")
    
    collector = IntentEventCollector()
    ws_url = f"ws://localhost:8000/ws/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "type": "message",
                "content": "покажи мои события на сегодня",
                "mode": "agent"
            }))
            
            try:
                async with asyncio.timeout(60):
                    while not collector.is_complete:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=15)
                        event = json.loads(raw_msg)
                        collector.process_event(event)
            except asyncio.TimeoutError:
                pass
    
    except Exception as e:
        pytest.skip(f"WebSocket connection failed: {e}")
    
    # Check that intent details are meaningful
    generic_placeholders = ["...", "Выполняю", "Обрабатываю", "execute"]
    
    for detail in collector.intent_details:
        desc = detail.get("description", "")
        # Description should not be only placeholder
        is_meaningful = len(desc) > 10 and not all(p in desc for p in generic_placeholders)
        assert is_meaningful, \
            f"Intent detail should have meaningful description, got: {desc}"


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_intent_details_generation.py -v -s
    asyncio.run(test_meeting_scheduling_generates_multiple_intents())
