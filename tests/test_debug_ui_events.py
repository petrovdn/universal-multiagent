# tests/test_debug_ui_events.py
"""
DEBUG автотест для проверки отправки UI событий.

Этот тест проверяет:
1. Какие WebSocket события отправляются при обработке сообщения
2. Правильно ли работает flow _answer_directly vs ReAct loop
3. Получает ли frontend нужные события (thinking_started, final_result, etc.)

Запуск: python -m pytest tests/test_debug_ui_events.py -v -s
"""
import pytest
import asyncio
import json
import time
from typing import List, Dict, Any
from pathlib import Path

# Log file path for debug
LOG_PATH = Path("/Users/Dima/universal-multiagent/.cursor/debug.log")

def log_debug(location: str, message: str, data: dict, hypothesis: str):
    """Write debug log entry."""
    entry = {
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "hypothesisId": hypothesis,
        "source": "autotest"
    }
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')


class MockWebSocketManager:
    """Mock WebSocket manager that captures all events."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.connection_count = 1
    
    async def send_event(self, session_id: str, event_type: str, data: Dict[str, Any]):
        """Capture event."""
        event = {
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "timestamp": time.time()
        }
        self.events.append(event)
        
        # Log to debug file
        log_debug(
            f"MockWS:send_event:{event_type}",
            f"Event sent: {event_type}",
            {"event_type": event_type, "data_keys": list(data.keys()) if isinstance(data, dict) else str(type(data))},
            "H1,H3,H5"
        )
        print(f"  📨 WS Event: {event_type} | keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
    
    def get_connection_count(self, session_id: str) -> int:
        return self.connection_count
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["event_type"] == event_type]
    
    def has_event(self, event_type: str) -> bool:
        return any(e["event_type"] == event_type for e in self.events)
    
    def print_all_events(self):
        print("\n📋 All WebSocket Events:")
        for i, e in enumerate(self.events):
            print(f"  {i+1}. {e['event_type']}: {list(e['data'].keys()) if isinstance(e['data'], dict) else 'N/A'}")


class TestUIEventsDebug:
    """Debug tests for UI events flow."""
    
    @pytest.mark.asyncio
    async def test_simple_query_events_flow(self):
        """
        H3: Test that simple queries go through _answer_directly 
        and send correct events.
        
        Expected flow:
        1. thinking_started
        2. thinking_completed  
        3. final_result
        """
        log_debug("test:start", "Starting simple query test", {"query": "привет"}, "H3")
        print("\n" + "="*60)
        print("TEST: Simple query events flow")
        print("="*60)
        
        from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
        from src.core.capability_registry import CapabilityRegistry
        from src.core.action_provider import CapabilityCategory
        from src.core.context_manager import ConversationContext
        
        mock_ws = MockWebSocketManager()
        
        config = ReActConfig(
            mode="agent",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=3
        )
        
        registry = CapabilityRegistry()
        
        log_debug("test:create_engine", "Creating UnifiedReActEngine", {}, "H1,H4")
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=registry,
            ws_manager=mock_ws,
            session_id="test-session-debug",
            model_name=None
        )
        
        context = ConversationContext(session_id="test-session-debug")
        
        # Simple query that should go through _answer_directly
        test_query = "привет"
        
        log_debug("test:execute_start", "Calling engine.execute", {"query": test_query}, "H3")
        print(f"\n📝 Query: '{test_query}'")
        print(f"🔧 Mode: agent")
        print(f"\n🔄 Executing...\n")
        
        try:
            result = await engine.execute(goal=test_query, context=context)
            
            log_debug("test:execute_done", "engine.execute completed", {
                "status": result.get("status"),
                "iterations": result.get("iterations"),
                "events_count": len(mock_ws.events)
            }, "H3")
            
            print(f"\n📊 Result:")
            print(f"   Status: {result.get('status')}")
            print(f"   Iterations: {result.get('iterations')}")
            print(f"   Events count: {len(mock_ws.events)}")
            
            mock_ws.print_all_events()
            
            # Check events
            print("\n🔍 Checking events...")
            
            has_thinking_started = mock_ws.has_event("thinking_started")
            has_thinking_completed = mock_ws.has_event("thinking_completed")
            has_final_result = mock_ws.has_event("final_result")
            has_react_start = mock_ws.has_event("react_start")
            has_intent_start = mock_ws.has_event("intent_start")
            
            print(f"   thinking_started: {'✅' if has_thinking_started else '❌'}")
            print(f"   thinking_completed: {'✅' if has_thinking_completed else '❌'}")
            print(f"   final_result: {'✅' if has_final_result else '❌'}")
            print(f"   react_start: {'⚠️ (ReAct path)' if has_react_start else '✅ (direct path)'}")
            print(f"   intent_start: {'⚠️ (ReAct path)' if has_intent_start else '✅ (direct path)'}")
            
            log_debug("test:events_check", "Events check completed", {
                "has_thinking_started": has_thinking_started,
                "has_thinking_completed": has_thinking_completed,
                "has_final_result": has_final_result,
                "has_react_start": has_react_start,
                "has_intent_start": has_intent_start,
                "total_events": len(mock_ws.events)
            }, "H1,H3,H5")
            
            # Assertions
            assert has_final_result, "❌ FAIL: No final_result event! UI won't show response."
            
            # Log final_result content
            final_events = mock_ws.get_events_by_type("final_result")
            if final_events:
                content = final_events[0]["data"].get("content", "")
                print(f"\n📄 final_result content ({len(content)} chars):")
                print(f"   {content[:200]}..." if len(content) > 200 else f"   {content}")
                
                log_debug("test:final_result_content", "final_result content", {
                    "content_length": len(content),
                    "content_preview": content[:100]
                }, "H5")
            
            print("\n✅ TEST PASSED")
            return True
            
        except Exception as e:
            log_debug("test:error", f"Test failed with error: {str(e)}", {"error": str(e)}, "H1,H3,H4,H5")
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    @pytest.mark.asyncio
    async def test_complex_query_events_flow(self):
        """
        H1,H2: Test that complex queries go through ReAct loop
        and send intent events.
        
        Expected flow:
        1. react_start
        2. thinking_started
        3. intent_start
        4. (tool execution events)
        5. intent_complete
        6. final_result
        """
        log_debug("test:complex:start", "Starting complex query test", {"query": "покажи мои встречи"}, "H1,H2")
        print("\n" + "="*60)
        print("TEST: Complex query events flow (ReAct)")
        print("="*60)
        
        from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
        from src.core.capability_registry import CapabilityRegistry
        from src.core.action_provider import CapabilityCategory, ActionProvider, ActionCapability
        from src.core.context_manager import ConversationContext
        
        mock_ws = MockWebSocketManager()
        
        # Create a mock capability for calendar
        class MockCalendarProvider(ActionProvider):
            def get_capabilities(self):
                return [ActionCapability(
                    name="calendar_list_events",
                    description="List calendar events",
                    category=CapabilityCategory.READ,
                    parameters={"timeMin": {"type": "string"}, "timeMax": {"type": "string"}}
                )]
            
            async def execute(self, capability_name: str, arguments: dict):
                log_debug("mock_calendar:execute", "Mock calendar called", {
                    "capability": capability_name,
                    "args": str(arguments)[:100]
                }, "H2,H6")
                return {"events": [{"summary": "Test meeting", "start": "2026-01-09T10:00:00"}]}
        
        config = ReActConfig(
            mode="agent",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=3
        )
        
        registry = CapabilityRegistry()
        registry.register_provider(MockCalendarProvider())
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=registry,
            ws_manager=mock_ws,
            session_id="test-session-complex",
            model_name=None
        )
        
        context = ConversationContext(session_id="test-session-complex")
        
        # Complex query that should go through ReAct loop
        test_query = "покажи мои встречи на сегодня"
        
        log_debug("test:complex:execute_start", "Calling engine.execute for complex query", {"query": test_query}, "H1,H2")
        print(f"\n📝 Query: '{test_query}'")
        print(f"🔧 Mode: agent (with calendar capability)")
        print(f"\n🔄 Executing...\n")
        
        try:
            result = await engine.execute(goal=test_query, context=context)
            
            log_debug("test:complex:execute_done", "Complex query completed", {
                "status": result.get("status"),
                "iterations": result.get("iterations"),
                "actions_taken": result.get("actions_taken"),
                "events_count": len(mock_ws.events)
            }, "H1,H2")
            
            print(f"\n📊 Result:")
            print(f"   Status: {result.get('status')}")
            print(f"   Iterations: {result.get('iterations')}")
            print(f"   Actions: {result.get('actions_taken')}")
            print(f"   Events count: {len(mock_ws.events)}")
            
            mock_ws.print_all_events()
            
            # Check events
            print("\n🔍 Checking events...")
            
            has_react_start = mock_ws.has_event("react_start")
            has_thinking_started = mock_ws.has_event("thinking_started")
            has_intent_start = mock_ws.has_event("intent_start")
            has_intent_detail = mock_ws.has_event("intent_detail")
            has_intent_complete = mock_ws.has_event("intent_complete")
            has_final_result = mock_ws.has_event("final_result")
            
            print(f"   react_start: {'✅' if has_react_start else '❌'}")
            print(f"   thinking_started: {'✅' if has_thinking_started else '❌'}")
            print(f"   intent_start: {'✅' if has_intent_start else '❌'}")
            print(f"   intent_detail: {'✅' if has_intent_detail else '⚠️ (no tool calls?)'}")
            print(f"   intent_complete: {'✅' if has_intent_complete else '❌'}")
            print(f"   final_result: {'✅' if has_final_result else '❌'}")
            
            log_debug("test:complex:events_check", "Complex query events check", {
                "has_react_start": has_react_start,
                "has_thinking_started": has_thinking_started,
                "has_intent_start": has_intent_start,
                "has_intent_detail": has_intent_detail,
                "has_intent_complete": has_intent_complete,
                "has_final_result": has_final_result,
                "total_events": len(mock_ws.events),
                "event_types": [e["event_type"] for e in mock_ws.events]
            }, "H1,H2,H5")
            
            print("\n✅ TEST COMPLETED (check events above)")
            return True
            
        except Exception as e:
            log_debug("test:complex:error", f"Complex test failed: {str(e)}", {"error": str(e)}, "H1,H2")
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            raise


# Direct run
if __name__ == "__main__":
    # Clear log file
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    
    print("🧪 DEBUG UI Events Test")
    print("="*60)
    
    async def run_tests():
        test = TestUIEventsDebug()
        await test.test_simple_query_events_flow()
        print("\n" + "-"*60 + "\n")
        await test.test_complex_query_events_flow()
    
    asyncio.run(run_tests())
    
    print("\n" + "="*60)
    print("📋 Debug log written to:", LOG_PATH)
    print("="*60)
