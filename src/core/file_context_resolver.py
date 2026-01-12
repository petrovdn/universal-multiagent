"""
FileContextResolver - единая точка принятия решений о файлах.

Определяет приоритеты источников файлов:
1. ATTACHED (прикреплённые) - содержимое УЖЕ в контексте, не нужно читать
2. OPEN_TAB (открытые вкладки) - ID известен, нужно только прочитать, НЕ искать
3. WORKSPACE (рабочая папка) - нужен поиск в Google Drive
4. UNKNOWN - нужен полный поиск через MCP/A2A

Использование:
    resolver = FileContextResolver()
    result = resolver.resolve("Сказка", attached_files, open_files)
    if result.needs_read:
        tool = resolver.get_recommended_tool(result)
"""
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class FileSource(Enum):
    """Источник файла по приоритету."""
    ATTACHED = 1      # Прикреплённый файл - контент уже есть
    OPEN_TAB = 2      # Открытая вкладка - ID известен, нужно прочитать
    WORKSPACE = 3     # Рабочая папка - нужен поиск
    UNKNOWN = 4       # Неизвестен - нужен полный поиск


@dataclass
class FileResolution:
    """Результат разрешения файла."""
    source: FileSource
    
    # Контент (для ATTACHED)
    content: Optional[str] = None
    
    # ID файла (для OPEN_TAB)
    document_id: Optional[str] = None
    spreadsheet_id: Optional[str] = None
    
    # Метаданные
    filename: Optional[str] = None
    file_type: Optional[str] = None  # docs, sheets, pdf, image, etc.
    url: Optional[str] = None
    
    # Флаги действий
    needs_read: bool = False      # Нужно прочитать содержимое
    needs_search: bool = False    # Нужен поиск файла
    is_image: bool = False        # Это изображение (передано через Vision)
    
    # Дополнительные данные
    raw_data: Dict[str, Any] = field(default_factory=dict)


class FileContextResolver:
    """
    Единая точка принятия решений о файлах.
    
    Определяет откуда брать файл и что с ним делать.
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
    
    def __init__(self):
        pass
    
    def resolve(
        self,
        query: str,
        attached_files: Dict[str, Dict[str, Any]],
        open_files: List[Dict[str, Any]]
    ) -> FileResolution:
        """
        Определяет источник файла и необходимые действия.
        
        Args:
            query: Поисковый запрос (название файла или его часть)
            attached_files: Прикреплённые файлы {file_id: {filename, type, text?, data?}}
            open_files: Открытые вкладки [{title, type, document_id?, spreadsheet_id?, url}]
            
        Returns:
            FileResolution с информацией об источнике и действиях
        """
        if not query or not query.strip():
            return FileResolution(source=FileSource.UNKNOWN, needs_search=True)
        
        query_lower = query.lower().strip()
        
        # Приоритет #1: Проверяем прикреплённые файлы
        attached_match = self._find_in_attached(query_lower, attached_files)
        if attached_match:
            return attached_match
        
        # Приоритет #2: Проверяем открытые вкладки
        open_match = self._find_in_open_files(query_lower, open_files)
        if open_match:
            return open_match
        
        # Файл не найден - нужен поиск
        return FileResolution(source=FileSource.UNKNOWN, needs_search=True)
    
    def _find_in_attached(
        self, 
        query_lower: str, 
        attached_files: Dict[str, Dict[str, Any]]
    ) -> Optional[FileResolution]:
        """Ищет файл среди прикреплённых."""
        if not attached_files:
            return None
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"[_find_in_attached] Searching for query: '{query_lower}' in {len(attached_files)} attached files")
        print(f"[_find_in_attached] Searching query: '{query_lower}' in files: {[f.get('filename') for f in attached_files.values()]}", flush=True)
        # Ключевые слова, которые указывают на прикрепленный файл (если есть только один файл)
        generic_file_keywords = ["файл", "file", "документ", "document", "word", "pdf", "изображение", "image"]
        has_generic_keyword = any(keyword in query_lower for keyword in generic_file_keywords)
        
        # Если есть только один прикрепленный файл и query содержит общее слово - считаем что это он
        if len(attached_files) == 1 and has_generic_keyword:
            file_id, file_data = list(attached_files.items())[0]
            _logger.info(f"[_find_in_attached] Found match via generic keyword (single file): {file_data.get('filename')}")
            print(f"[_find_in_attached] Match via generic keyword: {file_data.get('filename')}", flush=True)
            match = (file_id, file_data)
        else:
            # Сначала ищем точное совпадение
            exact_match = None
            partial_match = None
            
            for file_id, file_data in attached_files.items():
                filename = file_data.get("filename", "")
                filename_lower = filename.lower()
                
                # Убираем расширение для сравнения
                filename_no_ext = re.sub(r'\.[^.]+$', '', filename_lower)
                
                # Точное совпадение (без расширения)
                if filename_no_ext == query_lower or filename_lower == query_lower:
                    exact_match = (file_id, file_data)
                    break
                
                # Частичное совпадение
                if query_lower in filename_lower or filename_no_ext.startswith(query_lower):
                    if partial_match is None:
                        partial_match = (file_id, file_data)
            
            match = exact_match or partial_match
            if not match:
                _logger.warning(f"[_find_in_attached] No match found for query: '{query_lower}'")
                print(f"[_find_in_attached] No match found for query: '{query_lower}'", flush=True)
                return None
        
        file_id, file_data = match
        file_type = file_data.get("type", "")
        
        # Определяем тип файла
        is_image = file_type.startswith("image/")
        has_text = "text" in file_data and file_data["text"]
        _logger.info(f"[_find_in_attached] Found match: {file_data.get('filename')}, type: {file_type}, has_text: {has_text}")
        print(f"[_find_in_attached] Found match: {file_data.get('filename')}, has_text: {has_text}", flush=True)
        return FileResolution(
            source=FileSource.ATTACHED,
            content=file_data.get("text"),
            filename=file_data.get("filename"),
            file_type=file_type,
            needs_read=False,  # Контент уже есть
            needs_search=False,
            is_image=is_image,
            raw_data=file_data
        )
    
    def _find_in_open_files(
        self, 
        query_lower: str, 
        open_files: List[Dict[str, Any]]
    ) -> Optional[FileResolution]:
        """Ищет файл среди открытых вкладок."""
        if not open_files:
            return None
        
        exact_match = None
        partial_match = None
        
        for file_data in open_files:
            title = file_data.get("title", "")
            title_lower = title.lower()
            
            # Точное совпадение
            if title_lower == query_lower:
                exact_match = file_data
                break
            
            # Частичное совпадение
            if query_lower in title_lower or title_lower.startswith(query_lower):
                if partial_match is None:
                    partial_match = file_data
        
        match = exact_match or partial_match
        if not match:
            return None
        
        file_type = match.get("type", "unknown")
        
        # Извлекаем ID
        document_id = match.get("document_id") or match.get("documentId")
        spreadsheet_id = match.get("spreadsheet_id") or match.get("spreadsheetId")
        
        # Если ID не указан явно, пробуем извлечь из URL
        url = match.get("url", "")
        if not document_id and file_type == "docs" and url:
            doc_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', url)
            if doc_match:
                document_id = doc_match.group(1)
        
        if not spreadsheet_id and file_type == "sheets" and url:
            sheet_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
            if sheet_match:
                spreadsheet_id = sheet_match.group(1)
        
        return FileResolution(
            source=FileSource.OPEN_TAB,
            document_id=document_id,
            spreadsheet_id=spreadsheet_id,
            filename=match.get("title"),
            file_type=file_type,
            url=url,
            needs_read=True,   # Нужно прочитать содержимое
            needs_search=False,  # НЕ нужен поиск - ID уже известен!
            raw_data=match
        )
    
    def should_block_search(
        self,
        tool_name: str,
        query: str,
        attached_files: Dict[str, Dict[str, Any]],
        open_files: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверяет, нужно ли заблокировать вызов инструмента поиска.
        
        Args:
            tool_name: Название инструмента
            query: Поисковый запрос
            attached_files: Прикреплённые файлы
            open_files: Открытые вкладки
            
        Returns:
            (should_block, alternative) - нужно ли блокировать и альтернативное действие
        """
        # Проверяем только инструменты поиска
        if tool_name not in self.SEARCH_TOOLS:
            return False, None
        
        # Резолвим файл
        resolution = self.resolve(query, attached_files, open_files)
        
        if resolution.source == FileSource.ATTACHED:
            # Файл прикреплён - блокируем поиск, возвращаем контент
            return True, {
                "action": "use_attached_content",
                "content": resolution.content,
                "filename": resolution.filename,
                "reason": f"Файл '{resolution.filename}' уже прикреплён к запросу. Используй его содержимое напрямую."
            }
        
        if resolution.source == FileSource.OPEN_TAB:
            # Файл открыт во вкладке - блокируем поиск, рекомендуем read
            tool_rec = self.get_recommended_tool(resolution)
            return True, {
                **tool_rec,
                "reason": f"Файл '{resolution.filename}' уже открыт во вкладке. Используй {tool_rec['tool_name']} напрямую."
            }
        
        # Файл не найден - поиск разрешён
        return False, None
    
    def get_recommended_tool(self, resolution: FileResolution) -> Dict[str, Any]:
        """
        Возвращает рекомендуемый инструмент для работы с файлом.
        
        Args:
            resolution: Результат разрешения файла
            
        Returns:
            Dict с tool_name и arguments
        """
        if resolution.source == FileSource.ATTACHED:
            # Для прикреплённых файлов инструмент не нужен
            return {
                "tool_name": "none",
                "arguments": {},
                "action": "use_content_directly",
                "content": resolution.content
            }
        
        if resolution.source == FileSource.OPEN_TAB:
            if resolution.file_type == "sheets" and resolution.spreadsheet_id:
                return {
                    "tool_name": "sheets_read_range",
                    "arguments": {
                        "spreadsheet_id": resolution.spreadsheet_id,
                        "range": "A1:Z100"  # Дефолтный диапазон
                    }
                }
            elif resolution.file_type == "docs" and resolution.document_id:
                return {
                    "tool_name": "read_document",
                    "arguments": {
                        "document_id": resolution.document_id
                    }
                }
        
        # Для UNKNOWN - нужен поиск
        return {
            "tool_name": "find_and_open_file",
            "arguments": {
                "query": resolution.filename or ""
            }
        }
    
    def build_context_string(
        self,
        attached_files: Dict[str, Dict[str, Any]],
        open_files: List[Dict[str, Any]],
        workspace_folder: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Строит строку контекста с чёткими приоритетами для промпта.
        
        Args:
            attached_files: Прикреплённые файлы
            open_files: Открытые вкладки
            workspace_folder: Рабочая папка {folder_id, folder_name}
            
        Returns:
            Строка контекста для добавления в промпт
        """
        sections = []
        
        # ПРИОРИТЕТ #1: Прикреплённые файлы
        if attached_files:
            section = ["📎 ПРИОРИТЕТ #1 - ПРИКРЕПЛЁННЫЕ ФАЙЛЫ (содержимое УЖЕ доступно):"]
            section.append("⚠️ КРИТИЧНО: Текст этих файлов УЖЕ включён в контекст! НЕ ищи их!")
            section.append("")
            
            for file_id, file_data in attached_files.items():
                filename = file_data.get("filename", "unknown")
                file_type = file_data.get("type", "")
                
                if file_type.startswith("image/"):
                    section.append(f"  • 🖼️ {filename} - изображение (передано через Vision API)")
                elif "text" in file_data:
                    text_preview = file_data["text"][:200] + "..." if len(file_data.get("text", "")) > 200 else file_data.get("text", "")
                    section.append(f"  • 📄 {filename}")
                    section.append(f"    Содержимое: {text_preview}")
                else:
                    section.append(f"  • {filename} ({file_type})")
            
            section.append("")
            section.append("🚫 НЕ используй find_and_open_file или search для этих файлов!")
            sections.append("\n".join(section))
        
        # ПРИОРИТЕТ #2: Открытые вкладки
        if open_files:
            section = ["📂 ПРИОРИТЕТ #2 - ОТКРЫТЫЕ ФАЙЛЫ (ID известен, нужно только прочитать):"]
            section.append("⚠️ КРИТИЧНО: Используй ID напрямую! НЕ ищи эти файлы!")
            section.append("")
            
            for file_data in open_files:
                title = file_data.get("title", "Без названия")
                file_type = file_data.get("type", "unknown")
                
                if file_type == "docs":
                    doc_id = file_data.get("document_id") or file_data.get("documentId")
                    if not doc_id and file_data.get("url"):
                        match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', file_data.get("url", ""))
                        if match:
                            doc_id = match.group(1)
                    section.append(f"  • 📄 Документ: {title}")
                    section.append(f"    → Используй: read_document(document_id=\"{doc_id}\")")
                    
                elif file_type == "sheets":
                    sheet_id = file_data.get("spreadsheet_id") or file_data.get("spreadsheetId")
                    if not sheet_id and file_data.get("url"):
                        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', file_data.get("url", ""))
                        if match:
                            sheet_id = match.group(1)
                    section.append(f"  • 📊 Таблица: {title}")
                    section.append(f"    → Используй: sheets_read_range(spreadsheet_id=\"{sheet_id}\", range=\"A1:Z100\")")
            
            section.append("")
            section.append("🚫 НЕ используй find_and_open_file или search для этих файлов!")
            sections.append("\n".join(section))
        
        # ПРИОРИТЕТ #3: Рабочая папка
        if workspace_folder:
            folder_id = workspace_folder.get("folder_id", "")
            folder_name = workspace_folder.get("folder_name", "Рабочая папка")
            
            section = [f"📁 ПРИОРИТЕТ #3 - РАБОЧАЯ ПАПКА Google Drive:"]
            section.append(f"  Название: {folder_name}")
            section.append(f"  ID: {folder_id}")
            section.append("")
            section.append("  Используй только если файл НЕ найден в приоритетах #1 и #2!")
            sections.append("\n".join(section))
        
        if not sections:
            return ""
        
        return "\n\n".join(sections)
