"""
TDD тесты для ActionFilter - фильтрации действий агента.

ActionFilter проверяет планируемые действия и:
1. Блокирует избыточные поиски файлов которые уже доступны
2. Предлагает альтернативные действия
3. Валидирует корректность параметров
"""
import pytest
from typing import Dict, List, Any, Optional


class TestActionFilter:
    """Тесты для ActionFilter."""
    
    def test_blocks_search_for_attached_file(self):
        """Блокирует поиск для прикреплённого файла."""
        from src.core.action_filter import ActionFilter, ActionValidationResult
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        # Прикреплён PDF с текстом
        context.add_file("file1", {
            "filename": "Сказка.pdf",
            "type": "application/pdf",
            "text": "Однажды зайчик Прыг решил исследовать холм..."
        })
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {"query": "Сказка"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == False
        assert "уже прикреплён" in result.reason.lower() or "already attached" in result.reason.lower()
        assert result.alternative is not None
        assert result.alternative["action"] == "use_attached_content"
    
    def test_blocks_search_for_open_file(self):
        """Блокирует поиск для открытого файла."""
        from src.core.action_filter import ActionFilter, ActionValidationResult
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        # Открыт документ во вкладке
        context.set_open_files([
            {"title": "Сказка", "type": "docs", "document_id": "abc123"}
        ])
        
        action = {
            "tool_name": "workspace_search_files",
            "arguments": {"query": "сказка"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == False
        assert "открыт" in result.reason.lower() or "already open" in result.reason.lower()
        assert result.alternative is not None
        assert result.alternative["tool_name"] == "read_document"
        assert result.alternative["arguments"]["document_id"] == "abc123"
    
    def test_allows_search_for_unknown_file(self):
        """Разрешает поиск для неизвестного файла."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {"query": "Новый документ"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == True
        assert result.alternative is None
    
    def test_allows_non_search_actions(self):
        """Разрешает действия не связанные с поиском."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        # Прикреплён файл
        context.add_file("file1", {"filename": "test.pdf", "type": "application/pdf", "text": "test"})
        
        # Действие не связанное с поиском
        action = {
            "tool_name": "send_email",
            "arguments": {"to": "test@example.com", "subject": "Test"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == True
    
    def test_allows_read_document_directly(self):
        """Разрешает прямое чтение документа (не поиск)."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        context.set_open_files([
            {"title": "Сказка", "type": "docs", "document_id": "abc123"}
        ])
        
        # Прямое чтение документа - это правильное действие!
        action = {
            "tool_name": "read_document",
            "arguments": {"document_id": "abc123"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == True
    
    def test_extracts_query_from_different_argument_names(self):
        """Извлекает поисковый запрос из разных названий аргументов."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        context.set_open_files([
            {"title": "Отчёт", "type": "docs", "document_id": "doc123"}
        ])
        
        # Разные названия параметров запроса
        for param_name in ["query", "search_query", "file_name", "filename", "name"]:
            action = {
                "tool_name": "find_and_open_file",
                "arguments": {param_name: "Отчёт"}
            }
            
            result = filter.validate(action, context)
            
            assert result.allowed == False, f"Should block search with param '{param_name}'"
    
    def test_validate_batch_returns_all_results(self):
        """Валидация батча возвращает результаты для всех действий."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        context.set_open_files([
            {"title": "Документ1", "type": "docs", "document_id": "doc1"}
        ])
        
        actions = [
            {"tool_name": "find_and_open_file", "arguments": {"query": "Документ1"}},  # Должен быть заблокирован
            {"tool_name": "send_email", "arguments": {"to": "test@example.com"}},  # Должен быть разрешён
            {"tool_name": "find_and_open_file", "arguments": {"query": "Новый файл"}}  # Должен быть разрешён
        ]
        
        results = filter.validate_batch(actions, context)
        
        assert len(results) == 3
        assert results[0].allowed == False
        assert results[1].allowed == True
        assert results[2].allowed == True


class TestActionFilterWithFileIds:
    """Тесты ActionFilter с file_ids."""
    
    def test_uses_file_ids_for_attached_files(self):
        """Использует file_ids для поиска прикреплённых файлов."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        # Прикреплён файл
        context.add_file("upload_123", {
            "filename": "Договор.pdf",
            "type": "application/pdf",
            "text": "Текст договора..."
        })
        
        action = {
            "tool_name": "workspace_search_files",
            "arguments": {"query": "договор"}
        }
        
        # Передаём file_ids явно
        result = filter.validate(action, context, file_ids=["upload_123"])
        
        assert result.allowed == False
        assert result.alternative is not None


class TestActionFilterEdgeCases:
    """Граничные случаи для ActionFilter."""
    
    def test_empty_arguments(self):
        """Обрабатывает пустые аргументы."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {}
        }
        
        result = filter.validate(action, context)
        
        # Без query не можем определить файл - разрешаем
        assert result.allowed == True
    
    def test_none_context(self):
        """Обрабатывает None контекст."""
        from src.core.action_filter import ActionFilter
        
        filter = ActionFilter()
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {"query": "test"}
        }
        
        # Не должен падать с None контекстом
        result = filter.validate(action, None)
        
        assert result.allowed == True
    
    def test_partial_match_in_filename(self):
        """Находит частичное совпадение в имени файла."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        context.add_file("file1", {
            "filename": "Квартальный_отчёт_2024.pdf",
            "type": "application/pdf",
            "text": "Данные отчёта..."
        })
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {"query": "отчёт"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == False
    
    def test_case_insensitive_search(self):
        """Поиск нечувствителен к регистру."""
        from src.core.action_filter import ActionFilter
        from src.core.context_manager import ConversationContext
        
        filter = ActionFilter()
        context = ConversationContext("test-session")
        
        context.set_open_files([
            {"title": "ВАЖНЫЙ ДОКУМЕНТ", "type": "docs", "document_id": "doc123"}
        ])
        
        action = {
            "tool_name": "find_and_open_file",
            "arguments": {"query": "важный документ"}
        }
        
        result = filter.validate(action, context)
        
        assert result.allowed == False
