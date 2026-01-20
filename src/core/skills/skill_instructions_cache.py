"""
Short-lived cache для отформатированных skill instructions.

Кеширует отформатированные skill instructions с TTL (Time To Live).
Используется для избежания повторного форматирования при работе с одним доменом.
"""
import time
from typing import Dict, Optional, Tuple
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SkillInstructionsCache:
    """
    Short-lived cache для отформатированных skill instructions.
    
    Хранит инструкции в памяти с TTL. Автоматически удаляет устаревшие записи.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Инициализация cache.
        
        Args:
            ttl_seconds: Time To Live в секундах (по умолчанию: 5 минут)
        """
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._ttl = ttl_seconds
        logger.debug(f"[SkillInstructionsCache] Initialized with TTL={ttl_seconds}s")
    
    def get(self, skill_name: str) -> Optional[str]:
        """
        Получить отформатированные инструкции из cache.
        
        Args:
            skill_name: Имя skill (например, "calendar", "gmail")
            
        Returns:
            Отформатированные инструкции или None если cache miss или expired
        """
        if skill_name in self._cache:
            instructions, timestamp = self._cache[skill_name]
            
            # Проверяем TTL
            age = time.time() - timestamp
            if age < self._ttl:
                logger.debug(f"[SkillInstructionsCache] Cache HIT for {skill_name} (age={age:.1f}s)")
                return instructions
            else:
                # Истекло — удаляем
                logger.debug(f"[SkillInstructionsCache] Cache EXPIRED for {skill_name} (age={age:.1f}s)")
                del self._cache[skill_name]
        
        logger.debug(f"[SkillInstructionsCache] Cache MISS for {skill_name}")
        return None
    
    def set(self, skill_name: str, instructions: str):
        """
        Сохранить отформатированные инструкции в cache.
        
        Args:
            skill_name: Имя skill
            instructions: Отформатированные инструкции
        """
        self._cache[skill_name] = (instructions, time.time())
        logger.debug(f"[SkillInstructionsCache] Cached instructions for {skill_name} (size={len(instructions)} chars)")
    
    def invalidate(self, skill_name: str):
        """
        Удалить skill из cache (при изменении файла).
        
        Args:
            skill_name: Имя skill для удаления
        """
        if skill_name in self._cache:
            del self._cache[skill_name]
            logger.debug(f"[SkillInstructionsCache] Invalidated cache for {skill_name}")
    
    def clear(self):
        """Очистить весь cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[SkillInstructionsCache] Cleared cache ({count} entries)")
    
    def size(self) -> int:
        """
        Получить количество записей в cache.
        
        Returns:
            Количество активных записей
        """
        # Удаляем expired entries перед подсчётом
        now = time.time()
        expired = [name for name, (_, timestamp) in self._cache.items() 
                   if now - timestamp >= self._ttl]
        for name in expired:
            del self._cache[name]
        
        return len(self._cache)
