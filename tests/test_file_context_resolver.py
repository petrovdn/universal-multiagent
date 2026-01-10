"""
TDD тесты для FileContextResolver - единой точки принятия решений о файлах.

Приоритеты:
1. Прикреплённые файлы (attached/uploaded) - содержимое УЖЕ в контексте
2. Открытые вкладки (open_files) - ID известен, нужно только прочитать
3. Рабочая папка Google Drive - нужен поиск
4. MCP/A2A - внешний поиск
"""
import pytest
from typing import Dict, List, Any, Optional


class TestFileContextResolver:
    """Тесты для FileContextResolver."""
    
    def test_attached_file_has_priority_over_open_file(self):
        """Прикреплённый файл с текстом должен иметь приоритет над открытым."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        # Прикреплённый PDF с извлечённым текстом
        attached_files = {
            "file1": {
                "filename": "Сказка.pdf", 
                "type": "application/pdf", 
                "text": "Однажды зайчик Прыг решил исследовать холм..."
            }
        }
        # Открытый документ с похожим названием
        open_files = [
            {"title": "Сказка", "type": "docs", "document_id": "abc123", "url": "https://docs.google.com/document/d/abc123"}
        ]
        
        result = resolver.resolve("Сказка", attached_files, open_files)
        
        assert result.source == FileSource.ATTACHED
        assert result.content == "Однажды зайчик Прыг решил исследовать холм..."
        assert result.needs_read == False
        assert result.needs_search == False
    
    def test_attached_file_with_partial_name_match(self):
        """Прикреплённый файл должен находиться по частичному совпадению имени."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {
            "file1": {
                "filename": "Сказка_про_зайца.pdf", 
                "type": "application/pdf", 
                "text": "Текст сказки..."
            }
        }
        open_files = []
        
        # Запрос по частичному имени
        result = resolver.resolve("сказка", attached_files, open_files)
        
        assert result.source == FileSource.ATTACHED
        assert result.content == "Текст сказки..."
    
    def test_open_file_needs_read_when_no_attached(self):
        """Открытый файл без прикреплённого аналога требует чтения (но НЕ поиска)."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {}
        open_files = [
            {"title": "Сказка", "type": "docs", "document_id": "abc123", "url": "https://docs.google.com/document/d/abc123"}
        ]
        
        result = resolver.resolve("Сказка", attached_files, open_files)
        
        assert result.source == FileSource.OPEN_TAB
        assert result.needs_read == True
        assert result.document_id == "abc123"
        assert result.needs_search == False  # НЕ нужен поиск - файл уже известен!
    
    def test_open_spreadsheet_needs_read(self):
        """Открытая таблица требует чтения с правильным ID."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {}
        open_files = [
            {"title": "Зарплаты", "type": "sheets", "spreadsheet_id": "sheet123", "url": "https://docs.google.com/spreadsheets/d/sheet123"}
        ]
        
        result = resolver.resolve("зарплаты", attached_files, open_files)
        
        assert result.source == FileSource.OPEN_TAB
        assert result.needs_read == True
        assert result.spreadsheet_id == "sheet123"
        assert result.needs_search == False
    
    def test_unknown_file_needs_search(self):
        """Неизвестный файл требует поиска."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {}
        open_files = []
        
        result = resolver.resolve("Сказка", attached_files, open_files)
        
        assert result.source == FileSource.UNKNOWN
        assert result.needs_search == True
        assert result.needs_read == False
    
    def test_image_attached_no_read_needed(self):
        """Прикреплённое изображение не требует дополнительного чтения."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {
            "img1": {
                "filename": "photo.jpg",
                "type": "image/jpeg",
                "data": "base64encodeddata..."
            }
        }
        open_files = []
        
        result = resolver.resolve("photo", attached_files, open_files)
        
        assert result.source == FileSource.ATTACHED
        assert result.needs_read == False
        assert result.is_image == True
    
    def test_should_block_search_for_open_file(self):
        """Должен блокировать поиск для уже открытого файла."""
        from src.core.file_context_resolver import FileContextResolver
        
        resolver = FileContextResolver()
        
        attached_files = {}
        open_files = [
            {"title": "Сказка", "type": "docs", "document_id": "abc123"}
        ]
        
        # Попытка вызвать поиск файла который уже открыт
        should_block, alternative = resolver.should_block_search(
            tool_name="find_and_open_file",
            query="Сказка",
            attached_files=attached_files,
            open_files=open_files
        )
        
        assert should_block == True
        assert alternative is not None
        assert alternative["tool_name"] == "read_document"
        assert alternative["arguments"]["document_id"] == "abc123"
    
    def test_should_block_search_for_attached_file(self):
        """Должен блокировать поиск для прикреплённого файла."""
        from src.core.file_context_resolver import FileContextResolver
        
        resolver = FileContextResolver()
        
        attached_files = {
            "file1": {
                "filename": "Сказка.pdf",
                "type": "application/pdf",
                "text": "Текст сказки..."
            }
        }
        open_files = []
        
        should_block, alternative = resolver.should_block_search(
            tool_name="workspace_search_files",
            query="сказка",
            attached_files=attached_files,
            open_files=open_files
        )
        
        assert should_block == True
        assert alternative is not None
        assert alternative["action"] == "use_attached_content"
        assert "Текст сказки..." in alternative["content"]
    
    def test_should_not_block_search_for_unknown_file(self):
        """Не должен блокировать поиск для неизвестного файла."""
        from src.core.file_context_resolver import FileContextResolver
        
        resolver = FileContextResolver()
        
        attached_files = {}
        open_files = []
        
        should_block, alternative = resolver.should_block_search(
            tool_name="find_and_open_file",
            query="Новый документ",
            attached_files=attached_files,
            open_files=open_files
        )
        
        assert should_block == False
        assert alternative is None
    
    def test_build_file_context_string(self):
        """Должен строить контекст с правильными приоритетами."""
        from src.core.file_context_resolver import FileContextResolver
        
        resolver = FileContextResolver()
        
        attached_files = {
            "file1": {"filename": "report.pdf", "type": "application/pdf", "text": "Отчёт за квартал..."}
        }
        open_files = [
            {"title": "Таблица данных", "type": "sheets", "spreadsheet_id": "sheet123"}
        ]
        workspace_folder = {"folder_id": "folder456", "folder_name": "Рабочая папка"}
        
        context_str = resolver.build_context_string(attached_files, open_files, workspace_folder)
        
        # Проверяем что приоритеты указаны явно
        assert "ПРИОРИТЕТ #1" in context_str or "PRIORITY #1" in context_str
        assert "ПРИОРИТЕТ #2" in context_str or "PRIORITY #2" in context_str
        assert "ПРИОРИТЕТ #3" in context_str or "PRIORITY #3" in context_str
        
        # Проверяем что прикреплённые файлы идут первыми
        attached_pos = context_str.find("report.pdf")
        open_pos = context_str.find("Таблица данных")
        folder_pos = context_str.find("Рабочая папка")
        
        assert attached_pos < open_pos < folder_pos
    
    def test_get_recommended_tool_for_open_doc(self):
        """Должен рекомендовать правильный инструмент для открытого документа."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        open_files = [
            {"title": "Сказка", "type": "docs", "document_id": "abc123"}
        ]
        
        result = resolver.resolve("Сказка", {}, open_files)
        tool_recommendation = resolver.get_recommended_tool(result)
        
        assert tool_recommendation["tool_name"] == "read_document"
        assert tool_recommendation["arguments"]["document_id"] == "abc123"
    
    def test_get_recommended_tool_for_open_sheet(self):
        """Должен рекомендовать правильный инструмент для открытой таблицы."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        open_files = [
            {"title": "Данные", "type": "sheets", "spreadsheet_id": "sheet456"}
        ]
        
        result = resolver.resolve("данные", {}, open_files)
        tool_recommendation = resolver.get_recommended_tool(result)
        
        assert tool_recommendation["tool_name"] == "sheets_read_range"
        assert tool_recommendation["arguments"]["spreadsheet_id"] == "sheet456"
        assert "range" in tool_recommendation["arguments"]


class TestFileContextResolverEdgeCases:
    """Тесты граничных случаев."""
    
    def test_empty_query(self):
        """Пустой запрос должен возвращать UNKNOWN."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        result = resolver.resolve("", {}, [])
        
        assert result.source == FileSource.UNKNOWN
    
    def test_multiple_matches_prefers_exact(self):
        """При нескольких совпадениях предпочитает точное."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        attached_files = {
            "file1": {"filename": "Сказка.pdf", "type": "application/pdf", "text": "Точное совпадение"},
            "file2": {"filename": "Сказка_продолжение.pdf", "type": "application/pdf", "text": "Частичное совпадение"}
        }
        
        result = resolver.resolve("Сказка", attached_files, [])
        
        assert result.content == "Точное совпадение"
    
    def test_case_insensitive_matching(self):
        """Поиск должен быть нечувствителен к регистру."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        open_files = [
            {"title": "ВАЖНЫЙ ДОКУМЕНТ", "type": "docs", "document_id": "doc123"}
        ]
        
        result = resolver.resolve("важный документ", {}, open_files)
        
        assert result.source == FileSource.OPEN_TAB
        assert result.document_id == "doc123"
    
    def test_extract_id_from_url(self):
        """Должен извлекать ID из URL если не указан явно."""
        from src.core.file_context_resolver import FileContextResolver, FileSource
        
        resolver = FileContextResolver()
        
        open_files = [
            {
                "title": "Документ", 
                "type": "docs", 
                "url": "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
                # document_id не указан явно
            }
        ]
        
        result = resolver.resolve("документ", {}, open_files)
        
        assert result.source == FileSource.OPEN_TAB
        assert result.document_id == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
