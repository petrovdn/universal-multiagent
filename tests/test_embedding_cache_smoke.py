"""
Smoke test for EmbeddingCache - проверка без numpy (для sandbox окружения).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Mock config before imports
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
    mock_embedding_data.embedding = [0.1] * 1536
    mock_embedding_response.data = [mock_embedding_data]
    mock_client.embeddings.create = MagicMock(return_value=mock_embedding_response)
    return mock_client


@pytest.fixture
def mock_openai_class(mock_openai_client):
    """Mock OpenAI class."""
    with patch('src.core.tool_selection.embedding_cache.OpenAI', return_value=mock_openai_client):
        yield mock_openai_client


def test_embedding_cache_basic_functionality(temp_cache_dir, mock_openai_class):
    """
    Smoke test: базовая функциональность EmbeddingCache.
    Проверяет что класс создаётся и может сохранять/загружать embeddings.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    # Create cache
    cache = EmbeddingCache(cache_dir=temp_cache_dir)
    
    # Get embedding (should compute and save)
    embedding = cache.get_embedding("test_tool", "Test description")
    
    # Check that embedding is returned
    assert embedding is not None
    assert len(embedding) == 1536, "Embedding should have 1536 dimensions"
    
    # Check that cache file was created
    cache_file = temp_cache_dir / "test_tool.json"
    assert cache_file.exists(), "Cache file should be created"
    
    # Verify cache content
    with open(cache_file) as f:
        cached_data = json.load(f)
    assert cached_data["description"] == "Test description"
    assert "embedding" in cached_data
    assert len(cached_data["embedding"]) == 1536
    
    # Verify OpenAI was called
    mock_openai_class.embeddings.create.assert_called_once()
    call_args = mock_openai_class.embeddings.create.call_args
    assert call_args.kwargs["model"] == "text-embedding-3-small"


def test_embedding_cache_reloads_from_disk(temp_cache_dir, mock_openai_class):
    """
    Smoke test: кэш загружается с диска при повторном использовании.
    """
    from src.core.tool_selection.embedding_cache import EmbeddingCache
    
    # First instance - compute and save
    cache1 = EmbeddingCache(cache_dir=temp_cache_dir)
    embedding1 = cache1.get_embedding("test_tool", "Test description")
    
    # Reset mock
    mock_openai_class.embeddings.create.reset_mock()
    
    # Second instance - should load from disk
    cache2 = EmbeddingCache(cache_dir=temp_cache_dir)
    embedding2 = cache2.get_embedding("test_tool", "Test description")
    
    # Should have same length
    assert len(embedding1) == len(embedding2)
    
    # OpenAI should NOT be called (cache hit)
    mock_openai_class.embeddings.create.assert_not_called()
