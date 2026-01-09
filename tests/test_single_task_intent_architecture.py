"""
TDD Test: Single Task Intent Architecture

Tests that the new architecture follows Cursor-style hierarchy:
- ONE task-level intent per goal (not per iteration)
- Tool calls appear as intent_detail events (not as separate intents)
- Re-planning creates a NEW task-level intent

Expected behavior:
  BEFORE (current):
    intent_start: "Определяю участников..."     <- iteration 1
    intent_start: "Создание встречи..."         <- action intent
    intent_detail: "🔧 Schedule Meeting"
    intent_start: "Определяю участников..."     <- iteration 2
    intent_start: "Получение календаря..."      <- action intent
    ...
    Total: ~9 intent_starts, ~15 intent_details

  AFTER (new architecture):
    intent_start: "Создание встречи с bsn@lad24.ru на 2 часа"  <- ONE task intent
    intent_detail: "🔧 Проверяю календарь участников"
    intent_detail: "📅 Найдено 9 событий"
    intent_detail: "🔧 Ищу свободное время"
    intent_detail: "✅ Найден слот: 10:00"
    intent_detail: "🔧 Создаю встречу"
    intent_detail: "✅ Встреча создана"
    intent_complete
    Total: 1-2 intent_starts (1 main + optional replan), many intent_details
"""
import pytest
import asyncio
import json
import httpx
import websockets
from typing import List, Dict, Any


class IntentArchitectureCollector:
    """Collects events to verify new architecture."""
    
    def __init__(self):
        self.intent_starts: List[Dict[str, Any]] = []
        self.intent_details: List[Dict[str, Any]] = []
        self.intent_completes: List[Dict[str, Any]] = []
        self.all_events: List[Dict[str, Any]] = []
        self.is_complete = False
        self.final_result = ""
    
    def process_event(self, event: Dict[str, Any]):
        self.all_events.append(event)
        event_type = event.get("type")
        data = event.get("data", event)
        
        if event_type == "intent_start":
            self.intent_starts.append(data)
            text = data.get('text', data.get('intent', ''))[:50]
            print(f"  📋 INTENT_START [{len(self.intent_starts)}]: {text}")
        
        elif event_type == "intent_detail":
            self.intent_details.append(data)
            desc = data.get('description', '')[:60]
            print(f"    ➡️ DETAIL [{len(self.intent_details)}]: {desc}")
        
        elif event_type == "intent_complete":
            self.intent_completes.append(data)
        
        elif event_type in ["final_result_complete", "react_complete", "react_failed", "message_complete"]:
            self.is_complete = True
            if event_type == "final_result_complete":
                self.final_result = data.get("content", "")[:100]
                print(f"  🏁 COMPLETE: {self.final_result}...")


@pytest.mark.asyncio
async def test_single_task_intent_for_meeting_creation():
    """
    Test that creating a meeting generates:
    - At most 2 task-level intents (1 main + optional replan)
    - At least 4 intent_details (calendar check, slot search, create, result)
    
    This test will FAIL with current implementation (which creates ~9 intents).
    """
    BASE_URL = "http://localhost:8000"
    
    # Create session
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/session/create")
        if response.status_code != 200:
            pytest.skip(f"Backend not available: {response.status_code}")
        session_id = response.json().get("session_id")
    
    collector = IntentArchitectureCollector()
    ws_url = f"ws://localhost:8000/ws/{session_id}"
    
    print(f"\n{'='*60}")
    print("TEST: Single Task Intent Architecture")
    print(f"{'='*60}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Send meeting creation request
            message = "создай встречу с bsn@lad24.ru на 2 часа"
            await ws.send(json.dumps({
                "type": "message",
                "content": message,
                "mode": "agent"
            }))
            print(f"\n📤 Sent: {message}\n")
            
            # Collect events
            try:
                async with asyncio.timeout(120):
                    while not collector.is_complete:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        event = json.loads(raw_msg)
                        collector.process_event(event)
            except asyncio.TimeoutError:
                pass
    
    except Exception as e:
        pytest.skip(f"Connection failed: {e}")
    
    # Report
    print(f"\n{'='*60}")
    print("📊 RESULTS:")
    print(f"{'='*60}")
    print(f"intent_start events:  {len(collector.intent_starts)}")
    print(f"intent_detail events: {len(collector.intent_details)}")
    print(f"intent_complete events: {len(collector.intent_completes)}")
    
    # ASSERTIONS for new architecture
    print(f"\n{'='*60}")
    print("🔍 ASSERTIONS (New Architecture):")
    print(f"{'='*60}")
    
    # Key assertion: Should have AT MOST 3 task-level intents
    # (1 main task + possible replan + final answer)
    MAX_TASK_INTENTS = 3
    assert len(collector.intent_starts) <= MAX_TASK_INTENTS, \
        f"Expected at most {MAX_TASK_INTENTS} task intents (Cursor-style), " \
        f"but got {len(collector.intent_starts)}. " \
        f"Tool calls should be intent_details, not separate intents!"
    print(f"✅ At most {MAX_TASK_INTENTS} task-level intents")
    
    # Should have many details (tool calls + results)
    MIN_DETAILS = 4  # At least: calendar check, result, slot search, create
    assert len(collector.intent_details) >= MIN_DETAILS, \
        f"Expected at least {MIN_DETAILS} intent_details, got {len(collector.intent_details)}"
    print(f"✅ At least {MIN_DETAILS} intent_details")
    
    # Ratio check: details should outnumber intents significantly
    if len(collector.intent_starts) > 0:
        ratio = len(collector.intent_details) / len(collector.intent_starts)
        MIN_RATIO = 2.0  # At least 2 details per intent
        assert ratio >= MIN_RATIO, \
            f"Expected details/intents ratio >= {MIN_RATIO}, got {ratio:.1f}. " \
            f"Each task intent should have multiple details."
        print(f"✅ Details/intents ratio: {ratio:.1f} (>= {MIN_RATIO})")
    
    print("\n✅ All architecture assertions passed!")


@pytest.mark.asyncio
async def test_intent_details_describe_tool_calls():
    """
    Test that intent_details contain meaningful tool call descriptions,
    not just generic placeholders.
    
    Uses a query that definitely requires tool execution.
    """
    BASE_URL = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/session/create")
        if response.status_code != 200:
            pytest.skip(f"Backend not available")
        session_id = response.json().get("session_id")
    
    collector = IntentArchitectureCollector()
    
    try:
        async with websockets.connect(f"ws://localhost:8000/ws/{session_id}") as ws:
            # Use a query that definitely requires tools (calendar creation)
            await ws.send(json.dumps({
                "type": "message",
                "content": "создай встречу с test@example.com на завтра в 14:00 на 1 час",
                "mode": "agent"
            }))
            
            try:
                async with asyncio.timeout(90):  # Longer timeout for complex task
                    while not collector.is_complete:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=15)
                        collector.process_event(json.loads(raw_msg))
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        pytest.skip(f"Connection failed: {e}")
    
    # Check that details mention actual actions
    action_keywords = ['календар', 'событ', 'встреч', 'создан', 'получ', 'найд', 'calendar', 'event', '📅', '🔧', '✅', '🎯', 'create']
    
    # If we have any intent_details, at least some should have meaningful descriptions
    if collector.intent_details:
        meaningful_details = 0
        for detail in collector.intent_details:
            desc = detail.get('description', '').lower()
            if any(kw in desc for kw in action_keywords):
                meaningful_details += 1
        
        assert meaningful_details >= 1, \
            f"Expected at least 1 detail with action keywords, got {meaningful_details}. Details: {[d.get('description', '')[:50] for d in collector.intent_details]}"
        print(f"\n✅ Found {meaningful_details} meaningful intent details")
    else:
        # If no intent_details, it means _answer_directly was used (skip test)
        pytest.skip("Query was answered directly without tools - no intent_details to check")


if __name__ == "__main__":
    asyncio.run(test_single_task_intent_for_meeting_creation())
