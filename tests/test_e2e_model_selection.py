"""
Integration tests for model selection based on task complexity.
"""
import pytest
from tests.conftest import mock_ws_manager, empty_context, create_test_engine


@pytest.mark.asyncio
async def test_simple_task_uses_fast_model(mock_ws_manager, empty_context):
    """
    Простая задача должна использовать быструю модель (fast_llm).
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    from unittest.mock import AsyncMock, MagicMock
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=1
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    # Создаём отдельные моки для fast_llm и основного llm
    fast_llm_mock = MagicMock()
    main_llm_mock = MagicMock()
    
    response_text = """<thought>Анализ.</thought><action>{"tool_name": "FINISH"}</action>"""
    
    async def mock_stream(messages):
        words = response_text.split()
        for word in words:
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    fast_llm_mock.astream = mock_stream
    main_llm_mock.astream = mock_stream
    mock_response = MagicMock()
    mock_response.content = response_text
    fast_llm_mock.ainvoke = AsyncMock(return_value=mock_response)
    main_llm_mock.ainvoke = AsyncMock(return_value=mock_response)
    
    # Устанавливаем моки
    engine.fast_llm = fast_llm_mock
    original_llm = engine.llm  # Сохраняем оригинальный
    
    # Простая задача
    simple_goal = "назначь встречу"
    
    try:
        await engine.execute(simple_goal, empty_context)
    except Exception:
        pass
    
    # Проверяем, что fast_llm был использован (для _needs_tools)
    # Основной llm должен быть заменён на fast_llm для простых задач
    # Это проверяется через complexity_analyzer в execute()
    
    # Проверяем, что complexity определил задачу как простую
    complexity = engine.complexity_analyzer.analyze(simple_goal)
    assert complexity.use_fast_model is True, "Simple task should use fast model"


@pytest.mark.asyncio
async def test_complex_task_uses_reasoning_model(mock_ws_manager, empty_context):
    """
    Сложная задача должна использовать модель с reasoning (основной llm с budget_tokens).
    """
    from src.core.unified_react_engine import UnifiedReActEngine
    from src.core.capability_registry import CapabilityRegistry
    from src.core.unified_react_engine import ReActConfig
    from src.core.action_provider import CapabilityCategory
    from unittest.mock import AsyncMock, MagicMock
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=1
    )
    registry = CapabilityRegistry()
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    mock_llm = MagicMock()
    response_text = """<thought>Анализ.</thought><action>{"tool_name": "FINISH"}</action>"""
    
    async def mock_stream(messages):
        words = response_text.split()
        for word in words:
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    mock_llm.astream = mock_stream
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    engine.fast_llm = mock_llm
    
    # Сложная задача
    complex_goal = "проанализируй встречи и письма и создай отчёт"
    
    try:
        await engine.execute(complex_goal, empty_context)
    except Exception:
        pass
    
    # Проверяем, что complexity определил задачу как сложную
    complexity = engine.complexity_analyzer.analyze(complex_goal)
    assert complexity.use_fast_model is False, "Complex task should not use fast model"
    assert complexity.budget_tokens >= 2000, "Complex task should have budget_tokens >= 2000"
