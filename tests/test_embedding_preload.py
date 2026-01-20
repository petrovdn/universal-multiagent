"""
Tests для preload embeddings в память.
Проверяет что EmbeddingCache может предзагружать embeddings для быстрого доступа.
"""
import sys
import time
from pathlib import Path
import tempfile
import json
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.tool_selection.embedding_cache import EmbeddingCache


def create_mock_embedding_cache(tmp_dir):
    """Создать тестовый кеш с несколькими embeddings."""
    cache_dir = Path(tmp_dir) / "tool_embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаём несколько тестовых embeddings
    test_tools = [
        {"name": "test_tool_1", "description": "Test tool 1 description"},
        {"name": "test_tool_2", "description": "Test tool 2 description"},
        {"name": "test_tool_3", "description": "Test tool 3 description"},
    ]
    
    for tool in test_tools:
        # Создаём mock embedding (1536 floats)
        mock_embedding = np.random.rand(1536).astype(np.float32).tolist()
        
        cache_file = cache_dir / f"{tool['name']}.json"
        cache_data = {
            "tool_name": tool['name'],
            "description": tool['description'],
            "embedding": mock_embedding,
            "model": "text-embedding-3-small",
            "dimension": 1536
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    
    return cache_dir


def test_embedding_cache_has_preload_parameter():
    """Test: EmbeddingCache должен иметь параметр preload_embeddings"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = create_mock_embedding_cache(tmpdir)
        
        # Проверяем что параметр существует
        try:
            cache = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=False)
            assert hasattr(cache, '_memory_embeddings')
            print("✅ test_embedding_cache_has_preload_parameter PASSED")
        except TypeError as e:
            if "preload_embeddings" in str(e):
                print(f"❌ test_embedding_cache_has_preload_parameter FAILED: {e}")
                raise
            else:
                raise


def test_embedding_cache_preloads_to_memory():
    """Test: EmbeddingCache preload должен загрузить embeddings в память"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = create_mock_embedding_cache(tmpdir)
        
        # Создаём cache с preload
        cache = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=True)
        
        assert hasattr(cache, '_memory_embeddings')
        assert len(cache._memory_embeddings) > 0
        
        print(f"✅ test_embedding_cache_preloads_to_memory PASSED (preloaded {len(cache._memory_embeddings)} embeddings)")


def test_preloaded_embeddings_are_accessible():
    """Test: Preloaded embeddings должны быть доступны через get_embedding"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = create_mock_embedding_cache(tmpdir)
        
        cache = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=True)
        
        # Проверяем что можем получить embedding из памяти
        embedding = cache.get_embedding("test_tool_1", "Test tool 1 description")
        
        assert embedding is not None
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1536,)
        print("✅ test_preloaded_embeddings_are_accessible PASSED")


def test_preloaded_embeddings_are_fast():
    """Test: Доступ к preloaded embeddings должен быть < 1ms"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = create_mock_embedding_cache(tmpdir)
        
        cache = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=True)
        
        # Warm up
        _ = cache.get_embedding("test_tool_1", "Test tool 1 description")
        
        # Measure access time
        start = time.time()
        for _ in range(10):
            _ = cache.get_embedding("test_tool_1", "Test tool 1 description")
        duration = (time.time() - start) * 1000  # ms
        
        avg_time = duration / 10
        assert avg_time < 1.0, f"Too slow: {avg_time:.3f}ms per access"
        print(f"✅ test_preloaded_embeddings_are_fast PASSED ({avg_time:.3f}ms avg)")


def test_preload_vs_no_preload_comparison():
    """Test: Preload должен быть значительно быстрее чем disk I/O"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = create_mock_embedding_cache(tmpdir)
        
        # With preload
        cache_preload = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=True)
        start = time.time()
        for _ in range(10):
            cache_preload.get_embedding("test_tool_1", "Test tool 1 description")
        preload_time = time.time() - start
        
        # Without preload (simulate - но на самом деле тоже будет в памяти после первого вызова)
        # Но первый вызов будет медленнее
        cache_no_preload = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=False)
        start = time.time()
        # Первый вызов (disk I/O)
        cache_no_preload.get_embedding("test_tool_2", "Test tool 2 description")
        first_call_time = time.time() - start
        
        # Последующие вызовы (уже в памяти)
        start = time.time()
        for _ in range(9):
            cache_no_preload.get_embedding("test_tool_2", "Test tool 2 description")
        subsequent_time = time.time() - start
        
        # Preload должен быть быстрее первого вызова
        speedup = first_call_time / (preload_time / 10)
        assert speedup > 1, f"Preload should be faster, but speedup is {speedup:.2f}x"
        print(f"✅ test_preload_vs_no_preload_comparison PASSED (speedup: {speedup:.2f}x)")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ EmbeddingCache preload")
    print("=" * 70)
    
    try:
        test_embedding_cache_has_preload_parameter()
        test_embedding_cache_preloads_to_memory()
        test_preloaded_embeddings_are_accessible()
        test_preloaded_embeddings_are_fast()
        test_preload_vs_no_preload_comparison()
        
        print("=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
