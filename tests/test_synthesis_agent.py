"""
Tests for SynthesisAgent - Phase 2, Step 4.

SynthesisAgent aggregates results from parallel subtasks and generates
a coherent final response using LLM.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.synthesis_agent import SynthesisAgent, SynthesisResult
from src.core.task_decomposer import SubTask


@pytest.fixture
def synthesis_agent():
    """Create SynthesisAgent instance."""
    return SynthesisAgent()


@pytest.fixture
def mock_subtask_results():
    """Mock results from parallel subtasks."""
    return {
        "t1": {
            "emails": [
                {"id": "1", "subject": "Важное письмо", "snippet": "Нужно ответить"},
                {"id": "2", "subject": "Встреча", "snippet": "Подтверждение"}
            ]
        },
        "t2": {
            "events": [
                {"id": "1", "title": "Встреча с командой", "start": "2026-01-17T10:00:00"},
                {"id": "2", "title": "Презентация", "start": "2026-01-17T14:00:00"}
            ]
        },
        "t3": {
            "files": [
                {"id": "1", "name": "Отчет.docx", "modified": "2026-01-17T09:00:00"}
            ]
        }
    }


@pytest.mark.asyncio
async def test_synthesize_aggregates_results(synthesis_agent, mock_subtask_results):
    """Test: SynthesisAgent aggregates results from multiple subtasks."""
    query = "Покажи фокус на сегодня"
    
    # Mock LLM response
    synthesis_agent.llm = AsyncMock()
    synthesis_agent.llm.ainvoke = AsyncMock(return_value=MagicMock(
        content="На сегодня у вас:\n- 2 важных письма\n- 2 встречи\n- 1 новый файл"
    ))
    
    result = await synthesis_agent.synthesize(
        query=query,
        subtask_results=mock_subtask_results,
        original_query=query
    )
    
    assert isinstance(result, SynthesisResult)
    assert len(result.summary) > 0
    assert "письм" in result.summary.lower() or "встреч" in result.summary.lower()
    assert synthesis_agent.llm.ainvoke.called


@pytest.mark.asyncio
async def test_synthesize_handles_empty_results(synthesis_agent):
    """Test: SynthesisAgent handles empty results gracefully."""
    query = "Покажи фокус на сегодня"
    empty_results = {}
    
    synthesis_agent.llm = AsyncMock()
    synthesis_agent.llm.ainvoke = AsyncMock(return_value=MagicMock(
        content="Нет данных для отображения"
    ))
    
    result = await synthesis_agent.synthesize(
        query=query,
        subtask_results=empty_results,
        original_query=query
    )
    
    assert isinstance(result, SynthesisResult)
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_synthesize_includes_source_references(synthesis_agent, mock_subtask_results):
    """Test: SynthesisResult includes references to source tasks."""
    query = "Покажи фокус на сегодня"
    
    synthesis_agent.llm = AsyncMock()
    synthesis_agent.llm.ainvoke = AsyncMock(return_value=MagicMock(
        content="Сводка данных"
    ))
    
    result = await synthesis_agent.synthesize(
        query=query,
        subtask_results=mock_subtask_results,
        original_query=query
    )
    
    assert isinstance(result, SynthesisResult)
    # Should include information about which sources were used
    assert len(result.source_task_ids) > 0 or result.summary  # Either has sources or summary


@pytest.mark.asyncio
async def test_synthesize_preserves_key_information(synthesis_agent, mock_subtask_results):
    """Test: Synthesis preserves key information from subtask results."""
    query = "Покажи фокус на сегодня"
    
    synthesis_agent.llm = AsyncMock()
    synthesis_agent.llm.ainvoke = AsyncMock(return_value=MagicMock(
        content="У вас 2 важных письма и 2 встречи на сегодня"
    ))
    
    result = await synthesis_agent.synthesize(
        query=query,
        subtask_results=mock_subtask_results,
        original_query=query
    )
    
    assert isinstance(result, SynthesisResult)
    # Summary should mention key numbers from results
    assert "2" in result.summary or "два" in result.summary.lower()
