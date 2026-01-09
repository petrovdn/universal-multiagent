"""
Tests for combined _think_and_plan method - объединённый вызов анализа и планирования.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from tests.conftest import mock_ws_manager, empty_context, create_test_engine


@pytest.mark.asyncio
async def test_returns_both_thought_and_plan(mock_ws_manager, empty_context):
    """
    _think_and_plan должен возвращать и thought, и action plan.
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.react_state import ReActState
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    
    # Создаём engine
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    # Мокаем LLM для возврата правильного формата
    mock_llm = MagicMock()
    mock_response = MagicMock()
    
    # Формируем ответ в формате <thought>...</thought><action>...</action>
    response_text = """<thought>
Анализирую задачу: нужно назначить встречу на завтра.
</thought>
<action>
{
    "tool_name": "create_event",
    "arguments": {"title": "Встреча", "start_time": "завтра 10:00"},
    "reasoning": "Создаю событие в календаре"
}
</action>"""
    
    mock_response.content = response_text
    
    # Мокаем стриминг
    async def mock_stream(messages):
        # Имитируем стриминг по частям
        chunks = response_text.split()
        for chunk in chunks:
            mock_chunk = MagicMock()
            mock_chunk.content = chunk + " "
            yield mock_chunk
    
    mock_llm.astream = mock_stream
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    # Заменяем LLM
    engine.llm = mock_llm
    
    # Создаём state
    state = ReActState(goal="назначь встречу на завтра")
    
    # Вызываем _think_and_plan
    thought, action_plan = await engine._think_and_plan(state, empty_context, [])
    
    # Проверяем результаты
    assert thought is not None, "Thought should not be None"
    assert len(thought) > 0, "Thought should not be empty"
    assert "Анализирую задачу" in thought or "встречу" in thought.lower(), (
        f"Thought should contain analysis. Got: {thought}"
    )
    
    assert action_plan is not None, "Action plan should not be None"
    assert isinstance(action_plan, dict), "Action plan should be a dict"
    assert "tool_name" in action_plan, "Action plan should contain tool_name"
    assert action_plan["tool_name"] == "create_event", (
        f"Expected tool_name='create_event', got {action_plan.get('tool_name')}"
    )


@pytest.mark.asyncio
async def test_streams_thought_while_processing(mock_ws_manager, empty_context):
    """
    _think_and_plan должен стримить thought по мере поступления.
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.react_state import ReActState
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    # Мокаем LLM для стриминга
    mock_llm = MagicMock()
    
    response_text = """<thought>
Анализирую задачу.
</thought>
<action>
{"tool_name": "create_event", "arguments": {}}
</action>"""
    
    async def mock_stream(messages):
        # Стримим по словам
        words = response_text.split()
        for word in words:
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    mock_llm.astream = mock_stream
    
    engine.llm = mock_llm
    
    state = ReActState(goal="назначь встречу")
    
    # Вызываем _think_and_plan
    await engine._think_and_plan(state, empty_context, [])
    
    # Проверяем, что были отправлены thinking события
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    # Должны быть thinking_started и thinking_chunk события
    assert "thinking_started" in event_types, "thinking_started event should be sent"
    
    # Проверяем наличие thinking_chunk событий
    thinking_chunks = [
        e for e in mock_ws_manager.events 
        if e["type"] == "thinking_chunk"
    ]
    assert len(thinking_chunks) > 0, "thinking_chunk events should be sent during streaming"


@pytest.mark.asyncio
async def test_fallback_on_parse_error(mock_ws_manager, empty_context):
    """
    _think_and_plan должен корректно обрабатывать ошибки парсинга.
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.react_state import ReActState
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    # Мокаем LLM для возврата некорректного формата
    mock_llm = MagicMock()
    mock_response = MagicMock()
    
    # Некорректный формат (нет тегов)
    response_text = "Просто текст без тегов"
    mock_response.content = response_text
    
    async def mock_stream(messages):
        words = response_text.split()
        for word in words:
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    mock_llm.astream = mock_stream
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    engine.llm = mock_llm
    
    state = ReActState(goal="назначь встречу")
    
    # Вызываем _think_and_plan - не должно падать
    try:
        thought, action_plan = await engine._think_and_plan(state, empty_context, [])
        
        # Должен вернуть fallback значения
        assert thought is not None, "Should return fallback thought"
        assert action_plan is not None, "Should return fallback action plan"
        
        # Action plan должен иметь tool_name (даже если fallback)
        assert "tool_name" in action_plan, "Action plan should have tool_name"
        
    except Exception as e:
        pytest.fail(f"_think_and_plan should handle parse errors gracefully, got: {e}")


@pytest.mark.asyncio
async def test_handles_malformed_json(mock_ws_manager, empty_context):
    """
    _think_and_plan должен обрабатывать некорректный JSON в action.
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.react_state import ReActState
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    mock_llm = MagicMock()
    mock_response = MagicMock()
    
    # Некорректный JSON
    response_text = """<thought>
Анализ задачи.
</thought>
<action>
{invalid json}
</action>"""
    
    mock_response.content = response_text
    
    async def mock_stream(messages):
        words = response_text.split()
        for word in words:
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    mock_llm.astream = mock_stream
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    engine.llm = mock_llm
    
    state = ReActState(goal="назначь встречу")
    
    # Не должно падать
    thought, action_plan = await engine._think_and_plan(state, empty_context, [])
    
    assert thought is not None
    assert action_plan is not None
    # Должен быть fallback action plan
    assert "tool_name" in action_plan
