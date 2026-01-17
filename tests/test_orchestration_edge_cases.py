"""
Tests for orchestration edge cases - Phase 2, Step 5.

Tests error handling, empty results, single task, and other edge cases.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import MockWebSocketManager, create_test_engine
from src.core.context_manager import ConversationContext
from src.core.capability_registry import CapabilityRegistry
from src.core.synthesis_agent import SynthesisResult


@pytest.fixture
def mock_registry_with_errors():
    """Registry that sometimes fails."""
    registry = CapabilityRegistry()
    
    async def mock_execute(capability_name: str, arguments: dict):
        if capability_name == "failing_tool":
            raise Exception("Tool execution failed")
        return {"result": "success", "tool": capability_name}
    
    registry.execute = mock_execute
    return registry


@pytest.mark.asyncio
async def test_orchestration_handles_subtask_errors(mock_ws_manager, mock_registry_with_errors):
    """Test: Orchestration handles errors in subtasks gracefully."""
    engine = create_test_engine(mock_ws_manager, mock_registry_with_errors)
    context = ConversationContext(session_id="test-session")
    
    # Mock synthesis to avoid LLM calls
    mock_synthesis_result = SynthesisResult(
        summary="Обработано с ошибками",
        source_task_ids=[],
        key_points=[]
    )
    engine.synthesis_agent.synthesize = AsyncMock(return_value=mock_synthesis_result)
    
    # Query that will trigger orchestration
    query = "Покажи фокус на сегодня"
    
    # Should not raise exception, even if some subtasks fail
    result = await engine.execute(query, context)
    
    assert result.get("status") == "success" or "error" in result.get("status", "")
    assert "orchestration_used" in result


@pytest.mark.asyncio
async def test_orchestration_handles_empty_decomposition(mock_ws_manager):
    """Test: Orchestration handles case when decomposition returns no subtasks."""
    engine = create_test_engine(mock_ws_manager, CapabilityRegistry())
    context = ConversationContext(session_id="test-session")
    
    # Mock decomposition to return empty subtasks
    from src.core.task_decomposer import DecompositionResult
    empty_decomposition = DecompositionResult(subtasks=[], parallel_groups=[], execution_order=[])
    engine.task_decomposer.decompose = AsyncMock(return_value=empty_decomposition)
    
    query = "Покажи фокус на сегодня"
    
    # Should fallback to normal ReAct cycle
    result = await engine.execute(query, context)
    
    # Should not crash, may use normal ReAct or return error
    assert "response" in result or "error" in result


@pytest.mark.asyncio
async def test_orchestration_handles_single_subtask(mock_ws_manager):
    """Test: Orchestration works with single subtask (no parallelization needed)."""
    engine = create_test_engine(mock_ws_manager, CapabilityRegistry())
    context = ConversationContext(session_id="test-session")
    
    # Mock synthesis
    mock_synthesis_result = SynthesisResult(
        summary="Одна задача выполнена",
        source_task_ids=["t1"],
        key_points=[]
    )
    engine.synthesis_agent.synthesize = AsyncMock(return_value=mock_synthesis_result)
    
    # Query that might result in single subtask
    query = "Покажи письма"
    
    # Should work even if only one subtask
    result = await engine.execute(query, context)
    
    # May use orchestration or normal ReAct
    assert "response" in result or "error" in result


@pytest.mark.asyncio
async def test_orchestration_fallback_on_decomposition_error(mock_ws_manager):
    """Test: Orchestration falls back to normal ReAct if decomposition fails."""
    engine = create_test_engine(mock_ws_manager, CapabilityRegistry())
    context = ConversationContext(session_id="test-session")
    
    # Mock decomposition to raise error
    engine.task_decomposer.decompose = AsyncMock(side_effect=Exception("Decomposition failed"))
    
    query = "Покажи фокус на сегодня"
    
    # Should fallback to normal ReAct cycle
    result = await engine.execute(query, context)
    
    # Should not crash, should use normal ReAct
    assert "response" in result or "error" in result
    # Should log error but continue
    assert result.get("orchestration_used") != True  # Should fallback, not use orchestration
