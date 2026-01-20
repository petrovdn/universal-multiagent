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
    
    Оптимизация: предзагружает embeddings всех инструментов в память при инициализации
    для избежания дисковых операций при каждом вызове select_tools.
    """
    
    def __init__(
        self,
        capabilities: List[ActionCapability],
        cache_dir: Optional[Path] = None,
        preload_embeddings: bool = True,
        force_recompute: bool = False
    ):
        """
        Инициализация SmartToolSelector.
        
        Args:
            capabilities: Список доступных capabilities
            cache_dir: Директория для кэша embeddings (опционально)
            preload_embeddings: Предзагрузить embeddings всех инструментов в память (по умолчанию: True)
            force_recompute: Принудительно пересчитать все embeddings при инициализации (по умолчанию: False)
        """
        self.capabilities = capabilities
        self.embedding_cache = EmbeddingCache(cache_dir=cache_dir, preload_embeddings=preload_embeddings)
        
        # In-memory cache для embeddings инструментов (предзагруженные из кэша)
        # Ключ: tool_name, Значение: numpy array с embedding
        self._tool_embeddings_cache: dict[str, any] = {}
        
        if preload_embeddings:
            self._preload_all_embeddings(force_recompute=force_recompute)
        
        logger.info(f"[SmartToolSelector] Initialized with {len(capabilities)} capabilities (preloaded: {len(self._tool_embeddings_cache)})")
    
    def _preload_all_embeddings(self, force_recompute: bool = False):
        """
        Предзагрузить embeddings всех инструментов в память.
        
        Args:
            force_recompute: Принудительно пересчитать все embeddings
        """
        import time
        _preload_start = time.time()
        
        if force_recompute:
            logger.info(f"[SmartToolSelector] Force recompute: clearing cache before preload")
            self.embedding_cache.clear_cache()
        
        # Предзагружаем embeddings для всех инструментов
        # get_embedding автоматически использует кэш если он валиден,
        # или пересчитывает если описание изменилось
        for cap in self.capabilities:
            try:
                # Проверяем, нужно ли пересчитать
                if force_recompute:
                    self.embedding_cache.invalidate_cache(cap.name)
                
                # Загружаем или вычисляем embedding
                # get_embedding автоматически использует кэш если он валиден
                embedding = self.embedding_cache.get_embedding(
                    tool_name=cap.name,
                    description=cap.description
                )
                
                # Сохраняем в памяти для быстрого доступа
                self._tool_embeddings_cache[cap.name] = embedding
                
                # Упрощенная проверка: если файл кэша существует ДО вызова get_embedding,
                # то скорее всего embedding был загружен из кэша (но не гарантировано, т.к. 
                # описание могло измениться). Для точной статистики это не критично.
                # get_embedding сам проверяет валидность кэша и пересчитывает если нужно.
                    
            except Exception as e:
                logger.error(f"[SmartToolSelector] Failed to preload embedding for {cap.name}: {e}")
                continue
        
        _preload_duration = time.time() - _preload_start
        logger.info(
            f"[SmartToolSelector] Preloaded {len(self._tool_embeddings_cache)} embeddings "
            f"in {_preload_duration:.3f}s"
        )
    
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
        import time
        _query_embed_start = time.time()
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        query_embedding = self.embedding_cache.get_embedding(
            tool_name=f"__query_{query_hash}__",
            description=query
        )
        _query_embed_duration = time.time() - _query_embed_start
        logger.info(f"[SmartToolSelector] Query embedding took {_query_embed_duration:.3f}s")
        
        # Вычисляем similarity для каждого инструмента
        # ОПТИМИЗАЦИЯ: используем предзагруженные embeddings из памяти вместо дисковых операций
        _tools_embed_start = time.time()
        similarities = []
        for cap in available_caps:
            # Получаем embedding из in-memory cache (быстро)
            if cap.name in self._tool_embeddings_cache:
                tool_embedding = self._tool_embeddings_cache[cap.name]
            else:
                # Fallback: если embedding не был предзагружен, загружаем/вычисляем
                logger.warning(f"[SmartToolSelector] Embedding for {cap.name} not in cache, loading on-demand")
                tool_embedding = self.embedding_cache.get_embedding(
                    tool_name=cap.name,
                    description=cap.description
                )
                # Сохраняем в памяти для следующих раз
                self._tool_embeddings_cache[cap.name] = tool_embedding
            
            # Вычисляем cosine similarity
            similarity = cosine_similarity(query_embedding, tool_embedding)
            similarities.append((cap, similarity))
        _tools_embed_duration = time.time() - _tools_embed_start
        logger.info(f"[SmartToolSelector] Tool embeddings for {len(available_caps)} tools took {_tools_embed_duration:.3f}s (from memory cache)")
        
        # Сортируем по similarity (убывание)
        _sort_start = time.time()
        similarities.sort(key=lambda x: x[1], reverse=True)
        _sort_duration = time.time() - _sort_start
        
        # #region agent log
        import json as _debug_json_smart; import time as _debug_time_smart
        try:
            top_tools_with_scores = [(cap.name, score) for cap, score in similarities[:max_tools]]
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_smart:
                _debug_f_smart.write(_debug_json_smart.dumps({"id":f"log_{int(_debug_time_smart.time()*1000)}_smart_tool_scores","timestamp":int(_debug_time_smart.time()*1000),"location":"smart_selector.py:205","message":"Tool similarity scores from smart selector","data":{"query":query,"top_tools":top_tools_with_scores,"total_tools_checked":len(similarities)},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Возвращаем топ-N
        result = [cap for cap, _ in similarities[:max_tools]]
        
        total_duration = _query_embed_duration + _tools_embed_duration + _sort_duration
        logger.info(
            f"[SmartToolSelector] Selected {len(result)} tools for query: {query[:50]} "
            f"(total: {total_duration:.3f}s, query_embed: {_query_embed_duration:.3f}s, "
            f"tools_embed: {_tools_embed_duration:.3f}s, sort: {_sort_duration:.3f}s)"
        )
        
        # Log top-10 similarity scores for debugging
        top_10 = similarities[:10]
        scores_info = [(cap.name, f"{score:.3f}") for cap, score in top_10]
        logger.info(f"[SmartToolSelector] Top-10 similarity scores: {scores_info}")
        
        # Для email запросов логируем подробности email tools
        if any(keyword in query.lower() for keyword in ["письма", "email", "почта", "mail"]):
            email_tools_scores = [
                (cap.name, f"{score:.3f}", cap.description[:100])
                for cap, score in similarities
                if "email" in cap.name.lower() or "gmail" in cap.name.lower() or "mail" in cap.name.lower()
            ][:5]
            if email_tools_scores:
                logger.info(f"[SmartToolSelector] Email tools similarity for query '{query[:50]}': {email_tools_scores}")
        
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
