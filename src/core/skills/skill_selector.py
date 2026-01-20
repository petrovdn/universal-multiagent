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
        similarity_threshold: float = 0.3
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
    
    def select_skill(self, query: str, skill_type: Optional[str] = None) -> Optional[Skill]:
        """
        Выбрать наиболее релевантный skill для запроса.
        
        Args:
            query: Запрос пользователя
            skill_type: Фильтр по типу ('domain', 'composite', None для всех)
            
        Returns:
            Наиболее релевантный Skill или None если нет подходящего
        """
        if not query or not query.strip():
            logger.debug("[SkillSelector] Empty query, returning None")
            return None
        
        if not self.skills:
            logger.debug("[SkillSelector] No skills available")
            return None
        
        # Фильтруем skills по типу если указан
        skills_to_search = self.skills
        if skill_type:
            skills_to_search = [
                s for s in self.skills 
                if s.metadata.get('type') == skill_type
            ]
            if not skills_to_search:
                logger.debug(f"[SkillSelector] No skills of type '{skill_type}' found")
                return None
        
        # Получаем embedding для запроса
        import hashlib
        import time
        _query_embed_start = time.time()
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        query_embedding = self.embedding_cache.get_embedding(
            tool_name=f"__query_{query_hash}__",
            description=query
        )
        _query_embed_duration = time.time() - _query_embed_start
        logger.info(f"[SkillSelector] Query embedding took {_query_embed_duration:.3f}s")
        
        # Вычисляем similarity для каждого skill
        _skills_embed_start = time.time()
        similarities = []
        for skill in skills_to_search:
            # Используем полные инструкции для более точного matching
            full_content = f"{skill.description}\n\n{skill.content}"
            skill_embedding = self.embedding_cache.get_embedding(
                tool_name=f"skill_{skill.name}_full",
                description=full_content
            )
            
            similarity = cosine_similarity(query_embedding, skill_embedding)
            similarities.append((skill, similarity))
        _skills_embed_duration = time.time() - _skills_embed_start
        logger.info(f"[SkillSelector] Skill embeddings for {len(skills_to_search)} skills took {_skills_embed_duration:.3f}s")
        
        # Сортируем по similarity (убывание)
        _sort_start = time.time()
        similarities.sort(key=lambda x: x[1], reverse=True)
        _sort_duration = time.time() - _sort_start
        
        # Проверяем threshold
        if not similarities:
            return None
        
        best_skill, best_similarity = similarities[0]
        
        total_duration = _query_embed_duration + _skills_embed_duration + _sort_duration
        if best_similarity < self.similarity_threshold:
            logger.info(
                f"[SkillSelector] Best similarity {best_similarity:.3f} "
                f"below threshold {self.similarity_threshold} for query: {query[:50]} "
                f"(total: {total_duration:.3f}s)"
            )
            return None
        
        logger.info(
            f"[SkillSelector] Selected skill '{best_skill.name}' "
            f"with similarity {best_similarity:.3f} for query: {query[:50]} "
            f"(total: {total_duration:.3f}s)"
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
            # Используем полные инструкции для более точного matching
            full_content = f"{skill.description}\n\n{skill.content}"
            skill_embedding = self.embedding_cache.get_embedding(
                tool_name=f"skill_{skill.name}_full",
                description=full_content
            )
            
            similarity = cosine_similarity(query_embedding, skill_embedding)
            similarities.append((skill, similarity))
        
        # Сортируем и возвращаем топ-K
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_domain_skills_for_composite(self, composite_skill: Skill) -> List[Skill]:
        """
        Получить domain skills для composite skill.
        
        Args:
            composite_skill: Composite skill с metadata.domains
            
        Returns:
            Список domain skills, указанных в composite_skill.metadata.domains
        """
        domains = composite_skill.metadata.get('domains', [])
        if not domains:
            logger.warning(f"[SkillSelector] Composite skill '{composite_skill.name}' has no domains")
            return []
        
        domain_skills = [s for s in self.skills if s.name in domains]
        logger.debug(f"[SkillSelector] Found {len(domain_skills)} domain skills for composite '{composite_skill.name}'")
        return domain_skills