"""
SmartToolSelector - semantic search для выбора релевантных инструментов.

Использует embeddings для семантического поиска вместо keyword matching.
Основано на подходе RAG-MCP и AnyTool.
"""
from typing import List, Optional
from pathlib import Path
# Lazy import numpy to avoid segmentation fault in sandbox
from src.core.action_provider import ActionCapability
from src.core.tool_selection.embedding_cache import EmbeddingCache
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def cosine_similarity(a, b) -> float:
    """
    Вычислить cosine similarity между двумя векторами.
    
    Args:
        a: Первый вектор (np.ndarray или list)
        b: Второй вектор (np.ndarray или list)
        
    Returns:
        Cosine similarity (0-1)
    """
    import numpy as np
    
    # Convert to numpy arrays if needed
    if not isinstance(a, np.ndarray):
        a = np.array(a)
    if not isinstance(b, np.ndarray):
        b = np.array(b)
    
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


class SmartToolSelector:
    """
    Smart tool selector using semantic search.
    
    Использует embeddings для поиска релевантных инструментов по запросу пользователя.
    """
    
    def __init__(
        self,
        capabilities: List[ActionCapability],
        cache_dir: Optional[Path] = None
    ):
        """
        Инициализация SmartToolSelector.
        
        Args:
            capabilities: Список доступных capabilities
            cache_dir: Директория для кэша embeddings (опционально)
        """
        self.capabilities = capabilities
        self.embedding_cache = EmbeddingCache(cache_dir=cache_dir)
        logger.info(f"[SmartToolSelector] Initialized with {len(capabilities)} capabilities")
    
    def select_tools(
        self,
        query: str,
        max_tools: int = 7,
        completed_tools: Optional[List[str]] = None
    ) -> List[ActionCapability]:
        """
        Выбрать релевантные инструменты для запроса.
        
        Args:
            query: Запрос пользователя
            max_tools: Максимальное количество инструментов
            completed_tools: Список уже выполненных инструментов (исключаются)
            
        Returns:
            Список релевантных ActionCapability, отсортированных по релевантности
        """
        if not query or not query.strip():
            # Fallback: возвращаем первые max_tools
            return self.capabilities[:max_tools]
        
        if completed_tools is None:
            completed_tools = []
        
        # Исключаем уже выполненные инструменты
        available_caps = [
            cap for cap in self.capabilities
            if cap.name not in completed_tools
        ]
        
        if not available_caps:
            logger.warning("[SmartToolSelector] No available capabilities after filtering")
            return []
        
        # Получаем embedding для запроса
        # Используем хэш запроса как имя для кэширования
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        query_embedding = self.embedding_cache.get_embedding(
            tool_name=f"__query_{query_hash}__",
            description=query
        )
        
        # Вычисляем similarity для каждого инструмента
        similarities = []
        for cap in available_caps:
            # Получаем embedding для описания инструмента
            tool_embedding = self.embedding_cache.get_embedding(
                tool_name=cap.name,
                description=cap.description
            )
            
            # Вычисляем cosine similarity
            similarity = cosine_similarity(query_embedding, tool_embedding)
            similarities.append((cap, similarity))
        
        # Сортируем по similarity (убывание)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Возвращаем топ-N
        result = [cap for cap, _ in similarities[:max_tools]]
        
        logger.debug(
            f"[SmartToolSelector] Selected {len(result)} tools for query: {query[:50]}"
        )
        
        return result
    
    def get_tool_embedding(self, capability: ActionCapability):
        """
        Получить embedding для capability (для отладки/тестирования).
        
        Args:
            capability: ActionCapability
            
        Returns:
            Embedding вектор
        """
        return self.embedding_cache.get_embedding(
            tool_name=capability.name,
            description=capability.description
        )
