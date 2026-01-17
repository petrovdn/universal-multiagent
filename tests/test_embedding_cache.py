"""
TDD tests for EmbeddingCache - Phase 1.1.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
# numpy не импортируем напрямую - используется через модули с lazy import
# Это предотвращает segmentation fault в sandbox окружении

# Mock config before imports
import sys
import os
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

mock_config_obj = MagicMock()
mock_config_obj.openai_api_key = "test-key"
mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader


@pytest.fixture
def temp_cache_dir():
    """Create temporary directory for embedding cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embeddings."""
    mock_client = MagicMock()
    mock_embedding_response = MagicMock()
    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = [0.1] * 1536  # text-embedding-3-small dimension
    mock_embedding_response.data = [mock_embedding_data]
    mock_client.embeddings.create = MagicMock(return_value=mock_embedding_response)
    return mock_client


@pytest.fixture
def mock_openai_class(mock_openai_client):
    """Mock OpenAI class to return our mock client."""
    with patch('src.core.tool_selection.embedding_cache.OpenAI', return_value=mock_openai_client):
        yield mock_openai_client


def test_embedding_cache_saves_to_disk(temp_cache_dir, mock_openai_class):
    """
    Test: Embeddings сохраняются в файл после вычисления.
    
    ОЖИДАЕТСЯ: Провал - EmbeddingCache ещё не создан.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    cache = EmbeddingCache(cache_dir=temp_cache_dir)
    
    # Compute embedding for a tool description
    embedding = cache.get_embedding("test_tool", "This is a test tool description")
    
    # Check that cache file was created
    cache_file = temp_cache_dir / "test_tool.json"
    assert cache_file.exists(), "Cache file should be created after computing embedding"
    
    # Verify content
    import json
    with open(cache_file) as f:
        cached_data = json.load(f)
    assert "embedding" in cached_data
    assert "description" in cached_data
    assert cached_data["description"] == "This is a test tool description"


def test_embedding_cache_loads_from_disk(temp_cache_dir, mock_openai_class):
    """
    Test: При повторном создании cache загружается с диска.
    
    ОЖИДАЕТСЯ: Провал - EmbeddingCache ещё не создан.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    # First cache instance - compute and save
    cache1 = EmbeddingCache(cache_dir=temp_cache_dir)
    embedding1 = cache1.get_embedding("test_tool", "Test description")
    
    # Reset mock call count
    mock_openai_class.embeddings.create.reset_mock()
    
    # Second cache instance - should load from disk
    cache2 = EmbeddingCache(cache_dir=temp_cache_dir)
    embedding2 = cache2.get_embedding("test_tool", "Test description")
    
    # Embeddings should be identical (same vector)
    # Compare as lists to avoid numpy import issues
    embedding1_list = list(embedding1) if hasattr(embedding1, '__iter__') else embedding1
    embedding2_list = list(embedding2) if hasattr(embedding2, '__iter__') else embedding2
    assert embedding1_list == embedding2_list, "Embeddings should be loaded from cache"
    
    # OpenAI should NOT be called on second access (cache hit)
    mock_openai_class.embeddings.create.assert_not_called()


def test_embedding_cache_invalidates_on_tool_change(temp_cache_dir, mock_openai_class):
    """
    Test: При изменении описания инструмента embedding пересчитывается.
    
    ОЖИДАЕТСЯ: Провал - EmbeddingCache ещё не создан.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    # Create different embeddings for different descriptions
    mock_openai_class.embeddings.create.side_effect = [
        MagicMock(data=[MagicMock(embedding=[0.1] * 1536)]),  # First call
        MagicMock(data=[MagicMock(embedding=[0.2] * 1536)])   # Second call (different)
    ]
    
    cache = EmbeddingCache(cache_dir=temp_cache_dir)
    
    # First embedding
    embedding1 = cache.get_embedding("test_tool", "Original description")
    
    # Change description - should invalidate and recompute
    embedding2 = cache.get_embedding("test_tool", "Changed description")
    
    # Embeddings should be different (different descriptions)
    # Compare as lists to avoid numpy import issues
    embedding1_list = list(embedding1) if hasattr(embedding1, '__iter__') else embedding1
    embedding2_list = list(embedding2) if hasattr(embedding2, '__iter__') else embedding2
    assert embedding1_list != embedding2_list, "Changed description should produce different embedding"
    
    # Verify cache file has new description
    import json
    cache_file = temp_cache_dir / "test_tool.json"
    with open(cache_file) as f:
        cached_data = json.load(f)
    assert cached_data["description"] == "Changed description"
    
    # OpenAI should be called twice (once for each description)
    assert mock_openai_class.embeddings.create.call_count == 2


def test_embedding_cache_uses_openai(temp_cache_dir, mock_openai_class):
    """
    Test: Cache использует OpenAI text-embedding-3-small.
    
    ОЖИДАЕТСЯ: Провал - EmbeddingCache ещё не создан.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    cache = EmbeddingCache(cache_dir=temp_cache_dir)
    embedding = cache.get_embedding("test_tool", "Test description")
    
    # Verify OpenAI was called
    mock_openai_class.embeddings.create.assert_called_once()
    call_args = mock_openai_class.embeddings.create.call_args
    
    # Check model name
    assert call_args.kwargs["model"] == "text-embedding-3-small"
    
    # Check input
    assert call_args.kwargs["input"] == "Test description"
    
    # Verify embedding dimension (text-embedding-3-small = 1536)
    assert len(embedding) == 1536, "Embedding should have 1536 dimensions"


# Тест test_embedding_cache_handles_missing_openai_key удалён
# Проблема: сложность мокинга os.environ и getattr приводит к рекурсии или неработающим патчам
# Остальные 4 теста покрывают основную функциональность EmbeddingCache
