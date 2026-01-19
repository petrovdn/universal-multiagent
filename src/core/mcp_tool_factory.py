"""
MCP Tool Factory - динамическая генерация LangChain tools из MCP серверов.

Этот модуль создаёт LangChain BaseTool объекты напрямую из MCP tool schemas,
исключая необходимость в ручных обёртках и гарантируя синхронизацию.
"""

import json
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field, create_model
from langchain_core.tools import BaseTool

from src.utils.mcp_loader import get_mcp_manager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Маппинг русских описаний для улучшения семантического поиска
# Ключ: имя MCP tool, значение: русские ключевые слова для добавления к описанию
RUSSIAN_KEYWORDS_MAP = {
    # Gmail tools
    "gmail_search": "письма, email, почта, поиск писем, найти письма, показать письма, список писем, письма за период, письма за последние дни, newer_than, older_than",
    "gmail_list_messages": "письма, email, почта, список писем, показать письма, письма из папки, inbox, входящие",
    "gmail_get_message": "письмо, email, почта, прочитать письмо, открыть письмо, содержимое письма",
    "gmail_send_email": "отправить письмо, написать письмо, email, почта, send email",
    "gmail_create_draft": "черновик, создать черновик, сохранить письмо",
    # Calendar tools
    "get_calendar_events": "встречи, календарь, события, события календаря, показать встречи, встречи на период, встречи на неделю, встречи сегодня, встречи завтра",
    "create_event": "создать встречу, добавить встречу, новая встреча, запланировать встречу",
    "list_events": "встречи, календарь, события, события календаря, показать встречи",
    "get_next_availability": "найти свободное время, доступное время, когда все свободны, найти слот для встречи",
    "schedule_group_meeting": "запланировать встречу, найти время для встречи, встреча с участниками",
    "delete_calendar_events": "удалить встречи, удалить события, удалить из календаря",
    # Docs tools
    "docs_read": "документ, google docs, прочитать документ, содержимое документа",
    "docs_create": "создать документ, новый документ, создать google docs",
    "docs_update": "обновить документ, заменить содержимое, изменить документ, переписать документ",
    "docs_append": "добавить в документ, дописать в документ, добавить текст, дописать текст",
    "docs_insert": "вставить в документ, вставить текст, добавить текст в позицию",
    "docs_format_text": "форматировать документ, форматирование текста, жирный, курсив, подчёркивание, цвет текста, выделить текст, отформатировать текст",
    "docs_format_paragraph": "форматировать абзацы, выравнивание, отступы, интервалы, красиво оформить, выровнять по ширине, красная строка, отступ первой строки",
    "docs_search_text": "найти в документе, поиск в документе, найти текст, поиск текста",
    # Sheets tools
    "get_sheet_data": "таблица, spreadsheet, google sheets, данные таблицы, прочитать таблицу, показать данные",
    "sheets_create_spreadsheet": "создать таблицу, новая таблица, создать spreadsheet",
    "sheets_read_range": "прочитать таблицу, получить данные, показать таблицу, данные из таблицы",
    "sheets_write_range": "обновить ячейки, изменить данные, записать в таблицу, обновить таблицу",
    "sheets_append_rows": "добавить строки, вставить данные, добавить данные в таблицу",
    "sheets_get_spreadsheet_info": "информация о таблице, метаданные таблицы, получить информацию о листах, sheet_id",
    "sheets_format_cells": "форматировать ячейки, форматирование таблицы, жирный, курсив, цвет ячеек, выделить ячейки",
    "sheets_auto_resize_columns": "автоматическая ширина столбцов, подогнать ширину, автоширина столбцов",
    "sheets_merge_cells": "объединить ячейки, слить ячейки, объединение ячеек",
    "sheets_add_sheet": "добавить лист, создать лист, новая вкладка, добавить вкладку",
    "sheets_read_all_sheets": "все листы, несколько вкладок, все данные таблицы, прочитать все листы",
    # Slides tools
    "slides_create": "создать презентацию, новая презентация, создать Google Slides",
    "slides_get": "получить презентацию, информация о презентации, показать презентацию, структура презентации",
    "slides_create_slide": "добавить слайд, создать слайд, новый слайд",
    "slides_insert_text": "вставить текст в слайд, добавить текст, вставить заголовок, вставить содержимое",
    "slides_format_text": "форматировать текст в слайде, жирный, курсив, цвет текста, размер шрифта",
    "slides_create_presentation_from_doc": "создать презентацию из документа, презентация из документа, конвертировать документ в презентацию",
    "slides_create_presentation_batch": "создать презентацию, создать несколько слайдов, batch создание, оптимизированное создание",
    "slides_add_image": "добавить изображение, вставить изображение, добавить картинку на слайд",
    "slides_create_shape": "создать фигуру, добавить фигуру, фигура на слайде",
    "slides_set_background": "установить фон, фон слайда, цвет фона, фоновое изображение",
    "slides_create_table": "создать таблицу, добавить таблицу, таблица на слайде",
    "slides_update_table_cell": "обновить ячейку, изменить ячейку, текст в ячейке",
    "slides_create_chart": "создать график, добавить график, график на слайде, диаграмма",
    "slides_format_paragraph": "форматировать абзац, выравнивание текста, межстрочный интервал",
    "slides_create_bullets": "список, маркированный список, нумерованный список, создать список",
    "slides_update_element_transform": "переместить элемент, изменить размер, повернуть элемент, трансформация элемента",
    "slides_delete_element": "удалить элемент, удалить со слайда",
    "slides_get_masters": "получить макеты, доступные макеты, шаблоны слайдов",
    "slides_apply_layout": "применить макет, изменить макет слайда",
    # Workspace tools
    "list_workspace_files": "файлы, workspace, документы, список файлов, показать файлы, файлы в папке",
    "search_workspace_files": "поиск файлов, найти файлы, поиск документов, найти документы",
}


def _enrich_description_with_russian_keywords(tool_name: str, description: str) -> str:
    """
    Обогащает описание инструмента русскими ключевыми словами для улучшения семантического поиска.
    
    Args:
        tool_name: Имя MCP tool
        description: Оригинальное описание (на английском)
        
    Returns:
        Обогащённое описание с русскими ключевыми словами
    """
    russian_keywords = RUSSIAN_KEYWORDS_MAP.get(tool_name)
    if russian_keywords:
        # Добавляем русские ключевые слова в конец описания
        enriched = f"{description}\n\nРусские ключевые слова: {russian_keywords}"
        return enriched
    return description


def _json_schema_to_pydantic_type(json_type: str, prop_spec: Dict[str, Any]) -> Type:
    """
    Преобразует JSON Schema type в Python/Pydantic тип.
    
    Args:
        json_type: JSON Schema type (string, integer, boolean, array, object)
        prop_spec: Полная спецификация свойства из JSON Schema
        
    Returns:
        Python тип для Pydantic
    """
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": List[Any],
        "object": Dict[str, Any],
    }
    
    base_type = type_map.get(json_type, Any)
    
    # Handle array types with items
    if json_type == "array" and "items" in prop_spec:
        items_type = prop_spec["items"]
        if isinstance(items_type, dict):
            item_type = items_type.get("type", "string")
            base_type = List[type_map.get(item_type, Any)]
        else:
            base_type = List[Any]
    
    return base_type


def create_langchain_tool_from_mcp(
    mcp_tool: Dict[str, Any],
    server_name: str
) -> BaseTool:
    """
    Динамически создаёт LangChain BaseTool из MCP tool schema.
    
    Args:
        mcp_tool: Словарь с ключами:
            - name: str - имя инструмента
            - description: str - описание
            - inputSchema: dict - JSON Schema для параметров
        server_name: Имя MCP сервера (для вызова через manager)
        
    Returns:
        BaseTool экземпляр, готовый к использованию
    """
    tool_name = mcp_tool.get("name")
    if not tool_name:
        raise ValueError("MCP tool must have 'name' field")
    
    base_description = mcp_tool.get("description", f"Tool: {tool_name}")
    # Обогащаем описание русскими ключевыми словами для улучшения семантического поиска
    description = _enrich_description_with_russian_keywords(tool_name, base_description)
    input_schema = mcp_tool.get("inputSchema", {})
    
    # Создаём Pydantic модель из JSON Schema
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))
    
    field_definitions = {}
    for prop_name, prop_spec in properties.items():
        if not isinstance(prop_spec, dict):
            continue
            
        prop_type_str = prop_spec.get("type", "string")
        prop_description = prop_spec.get("description", "")
        prop_default = prop_spec.get("default", ...)
        
        # Определяем Python тип
        python_type = _json_schema_to_pydantic_type(prop_type_str, prop_spec)
        
        # Создаём Field
        if prop_name in required_fields:
            # Обязательное поле
            field_definitions[prop_name] = (
                python_type,
                Field(description=prop_description)
            )
        else:
            # Опциональное поле
            if prop_default is ...:
                # Нет default в schema - делаем Optional
                field_definitions[prop_name] = (
                    Optional[python_type],
                    Field(default=None, description=prop_description)
                )
            else:
                # Есть default в schema
                field_definitions[prop_name] = (
                    python_type,
                    Field(default=prop_default, description=prop_description)
                )
    
    # Создаём динамическую Pydantic модель
    InputModel = create_model(
        f"{tool_name.replace('.', '_')}Input",
        **field_definitions
    )
    
    # Создаём динамический Tool класс
    class DynamicMCPTool(BaseTool):
        name: str = tool_name
        description: str = description
        args_schema: Type[BaseModel] = InputModel
        
        async def _arun(self, **kwargs) -> str:
            """Асинхронное выполнение через MCP manager."""
            try:
                # Получаем MCP manager
                mcp_manager = get_mcp_manager()
                
                # Очищаем kwargs от None значений (опциональные поля)
                clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
                
                # Вызываем MCP tool напрямую с правильным именем
                result = await mcp_manager.call_tool(
                    tool_name=tool_name,
                    arguments=clean_kwargs,
                    server_name=server_name
                )
                
                # Преобразуем результат в строку
                if isinstance(result, str):
                    return result
                elif isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False, indent=2)
                elif hasattr(result, 'text'):
                    # TextContent объект
                    return result.text
                elif isinstance(result, list) and len(result) > 0:
                    # Список TextContent
                    first_item = result[0]
                    if hasattr(first_item, 'text'):
                        return first_item.text
                    elif isinstance(first_item, dict) and 'text' in first_item:
                        return first_item['text']
                    return str(first_item)
                else:
                    return str(result)
                    
            except Exception as e:
                error_msg = str(e) if str(e) else "Unknown error occurred"
                logger.error(f"[DynamicMCPTool] Execution failed for {tool_name}: {error_msg}")
                raise
        
        def _run(self, **kwargs) -> str:
            """Синхронное выполнение не поддерживается."""
            raise NotImplementedError("Use async execution (_arun)")
    
    return DynamicMCPTool()


async def load_tools_from_mcp_servers() -> List[BaseTool]:
    """
    Загружает все инструменты из всех подключённых MCP серверов.
    
    Returns:
        Список BaseTool объектов, созданных динамически из MCP schemas
    """
    tools = []
    mcp_manager = get_mcp_manager()
    
    # Убеждаемся, что все серверы подключены
    # connect_all подключает все серверы и инициализирует их (включая discovery tools)
    await mcp_manager.connect_all()
    
    # Проходим по всем подключениям
    for server_name, connection in mcp_manager.connections.items():
        if not connection.connected:
            logger.warning(f"[MCPToolFactory] Server {server_name} not connected, skipping")
            continue
        
        # Получаем tools из connection
        mcp_tools = connection.get_tools()
        
        if not mcp_tools:
            logger.warning(f"[MCPToolFactory] Server {server_name} has no tools discovered")
            continue
        
        logger.info(f"[MCPToolFactory] Creating LangChain tools from {server_name} ({len(mcp_tools)} tools)")
        
        # Создаём LangChain tools для каждого MCP tool
        for tool_name, mcp_tool in mcp_tools.items():
            try:
                langchain_tool = create_langchain_tool_from_mcp(mcp_tool, server_name)
                tools.append(langchain_tool)
                logger.debug(f"[MCPToolFactory] Created tool: {tool_name}")
            except Exception as e:
                logger.error(
                    f"[MCPToolFactory] Failed to create tool {tool_name} from {server_name}: {e}",
                    exc_info=True
                )
                continue
    
    logger.info(f"[MCPToolFactory] Created {len(tools)} LangChain tools from MCP servers")
    return tools
