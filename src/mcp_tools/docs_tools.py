"""
Google Docs MCP tool wrappers for LangChain.
Provides validated interfaces to document operations.
"""

from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError
from src.utils.retry import retry_on_mcp_error
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CreateDocumentInput(BaseModel):
    """Input schema for create_document tool."""
    
    title: str = Field(description="Document title")
    initial_text: Optional[str] = Field(default=None, description="Initial text content")


class CreateDocumentTool(BaseTool):
    """Tool for creating a Google Docs document."""
    
    name: str = "create_document"
    description: str = """
    Создать новый документ Google Docs в рабочей папке.
    
    Параметры:
    - title: Название документа
    - initial_text: Опциональный начальный текст
    
    Ключевые слова: создать документ, новый документ, создать Google Docs.
    """
    args_schema: type = CreateDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, title: str, initial_text: Optional[str] = None) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            if initial_text:
                args["initialText"] = initial_text
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_create", args, server_name="docs")
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            document_id = result.get("documentId")
            url = result.get("url", "")
            
            return f"Document '{title}' created successfully (ID: {document_id})" + (f" URL: {url}" if url else "")
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ReadDocumentInput(BaseModel):
    """Input schema for read_document tool."""
    
    document_id: str = Field(description="Document ID or URL")


class ReadDocumentTool(BaseTool):
    """Tool for reading a Google Docs document."""
    
    name: str = "read_document"
    description: str = """
    Прочитать полное содержимое документа Google Docs.
    
    Параметры:
    - document_id: ID документа или URL
    
    Ключевые слова: прочитать документ, открыть документ, показать документ, содержимое документа.
    """
    args_schema: type = ReadDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"documentId": document_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_read", args, server_name="docs")
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if "error" in result:
                return f"Error reading document: {result['error']}"
            
            title = result.get("title", "Untitled")
            content = result.get("content", "")
            text_length = len(content)
            
            # Include text length for formatting tools to use the correct end_index
            return f"Document: {title}\n[TEXT_LENGTH: {text_length} characters - use this as end_index for format_document_paragraph to format the ENTIRE document]\n\n{content}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to read document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class UpdateDocumentInput(BaseModel):
    """Input schema for update_document tool."""
    
    document_id: str = Field(description="Document ID or URL")
    content: str = Field(description="New content to write")


class UpdateDocumentTool(BaseTool):
    """Tool for updating a Google Docs document."""
    
    name: str = "update_document"
    description: str = """
    Заменить всё содержимое документа Google Docs новым текстом.
    
    Параметры:
    - document_id: ID документа или URL
    - content: Новое содержимое для записи
    
    Ключевые слова: обновить документ, заменить содержимое, изменить документ, переписать документ.
    """
    args_schema: type = UpdateDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, content: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "content": content
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_update", args, server_name="docs")
            
            return f"Document updated successfully (ID: {document_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to update document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class AppendToDocumentInput(BaseModel):
    """Input schema for append_to_document tool."""
    
    document_id: str = Field(description="Document ID or URL")
    content: str = Field(description="Text to append")


class AppendToDocumentTool(BaseTool):
    """Tool for appending text to a Google Docs document."""
    
    name: str = "append_to_document"
    description: str = """
    Добавить текст в конец документа Google Docs.
    
    Параметры:
    - document_id: ID документа или URL
    - content: Текст для добавления
    
    Ключевые слова: добавить в документ, дописать в документ, добавить текст, дописать текст.
    """
    args_schema: type = AppendToDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, content: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "content": content
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_append", args, server_name="docs")
            
            return f"Text appended to document successfully (ID: {document_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to append to document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class InsertIntoDocumentInput(BaseModel):
    """Input schema for insert_into_document tool."""
    
    document_id: str = Field(description="Document ID or URL")
    index: int = Field(description="Character index where to insert (0-based)")
    content: str = Field(description="Text to insert")


class InsertIntoDocumentTool(BaseTool):
    """Tool for inserting text into a Google Docs document."""
    
    name: str = "insert_into_document"
    description: str = """
    Вставить текст в определённую позицию документа Google Docs.
    
    Параметры:
    - document_id: ID документа или URL
    - index: Индекс символа для вставки (начиная с 0)
    - content: Текст для вставки
    
    Ключевые слова: вставить в документ, вставить текст, добавить текст в позицию.
    """
    args_schema: type = InsertIntoDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, index: int, content: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "index": index,
                "content": content
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_insert", args, server_name="docs")
            
            return f"Text inserted into document successfully (ID: {document_id}, index: {index})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to insert into document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FormatDocumentTextInput(BaseModel):
    """Input schema for format_document_text tool."""
    
    document_id: str = Field(description="Document ID or URL")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
    bold: Optional[bool] = Field(default=None, description="Make text bold")
    italic: Optional[bool] = Field(default=None, description="Make text italic")
    underline: Optional[bool] = Field(default=None, description="Make text underlined")
    foreground_color: Optional[Dict[str, float]] = Field(default=None, description="Text color as {red, green, blue, alpha} (0-1)")
    background_color: Optional[Dict[str, float]] = Field(default=None, description="Background/highlight color as {red, green, blue, alpha} (0-1)")


class FormatDocumentTextTool(BaseTool):
    """Tool for formatting text in a Google Docs document."""
    
    name: str = "format_document_text"
    description: str = """
    Форматировать текст в документе Google Docs (жирный, курсив, подчёркивание, цвета).
    
    Параметры:
    - document_id: ID документа или URL
    - start_index: Начальный индекс символа (начиная с 0)
    - end_index: Конечный индекс символа (исключающий)
    - bold: Опциональный boolean - сделать текст жирным
    - italic: Опциональный boolean - сделать текст курсивом
    - underline: Опциональный boolean - подчеркнуть текст
    - foreground_color: Опциональный dict с 'red', 'green', 'blue', 'alpha' (0.0-1.0) - цвет текста
    - background_color: Опциональный dict с 'red', 'green', 'blue', 'alpha' (0.0-1.0) - цвет фона/выделения
    
    Примеры цветов:
    - Красный текст: {'red': 1.0, 'green': 0.0, 'blue': 0.0, 'alpha': 1.0}
    - Синий текст: {'red': 0.0, 'green': 0.0, 'blue': 1.0, 'alpha': 1.0}
    - Жёлтое выделение: {'red': 1.0, 'green': 1.0, 'blue': 0.0, 'alpha': 1.0}
    
    Ключевые слова: форматировать документ, форматирование текста, жирный, курсив, подчёркивание, цвет текста, выделить текст, отформатировать текст.
    """
    args_schema: type = FormatDocumentTextInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        document_id: str,
        start_index: int,
        end_index: int,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        foreground_color: Optional[Dict[str, float]] = None,
        background_color: Optional[Dict[str, float]] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "startIndex": start_index,
                "endIndex": end_index
            }
            
            if bold is not None:
                args["bold"] = bold
            if italic is not None:
                args["italic"] = italic
            if underline is not None:
                args["underline"] = underline
            if foreground_color:
                args["foregroundColor"] = foreground_color
            if background_color:
                args["backgroundColor"] = background_color
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_format_text", args, server_name="docs")
            
            formats = []
            if bold:
                formats.append("bold")
            if italic:
                formats.append("italic")
            if underline:
                formats.append("underline")
            if foreground_color:
                formats.append("text color")
            if background_color:
                formats.append("background color")
            
            format_desc = ", ".join(formats) if formats else "formatting"
            return f"Successfully applied {format_desc} to text (characters {start_index}-{end_index-1})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to format text: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FormatDocumentParagraphInput(BaseModel):
    """Input schema for format_document_paragraph tool."""
    
    document_id: str = Field(description="Document ID or URL")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
    alignment: Optional[str] = Field(default=None, description="Paragraph alignment: START, CENTER, END, JUSTIFIED")
    indent_first_line: Optional[float] = Field(default=None, description="First line indent in points (36pt = ~1.27cm)")
    indent_start: Optional[float] = Field(default=None, description="Left indent in points")
    indent_end: Optional[float] = Field(default=None, description="Right indent in points")
    space_above: Optional[float] = Field(default=None, description="Space above paragraph in points")
    space_below: Optional[float] = Field(default=None, description="Space below paragraph in points")
    line_spacing: Optional[float] = Field(default=None, description="Line spacing multiplier (e.g., 1.15, 1.5, 2.0)")


class FormatDocumentParagraphTool(BaseTool):
    """Tool for formatting paragraph style in a Google Docs document."""
    
    name: str = "format_document_paragraph"
    description: str = """
    Форматировать стиль абзацев в документе Google Docs (выравнивание, отступы, интервалы).
    Используй для "красивого" форматирования: выравнивание по ширине, отступ первой строки.
    
    Параметры:
    - document_id: ID документа или URL
    - start_index: Начальный индекс символа (начиная с 0)
    - end_index: Конечный индекс символа (исключающий) - используй TEXT_LENGTH из read_document для форматирования ВСЕГО документа
    - alignment: Опциональное выравнивание абзаца (START, CENTER, END, JUSTIFIED)
    - indent_first_line: Опциональный отступ первой строки в пунктах (36pt = ~1.27см стандартный)
    - indent_start: Опциональный левый отступ в пунктах
    - indent_end: Опциональный правый отступ в пунктах
    - space_above: Опциональный отступ сверху абзаца в пунктах
    - space_below: Опциональный отступ снизу абзаца в пунктах
    - line_spacing: Опциональный множитель межстрочного интервала (1.15, 1.5, 2.0)
    
    Пример для "красивого" форматирования:
    - alignment="JUSTIFIED", indent_first_line=36 для выравнивания по ширине с отступом первой строки
    
    Ключевые слова: форматировать абзацы, выравнивание, отступы, интервалы, красиво оформить, выровнять по ширине, красная строка, отступ первой строки.
    """
    args_schema: type = FormatDocumentParagraphInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        document_id: str,
        start_index: int,
        end_index: int,
        alignment: Optional[str] = None,
        indent_first_line: Optional[float] = None,
        indent_start: Optional[float] = None,
        indent_end: Optional[float] = None,
        space_above: Optional[float] = None,
        space_below: Optional[float] = None,
        line_spacing: Optional[float] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "startIndex": start_index,
                "endIndex": end_index
            }
            
            if alignment:
                args["alignment"] = alignment
            if indent_first_line is not None:
                args["indentFirstLine"] = indent_first_line
            if indent_start is not None:
                args["indentStart"] = indent_start
            if indent_end is not None:
                args["indentEnd"] = indent_end
            if space_above is not None:
                args["spaceAbove"] = space_above
            if space_below is not None:
                args["spaceBelow"] = space_below
            if line_spacing is not None:
                args["lineSpacing"] = line_spacing
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_format_paragraph", args, server_name="docs")
            
            styles = []
            if alignment:
                styles.append(f"alignment={alignment}")
            if indent_first_line:
                styles.append(f"first-line indent={indent_first_line}pt")
            if indent_start:
                styles.append(f"left indent={indent_start}pt")
            if line_spacing:
                styles.append(f"line spacing={line_spacing}")
            
            style_desc = ", ".join(styles) if styles else "paragraph formatting"
            return f"Successfully applied {style_desc} (characters {start_index}-{end_index-1})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to format paragraph: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class SearchDocumentTextInput(BaseModel):
    """Input schema for search_document_text tool."""
    
    document_id: str = Field(description="Document ID or URL")
    search_text: str = Field(description="Text to search for")
    match_case: bool = Field(default=False, description="Whether to match case")


class SearchDocumentTextTool(BaseTool):
    """Tool for searching text in a Google Docs document."""
    
    name: str = "search_document_text"
    description: str = """
    Найти текст в документе Google Docs и вернуть позиции совпадений.
    
    Параметры:
    - document_id: ID документа или URL
    - search_text: Текст для поиска
    - match_case: Учитывать регистр (по умолчанию: false)
    
    Ключевые слова: найти в документе, поиск в документе, найти текст, поиск текста.
    """
    args_schema: type = SearchDocumentTextInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, search_text: str, match_case: bool = False) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "searchText": search_text,
                "matchCase": match_case
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_search_text", args, server_name="docs")
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            match_count = result.get("matchCount", 0)
            matches = result.get("matches", [])
            
            if match_count == 0:
                return f"No matches found for '{search_text}'"
            
            match_str = f"Found {match_count} match(es) for '{search_text}':\n"
            for i, match in enumerate(matches[:10], 1):  # Limit to first 10
                match_str += f"  {i}. Characters {match.get('startIndex')}-{match.get('endIndex')}\n"
            
            if match_count > 10:
                match_str += f"  ... and {match_count - 10} more"
            
            return match_str
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to search document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_docs_tools() -> List[BaseTool]:
    """
    Get Google Docs tools for document operations.
    
    Returns:
        List of BaseTool instances for Docs operations
    """
    return [
        CreateDocumentTool(),
        ReadDocumentTool(),
        UpdateDocumentTool(),
        AppendToDocumentTool(),
        InsertIntoDocumentTool(),
        FormatDocumentTextTool(),
        FormatDocumentParagraphTool(),
        SearchDocumentTextTool(),
    ]




