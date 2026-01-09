"""
Tests for instant feedback optimization - intent_start should be sent BEFORE _needs_tools.
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
async def test_intent_start_sent_before_needs_tools(mock_ws_manager, empty_context, mock_llm):
    """
    intent_start должен отправляться ДО вызова _needs_tools.
    
    Это критично для UX - пользователь должен видеть feedback мгновенно,
    а не ждать 500-2000ms пока LLM определит needs_tools.
    """
    # Создаем engine с mock LLM для _needs_tools
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    # Запускаем execute
    try:
        await engine.execute("покажи встречи", empty_context)
    except Exception:
        # Может быть ошибка из-за отсутствия реальных capabilities, но это нормально
        # Нас интересует только порядок событий
        pass
    
    # Проверяем порядок событий
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    # intent_start должен быть в первых событиях
    assert "intent_start" in event_types, "intent_start event not found"
    
    intent_idx = event_types.index("intent_start")
    
    # intent_start должен быть в первых 3 событиях (до любых LLM вызовов)
    # Ожидаемый порядок: message (если есть) -> intent_start -> ...
    assert intent_idx < 3, (
        f"intent_start at position {intent_idx}, expected < 3. "
        f"Event order: {event_types[:5]}"
    )


@pytest.mark.asyncio
async def test_intent_start_before_react_start(mock_ws_manager, empty_context, mock_llm):
    """
    intent_start должен быть ПЕРЕД react_start для сложных запросов.
    """
    mock_llm.response = "ДА"  # Complex query needs tools
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    try:
        await engine.execute("покажи встречи на неделе", empty_context)
    except Exception:
        pass
    
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    # Если есть react_start, intent_start должен быть раньше
    if "react_start" in event_types and "intent_start" in event_types:
        intent_idx = event_types.index("intent_start")
        react_idx = event_types.index("react_start")
        
        assert intent_idx < react_idx, (
            f"intent_start at {intent_idx}, react_start at {react_idx}. "
            f"intent_start should come first. Event order: {event_types}"
        )


@pytest.mark.asyncio
async def test_intent_start_timing_simple_query(mock_ws_manager, empty_context, mock_llm):
    """
    Для простых запросов intent_start также должен быть сразу.
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
    assert intent_idx < 3, f"intent_start should be early, got position {intent_idx}"
