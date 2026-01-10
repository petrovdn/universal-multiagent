"""
ActionFilter - фильтрация и валидация действий агента.

Проверяет планируемые действия перед выполнением:
1. Блокирует избыточные поиски файлов которые уже доступны
2. Предлагает альтернативные действия
3. Валидирует корректность параметров

Использование:
    filter = ActionFilter()
    result = filter.validate(action, context)
    if not result.allowed:
        # Использовать result.alternative вместо action
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src.core.file_context_resolver import FileContextResolver, FileSource

logger = logging.getLogger(__name__)


@dataclass
class ActionValidationResult:
    """Результат валидации действия."""
    allowed: bool
    reason: str = ""
    alternative: Optional[Dict[str, Any]] = None


class ActionFilter:
    """
    Фильтр для валидации и блокировки избыточных действий агента.
    
    Основная задача - предотвратить поиск файлов которые уже доступны
    в контексте (прикреплены или открыты во вкладках).
    """
    
    # Инструменты поиска файлов которые можно заблокировать
    SEARCH_TOOLS = {
        "find_and_open_file",
        "workspace_find_and_open_file",
        "workspace_search_files",
        "workspace_open_file",
        "drive_search_files",
        "search_files"
    }
    
    # Параметры которые могут содержать поисковый запрос
    QUERY_PARAM_NAMES = ["query", "search_query", "file_name", "filename", "name", "title"]
    
    def __init__(self):
        self.resolver = FileContextResolver()
    
    def validate(
        self,
        action: Dict[str, Any],
        context: Optional[Any],  # ConversationContext
        file_ids: Optional[List[str]] = None
    ) -> ActionValidationResult:
        """
        Валидирует действие и определяет нужно ли его блокировать.
        
        Args:
            action: Действие {tool_name, arguments}
            context: ConversationContext (может быть None)
            file_ids: Список ID прикреплённых файлов
            
        Returns:
            ActionValidationResult
        """
        tool_name = action.get("tool_name", "")
        arguments = action.get("arguments", {})
        
        # Если это не инструмент поиска - разрешаем
        if tool_name not in self.SEARCH_TOOLS:
            return ActionValidationResult(allowed=True)
        
        # Если нет контекста - разрешаем
        if context is None:
            return ActionValidationResult(allowed=True)
        
        # Извлекаем поисковый запрос
        query = self._extract_query(arguments)
        if not query:
            return ActionValidationResult(allowed=True)
        
        # Собираем прикреплённые файлы
        attached_files = self._get_attached_files(context, file_ids)
        
        # Получаем открытые файлы
        open_files = []
        if hasattr(context, 'get_open_files'):
            open_files = context.get_open_files() or []
        
        # Проверяем через FileContextResolver
        should_block, alternative = self.resolver.should_block_search(
            tool_name=tool_name,
            query=query,
            attached_files=attached_files,
            open_files=open_files
        )
        
        if should_block:
            reason = alternative.get("reason", "Файл уже доступен")
            return ActionValidationResult(
                allowed=False,
                reason=reason,
                alternative=alternative
            )
        
        return ActionValidationResult(allowed=True)
    
    def validate_batch(
        self,
        actions: List[Dict[str, Any]],
        context: Optional[Any],
        file_ids: Optional[List[str]] = None
    ) -> List[ActionValidationResult]:
        """
        Валидирует батч действий.
        
        Args:
            actions: Список действий
            context: ConversationContext
            file_ids: Список ID прикреплённых файлов
            
        Returns:
            Список результатов валидации
        """
        return [self.validate(action, context, file_ids) for action in actions]
    
    def _extract_query(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Извлекает поисковый запрос из аргументов."""
        for param_name in self.QUERY_PARAM_NAMES:
            if param_name in arguments:
                value = arguments[param_name]
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None
    
    def _get_attached_files(
        self,
        context: Any,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Собирает прикреплённые файлы из контекста."""
        attached_files = {}
        
        # Из uploaded_files контекста
        if hasattr(context, 'uploaded_files'):
            attached_files.update(context.uploaded_files or {})
        
        # Из явно переданных file_ids
        if file_ids and hasattr(context, 'get_file'):
            for file_id in file_ids:
                file_data = context.get_file(file_id)
                if file_data:
                    attached_files[file_id] = file_data
        
        return attached_files
