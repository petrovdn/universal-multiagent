"""
EmbeddingCache - кэширование embeddings инструментов на диск.

Zero-waste подход: embeddings вычисляются один раз и сохраняются для повторного использования.
"""
import json
import os
from pathlib import Path
from typing import Optional, List
# Lazy import numpy to avoid segmentation fault in sandbox
from openai import OpenAI
from src.utils.config_loader import get_config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """
    Кэш для embeddings инструментов.
    
    Сохраняет embeddings на диск для избежания повторных вызовов OpenAI API.
    Автоматически инвалидирует кэш при изменении описания инструмента.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Инициализация EmbeddingCache.
        
        Args:
            cache_dir: Директория для кэша (по умолчанию: data/tool_embeddings)
        """
        if cache_dir is None:
            from src.utils.config_loader import DATA_DIR
            cache_dir = DATA_DIR / "tool_embeddings"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize OpenAI client
        config = get_config()
        api_key = getattr(config, 'openai_api_key', None) or os.environ.get('OPENAI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or configure in config/.env"
            )
        
        self.client = OpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"
        self.dimension = 1536  # text-embedding-3-small dimension
    
    def _get_cache_path(self, tool_name: str) -> Path:
        """Получить путь к файлу кэша для инструмента."""
        # Sanitize tool name for filesystem
        safe_name = tool_name.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_name}.json"
    
    def _compute_embedding(self, text: str):
        """
        Вычислить embedding через OpenAI API.
        
        Args:
            text: Текст для embedding
            
        Returns:
            numpy array с embedding вектором
        """
        import numpy as np
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"[EmbeddingCache] Failed to compute embedding: {e}")
            raise
    
    def _save_to_cache(self, tool_name: str, description: str, embedding):
        """
        Сохранить embedding в кэш.
        
        Args:
            tool_name: Имя инструмента
            description: Описание инструмента
            embedding: Embedding вектор
        """
        cache_path = self._get_cache_path(tool_name)
        cache_data = {
            "tool_name": tool_name,
            "description": description,
            "embedding": embedding.tolist(),  # Convert numpy to list for JSON
            "model": self.model,
            "dimension": self.dimension
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[EmbeddingCache] Saved embedding for {tool_name} to {cache_path}")
    
    def _load_from_cache(self, tool_name: str) -> Optional[dict]:
        """
        Загрузить embedding из кэша.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            Словарь с данными кэша или None если не найден
        """
        cache_path = self._get_cache_path(tool_name)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            return cache_data
        except Exception as e:
            logger.warning(f"[EmbeddingCache] Failed to load cache for {tool_name}: {e}")
            return None
    
    def _is_cache_valid(self, cached_data: dict, description: str) -> bool:
        """
        Проверить валидность кэша.
        
        Кэш валиден если:
        1. Описание совпадает
        2. Модель совпадает
        
        Args:
            cached_data: Данные из кэша
            description: Текущее описание инструмента
            
        Returns:
            True если кэш валиден
        """
        if cached_data.get("description") != description:
            return False
        
        if cached_data.get("model") != self.model:
            return False
        
        return True
    
    def get_embedding(self, tool_name: str, description: str):
        """
        Получить embedding для инструмента.
        
        Если embedding есть в кэше и валиден - возвращает из кэша.
        Иначе вычисляет через OpenAI и сохраняет в кэш.
        
        Args:
            tool_name: Имя инструмента
            description: Описание инструмента
            
        Returns:
            numpy array с embedding вектором
        """
        # Try to load from cache
        cached_data = self._load_from_cache(tool_name)
        
        if cached_data and self._is_cache_valid(cached_data, description):
            # Cache hit - return cached embedding
            import numpy as np
            embedding_list = cached_data["embedding"]
            embedding = np.array(embedding_list, dtype=np.float32)
            logger.debug(f"[EmbeddingCache] Cache hit for {tool_name}")
            return embedding
        
        # Cache miss or invalid - compute new embedding
        logger.debug(f"[EmbeddingCache] Computing embedding for {tool_name}")
        embedding = self._compute_embedding(description)
        
        # Save to cache
        self._save_to_cache(tool_name, description, embedding)
        
        return embedding
    
    def invalidate_cache(self, tool_name: str):
        """
        Удалить кэш для инструмента.
        
        Args:
            tool_name: Имя инструмента
        """
        cache_path = self._get_cache_path(tool_name)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"[EmbeddingCache] Invalidated cache for {tool_name}")
    
    def clear_cache(self):
        """Очистить весь кэш."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        logger.info(f"[EmbeddingCache] Cleared all cache files from {self.cache_dir}")
