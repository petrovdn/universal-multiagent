"""
SkillSelector - semantic search для выбора релевантного skill.

Использует embeddings для поиска наиболее подходящего skill по запросу пользователя.
"""
from typing import List, Optional
from pathlib import Path
from src.core.skills.skill_loader import Skill
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
    # Lazy import numpy to avoid segmentation fault in sandbox
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


class SkillSelector:
    """
    Smart skill selector using semantic search.
    
    Использует embeddings для поиска наиболее релевантного skill по запросу пользователя.
    """
    
    def __init__(
        self,
        skills: List[Skill],
        cache_dir: Optional[Path] = None,
        similarity_threshold: float = 0.5
    ):
        """
        Инициализация SkillSelector.
        
        Args:
            skills: Список доступных skills
            cache_dir: Директория для кэша embeddings (опционально)
            similarity_threshold: Минимальный порог similarity для выбора skill
        """
        self.skills = skills
        self.embedding_cache = EmbeddingCache(cache_dir=cache_dir)
        self.similarity_threshold = similarity_threshold
        logger.info(f"[SkillSelector] Initialized with {len(skills)} skills, threshold={similarity_threshold}")
    
    def select_skill(self, query: str) -> Optional[Skill]:
        """
        Выбрать наиболее релевантный skill для запроса.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Наиболее релевантный Skill или None если нет подходящего
        """
        if not query or not query.strip():
            logger.debug("[SkillSelector] Empty query, returning None")
            return None
        
        if not self.skills:
            logger.debug("[SkillSelector] No skills available")
            return None
        
        # Получаем embedding для запроса
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        query_embedding = self.embedding_cache.get_embedding(
            tool_name=f"__query_{query_hash}__",
            description=query
        )
        
        # Вычисляем similarity для каждого skill
        similarities = []
        for skill in self.skills:
            # Используем description для поиска (более краткое и релевантное)
            skill_embedding = self.embedding_cache.get_embedding(
                tool_name=f"skill_{skill.name}",
                description=skill.description
            )
            
            similarity = cosine_similarity(query_embedding, skill_embedding)
            similarities.append((skill, similarity))
        
        # Сортируем по similarity (убывание)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Проверяем threshold
        if not similarities:
            return None
        
        best_skill, best_similarity = similarities[0]
        
        if best_similarity < self.similarity_threshold:
            logger.debug(
                f"[SkillSelector] Best similarity {best_similarity:.3f} "
                f"below threshold {self.similarity_threshold} for query: {query[:50]}"
            )
            return None
        
        logger.debug(
            f"[SkillSelector] Selected skill '{best_skill.name}' "
            f"with similarity {best_similarity:.3f} for query: {query[:50]}"
        )
        
        return best_skill
    
    def select_top_skills(self, query: str, top_k: int = 3) -> List[tuple[Skill, float]]:
        """
        Выбрать топ-K skills с их similarity scores.
        
        Args:
            query: Запрос пользователя
            top_k: Количество skills для возврата
            
        Returns:
            Список кортежей (Skill, similarity), отсортированных по similarity
        """
        if not query or not query.strip() or not self.skills:
            return []
        
        # Получаем embedding для запроса
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        query_embedding = self.embedding_cache.get_embedding(
            tool_name=f"__query_{query_hash}__",
            description=query
        )
        
        # Вычисляем similarity для каждого skill
        similarities = []
        for skill in self.skills:
            skill_embedding = self.embedding_cache.get_embedding(
                tool_name=f"skill_{skill.name}",
                description=skill.description
            )
            
            similarity = cosine_similarity(query_embedding, skill_embedding)
            similarities.append((skill, similarity))
        
        # Сортируем и возвращаем топ-K
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
