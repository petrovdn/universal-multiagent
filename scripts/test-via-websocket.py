#!/usr/bin/env python3
"""
Скрипт для тестирования Smart Tool Selection через WebSocket.

Использование:
    python3 scripts/test-via-websocket.py "создай красивую презентацию"
"""
import asyncio
import websockets
import json
import sys
import time
from typing import Optional

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
TIMEOUT = 60  # seconds


async def create_session() -> str:
    """Создать сессию через REST API."""
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/api/sessions")
        if response.status_code == 200:
            data = response.json()
            return data.get("session_id", "test-session")
        else:
            raise Exception(f"Failed to create session: {response.status_code}")


async def test_smart_selection(query: str):
    """Тестировать smart tool selection через WebSocket."""
    print(f"\n{'='*60}")
    print(f"🧪 Тест Smart Tool Selection")
    print(f"{'='*60}")
    print(f"Запрос: {query}")
    print(f"Ожидаем: slides-formatting skill должен быть выбран")
    print(f"{'='*60}\n")
    
    try:
        # Создаём сессию
        print("1️⃣  Создание сессии...")
        session_id = await create_session()
        print(f"   ✅ Сессия создана: {session_id}")
    except Exception as e:
        print(f"   ❌ Ошибка создания сессии: {e}")
        print(f"   💡 Убедитесь что backend запущен: python3 -m uvicorn src.api.server:app --reload")
        return
    
    # Подключаемся к WebSocket
    uri = f"{WS_BASE}/ws/{session_id}"
    print(f"\n2️⃣  Подключение к WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as ws:
            print("   ✅ Подключено")
            
            # Отправляем сообщение
            print(f"\n3️⃣  Отправка запроса...")
            await ws.send(json.dumps({
                "type": "message",
                "content": query
            }))
            print(f"   ✅ Запрос отправлен")
            
            # Слушаем события
            print(f"\n4️⃣  Ожидание ответа (timeout: {TIMEOUT}s)...")
            print("   События:")
            
            events_received = []
            start_time = time.time()
            skill_selected = False
            tools_selected = []
            
            try:
                async for message in ws:
                    elapsed = time.time() - start_time
                    if elapsed > TIMEOUT:
                        print(f"\n   ⏱️  Timeout ({TIMEOUT}s)")
                        break
                    
                    data = json.loads(message)
                    event_type = data.get("type")
                    events_received.append(event_type)
                    
                    # Выводим события
                    if event_type == "thinking_started":
                        print(f"   🧠 thinking_started")
                    elif event_type == "thinking_completed":
                        print(f"   ✅ thinking_completed")
                    elif event_type == "tool_call":
                        tool_name = data.get("data", {}).get("tool_name", "unknown")
                        tools_selected.append(tool_name)
                        print(f"   🔧 tool_call: {tool_name}")
                    elif event_type == "final_result":
                        content = data.get("data", {}).get("content", "")
                        print(f"   📝 final_result: {content[:100]}...")
                        break
                    elif event_type == "error":
                        error = data.get("data", {}).get("error", "Unknown error")
                        print(f"   ❌ error: {error}")
                        break
                    else:
                        print(f"   📨 {event_type}")
            
            except websockets.exceptions.ConnectionClosed:
                print("   ⚠️  Соединение закрыто")
            
            # Анализ результатов
            print(f"\n{'='*60}")
            print("📊 Результаты:")
            print(f"{'='*60}")
            print(f"События получены: {len(events_received)}")
            print(f"Последовательность: {' → '.join(events_received)}")
            
            if tools_selected:
                print(f"\n🔧 Выбранные инструменты:")
                for tool in tools_selected:
                    print(f"   - {tool}")
                
                # Проверяем что выбраны slides инструменты
                slides_tools = [t for t in tools_selected if "presentation" in t.lower() or "slide" in t.lower()]
                if slides_tools:
                    print(f"\n✅ Slides инструменты выбраны: {slides_tools}")
                else:
                    print(f"\n⚠️  Slides инструменты не выбраны (возможно keyword-based selection)")
            else:
                print(f"\n⚠️  Инструменты не были вызваны (возможно простой запрос)")
            
            print(f"\n💡 Проверьте логи backend на наличие:")
            print(f"   - [UnifiedReActEngine] Smart tool selection enabled")
            print(f"   - [SkillSelector] Selected skill 'slides-formatting'")
            print(f"   - [SmartToolSelector] Selected X tools")
            
    except websockets.exceptions.InvalidURI:
        print(f"   ❌ Неверный URI: {uri}")
        print(f"   💡 Убедитесь что backend запущен на порту 8000")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")


if __name__ == "__main__":
    # Запрос из аргументов или по умолчанию
    query = sys.argv[1] if len(sys.argv) > 1 else "создай красивую презентацию про искусственный интеллект"
    
    # Проверка что backend доступен
    import httpx
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=2)
        if response.status_code != 200:
            print("⚠️  Backend не отвечает на /health")
    except:
        print("❌ Backend не доступен на http://localhost:8000")
        print("💡 Запустите backend:")
        print("   USE_SMART_TOOL_SELECTION=true python3 -m uvicorn src.api.server:app --reload")
        sys.exit(1)
    
    # Запуск теста
    asyncio.run(test_smart_selection(query))
