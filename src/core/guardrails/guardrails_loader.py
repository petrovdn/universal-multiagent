"""
GuardrailsLoader - загрузка критических правил безопасности из GUARDRAILS.md.

Поддерживает:
- YAML frontmatter для metadata
- Markdown контент для инструкций
- In-memory кеширование
- Автоматическая инвалидация при изменении файла
"""
from pathlib import Path
from typing import Optional
import re
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class GuardrailsLoader:
    """
    Загрузчик критических правил безопасности.
    
    Загружает GUARDRAILS.md с кешированием в памяти.
    Автоматически инвалидирует кеш при изменении файла.
    """
    
    # Pattern для разделения YAML frontmatter и markdown контента
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL | re.MULTILINE
    )
    
    def __init__(self, guardrails_path: Optional[Path] = None):
        """
        Инициализация GuardrailsLoader.
        
        Args:
            guardrails_path: Путь к GUARDRAILS.md (по умолчанию: config/GUARDRAILS.md)
        """
        if guardrails_path is None:
            # Go up from src/core/guardrails/ to project root
            project_root = Path(__file__).parent.parent.parent.parent
            guardrails_path = project_root / "config" / "GUARDRAILS.md"
        
        self.guardrails_path = Path(guardrails_path)
        self._cached_content: Optional[str] = None
        self._cached_mtime: float = 0
        
        logger.info(f"[GuardrailsLoader] Initialized with path: {self.guardrails_path}")
    
    def load_guardrails(self) -> str:
        """
        Загрузить guardrails с кешированием в памяти.
        
        Returns:
            Отформатированная строка с guardrails для вставки в system prompt
        """
        if not self.guardrails_path.exists():
            logger.warning(f"[GuardrailsLoader] Guardrails file not found: {self.guardrails_path}")
            return ""
        
        # Check if file changed
        try:
            current_mtime = self.guardrails_path.stat().st_mtime
        except OSError as e:
            logger.error(f"[GuardrailsLoader] Failed to stat file: {e}")
            return ""
        
        # Invalidate cache if file changed
        if current_mtime != self._cached_mtime or self._cached_content is None:
            try:
                content = self.guardrails_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"[GuardrailsLoader] Failed to read file: {e}")
                return ""
            
            # Parse YAML frontmatter
            match = self.FRONTMATTER_PATTERN.match(content)
            if match:
                markdown_content = match.group(2).strip()
            else:
                # No frontmatter, use entire content
                markdown_content = content.strip()
            
            # Format for system prompt
            self._cached_content = f'<guardrails priority="critical">\n{markdown_content}\n</guardrails>'
            self._cached_mtime = current_mtime
            
            logger.info(f"[GuardrailsLoader] Loaded guardrails from {self.guardrails_path}")
        
        return self._cached_content
