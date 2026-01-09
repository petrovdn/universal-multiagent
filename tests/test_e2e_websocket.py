# tests/test_e2e_websocket.py
"""
E2E тест: имитирует поведение фронтенда через WebSocket.

Этот тест:
1. Создаёт сессию через REST API
2. Подключается к WebSocket
3. Отправляет сообщение
4. Ждёт события final_result
5. Проверяет что ответ получен

Запуск: python -m pytest tests/test_e2e_websocket.py -v -s

ВАЖНО: Требует запущенный backend на localhost:8000
"""
import pytest
import asyncio
import json
import time
import httpx
import websockets
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configuration
API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
LOG_PATH = Path("/Users/Dima/universal-multiagent/.cursor/debug.log")
TIMEOUT = 30  # seconds


def log_debug(location: str, message: str, data: dict, hypothesis: str):
    """Write debug log entry."""
    entry = {
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "hypothesisId": hypothesis,
        "source": "e2e_test"
    }
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')


class WebSocketTestClient:
    """WebSocket client that mimics frontend behavior."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.events: List[Dict[str, Any]] = []
        self.final_result: Optional[str] = None
        self.connected = False
    
    async def connect(self):
        """Connect to WebSocket."""
        url = f"{WS_BASE}/ws/{self.session_id}"
        log_debug("e2e:ws:connect", f"Connecting to {url}", {"session_id": self.session_id}, "H4")
        print(f"  📡 Connecting to {url}")
        
        try:
            self.ws = await websockets.connect(url)
            self.connected = True
            log_debug("e2e:ws:connected", "WebSocket connected", {}, "H4")
            print(f"  ✅ WebSocket connected")
        except Exception as e:
            log_debug("e2e:ws:connect_error", f"Connection failed: {e}", {"error": str(e)}, "H4")
            print(f"  ❌ Connection failed: {e}")
            raise
    
    async def send_message(self, content: str):
        """Send message like frontend does."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")
        
        payload = {
            "type": "message",
            "content": content
        }
        
        log_debug("e2e:ws:send", f"Sending message", {"content": content[:50]}, "H4")
        print(f"  📤 Sending: {content}")
        
        await self.ws.send(json.dumps(payload))
    
    async def listen_for_events(self, timeout: float = TIMEOUT) -> bool:
        """
        Listen for events until final_result or timeout.
        Returns True if final_result received.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")
        
        start_time = time.time()
        
        log_debug("e2e:ws:listen_start", "Starting to listen for events", {"timeout": timeout}, "H1,H5")
        print(f"\n  👂 Listening for events (timeout: {timeout}s)...")
        
        try:
            while time.time() - start_time < timeout:
                try:
                    # Wait for message with timeout
                    raw = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                    event = json.loads(raw)
                    
                    event_type = event.get("type", "unknown")
                    event_data = event.get("data", {})
                    
                    self.events.append(event)
                    
                    log_debug(
                        f"e2e:ws:event:{event_type}",
                        f"Received event: {event_type}",
                        {"event_type": event_type, "data_keys": list(event_data.keys()) if isinstance(event_data, dict) else "N/A"},
                        "H1,H5"
                    )
                    print(f"    📨 Event: {event_type}")
                    
                    # Check for final_result
                    if event_type == "final_result":
                        content = event_data.get("content", "")
                        self.final_result = content
                        log_debug("e2e:ws:final_result", "Got final_result!", {"content_len": len(content)}, "H5")
                        print(f"    🎯 final_result received! ({len(content)} chars)")
                        return True
                    
                    # Check for error
                    if event_type == "error":
                        error_msg = event_data.get("message", "Unknown error")
                        log_debug("e2e:ws:error", f"Error event: {error_msg}", {"error": error_msg}, "H1")
                        print(f"    ❌ Error: {error_msg}")
                        return False
                        
                except asyncio.TimeoutError:
                    # No message in 1 second, continue waiting
                    continue
                except websockets.ConnectionClosed:
                    log_debug("e2e:ws:closed", "WebSocket closed unexpectedly", {}, "H4")
                    print(f"    ⚠️ WebSocket closed")
                    return False
        
        except Exception as e:
            log_debug("e2e:ws:listen_error", f"Listen error: {e}", {"error": str(e)}, "H1")
            print(f"    ❌ Error: {e}")
            return False
        
        log_debug("e2e:ws:timeout", "Timeout waiting for final_result", {"events_count": len(self.events)}, "H1,H5")
        print(f"    ⏱️ Timeout! Received {len(self.events)} events but no final_result")
        return False
    
    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            log_debug("e2e:ws:close", "WebSocket closed", {}, "H4")


async def create_session() -> str:
    """Create a new session via REST API."""
    log_debug("e2e:api:create_session", "Creating session", {}, "H4")
    print("  🔧 Creating session...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/api/session/create")
        response.raise_for_status()
        data = response.json()
        session_id = data.get("session_id")
        
        log_debug("e2e:api:session_created", f"Session created: {session_id}", {"session_id": session_id}, "H4")
        print(f"  ✅ Session: {session_id}")
        return session_id


class TestE2EWebSocket:
    """E2E tests using WebSocket like frontend."""
    
    @pytest.mark.asyncio
    async def test_simple_message_returns_final_result(self):
        """
        Test: Simple message should return final_result event.
        
        This test mimics what the frontend does:
        1. Create session
        2. Connect WebSocket
        3. Send message
        4. Wait for final_result
        """
        print("\n" + "="*60)
        print("E2E TEST: Simple message via WebSocket")
        print("="*60)
        
        log_debug("e2e:test:start", "Starting E2E test", {"test": "simple_message"}, "H1,H3,H4,H5")
        
        # Step 1: Create session
        try:
            session_id = await create_session()
        except Exception as e:
            pytest.skip(f"Backend not running: {e}")
        
        # Step 2: Connect WebSocket
        client = WebSocketTestClient(session_id)
        try:
            await client.connect()
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
        
        try:
            # Step 3: Send message
            test_message = "привет"
            print(f"\n📝 Test message: '{test_message}'")
            await client.send_message(test_message)
            
            # Step 4: Wait for final_result
            success = await client.listen_for_events(timeout=TIMEOUT)
            
            # Report results
            print(f"\n📊 Results:")
            print(f"   Events received: {len(client.events)}")
            print(f"   Event types: {[e.get('type') for e in client.events]}")
            print(f"   final_result: {'✅ YES' if client.final_result else '❌ NO'}")
            
            if client.final_result:
                print(f"\n📄 Response ({len(client.final_result)} chars):")
                print(f"   {client.final_result[:200]}..." if len(client.final_result) > 200 else f"   {client.final_result}")
            
            log_debug("e2e:test:result", "Test completed", {
                "success": success,
                "events_count": len(client.events),
                "has_final_result": client.final_result is not None,
                "event_types": [e.get("type") for e in client.events]
            }, "H1,H5")
            
            # Assertions
            assert success, "Did not receive final_result event!"
            assert client.final_result, "final_result content is empty!"
            assert len(client.final_result) > 0, "Response is empty!"
            
            print("\n✅ TEST PASSED")
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_events_sequence(self):
        """
        Test: Check that events come in correct sequence.
        
        Expected for simple query:
        1. thinking_started
        2. thinking_completed
        3. final_result
        """
        print("\n" + "="*60)
        print("E2E TEST: Events sequence check")
        print("="*60)
        
        log_debug("e2e:test:sequence:start", "Starting sequence test", {}, "H1,H3")
        
        try:
            session_id = await create_session()
        except Exception as e:
            pytest.skip(f"Backend not running: {e}")
        
        client = WebSocketTestClient(session_id)
        await client.connect()
        
        try:
            await client.send_message("привет")
            await client.listen_for_events(timeout=TIMEOUT)
            
            event_types = [e.get("type") for e in client.events]
            print(f"\n📋 Event sequence: {event_types}")
            
            log_debug("e2e:test:sequence:events", "Event sequence", {"sequence": event_types}, "H1,H3")
            
            # Check key events
            assert "thinking_started" in event_types, "Missing thinking_started event"
            assert "final_result" in event_types, "Missing final_result event"
            
            # Check order: thinking_started should come before final_result
            thinking_idx = event_types.index("thinking_started")
            final_idx = event_types.index("final_result")
            assert thinking_idx < final_idx, "thinking_started should come before final_result"
            
            print("\n✅ TEST PASSED - Events in correct sequence")
            
        finally:
            await client.close()


# Direct run
if __name__ == "__main__":
    # Clear log file
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    
    print("🧪 E2E WebSocket Test")
    print("="*60)
    print("Make sure backend is running on localhost:8000")
    print("="*60)
    
    async def run():
        test = TestE2EWebSocket()
        try:
            await test.test_simple_message_returns_final_result()
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run())
    
    print("\n" + "="*60)
    print("📋 Debug log:", LOG_PATH)
    print("="*60)
