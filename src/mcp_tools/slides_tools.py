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
            args = {
                "presentationId": presentation_id,
                "pageId": page_id,
                "text": text
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
    page_id: str = Field(description="Page (slide) ID")
    element_id: str = Field(description="Text box element ID")
    start_index: int = Field(description="Start character index (0-based)")
    end_index: int = Field(description="End character index (exclusive)")
    bold: Optional[bool] = Field(default=None, description="Make text bold")
    italic: Optional[bool] = Field(default=None, description="Make text italic")
    foreground_color: Optional[Dict[str, float]] = Field(default=None, description="Text color as {red, green, blue, alpha} (0-1)")


class FormatSlideTextTool(BaseTool):
    """Tool for formatting text in a slide."""
    
    name: str = "format_slide_text"
    description: str = """
    Format text in a slide (bold, italic, colors).
    
    Input:
    - presentation_id: Presentation ID or URL
    - page_id: Page (slide) ID
    - element_id: Text box element ID
    - start_index: Start character index (0-based)
    - end_index: End character index (exclusive)
    - bold: Optional boolean to make text bold
    - italic: Optional boolean to make text italic
    - foreground_color: Optional dict with 'red', 'green', 'blue', 'alpha' (0.0-1.0)
    
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
        foreground_color: Optional[Dict[str, float]] = None
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
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("slides_format_text", args, server_name="slides")
            
            formats = []
            if bold:
                formats.append("bold")
            if italic:
                formats.append("italic")
            if foreground_color:
                formats.append("text color")
            
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
    slides_per_paragraph: bool = Field(default=True, description="Create one slide per paragraph (default: true)")


class CreatePresentationFromDocTool(BaseTool):
    """Tool for creating a presentation from a Google Docs document."""
    
    name: str = "create_presentation_from_doc"
    description: str = """
    Create a presentation from a Google Docs document, splitting content into slides.
    
    Input:
    - document_id: Document ID or URL
    - presentation_title: Title for the new presentation (optional, defaults to document title)
    - slides_per_paragraph: Create one slide per paragraph (default: true)
    
    This tool reads the document content and creates a presentation with slides based on the document structure.
    """
    args_schema: type = CreatePresentationFromDocInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        document_id: str,
        presentation_title: Optional[str] = None,
        slides_per_paragraph: bool = True
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "slidesPerParagraph": slides_per_paragraph
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
            
            return f"Presentation '{title}' created successfully from document (ID: {presentation_id}, {slides_created} slides)" + (f" URL: {url}" if url else "")
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create presentation from document: {e}",
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
    ]

