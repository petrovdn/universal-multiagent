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
    Create a NEW EMPTY Google Slides presentation in the workspace folder.
    
    ⚠️ IMPORTANT: This creates a NEW presentation file. To add slides to an EXISTING presentation, use create_slide instead!
    
    Input:
    - title: Title of the presentation
    
    Use this ONLY when you need to create a brand new presentation file.
    """
    args_schema: type = CreatePresentationInput
    
    @retry_on_mcp_error()
    async def _arun(self, title: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create", args, server_name="slides")
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreatePresentationTool._arun:after_mcp_call",
                        "message": "MCP call completed, raw result",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_is_list": isinstance(result, list),
                            "result_length": len(result) if isinstance(result, list) else None,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreatePresentationTool._arun:after_parse_list",
                        "message": "After parsing list, before JSON parse",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
            
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreatePresentationTool._arun:after_json_parse",
                        "message": "After JSON parse, before extracting fields",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                            "presentationId_raw": result.get("presentationId") if isinstance(result, dict) else None,
                            "presentationId_type": type(result.get("presentationId")).__name__ if isinstance(result, dict) else None,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Check for errors
            if isinstance(result, dict) and "error" in result:
                error_msg = result.get("error", "Unknown error")
                raise ToolExecutionError(
                    f"Failed to create presentation: {error_msg}",
                    tool_name=self.name
                )
            
            presentation_id = result.get("presentationId")
            url = result.get("url", "")
            
            if not presentation_id:
                raise ToolExecutionError(
                    f"Failed to create presentation: presentationId is missing from API response",
                    tool_name=self.name
                )
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreatePresentationTool._arun:before_return",
                        "message": "Before returning result string",
                        "data": {
                            "presentation_id": presentation_id,
                            "presentation_id_type": type(presentation_id).__name__ if presentation_id is not None else None,
                            "url": url
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
            
            return f"Presentation '{title}' created successfully (ID: {presentation_id})" + (f" URL: {url}" if url else "")
            
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
    Get information about a Google Slides presentation.
    
    Input:
    - presentation_id: Presentation ID or URL
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


class CreateSlideInput(BaseModel):
    """Input schema for create_slide tool."""
    
    presentation_id: str = Field(description="Presentation ID or URL")
    layout: Optional[str] = Field(default="TITLE_AND_BODY", description="Layout type (TITLE, TITLE_AND_BODY, BLANK, etc.)")
    insertion_index: Optional[int] = Field(default=None, description="Index where to insert the slide")


class CreateSlideTool(BaseTool):
    """Tool for creating a new slide in a presentation."""
    
    name: str = "create_slide"
    description: str = """
    Add a NEW SLIDE to an EXISTING Google Slides presentation.
    
    ⚠️ IMPORTANT: This adds a slide to an ALREADY CREATED presentation. Do NOT use create_presentation for this!
    
    Input:
    - presentation_id: Presentation ID or URL (from a previously created presentation)
    - layout: Layout type (TITLE, TITLE_AND_BODY, BLANK, etc.) (default: TITLE_AND_BODY)
    - insertion_index: Index where to insert the slide (optional)
    
    Use this to add slides to a presentation that was already created (either by create_presentation or create_presentation_from_doc).
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
            args = {"presentationId": presentation_id, "layout": layout}
            if insertion_index is not None:
                args["insertionIndex"] = insertion_index
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_create_slide", args, server_name="slides")
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreateSlideTool._arun:after_mcp_call",
                        "message": "After MCP call, before parsing",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_is_list": isinstance(result, list),
                            "result_length": len(result) if isinstance(result, list) else None,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "I"
                    }) + "\n")
            except: pass
            # #endregion
            
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
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreateSlideTool._arun:after_parse",
                        "message": "After parsing, before extracting slide_id",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "I"
                    }) + "\n")
            except: pass
            # #endregion
            
            slide_id = result.get("slideId")
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:CreateSlideTool._arun:before_return",
                        "message": "Before returning result string",
                        "data": {
                            "slide_id": slide_id,
                            "slide_id_type": type(slide_id).__name__ if slide_id is not None else None,
                            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                            "result_preview": str(result)[:500] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H"
                    }) + "\n")
            except: pass
            # #endregion
            
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
    element_id: Optional[str] = Field(default=None, description="Text box element ID (optional, will use first text box if not provided)")
    insert_index: Optional[int] = Field(default=-1, description="Character index where to insert (default: append to end)")


class InsertSlideTextTool(BaseTool):
    """Tool for inserting text into a slide."""
    
    name: str = "insert_slide_text"
    description: str = """
    Insert text into a slide's text box.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - text: Text to insert
    - element_id: Text box element ID (optional, will use first text box if not provided)
    - insert_index: Character index where to insert (default: append to end, use -1)
    """
    args_schema: type = InsertSlideTextInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        text: str,
        element_id: Optional[str] = None,
        insert_index: Optional[int] = -1
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:InsertSlideTextTool._arun:entry",
                        "message": "InsertSlideTextTool called",
                        "data": {
                            "presentation_id": presentation_id,
                            "page_id": page_id,
                            "text_preview": text[:50] if text else None,
                            "element_id": element_id,
                            "insert_index": insert_index
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H5"
                    }) + "\n")
            except: pass
            # #endregion
            
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "text": text
            }
            if element_id:
                args["elementId"] = element_id
            if insert_index is not None and insert_index != -1:
                args["insertIndex"] = insert_index
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:InsertSlideTextTool._arun:before_mcp_call",
                        "message": "Before MCP call",
                        "data": {"args": args},
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H5"
                    }) + "\n")
            except: pass
            # #endregion
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_insert_text", args, server_name="slides")
            
            # #region agent log
            try:
                import json
                import time
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "slides_tools.py:InsertSlideTextTool._arun:after_mcp_call",
                        "message": "After MCP call",
                        "data": {
                            "result_type": type(result).__name__,
                            "result_preview": str(result)[:200] if result else None
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H5"
                    }) + "\n")
            except: pass
            # #endregion
            
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
    page_id: str = Field(description="Page (slide) ID")
    element_id: str = Field(description="Text box element ID")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
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
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Text box element ID
    - start_index: Start character index (0-based)
    - end_index: End character index (exclusive)
    - bold: Optional boolean to make text bold
    - italic: Optional boolean to make text italic
    - foreground_color: Optional dict with 'red', 'green', 'blue', 'alpha' (0.0-1.0) for text color
    - font_size: Optional font size in points (e.g., 12, 14, 18, 24)
    - font_family: Optional font family name (e.g., 'Arial', 'Roboto', 'Times New Roman')
    - underline: Optional boolean to make text underlined
    - strikethrough: Optional boolean to make text strikethrough
    - background_color: Optional dict with 'red', 'green', 'blue', 'alpha' (0.0-1.0) for text background
    
    Example colors:
    - Red text: {'red': 1.0, 'green': 0.0, 'blue': 0.0, 'alpha': 1.0}
    - Blue text: {'red': 0.0, 'green': 0.0, 'blue': 1.0, 'alpha': 1.0}
    """
    args_schema: type = FormatSlideTextInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        presentation_id: str,
        page_id: str,
        element_id: str,
        start_index: int,
        end_index: int,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        foreground_color: Optional[Dict[str, float]] = None,
        font_size: Optional[float] = None,
        font_family: Optional[str] = None,
        underline: Optional[bool] = None,
        strikethrough: Optional[bool] = None,
        background_color: Optional[Dict[str, float]] = None
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
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_format_text", args, server_name="slides")
            
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
    Create a professional presentation from a Google Docs document.
    
    The document structure is automatically analyzed:
    - H1 headings create section divider slides
    - H2 headings create content slides with titles
    - Regular text becomes bullet points
    - Images from the document are included
    
    Input:
    - document_id: Document ID or URL
    - presentation_title: Title for the new presentation (optional, defaults to document title)
    - theme: Presentation theme - choose based on content:
      * professional: Business presentations, reports, formal documents (blue accents, white background)
      * creative: Marketing, startups, creative projects (bright colors, unique fonts)
      * minimal: Academic, technical presentations (clean, lots of whitespace)
      * dark: IT, technology presentations (dark background, light text)
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
            
            presentation_id = result.get("presentationId")
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            slides_created = result.get("slidesCreated", 0)
            theme_used = result.get("theme", "professional")
            template_used = result.get("templateUsed", False)
            
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
    Add an image to a slide from a public URL.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - image_url: Public URL of the image
    - x: X position in EMU (use inches_to_emu helper: 1 inch = 914400 EMU)
    - y: Y position in EMU
    - width: Width in EMU
    - height: Height in EMU
    
    Example: For 1 inch margin and 5x3 inch image:
    x = inches_to_emu(1.0), y = inches_to_emu(1.0)
    width = inches_to_emu(5.0), height = inches_to_emu(3.0)
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
    Create a shape on a slide (rectangle, circle, arrow, etc.).
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - shape_type: Shape type (RECTANGLE, ELLIPSE, ARROW_EAST, TEXT_BOX, etc.)
    - x, y: Position in EMU
    - width, height: Size in EMU
    - fill_color: Optional fill color
    - border_color: Optional border color
    - border_weight: Optional border weight in points
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
    Set slide background (solid color or image).
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - solid_color: Optional solid background color {red, green, blue, alpha} (0-1)
    - image_url: Optional background image URL (if not using solidColor)
    
    Provide either solid_color OR image_url, not both.
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
    Create a table on a slide.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - rows: Number of rows
    - columns: Number of columns
    - x, y: Position in EMU
    - width, height: Size in EMU
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
    Update text in a table cell.
    
    Input:
    - presentation_id: Presentation ID or URL
    - table_id: Table element ID
    - row_index: Row index (0-based)
    - column_index: Column index (0-based)
    - text: Text to insert into cell
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
    Create a chart on a slide from Google Sheets.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - spreadsheet_id: Google Sheets spreadsheet ID containing the chart
    - chart_id: Chart ID in the spreadsheet (must be created in Sheets first)
    - x, y: Position in EMU
    - width, height: Size in EMU
    - linking_mode: LINKED (updates with Sheets) or NOT_LINKED_IMAGE (static image)
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
    Format paragraph style (alignment, line spacing, margins).
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Text box element ID
    - start_index: Start character index (0-based)
    - end_index: End character index (exclusive)
    - alignment: Optional text alignment (START, CENTER, END, JUSTIFIED)
    - line_spacing: Optional line spacing multiplier (e.g., 1.5)
    - space_above: Optional space above paragraph in points
    - space_below: Optional space below paragraph in points
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
    Create bulleted or numbered list from text.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Text box element ID
    - start_index: Start character index (0-based)
    - end_index: End character index (exclusive)
    - bullet_preset: Bullet preset (BULLET_DISC_CIRCLE_SQUARE, NUMBERED_DIGIT_ALPHA_ROMAN, etc.)
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
    Update element position, size, and rotation.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Element ID
    - translate_x: Optional X translation in EMU
    - translate_y: Optional Y translation in EMU
    - scale_x: Optional X scale factor (1.0 = 100%, 2.0 = 200%)
    - scale_y: Optional Y scale factor (1.0 = 100%, 2.0 = 200%)
    - rotation: Optional rotation angle in degrees
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
    Delete an element from a slide.
    
    Input:
    - presentation_id: Presentation ID or URL
    - element_id: Element ID to delete
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
    Get available slide masters and layouts.
    
    Input:
    - presentation_id: Presentation ID or URL
    
    Returns list of available layouts with their IDs and names.
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
    Apply a layout to a slide.
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - layout_id: Layout ID to apply (use get_slide_masters to see available layouts)
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

