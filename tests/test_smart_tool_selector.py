"""
TDD tests for SmartToolSelector - Phase 1.2.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
# numpy не импортируем напрямую - используется через модули, которые делают lazy import

# Mock config before imports
import sys
import os
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

mock_config_obj = MagicMock()
mock_config_obj.openai_api_key = "test-key"
mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader

from src.core.action_provider import ActionCapability, CapabilityCategory, ProviderType


@pytest.fixture
def temp_cache_dir():
    """Create temporary directory for embedding cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_capabilities():
    """Create sample capabilities for testing."""
    return [
        ActionCapability(
            name="onec_get_salary_by_employee_month",
            description="Получить зарплату сотрудников из 1С по месяцам",
            category=CapabilityCategory.READ,
            provider_type=ProviderType.MCP_TOOL,
            input_schema={"from_date": "string", "to_date": "string"},
            service="onec"
        ),
        ActionCapability(
            name="create_presentation",
            description="Создать новую презентацию Google Slides",
            category=CapabilityCategory.WRITE,
            provider_type=ProviderType.MCP_TOOL,
            input_schema={"title": "string"},
            service="slides"
        ),
        ActionCapability(
            name="get_calendar_events",
            description="Получить события из календаря",
            category=CapabilityCategory.READ,
            provider_type=ProviderType.MCP_TOOL,
            input_schema={"start_time": "string"},
            service="calendar"
        ),
        ActionCapability(
            name="sheets_read_range",
            description="Прочитать диапазон из Google Sheets",
            category=CapabilityCategory.READ,
            provider_type=ProviderType.MCP_TOOL,
            input_schema={"spreadsheet_id": "string", "range": "string"},
            service="sheets"
        ),
    ]


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embeddings."""
    mock_client = MagicMock()
    
    # Different embeddings for different tool descriptions
    def create_embedding_side_effect(model, input):
        mock_response = MagicMock()
        # Simple mock: зарплата -> [0.1]*, презентация -> [0.2]*, календарь -> [0.3]*, таблица -> [0.4]*
        if "зарплат" in input.lower() or "salary" in input.lower():
            embedding = [0.1] * 1536
        elif "презентац" in input.lower() or "presentation" in input.lower() or "slides" in input.lower():
            embedding = [0.2] * 1536
        elif "календар" in input.lower() or "calendar" in input.lower():
            embedding = [0.3] * 1536
        elif "таблиц" in input.lower() or "sheets" in input.lower():
            embedding = [0.4] * 1536
        else:
            embedding = [0.5] * 1536
        
        mock_data = MagicMock()
        mock_data.embedding = embedding
        mock_response.data = [mock_data]
        return mock_response
    
    mock_client.embeddings.create = MagicMock(side_effect=create_embedding_side_effect)
    return mock_client


@pytest.fixture
def mock_openai_class(mock_openai_client):
    """Mock OpenAI class to return our mock client."""
    with patch('src.core.tool_selection.embedding_cache.OpenAI', return_value=mock_openai_client):
        yield mock_openai_client


def test_selector_finds_salary_tool_for_russian_query(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: 'выгрузи зарплату из 1С' -> onec_get_salary_by_employee_month.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    result = selector.select_tools(
        query="выгрузи зарплату из 1С",
        max_tools=5
    )
    
    # Should find salary tool
    tool_names = [cap.name for cap in result]
    assert "onec_get_salary_by_employee_month" in tool_names, "Should find salary tool for Russian query"


def test_selector_finds_slides_tools_for_presentation_query(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: 'создай красивую презентацию' -> slides tools.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    result = selector.select_tools(
        query="создай красивую презентацию",
        max_tools=5
    )
    
    # Should find slides tool
    tool_names = [cap.name for cap in result]
    assert "create_presentation" in tool_names, "Should find presentation tool for presentation query"


def test_selector_returns_max_n_tools(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: Selector возвращает не больше max_tools.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    result = selector.select_tools(
        query="работа с данными",
        max_tools=2
    )
    
    assert len(result) <= 2, f"Should return max 2 tools, got {len(result)}"


def test_selector_uses_cached_embeddings(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: При повторном запросе embeddings берутся из cache.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    # First call - should compute embeddings
    result1 = selector.select_tools(
        query="зарплата",
        max_tools=5
    )
    
    # Reset mock call count
    mock_openai_class.embeddings.create.reset_mock()
    
    # Second call - should use cached embeddings
    result2 = selector.select_tools(
        query="зарплата",
        max_tools=5
    )
    
    # OpenAI should NOT be called (cache hit)
    # Note: может быть вызван для query embedding, но не для tool embeddings
    # Проверяем что вызовов меньше чем capabilities
    call_count = mock_openai_class.embeddings.create.call_count
    assert call_count < len(sample_capabilities), "Should use cached embeddings for tools"


def test_selector_excludes_completed_tools(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: Уже выполненные tools исключаются из результата.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    # First call - get tools
    result1 = selector.select_tools(
        query="работа с данными",
        max_tools=5,
        completed_tools=[]
    )
    
    # Second call - exclude completed tool
    completed = [result1[0].name] if result1 else []
    result2 = selector.select_tools(
        query="работа с данными",
        max_tools=5,
        completed_tools=completed
    )
    
    # Completed tool should not be in result
    if completed:
        tool_names = [cap.name for cap in result2]
        assert completed[0] not in tool_names, "Completed tool should be excluded"


def test_selector_handles_empty_query(temp_cache_dir, sample_capabilities, mock_openai_class):
    """
    Test: Selector обрабатывает пустой запрос.
    
    ОЖИДАЕТСЯ: Провал - SmartToolSelector ещё не создан.
    """
    from src.core.tool_selection.smart_selector import SmartToolSelector
    
    selector = SmartToolSelector(
        capabilities=sample_capabilities,
        cache_dir=temp_cache_dir
    )
    
    result = selector.select_tools(
        query="",
        max_tools=5
    )
    
    # Should return some tools (fallback behavior)
    assert isinstance(result, list), "Should return list even for empty query"
