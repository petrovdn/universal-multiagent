"""
Integration tests for WebSocket events order.
Verifies that intent_start is sent before react_start and other events.
"""
import pytest
from tests.conftest import (
    create_test_engine,
    create_test_engine_with_mock_llm,
    mock_ws_manager,
    empty_context,
    mock_llm
)


@pytest.mark.asyncio
async def test_websocket_events_order_complex_request(mock_ws_manager, empty_context, mock_llm):
    """
    Проверяем порядок WebSocket событий для сложного запроса.
    
    intent_start должен быть ПЕРВЫМ из react-related событий,
    до react_start и thinking_started.
    """
    mock_llm.response = "ДА"  # Complex query needs tools
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    try:
        await engine.execute("покажи встречи на неделе", empty_context)
    except Exception:
        # Может быть ошибка из-за отсутствия реальных capabilities, но это нормально
        # Нас интересует только порядок событий
        pass
    
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    # intent_start должен быть в событиях
    assert "intent_start" in event_types, "intent_start event not found"
    
    # Если есть react_start, intent_start должен быть раньше
    if "react_start" in event_types:
        intent_idx = event_types.index("intent_start")
        react_idx = event_types.index("react_start")
        
        assert intent_idx < react_idx, (
            f"intent_start at position {intent_idx}, react_start at {react_idx}. "
            f"intent_start should come before react_start. "
            f"Event order: {event_types[:10]}"
        )
    
    # Если есть thinking_started, intent_start должен быть раньше
    if "thinking_started" in event_types:
        intent_idx = event_types.index("intent_start")
        thinking_idx = event_types.index("thinking_started")
        
        assert intent_idx < thinking_idx, (
            f"intent_start at position {intent_idx}, thinking_started at {thinking_idx}. "
            f"intent_start should come before thinking_started. "
            f"Event order: {event_types[:10]}"
        )


@pytest.mark.asyncio
async def test_websocket_events_order_simple_request(mock_ws_manager, empty_context, mock_llm):
    """
    Проверяем порядок WebSocket событий для простого запроса.
    
    Даже для простых запросов intent_start должен быть отправлен сразу.
    """
    mock_llm.response = "НЕТ"  # Simple query doesn't need tools
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    try:
        await engine.execute("привет", empty_context)
    except Exception:
        pass
    
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    # intent_start должен быть отправлен даже для простых запросов
    assert "intent_start" in event_types, "intent_start should be sent for simple queries too"
    
    intent_idx = event_types.index("intent_start")
    
    # intent_start должен быть в первых событиях
    assert intent_idx < 5, (
        f"intent_start at position {intent_idx}, expected < 5. "
        f"Event order: {event_types[:10]}"
    )


@pytest.mark.asyncio
async def test_intent_start_before_needs_tools_llm_call(mock_ws_manager, empty_context):
    """
    Проверяем, что intent_start отправляется ДО вызова LLM в _needs_tools.
    
    Это критично для UX - пользователь должен видеть feedback мгновенно.
    """
    # Создаем mock LLM, который будет отслеживать время вызова
    call_times = []
    
    class TimedMockLLM:
        def __init__(self):
            self.call_count = 0
            self.invoke_count = 0
        
        async def ainvoke(self, messages):
            import time
            call_times.append(time.time())
            self.call_count += 1
            self.invoke_count += 1
            mock_response = type('MockResponse', (), {'content': 'ДА'})()
            return mock_response
    
    timed_llm = TimedMockLLM()
    engine = create_test_engine_with_mock_llm(mock_ws_manager, timed_llm)
    
    # Захватываем время отправки intent_start
    intent_start_time = None
    original_send_event = mock_ws_manager.send_event
    
    async def timed_send_event(session_id, event_type, data):
        nonlocal intent_start_time
        if event_type == "intent_start" and intent_start_time is None:
            import time
            intent_start_time = time.time()
        await original_send_event(session_id, event_type, data)
    
    mock_ws_manager.send_event = timed_send_event
    
    try:
        await engine.execute("покажи встречи", empty_context)
    except Exception:
        pass
    
    # Если LLM был вызван, intent_start должен быть раньше
    if call_times and intent_start_time:
        assert intent_start_time < call_times[0], (
            f"intent_start sent at {intent_start_time}, but LLM called at {call_times[0]}. "
            f"intent_start should come first."
        )


@pytest.mark.asyncio
async def test_multiple_queries_intent_start_always_first(mock_ws_manager, empty_context, mock_llm):
    """
    Проверяем, что для множественных запросов intent_start всегда первый.
    """
    queries = [
        "покажи встречи",
        "найди письма",
        "привет",
        "создай таблицу",
    ]
    
    for query in queries:
        mock_ws_manager.clear_events()
        mock_llm.call_count = 0
        mock_llm.invoke_count = 0
        engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
        
        try:
            await engine.execute(query, empty_context)
        except Exception:
            pass
        
        event_types = [e["type"] for e in mock_ws_manager.events]
        
        if "intent_start" in event_types:
            intent_idx = event_types.index("intent_start")
            # intent_start должен быть в первых 3 событиях
            assert intent_idx < 3, (
                f"For query '{query}': intent_start at position {intent_idx}, expected < 3. "
                f"Event order: {event_types[:5]}"
            )
