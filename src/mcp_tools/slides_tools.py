"""
Google Slides MCP tool wrappers for LangChain.
Provides validated interfaces to presentation operations.
"""

from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError
from src.utils.retry import retry_on_mcp_error
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# Utility functions for unit conversion
def pt_to_emu(pt: float) -> int:
    """Convert points to EMU (English Metric Units). 1 pt = 12700 EMU."""
    return int(pt * 12700)


def inches_to_emu(inches: float) -> int:
    """Convert inches to EMU (English Metric Units). 1 inch = 914400 EMU."""
    return int(inches * 914400)


class CreatePresentationInput(BaseModel):
    """Input schema for create_presentation tool."""
    
    title: str = Field(description="Presentation title")


class CreatePresentationTool(BaseTool):
    """Tool for creating a Google Slides presentation."""
    
    name: str = "create_presentation"
    description: str = """
    Создать НОВУЮ презентацию Google Slides в рабочей папке.
    
    ⚠️ ВАЖНО: 
    - Это создаёт НОВЫЙ файл презентации с ОДНИМ ПУСТЫМ СЛАЙДОМ уже включённым.
    - Ответ включает ID первого слайда - используй insert_slide_text с этим ID слайда, чтобы добавить содержимое на первый слайд.
    - Чтобы добавить БОЛЬШЕ слайдов, используй create_slide (но помни: первый слайд уже существует, поэтому если пользователь просит N слайдов, нужно создать только N-1 дополнительных слайдов).
    
    Параметры:
    - title: Название презентации
    
    Используй это ТОЛЬКО когда нужно создать совершенно новый файл презентации.
    Результат будет включать ID презентации и ID первого слайда - используй ID первого слайда, чтобы добавить содержимое на первый слайд без создания нового.
    
    Ключевые слова: создать презентацию, новая презентация, создать Google Slides.
    """
    args_schema: type = CreatePresentationInput
    
    @retry_on_mcp_error()
    async def _arun(self, title: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create", args, server_name="slides")
            
            
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
            
            
            # Check for errors
            if isinstance(result, dict) and "error" in result:
                error_msg = result.get("error", "Unknown error")
                raise ToolExecutionError(
                    f"Failed to create presentation: {error_msg}",
                    tool_name=self.name
                )
            
            presentation_id = result.get("presentationId")
            url = result.get("url", "")
            first_slide_id = result.get("firstSlideId")
            
            if not presentation_id:
                raise ToolExecutionError(
                    f"Failed to create presentation: presentationId is missing from API response",
                    tool_name=self.name
                )
            
            
            result_msg = f"Presentation '{title}' created successfully (ID: {presentation_id})"
            if first_slide_id:
                result_msg += f" (First slide ID: {first_slide_id})"
            if url:
                result_msg += f" URL: {url}"
            
            return result_msg
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create presentation: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetPresentationInput(BaseModel):
    """Input schema for get_presentation tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")


class GetPresentationTool(BaseTool):
    """Tool for getting information about a Google Slides presentation."""
    
    name: str = "get_presentation"
    description: str = """
    Получить информацию о презентации Google Slides.
    
    Параметры:
    - presentation_id: ID презентации или URL
    
    Ключевые слова: получить презентацию, информация о презентации, показать презентацию, структура презентации.
    """
    args_schema: type = GetPresentationInput
    
    @retry_on_mcp_error()
    async def _arun(self, presentation_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"presentationId": presentation_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_get", args, server_name="slides")
            
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
            
            title = result.get("title", "Untitled")
            slides_count = result.get("slidesCount", 0)
            slides = result.get("slides", [])
            
            response = f"Presentation: {title}\nSlides: {slides_count}\n"
            if slides:
                response += "Slide IDs:\n"
                for i, slide in enumerate(slides[:10], 1):
                    response += f"  {i}. {slide.get('slideId')}\n"
                if len(slides) > 10:
                    response += f"  ... and {len(slides) - 10} more"
            
            return response
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get presentation: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreatePresentationBatchInput(BaseModel):
    """Input schema for create_presentation_batch tool."""
    
    title: str = Field(description="Title of the presentation")
    slides: List[Dict[str, Any]] = Field(
        description="""Array of slide definitions. Each slide can have:
        - title: Slide title (optional)
        - content: Slide content - string or array of content items (text, bullet, subheading)
        - layout: Layout type (TITLE_AND_BODY, TITLE, BLANK, etc.) - default: TITLE_AND_BODY
        - image: Optional image configuration:
          * search_query: Search query for Unsplash (e.g., "ancient rome architecture")
          * position: "left", "right", or "center" (default: "right")
          * width: Width in inches (default: 4.0)
          * height: Height in inches (default: 3.0)
        - formatting: Optional formatting object with title_bold, title_font_size, body_font_size"""
    )
    theme: str = Field(
        default="professional",
        description="Presentation theme: 'professional' (business), 'creative' (marketing), 'minimal' (academic), 'dark' (tech). DEPRECATED: Use theme_source instead to copy style from existing presentation."
    )
    theme_source: Optional[str] = Field(
        default=None,
        description="Source for theme/style: presentation name (e.g., 'О собачках') to find in workspace and use as template. If not specified, creates presentation with standard Google Slides theme (no custom template). Use this when user says 'оформи как презентация X'."
    )


class CreatePresentationBatchTool(BaseTool):
    """Tool for creating a presentation with multiple slides using optimized batch operations."""
    
    name: str = "create_presentation_batch"
    description: str = """
    Создать презентацию с несколькими слайдами, оптимизированную с помощью batch операций.
    
    ⚡ ОПТИМИЗИРОВАНО ПО ПРОИЗВОДИТЕЛЬНОСТИ: Этот инструмент использует batchUpdate операции для минимизации API вызовов.
    Для N слайдов он делает только ~3-5 запросов вместо ~4N запросов, сокращая время создания с 4-10 секунд до 1-2 секунд.
    
    Используй этот инструмент когда:
    - Создаёшь презентации с 5+ слайдами
    - У тебя готово всё содержимое слайдов заранее
    - Важна производительность
    
    Параметры:
    - title: Название презентации
    - theme: Тема презентации (professional, creative, minimal, dark) - ОБЯЗАТЕЛЬНО
    - theme_source: Опционально - название существующей презентации из workspace для копирования стиля
    - slides: Массив объектов слайдов, каждый с:
      * title: Заголовок слайда (опционально)
      * content: Содержимое слайда - может быть:
        - String: обычный текст
        - Array: [{"type": "text", "text": "..."}, {"type": "bullet", "text": "..."}, {"type": "subheading", "text": "..."}]
      * layout: Тип макета (TITLE_AND_BODY, TITLE, BLANK, и т.д.) - по умолчанию: TITLE_AND_BODY
      * image: Опциональная конфигурация изображения:
        - search_query: Поисковый запрос Unsplash (например, "ancient rome architecture")
        - position: "left", "right" (по умолчанию), или "center"
        - width: Ширина в дюймах (по умолчанию: 4.0)
        - height: Высота в дюймах (по умолчанию: 3.0)
      * formatting: Опциональный объект форматирования:
        - title_bold: Сделать заголовок жирным (по умолчанию: true)
        - title_font_size: Размер шрифта заголовка в пунктах (по умолчанию: 28)
        - body_font_size: Размер шрифта тела в пунктах (по умолчанию: 16)
    
    Пример:
    {
      "title": "Моя презентация",
      "theme": "professional",
      "slides": [
        {
          "title": "Введение",
          "content": "Добро пожаловать в презентацию",
          "layout": "TITLE_AND_BODY"
        },
        {
          "title": "Ключевые моменты",
          "content": [
            {"type": "bullet", "text": "Первый пункт"},
            {"type": "bullet", "text": "Второй пункт"}
          ],
          "layout": "TITLE_AND_BODY",
          "image": {
            "search_query": "business meeting collaboration",
            "position": "right",
            "width": 4.0,
            "height": 3.0
          }
        }
      ]
    }
    
    Ключевые слова: создать презентацию, создать несколько слайдов, batch создание, оптимизированное создание.
    """
    args_schema: type = CreatePresentationBatchInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        title: str,
        slides: List[Dict[str, Any]],
        theme: str = "professional",
        theme_source: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        # #region agent log
        import json as _debug_json; import time as _debug_time
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_tool_entry","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:265","message":"_arun called with parameters","data":{"has_title":bool(title),"title_preview":title[:30] if title else "","has_slides":bool(slides),"slides_count":len(slides) if slides else 0,"has_theme":bool(theme),"theme":theme},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        # #endregion
        try:
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_args_build","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:278","message":"Building args dict","data":{"title":title[:30] if title else "","slides_count":len(slides) if slides else 0,"theme":theme,"will_add_theme":bool(theme)},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
            # #endregion
            args = {
                "title": title,
                "slides": slides
            }
            # #region agent log
            import json as _debug_json; import time as _debug_time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_theme_before","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:287","message":"Theme before adding to args","data":{"theme":theme,"theme_is_none":theme is None,"theme_source":theme_source,"theme_source_is_none":theme_source is None},"sessionId":"debug-session","runId":"run1","hypothesisId":"2A"}) + '\n')
            # #endregion
            if theme:
                args["theme"] = theme  # Backward compatibility
            if theme_source:
                args["theme_source"] = theme_source  # New: use presentation from workspace
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_args_ready","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:283","message":"Args dict ready","data":{"args_keys":list(args.keys()),"has_title":bool(args.get("title")),"has_slides":bool(args.get("slides")),"has_theme":bool(args.get("theme"))},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            # #endregion
            
            mcp_manager = get_mcp_manager()
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_mcp_call","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:286","message":"Calling MCP tool","data":{"tool_name":"slides_create_presentation_batch","args_keys":list(args.keys())},"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
            # #endregion
            result = await mcp_manager.call_tool("slides_create_presentation_batch", args, server_name="slides")
            
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
            
            # Check for errors
            if isinstance(result, dict) and "error" in result:
                error_msg = result.get("error", "Unknown error")
                raise ToolExecutionError(
                    f"Failed to create presentation: {error_msg}",
                    tool_name=self.name
                )
            
            presentation_id = result.get("presentationId")
            url = result.get("url", "")
            slides_created = result.get("slidesCreated", 0)
            
            if not presentation_id:
                raise ToolExecutionError(
                    f"Failed to create presentation: presentationId is missing from API response",
                    tool_name=self.name
                )
            
            result_msg = f"Presentation '{title}' created successfully (ID: {presentation_id}, {slides_created} slides)"
            if url:
                result_msg += f" URL: {url}"
            
            return result_msg
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create presentation: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSlideInput(BaseModel):
    """Input schema for create_slide tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    layout: Optional[str] = Field(default="TITLE_AND_BODY", description="Layout type (TITLE, TITLE_AND_BODY, BLANK, etc.)")
    insertion_index: Optional[int] = Field(default=None, description="Index where to insert the slide")


class CreateSlideTool(BaseTool):
    """Tool for creating a new slide in a presentation."""
    
    name: str = "create_slide"
    description: str = """
    Добавить НОВЫЙ СЛАЙД в СУЩЕСТВУЮЩУЮ презентацию Google Slides.
    
    ⚠️ ВАЖНО: 
    - Это добавляет слайд в УЖЕ СОЗДАННУЮ презентацию. НЕ используй create_presentation для этого!
    - Помни: Когда вызывается create_presentation, она уже создаёт презентацию с ОДНИМ слайдом. Поэтому если пользователь просит N слайдов всего, нужно создать только N-1 дополнительных слайдов с помощью этого инструмента.
    
    Параметры:
    - presentation_id: ID презентации или URL (из ранее созданной презентации)
    - layout: Тип макета (TITLE, TITLE_AND_BODY, BLANK, и т.д.) (по умолчанию: TITLE_AND_BODY)
    - insertion_index: Индекс для вставки слайда (опционально)
    
    Используй это для добавления слайдов в презентацию, которая уже была создана (либо через create_presentation, либо через create_presentation_from_doc).
    
    Ключевые слова: добавить слайд, создать слайд, новый слайд.
    """
    args_schema: type = CreateSlideInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        layout: Optional[str] = "TITLE_AND_BODY",
        insertion_index: Optional[int] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # #region debug log
            args = {"presentationId": presentation_id, "layout": layout}
            if insertion_index is not None:
                args["insertionIndex"] = insertion_index
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_slide", args, server_name="slides")
            
            
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
            
            # Try multiple ways to get slide_id
            slide_id = None
            if isinstance(result, dict):
                slide_id = result.get("slideId") or result.get("slide_id") or result.get("objectId") or result.get("pageObjectId")
                # Check if result has nested structure
                if not slide_id and "replies" in result:
                    replies = result.get("replies", [])
                    if replies and isinstance(replies, list) and len(replies) > 0:
                        first_reply = replies[0]
                        if isinstance(first_reply, dict):
                            create_slide = first_reply.get("createSlide", {})
                            slide_id = create_slide.get("objectId")
            
            if not slide_id:
                raise ToolExecutionError(
                    f"Failed to create slide: slideId is missing from API response",
                    tool_name=self.name
                )
            
            return f"Slide created successfully (ID: {slide_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create slide: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class InsertSlideTextInput(BaseModel):
    """Input schema for insert_slide_text tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    text: str = Field(description="Text to insert")
    target_element: Optional[str] = Field(default="body", description="Which element to insert into: 'title' for slide title (bold), 'body' for content")
    element_id: Optional[str] = Field(default=None, description="Text box element ID (optional, auto-detected based on target_element)")
    insert_index: Optional[int] = Field(default=-1, description="Character index where to insert (default: append to end)")


class InsertSlideTextTool(BaseTool):
    """Tool for inserting text into a slide's title or body."""
    
    name: str = "insert_slide_text"
    description: str = """
    Вставить текст в заголовок или тело слайда.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - text: Текст для вставки
    - target_element: 'title' для заголовка слайда (жирный), 'body' для содержимого
    - element_id: ID текстового блока (опционально, определяется автоматически)
    - insert_index: Индекс символа (по умолчанию: добавить в конец)
    
    КРИТИЧЕСКИ ВАЖНЫЙ ПАТТЕРН ИСПОЛЬЗОВАНИЯ - вызывай этот инструмент ДВА РАЗА для каждого слайда:
    1. Первый вызов с target_element='title' для вставки заголовка слайда
    2. Второй вызов с target_element='body' для вставки содержимого/текста слайда
    
    Пример для одного слайда:
    - Вызов 1: insert_slide_text(page_id='slide_xyz', text='Мой заголовок', target_element='title')
    - Вызов 2: insert_slide_text(page_id='slide_xyz', text='Текст содержимого здесь', target_element='body')
    
    Ключевые слова: вставить текст в слайд, добавить текст, вставить заголовок, вставить содержимое.
    """
    args_schema: type = InsertSlideTextInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        text: str,
        target_element: Optional[str] = "body",
        element_id: Optional[str] = None,
        insert_index: Optional[int] = -1
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "text": text,
                "targetElement": target_element or "body"
            }
            if element_id:
                args["elementId"] = element_id
            if insert_index is not None and insert_index != -1:
                args["insertIndex"] = insert_index
            
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_insert_text", args, server_name="slides")
            
            
            return f"Text inserted into slide successfully (page ID: {page_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to insert text: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FormatSlideTextInput(BaseModel):
    """Input schema for format_slide_text tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID - REQUIRED. Get from get_presentation. DO NOT pass 'slides' array!")
    element_id: str = Field(description="Text box element ID - REQUIRED. Get from get_presentation. DO NOT pass 'slides' array!")
    start_index: Optional[int] = Field(default=0, description="Start character index (0-based). Default: 0 (start of text)")
    end_index: Optional[int] = Field(default=None, description="End character index (exclusive). Default: None (end of text - will be auto-detected)")
    bold: Optional[bool] = Field(default=None, description="Make text bold")
    italic: Optional[bool] = Field(default=None, description="Make text italic")
    foreground_color: Optional[Dict[str, float]] = Field(default=None, description="Text color as {red, green, blue, alpha} (0-1)")
    font_size: Optional[float] = Field(default=None, description="Font size in points")
    font_family: Optional[str] = Field(default=None, description="Font family name (e.g., 'Arial', 'Roboto')")
    underline: Optional[bool] = Field(default=None, description="Make text underlined")
    strikethrough: Optional[bool] = Field(default=None, description="Make text strikethrough")
    background_color: Optional[Dict[str, float]] = Field(default=None, description="Text background color as {red, green, blue, alpha} (0-1)")


class FormatSlideTextTool(BaseTool):
    """Tool for formatting text in a slide."""
    
    name: str = "format_slide_text"
    description: str = """
    Format text in a slide (bold, italic, colors, font size, font family, underline, strikethrough).
    
    ⚠️ ВАЖНО: 
    - Этот инструмент НЕ создаёт списки! Для списков используй create_slide_bullets.
    - Этот инструмент форматирует ТОЛЬКО ОДИН элемент текста за раз. НЕ передавай массив slides!
    - Если нужно отформатировать несколько элементов, вызывай этот инструмент несколько раз для каждого элемента отдельно.
    - Для форматирования всех слайдов презентации используй create_presentation_batch с форматированием в определении слайдов.
    
    Когда использовать:
    - Пользователь просит "жирный текст" → используй bold=True
    - Пользователь просит "курсив" → используй italic=True
    - Пользователь просит "большой шрифт" → используй font_size=24 (или больше, например 32 для заголовков)
    - Пользователь просит "красный текст" → используй foreground_color={"red": 1.0, "green": 0.0, "blue": 0.0, "alpha": 1.0}
    - Пользователь просит "подчёркнутый текст" → используй underline=True
    - Пользователь просит "зачёркнутый текст" → используй strikethrough=True
    
    ПРАВИЛЬНЫЙ ПОРЯДОК:
    1. Сначала вставь текст через insert_slide_text
    2. Затем примени форматирование через format_slide_text с правильными start_index и end_index
    
    ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ (всегда передавай):
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID (получи через get_presentation, НЕ передавай массив slides!)
    - element_id: Text box element ID (получи через get_presentation, НЕ передавай массив slides!)
    - start_index: Start character index (0-based) - начало текста для форматирования (default: 0)
    - end_index: End character index (exclusive) - конец текста для форматирования (default: None - форматирует весь текст)
    - bold: Optional boolean - сделать текст жирным
    - italic: Optional boolean - сделать текст курсивом
    - foreground_color: Optional dict - цвет текста {"red": 0-1, "green": 0-1, "blue": 0-1, "alpha": 0-1}
    - font_size: Optional float - размер шрифта в пунктах (например, 12, 14, 18, 24, 32)
    - font_family: Optional string - название шрифта (например, "Arial", "Roboto", "Times New Roman")
    - underline: Optional boolean - подчеркнуть текст
    - strikethrough: Optional boolean - зачеркнуть текст
    - background_color: Optional dict - цвет фона текста {"red": 0-1, "green": 0-1, "blue": 0-1, "alpha": 0-1}
    
    Примеры цветов:
    - Красный: {"red": 1.0, "green": 0.0, "blue": 0.0, "alpha": 1.0}
    - Синий: {"red": 0.0, "green": 0.0, "blue": 1.0, "alpha": 1.0}
    - Зелёный: {"red": 0.0, "green": 1.0, "blue": 0.0, "alpha": 1.0}
    - Чёрный: {"red": 0.0, "green": 0.0, "blue": 0.0, "alpha": 1.0}
    - Белый: {"red": 1.0, "green": 1.0, "blue": 1.0, "alpha": 1.0}
    """
    args_schema: type = FormatSlideTextInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str = None,
        element_id: str = None,
        start_index: Optional[int] = 0,
        end_index: Optional[int] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        foreground_color: Optional[Dict[str, float]] = None,
        font_size: Optional[float] = None,
        font_family: Optional[str] = None,
        underline: Optional[bool] = None,
        strikethrough: Optional[bool] = None,
        background_color: Optional[Dict[str, float]] = None,
        **kwargs  # Catch unexpected arguments like 'slides'
    ) -> str:
        """Execute the tool asynchronously."""
        # #region agent log
        import json as _debug_json; import time as _debug_time
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_entry","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:592","message":"format_slide_text _arun called","data":{"has_presentation_id":bool(presentation_id),"has_page_id":bool(page_id),"has_element_id":bool(element_id),"start_index":start_index,"end_index":end_index,"start_index_is_none":start_index is None,"end_index_is_none":end_index is None,"kwargs_keys":list(kwargs.keys()),"has_slides_in_kwargs":"slides" in kwargs},"sessionId":"debug-session","runId":"run1","hypothesisId":"Q"}) + '\n')
        # #endregion
        
        # #region agent log
        import json as _debug_json; import time as _debug_time
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_entry","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:609","message":"format_slide_text called","data":{"has_page_id":bool(page_id),"has_element_id":bool(element_id),"has_slides_in_kwargs":"slides" in kwargs,"kwargs_keys":list(kwargs.keys())},"sessionId":"debug-session","runId":"run1","hypothesisId":"3A"}) + '\n')
        # #endregion
        
        # Validate that 'slides' is not passed (common LLM mistake)
        if 'slides' in kwargs:
            error_msg = (
                "ERROR: format_slide_text does NOT accept 'slides' array. "
                "This tool formats only ONE text element at a time. "
                "Required parameters: presentation_id, page_id (slide ID), element_id (text box ID). "
                "To get page_id and element_id, first call get_presentation to see the structure. "
                "If you need to format multiple slides, call format_slide_text separately for each element."
            )
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_error_slides","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:600","message":"format_slide_text called with slides array (error)","data":{"error":error_msg},"sessionId":"debug-session","runId":"run1","hypothesisId":"3A"}) + '\n')
            # #endregion
            raise ToolExecutionError(error_msg, tool_name=self.name)
        
        # Validate required parameters
        if not page_id:
            error_msg = (
                "ERROR: 'page_id' is required for format_slide_text. "
                "This is the slide ID (e.g., 'slide_abc123'). "
                "Get it by calling get_presentation first to see the presentation structure."
            )
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_missing_page_id","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:627","message":"Missing page_id","data":{"error":error_msg},"sessionId":"debug-session","runId":"run1","hypothesisId":"3C"}) + '\n')
            # #endregion
            raise ToolExecutionError(error_msg, tool_name=self.name)
        
        if not element_id:
            error_msg = (
                "ERROR: 'element_id' is required for format_slide_text. "
                "This is the text box element ID. "
                "Get it by calling get_presentation first to see the presentation structure."
            )
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_missing_element_id","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:635","message":"Missing element_id","data":{"error":error_msg},"sessionId":"debug-session","runId":"run1","hypothesisId":"3C"}) + '\n')
            # #endregion
            raise ToolExecutionError(error_msg, tool_name=self.name)
        
        try:
            # Default start_index to 0 if None
            if start_index is None:
                start_index = 0
            
            # If end_index is None, use -1 as special value to indicate "format entire text"
            # MCP server will handle -1 by getting actual text length
            if end_index is None:
                end_index = -1  # Special value: format entire text
                # #region agent log
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                    _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_auto_end","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:600","message":"end_index not provided, using -1 for auto-detect","data":{"end_index":end_index},"sessionId":"debug-session","runId":"run1","hypothesisId":"AB"}) + '\n')
                # #endregion
            
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_args","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:594","message":"Building format_slide_text args","data":{"presentation_id":presentation_id[:30] if presentation_id else "","page_id":page_id[:20] if page_id else "","element_id":element_id[:20] if element_id else "","start_index":start_index,"end_index":end_index},"sessionId":"debug-session","runId":"run1","hypothesisId":"R"}) + '\n')
            # #endregion
            
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "elementId": element_id,
                "startIndex": start_index,
                "endIndex": end_index
            }
            
            if bold is not None:
                args["bold"] = bold
            if italic is not None:
                args["italic"] = italic
            if foreground_color:
                args["foregroundColor"] = foreground_color
            if font_size is not None:
                args["fontSize"] = font_size
            if font_family:
                args["fontFamily"] = font_family
            if underline is not None:
                args["underline"] = underline
            if strikethrough is not None:
                args["strikethrough"] = strikethrough
            if background_color:
                args["backgroundColor"] = background_color
            
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_mcp_call","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:641","message":"Calling MCP slides_format_text","data":{"args_keys":list(args.keys()),"has_bold":"bold" in args,"has_italic":"italic" in args,"has_font_size":"fontSize" in args,"has_font_family":"fontFamily" in args,"bold_value":args.get("bold"),"font_size_value":args.get("fontSize"),"font_family_value":args.get("fontFamily")},"sessionId":"debug-session","runId":"run1","hypothesisId":"AL"}) + '\n')
            # #endregion
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_format_text", args, server_name="slides")
            
            # #region agent log
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_format_text_mcp_result","timestamp":int(_debug_time.time()*1000),"location":"slides_tools.py:644","message":"MCP slides_format_text result","data":{"result_type":type(result).__name__,"result_preview":str(result)[:200] if result else ""},"sessionId":"debug-session","runId":"run1","hypothesisId":"AM"}) + '\n')
            # #endregion
            
            formats = []
            if bold:
                formats.append("bold")
            if italic:
                formats.append("italic")
            if foreground_color:
                formats.append("text color")
            if font_size:
                formats.append(f"font size {font_size}pt")
            if font_family:
                formats.append(f"font {font_family}")
            if underline:
                formats.append("underline")
            if strikethrough:
                formats.append("strikethrough")
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


class CreatePresentationFromDocInput(BaseModel):
    """Input schema for create_presentation_from_doc tool."""
    
    document_id: str = Field(description="Document ID or URL")
    presentation_title: Optional[str] = Field(default=None, description="Title for the new presentation (optional, defaults to document title)")
    theme: Optional[str] = Field(
        default="professional",
        description="Presentation theme. Choose based on content: professional (business), creative (marketing), minimal (academic), dark (tech)"
    )


class CreatePresentationFromDocTool(BaseTool):
    """Tool for creating a presentation from a Google Docs document."""
    
    name: str = "create_presentation_from_doc"
    description: str = """
    Создать профессиональную презентацию из документа Google Docs.
    
    Структура документа анализируется автоматически:
    - Заголовки H1 создают разделительные слайды
    - Заголовки H2 создают слайды с содержимым и заголовками
    - Обычный текст становится маркированными списками
    - Изображения из документа включаются
    
    Параметры:
    - document_id: ID документа или URL
    - presentation_title: Название новой презентации (опционально, по умолчанию: название документа)
    - theme: Тема презентации - выбирай в зависимости от содержимого:
      * professional: Бизнес-презентации, отчёты, официальные документы (синие акценты, белый фон)
      * creative: Маркетинг, стартапы, творческие проекты (яркие цвета, уникальные шрифты)
      * minimal: Академические, технические презентации (чистый стиль, много белого пространства)
      * dark: IT, технологические презентации (тёмный фон, светлый текст)
    
    Ключевые слова: создать презентацию из документа, презентация из документа, конвертировать документ в презентацию.
    """
    args_schema: type = CreatePresentationFromDocInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        document_id: str,
        presentation_title: Optional[str] = None,
        theme: Optional[str] = "professional"
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "theme": theme or "professional"
            }
            if presentation_title:
                args["presentationTitle"] = presentation_title
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_presentation_from_doc", args, server_name="slides")
            
            
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
            
            
            # Check for error in result first
            if isinstance(result, dict) and "error" in result:
                return f"Error creating presentation from document: {result['error']}"
            
            presentation_id = result.get("presentationId")
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            slides_created = result.get("slidesCreated", 0)
            theme_used = result.get("theme", "professional")
            template_used = result.get("templateUsed", False)
            
            # Additional check - if presentation_id is None, something went wrong
            if not presentation_id:
                return f"Error creating presentation from document: No presentation ID returned"
            
            response = f"Presentation '{title}' created successfully from document (ID: {presentation_id}, {slides_created} slides, theme: {theme_used})"
            if url:
                response += f" URL: {url}"
            if template_used:
                response += " [template applied]"
            
            
            return response
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create presentation from document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class AddSlideImageInput(BaseModel):
    """Input schema for add_slide_image tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    image_url: str = Field(description="Public URL of the image")
    x: float = Field(description="X position in EMU (use inches_to_emu helper for inches)")
    y: float = Field(description="Y position in EMU (use inches_to_emu helper for inches)")
    width: float = Field(description="Width in EMU (use inches_to_emu helper for inches)")
    height: float = Field(description="Height in EMU (use inches_to_emu helper for inches)")


class AddSlideImageTool(BaseTool):
    """Tool for adding an image to a slide."""
    
    name: str = "add_slide_image"
    description: str = """
    Добавить изображение на слайд из публичного URL.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - image_url: Публичный URL изображения
    - x: Позиция X в EMU (используй helper inches_to_emu: 1 дюйм = 914400 EMU)
    - y: Позиция Y в EMU
    - width: Ширина в EMU
    - height: Высота в EMU
    
    Пример: Для отступа 1 дюйм и изображения 5x3 дюйма:
    x = inches_to_emu(1.0), y = inches_to_emu(1.0)
    width = inches_to_emu(5.0), height = inches_to_emu(3.0)
    
    Ключевые слова: добавить изображение, вставить изображение, добавить картинку на слайд.
    """
    args_schema: type = AddSlideImageInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        image_url: str,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "imageUrl": image_url,
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_add_image", args, server_name="slides")
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if isinstance(result, dict) and "error" in result:
                raise ToolExecutionError(
                    f"Failed to add image: {result.get('error')}",
                    tool_name=self.name
                )
            
            image_id = result.get("imageId")
            return f"Image added successfully (ID: {image_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to add image: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSlideShapeInput(BaseModel):
    """Input schema for create_slide_shape tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    shape_type: str = Field(description="Shape type: RECTANGLE, ELLIPSE, ARROW_EAST, TEXT_BOX, etc.")
    x: float = Field(description="X position in EMU")
    y: float = Field(description="Y position in EMU")
    width: float = Field(description="Width in EMU")
    height: float = Field(description="Height in EMU")
    fill_color: Optional[Dict[str, float]] = Field(default=None, description="Fill color {red, green, blue, alpha} (0-1)")
    border_color: Optional[Dict[str, float]] = Field(default=None, description="Border color {red, green, blue, alpha} (0-1)")
    border_weight: Optional[float] = Field(default=None, description="Border weight in points")


class CreateSlideShapeTool(BaseTool):
    """Tool for creating a shape on a slide."""
    
    name: str = "create_slide_shape"
    description: str = """
    Создать фигуру на слайде (прямоугольник, круг, стрелка и т.д.).
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - shape_type: Тип фигуры (RECTANGLE, ELLIPSE, ARROW_EAST, TEXT_BOX, и т.д.)
    - x, y: Позиция в EMU
    - width, height: Размер в EMU
    - fill_color: Опциональный цвет заливки
    - border_color: Опциональный цвет границы
    - border_weight: Опциональная толщина границы в пунктах
    
    Ключевые слова: создать фигуру, добавить фигуру, фигура на слайде.
    """
    args_schema: type = CreateSlideShapeInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        shape_type: str,
        x: float,
        y: float,
        width: float,
        height: float,
        fill_color: Optional[Dict[str, float]] = None,
        border_color: Optional[Dict[str, float]] = None,
        border_weight: Optional[float] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "shapeType": shape_type,
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            }
            
            if fill_color:
                args["fillColor"] = fill_color
            if border_color:
                args["borderColor"] = border_color
            if border_weight:
                args["borderWeight"] = border_weight
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_shape", args, server_name="slides")
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if isinstance(result, dict) and "error" in result:
                raise ToolExecutionError(
                    f"Failed to create shape: {result.get('error')}",
                    tool_name=self.name
                )
            
            shape_id = result.get("shapeId")
            return f"Shape created successfully (ID: {shape_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create shape: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class SetSlideBackgroundInput(BaseModel):
    """Input schema for set_slide_background tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    solid_color: Optional[Dict[str, float]] = Field(default=None, description="Solid background color {red, green, blue, alpha} (0-1)")
    image_url: Optional[str] = Field(default=None, description="Background image URL (if not using solidColor)")


class SetSlideBackgroundTool(BaseTool):
    """Tool for setting slide background."""
    
    name: str = "set_slide_background"
    description: str = """
    Установить фон слайда (сплошной цвет или изображение).
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - solid_color: Опциональный сплошной цвет фона {red, green, blue, alpha} (0-1)
    - image_url: Опциональный URL фонового изображения (если не используешь solidColor)
    
    Укажи либо solid_color, либо image_url, не оба.
    
    Ключевые слова: установить фон, фон слайда, цвет фона, фоновое изображение.
    """
    args_schema: type = SetSlideBackgroundInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        solid_color: Optional[Dict[str, float]] = None,
        image_url: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id
            }
            
            if solid_color:
                args["solidColor"] = solid_color
            elif image_url:
                args["imageUrl"] = image_url
            else:
                raise ToolExecutionError(
                    "Either solid_color or image_url must be provided",
                    tool_name=self.name
                )
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_set_background", args, server_name="slides")
            
            return "Slide background updated successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to set background: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSlideTableInput(BaseModel):
    """Input schema for create_slide_table tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    rows: int = Field(description="Number of rows")
    columns: int = Field(description="Number of columns")
    x: float = Field(description="X position in EMU")
    y: float = Field(description="Y position in EMU")
    width: float = Field(description="Width in EMU")
    height: float = Field(description="Height in EMU")


class CreateSlideTableTool(BaseTool):
    """Tool for creating a table on a slide."""
    
    name: str = "create_slide_table"
    description: str = """
    Создать таблицу на слайде.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - rows: Количество строк
    - columns: Количество столбцов
    - x, y: Позиция в EMU
    - width, height: Размер в EMU
    
    Ключевые слова: создать таблицу, добавить таблицу, таблица на слайде.
    """
    args_schema: type = CreateSlideTableInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        rows: int,
        columns: int,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "rows": rows,
                "columns": columns,
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_table", args, server_name="slides")
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if isinstance(result, dict) and "error" in result:
                raise ToolExecutionError(
                    f"Failed to create table: {result.get('error')}",
                    tool_name=self.name
                )
            
            table_id = result.get("tableId")
            return f"Table created successfully (ID: {table_id}, {rows}x{columns})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create table: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class UpdateTableCellInput(BaseModel):
    """Input schema for update_table_cell tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    table_id: str = Field(description="Table element ID")
    row_index: int = Field(description="Row index (0-based)")
    column_index: int = Field(description="Column index (0-based)")
    text: str = Field(description="Text to insert into cell")


class UpdateTableCellTool(BaseTool):
    """Tool for updating text in a table cell."""
    
    name: str = "update_table_cell"
    description: str = """
    Обновить текст в ячейке таблицы.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - table_id: ID элемента таблицы
    - row_index: Индекс строки (начиная с 0)
    - column_index: Индекс столбца (начиная с 0)
    - text: Текст для вставки в ячейку
    
    Ключевые слова: обновить ячейку, изменить ячейку, текст в ячейке.
    """
    args_schema: type = UpdateTableCellInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        table_id: str,
        row_index: int,
        column_index: int,
        text: str
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "tableId": table_id,
                "rowIndex": row_index,
                "columnIndex": column_index,
                "text": text
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_update_table_cell", args, server_name="slides")
            
            return f"Table cell ({row_index}, {column_index}) updated successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to update table cell: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSlideChartInput(BaseModel):
    """Input schema for create_slide_chart tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID containing the chart")
    chart_id: int = Field(description="Chart ID in the spreadsheet")
    x: float = Field(description="X position in EMU")
    y: float = Field(description="Y position in EMU")
    width: float = Field(description="Width in EMU")
    height: float = Field(description="Height in EMU")
    linking_mode: Optional[str] = Field(default="LINKED", description="Linking mode: LINKED or NOT_LINKED_IMAGE")


class CreateSlideChartTool(BaseTool):
    """Tool for creating a chart on a slide from Google Sheets."""
    
    name: str = "create_slide_chart"
    description: str = """
    Создать график на слайде из Google Sheets.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - spreadsheet_id: ID таблицы Google Sheets, содержащей график
    - chart_id: ID графика в таблице (должен быть создан в Sheets сначала)
    - x, y: Позиция в EMU
    - width, height: Размер в EMU
    - linking_mode: LINKED (обновляется с Sheets) или NOT_LINKED_IMAGE (статическое изображение)
    
    Ключевые слова: создать график, добавить график, график на слайде, диаграмма.
    """
    args_schema: type = CreateSlideChartInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        spreadsheet_id: str,
        chart_id: int,
        x: float,
        y: float,
        width: float,
        height: float,
        linking_mode: Optional[str] = "LINKED"
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "spreadsheetId": spreadsheet_id,
                "chartId": chart_id,
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
                "linkingMode": linking_mode
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_chart", args, server_name="slides")
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if isinstance(result, dict) and "error" in result:
                raise ToolExecutionError(
                    f"Failed to create chart: {result.get('error')}",
                    tool_name=self.name
                )
            
            chart_element_id = result.get("chartId")
            return f"Chart created successfully (ID: {chart_element_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create chart: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FormatSlideParagraphInput(BaseModel):
    """Input schema for format_slide_paragraph tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    element_id: str = Field(description="Text box element ID")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
    alignment: Optional[str] = Field(default=None, description="Text alignment: START, CENTER, END, JUSTIFIED")
    line_spacing: Optional[float] = Field(default=None, description="Line spacing multiplier (e.g., 1.5 for 1.5x)")
    space_above: Optional[float] = Field(default=None, description="Space above paragraph in points")
    space_below: Optional[float] = Field(default=None, description="Space below paragraph in points")


class FormatSlideParagraphTool(BaseTool):
    """Tool for formatting paragraph style."""
    
    name: str = "format_slide_paragraph"
    description: str = """
    Форматировать стиль абзаца (выравнивание, межстрочный интервал, отступы).
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - element_id: ID текстового блока
    - start_index: Начальный индекс символа (начиная с 0)
    - end_index: Конечный индекс символа (исключающий)
    - alignment: Опциональное выравнивание текста (START, CENTER, END, JUSTIFIED)
    - line_spacing: Опциональный множитель межстрочного интервала (например, 1.5)
    - space_above: Опциональный отступ сверху абзаца в пунктах
    - space_below: Опциональный отступ снизу абзаца в пунктах
    
    Ключевые слова: форматировать абзац, выравнивание текста, межстрочный интервал.
    """
    args_schema: type = FormatSlideParagraphInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        element_id: str,
        start_index: int,
        end_index: int,
        alignment: Optional[str] = None,
        line_spacing: Optional[float] = None,
        space_above: Optional[float] = None,
        space_below: Optional[float] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "elementId": element_id,
                "startIndex": start_index,
                "endIndex": end_index
            }
            
            if alignment:
                args["alignment"] = alignment
            if line_spacing:
                args["lineSpacing"] = line_spacing
            if space_above:
                args["spaceAbove"] = space_above
            if space_below:
                args["spaceBelow"] = space_below
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_format_paragraph", args, server_name="slides")
            
            return "Paragraph formatting applied successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to format paragraph: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSlideBulletsInput(BaseModel):
    """Input schema for create_slide_bullets tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    element_id: str = Field(description="Text box element ID")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
    bullet_preset: Optional[str] = Field(default="BULLET_DISC_CIRCLE_SQUARE", description="Bullet preset: BULLET_DISC_CIRCLE_SQUARE, NUMBERED_DIGIT_ALPHA_ROMAN, etc.")


class CreateSlideBulletsTool(BaseTool):
    """Tool for creating bulleted or numbered list."""
    
    name: str = "create_slide_bullets"
    description: str = """
    Create bulleted or numbered list from text in a slide.
    
    ⚠️ КРИТИЧЕСКИ ВАЖНО: Используй этот инструмент, когда пользователь просит:
    - "нумерованный список" → используй bullet_preset="NUMBERED_DIGIT_ALPHA_ROMAN"
    - "маркированный список" → используй bullet_preset="BULLET_DISC_CIRCLE_SQUARE"
    - "список" (без уточнения) → используй bullet_preset="BULLET_DISC_CIRCLE_SQUARE" (по умолчанию)
    
    ПРАВИЛЬНЫЙ ПОРЯДОК ДЕЙСТВИЙ:
    1. Сначала вставь текст в слайд через insert_slide_text (каждая строка списка на новой строке, разделены \n)
    2. Затем примени форматирование списка через create_slide_bullets с правильными start_index и end_index
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Text box element ID (где находится текст)
    - start_index: Start character index (0-based) - начало текста для списка
    - end_index: End character index (exclusive) - конец текста для списка
    - bullet_preset: Bullet preset:
      * "BULLET_DISC_CIRCLE_SQUARE" - маркированный список (точки, круги, квадраты) - по умолчанию
      * "NUMBERED_DIGIT_ALPHA_ROMAN" - нумерованный список (1, 2, 3 или a, b, c или I, II, III)
      * "BULLET_ARROW_DIAMOND_DISC" - стрелки и ромбы
      * "BULLET_CHECKBOX" - чекбоксы
    
    Примеры использования:
    - Пользователь: "сделай нумерованный список" → 
      create_slide_bullets(..., bullet_preset="NUMBERED_DIGIT_ALPHA_ROMAN")
    - Пользователь: "сделай маркированный список" → 
      create_slide_bullets(..., bullet_preset="BULLET_DISC_CIRCLE_SQUARE")
    - Пользователь: "список" → 
      create_slide_bullets(..., bullet_preset="BULLET_DISC_CIRCLE_SQUARE")
    
    ВАЖНО: Этот инструмент НЕ вставляет текст! Сначала используй insert_slide_text, затем create_slide_bullets.
    """
    args_schema: type = CreateSlideBulletsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        element_id: str,
        start_index: int,
        end_index: int,
        bullet_preset: Optional[str] = "BULLET_DISC_CIRCLE_SQUARE"
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "elementId": element_id,
                "startIndex": start_index,
                "endIndex": end_index,
                "bulletPreset": bullet_preset
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_bullets", args, server_name="slides")
            
            return "Bullets created successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create bullets: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class UpdateElementTransformInput(BaseModel):
    """Input schema for update_element_transform tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    element_id: str = Field(description="Element ID")
    translate_x: Optional[float] = Field(default=None, description="X translation in EMU")
    translate_y: Optional[float] = Field(default=None, description="Y translation in EMU")
    scale_x: Optional[float] = Field(default=None, description="X scale factor (1.0 = 100%)")
    scale_y: Optional[float] = Field(default=None, description="Y scale factor (1.0 = 100%)")
    rotation: Optional[float] = Field(default=None, description="Rotation angle in degrees")


class UpdateElementTransformTool(BaseTool):
    """Tool for updating element position, size, and rotation."""
    
    name: str = "update_element_transform"
    description: str = """
    Обновить позицию, размер и поворот элемента.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - element_id: ID элемента
    - translate_x: Опциональное смещение по X в EMU
    - translate_y: Опциональное смещение по Y в EMU
    - scale_x: Опциональный масштаб по X (1.0 = 100%, 2.0 = 200%)
    - scale_y: Опциональный масштаб по Y (1.0 = 100%, 2.0 = 200%)
    - rotation: Опциональный угол поворота в градусах
    
    Ключевые слова: переместить элемент, изменить размер, повернуть элемент, трансформация элемента.
    """
    args_schema: type = UpdateElementTransformInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        element_id: str,
        translate_x: Optional[float] = None,
        translate_y: Optional[float] = None,
        scale_x: Optional[float] = None,
        scale_y: Optional[float] = None,
        rotation: Optional[float] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "elementId": element_id
            }
            
            if translate_x is not None:
                args["translateX"] = translate_x
            if translate_y is not None:
                args["translateY"] = translate_y
            if scale_x is not None:
                args["scaleX"] = scale_x
            if scale_y is not None:
                args["scaleY"] = scale_y
            if rotation is not None:
                args["rotation"] = rotation
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_update_element_transform", args, server_name="slides")
            
            return "Element transform updated successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to update element transform: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class DeleteSlideElementInput(BaseModel):
    """Input schema for delete_slide_element tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    element_id: str = Field(description="Element ID to delete")


class DeleteSlideElementTool(BaseTool):
    """Tool for deleting an element from a slide."""
    
    name: str = "delete_slide_element"
    description: str = """
    Удалить элемент со слайда.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - element_id: ID элемента для удаления
    
    Ключевые слова: удалить элемент, удалить со слайда.
    """
    args_schema: type = DeleteSlideElementInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        element_id: str
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "elementId": element_id
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_delete_element", args, server_name="slides")
            
            return f"Element {element_id} deleted successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to delete element: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetSlideMastersInput(BaseModel):
    """Input schema for get_slide_masters tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")


class GetSlideMastersTool(BaseTool):
    """Tool for getting available slide masters and layouts."""
    
    name: str = "get_slide_masters"
    description: str = """
    Получить доступные макеты слайдов и шаблоны.
    
    Параметры:
    - presentation_id: ID презентации или URL
    
    Возвращает список доступных макетов с их ID и названиями.
    
    Ключевые слова: получить макеты, доступные макеты, шаблоны слайдов.
    """
    args_schema: type = GetSlideMastersInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_get_masters", args, server_name="slides")
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            if isinstance(result, dict) and "error" in result:
                raise ToolExecutionError(
                    f"Failed to get masters: {result.get('error')}",
                    tool_name=self.name
                )
            
            masters = result.get("masters", [])
            response = f"Available layouts ({len(masters)}):\n"
            for i, master in enumerate(masters[:20], 1):
                layout_name = master.get("displayName") or master.get("name", "Unknown")
                response += f"  {i}. {layout_name} (ID: {master.get('layoutId')})\n"
            if len(masters) > 20:
                response += f"  ... and {len(masters) - 20} more"
            
            return response
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get masters: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ApplySlideLayoutInput(BaseModel):
    """Input schema for apply_slide_layout tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    page_id: str = Field(description="Page (slide) ID")
    layout_id: str = Field(description="Layout ID to apply")


class ApplySlideLayoutTool(BaseTool):
    """Tool for applying a layout to a slide."""
    
    name: str = "apply_slide_layout"
    description: str = """
    Применить макет к слайду.
    
    Параметры:
    - presentation_id: ID презентации или URL
    - page_id: ID страницы (слайда)
    - layout_id: ID макета для применения (используй get_slide_masters, чтобы увидеть доступные макеты)
    
    Ключевые слова: применить макет, изменить макет слайда.
    """
    args_schema: type = ApplySlideLayoutInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        layout_id: str
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "layoutId": layout_id
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_apply_layout", args, server_name="slides")
            
            return f"Layout {layout_id} applied successfully"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to apply layout: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_slides_tools() -> List[BaseTool]:
    """
    Get Google Slides tools for presentation operations.
    
    Returns:
        List of BaseTool instances for Slides operations
    """
    return [
        CreatePresentationTool(),
        GetPresentationTool(),
        CreateSlideTool(),
        InsertSlideTextTool(),
        FormatSlideTextTool(),
        CreatePresentationFromDocTool(),
        CreatePresentationBatchTool(),
        AddSlideImageTool(),
        CreateSlideShapeTool(),
        SetSlideBackgroundTool(),
        CreateSlideTableTool(),
        UpdateTableCellTool(),
        CreateSlideChartTool(),
        FormatSlideParagraphTool(),
        CreateSlideBulletsTool(),
        UpdateElementTransformTool(),
        DeleteSlideElementTool(),
        GetSlideMastersTool(),
        ApplySlideLayoutTool(),
    ]

