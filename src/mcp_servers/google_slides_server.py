"""
Google Slides MCP Server.
Provides MCP tools for Google Slides operations via OAuth2.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import re

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Slides API scopes
SLIDES_SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",  # For reading documents
]


class GoogleSlidesMCPServer:
    """MCP Server for Google Slides operations."""
    
    def __init__(self, token_path: Path, config_path: Optional[Path] = None):
        """
        Initialize Google Slides MCP Server.
        
        Args:
            token_path: Path to OAuth token file
            config_path: Path to workspace config file (optional, defaults to config/workspace_config.json)
        """
        self.token_path = Path(token_path)
        self.config_path = config_path or Path("config/workspace_config.json")
        self._slides_service = None
        self._drive_service = None
        self._docs_service = None
        self._workspace_folder_id = None
        self.server = Server("google-slides-mcp")
        self._setup_tools()
    
    def _get_slides_service(self):
        """Get or create Google Slides API service."""
        if self._slides_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SLIDES_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self._slides_service = build('slides', 'v1', credentials=creds)
        
        return self._slides_service
    
    def _get_drive_service(self):
        """Get or create Google Drive API service for presentation operations."""
        if self._drive_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SLIDES_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self._drive_service = build('drive', 'v3', credentials=creds)
        
        return self._drive_service
    
    def _get_docs_service(self):
        """Get or create Google Docs API service for reading documents."""
        if self._docs_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SLIDES_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self._docs_service = build('docs', 'v1', credentials=creds)
        
        return self._docs_service
    
    def _load_config(self) -> Dict[str, Any]:
        """Load workspace configuration."""
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load workspace config: {e}")
            return {}
    
    def _get_workspace_folder_id(self) -> Optional[str]:
        """Get the workspace folder ID from config."""
        if self._workspace_folder_id is None:
            config = self._load_config()
            self._workspace_folder_id = config.get("folder_id")
        return self._workspace_folder_id
    
    @staticmethod
    def _extract_file_id(file_id_or_url: str) -> str:
        """Extract file ID from URL or return as-is if already an ID."""
        patterns = [
            r'/presentation/d/([a-zA-Z0-9-_]+)',
            r'/document/d/([a-zA-Z0-9-_]+)',
            r'docs\.google\.com/presentation.*[?&]id=([a-zA-Z0-9-_]+)',
            r'docs\.google\.com/document.*[?&]id=([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_id_or_url)
            if match:
                return match.group(1)
        
        return file_id_or_url
    
    def _extract_text_from_docs_content(self, content: List[Dict]) -> str:
        """Extract text content from Google Docs document structure."""
        text_parts = []
        
        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                elements = paragraph.get('elements', [])
                for elem in elements:
                    if 'textRun' in elem:
                        text_run = elem['textRun']
                        text_parts.append(text_run.get('content', ''))
            elif 'table' in element:
                table = element['table']
                for row in table.get('tableRows', []):
                    row_text = []
                    for cell in row.get('tableCells', []):
                        cell_content = cell.get('content', [])
                        cell_text = self._extract_text_from_docs_content(cell_content)
                        row_text.append(cell_text)
                    if row_text:
                        text_parts.append(' | '.join(row_text))
                        text_parts.append('\n')
        
        return ''.join(text_parts)
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="slides_create",
                    description="Create a new Google Slides presentation in the workspace folder.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the presentation"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                Tool(
                    name="slides_get",
                    description="Get information about a Google Slides presentation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            }
                        },
                        "required": ["presentationId"]
                    }
                ),
                Tool(
                    name="slides_create_slide",
                    description="Create a new slide in a presentation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "layout": {
                                "type": "string",
                                "description": "Layout type (TITLE, TITLE_AND_BODY, BLANK, etc.)",
                                "default": "TITLE_AND_BODY"
                            },
                            "insertionIndex": {
                                "type": "integer",
                                "description": "Index where to insert the slide (optional)"
                            }
                        },
                        "required": ["presentationId"]
                    }
                ),
                Tool(
                    name="slides_insert_text",
                    description="Insert text into a slide's text box.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Text box element ID (optional, will use first text box if not provided)"
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to insert"
                            },
                            "insertIndex": {
                                "type": "integer",
                                "description": "Character index where to insert (default: append to end)",
                                "default": -1
                            }
                        },
                        "required": ["presentationId", "pageId", "text"]
                    }
                ),
                Tool(
                    name="slides_format_text",
                    description="Format text in a slide (bold, italic, colors, font size, font family, underline, strikethrough).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Text box element ID"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start character index (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End character index (exclusive)"
                            },
                            "bold": {
                                "type": "boolean",
                                "description": "Make text bold"
                            },
                            "italic": {
                                "type": "boolean",
                                "description": "Make text italic"
                            },
                            "foregroundColor": {
                                "type": "object",
                                "description": "Text color as {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            },
                            "fontSize": {
                                "type": "number",
                                "description": "Font size in points"
                            },
                            "fontFamily": {
                                "type": "string",
                                "description": "Font family name (e.g., 'Arial', 'Roboto')"
                            },
                            "underline": {
                                "type": "boolean",
                                "description": "Make text underlined"
                            },
                            "strikethrough": {
                                "type": "boolean",
                                "description": "Make text strikethrough"
                            },
                            "backgroundColor": {
                                "type": "object",
                                "description": "Text background color as {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            }
                        },
                        "required": ["presentationId", "pageId", "elementId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="slides_create_presentation_from_doc",
                    description="Create a presentation from a Google Docs document, splitting content into slides.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "presentationTitle": {
                                "type": "string",
                                "description": "Title for the new presentation (optional, defaults to document title)"
                            },
                            "slidesPerParagraph": {
                                "type": "boolean",
                                "description": "Create one slide per paragraph (default: true)",
                                "default": True
                            }
                        },
                        "required": ["documentId"]
                    }
                ),
                Tool(
                    name="slides_add_image",
                    description="Add an image to a slide from a public URL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "imageUrl": {
                                "type": "string",
                                "description": "Public URL of the image"
                            },
                            "x": {
                                "type": "number",
                                "description": "X position in EMU (or use inches_to_emu helper)"
                            },
                            "y": {
                                "type": "number",
                                "description": "Y position in EMU (or use inches_to_emu helper)"
                            },
                            "width": {
                                "type": "number",
                                "description": "Width in EMU (or use inches_to_emu helper)"
                            },
                            "height": {
                                "type": "number",
                                "description": "Height in EMU (or use inches_to_emu helper)"
                            }
                        },
                        "required": ["presentationId", "pageId", "imageUrl", "x", "y", "width", "height"]
                    }
                ),
                Tool(
                    name="slides_create_shape",
                    description="Create a shape on a slide (rectangle, circle, arrow, etc.).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "shapeType": {
                                "type": "string",
                                "description": "Shape type (RECTANGLE, ELLIPSE, ARROW_EAST, TEXT_BOX, etc.)"
                            },
                            "x": {
                                "type": "number",
                                "description": "X position in EMU"
                            },
                            "y": {
                                "type": "number",
                                "description": "Y position in EMU"
                            },
                            "width": {
                                "type": "number",
                                "description": "Width in EMU"
                            },
                            "height": {
                                "type": "number",
                                "description": "Height in EMU"
                            },
                            "fillColor": {
                                "type": "object",
                                "description": "Fill color {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            },
                            "borderColor": {
                                "type": "object",
                                "description": "Border color {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            },
                            "borderWeight": {
                                "type": "number",
                                "description": "Border weight in points"
                            }
                        },
                        "required": ["presentationId", "pageId", "shapeType", "x", "y", "width", "height"]
                    }
                ),
                Tool(
                    name="slides_set_background",
                    description="Set slide background (solid color or image).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "solidColor": {
                                "type": "object",
                                "description": "Solid background color {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            },
                            "imageUrl": {
                                "type": "string",
                                "description": "Background image URL (if not using solidColor)"
                            }
                        },
                        "required": ["presentationId", "pageId"]
                    }
                ),
                Tool(
                    name="slides_create_table",
                    description="Create a table on a slide.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "rows": {
                                "type": "integer",
                                "description": "Number of rows"
                            },
                            "columns": {
                                "type": "integer",
                                "description": "Number of columns"
                            },
                            "x": {
                                "type": "number",
                                "description": "X position in EMU"
                            },
                            "y": {
                                "type": "number",
                                "description": "Y position in EMU"
                            },
                            "width": {
                                "type": "number",
                                "description": "Width in EMU"
                            },
                            "height": {
                                "type": "number",
                                "description": "Height in EMU"
                            }
                        },
                        "required": ["presentationId", "pageId", "rows", "columns", "x", "y", "width", "height"]
                    }
                ),
                Tool(
                    name="slides_update_table_cell",
                    description="Update text in a table cell.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "tableId": {
                                "type": "string",
                                "description": "Table element ID"
                            },
                            "rowIndex": {
                                "type": "integer",
                                "description": "Row index (0-based)"
                            },
                            "columnIndex": {
                                "type": "integer",
                                "description": "Column index (0-based)"
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to insert into cell"
                            }
                        },
                        "required": ["presentationId", "tableId", "rowIndex", "columnIndex", "text"]
                    }
                ),
                Tool(
                    name="slides_create_chart",
                    description="Create a chart on a slide from Google Sheets.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "spreadsheetId": {
                                "type": "string",
                                "description": "Google Sheets spreadsheet ID containing the chart"
                            },
                            "chartId": {
                                "type": "integer",
                                "description": "Chart ID in the spreadsheet"
                            },
                            "x": {
                                "type": "number",
                                "description": "X position in EMU"
                            },
                            "y": {
                                "type": "number",
                                "description": "Y position in EMU"
                            },
                            "width": {
                                "type": "number",
                                "description": "Width in EMU"
                            },
                            "height": {
                                "type": "number",
                                "description": "Height in EMU"
                            },
                            "linkingMode": {
                                "type": "string",
                                "description": "Linking mode: LINKED or NOT_LINKED_IMAGE",
                                "default": "LINKED"
                            }
                        },
                        "required": ["presentationId", "pageId", "spreadsheetId", "chartId", "x", "y", "width", "height"]
                    }
                ),
                Tool(
                    name="slides_format_paragraph",
                    description="Format paragraph style (alignment, line spacing, margins).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Text box element ID"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start character index (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End character index (exclusive)"
                            },
                            "alignment": {
                                "type": "string",
                                "description": "Text alignment: START, CENTER, END, JUSTIFIED"
                            },
                            "lineSpacing": {
                                "type": "number",
                                "description": "Line spacing multiplier (e.g., 1.5 for 1.5x)"
                            },
                            "spaceAbove": {
                                "type": "number",
                                "description": "Space above paragraph in points"
                            },
                            "spaceBelow": {
                                "type": "number",
                                "description": "Space below paragraph in points"
                            }
                        },
                        "required": ["presentationId", "pageId", "elementId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="slides_create_bullets",
                    description="Create bulleted or numbered list from text.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Text box element ID"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start character index (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End character index (exclusive)"
                            },
                            "bulletPreset": {
                                "type": "string",
                                "description": "Bullet preset (BULLET_DISC_CIRCLE_SQUARE, NUMBERED_DIGIT_ALPHA_ROMAN, etc.)",
                                "default": "BULLET_DISC_CIRCLE_SQUARE"
                            }
                        },
                        "required": ["presentationId", "pageId", "elementId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="slides_update_element_transform",
                    description="Update element position, size, and rotation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Element ID"
                            },
                            "translateX": {
                                "type": "number",
                                "description": "X translation in EMU"
                            },
                            "translateY": {
                                "type": "number",
                                "description": "Y translation in EMU"
                            },
                            "scaleX": {
                                "type": "number",
                                "description": "X scale factor (1.0 = 100%)"
                            },
                            "scaleY": {
                                "type": "number",
                                "description": "Y scale factor (1.0 = 100%)"
                            },
                            "rotation": {
                                "type": "number",
                                "description": "Rotation angle in degrees"
                            }
                        },
                        "required": ["presentationId", "pageId", "elementId"]
                    }
                ),
                Tool(
                    name="slides_delete_element",
                    description="Delete an element from a slide.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "elementId": {
                                "type": "string",
                                "description": "Element ID to delete"
                            }
                        },
                        "required": ["presentationId", "elementId"]
                    }
                ),
                Tool(
                    name="slides_get_masters",
                    description="Get available slide masters and layouts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            }
                        },
                        "required": ["presentationId"]
                    }
                ),
                Tool(
                    name="slides_apply_layout",
                    description="Apply a layout to a slide.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "presentationId": {
                                "type": "string",
                                "description": "Presentation ID or URL"
                            },
                            "pageId": {
                                "type": "string",
                                "description": "Page (slide) ID"
                            },
                            "layoutId": {
                                "type": "string",
                                "description": "Layout ID to apply"
                            }
                        },
                        "required": ["presentationId", "pageId", "layoutId"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "slides_create":
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_create:entry",
                                "message": "slides_create handler called",
                                "data": {"arguments": arguments},
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H7"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    try:
                        drive_service = self._get_drive_service()
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:drive_service_obtained",
                                    "message": "Drive service obtained",
                                    "data": {},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        slides_service = self._get_slides_service()
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:slides_service_obtained",
                                    "message": "Slides service obtained",
                                    "data": {},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        folder_id = self._get_workspace_folder_id()
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:folder_id_obtained",
                                    "message": "Folder ID obtained",
                                    "data": {"folder_id": folder_id},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        if not folder_id:
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_create:no_folder_id",
                                        "message": "No folder ID configured",
                                        "data": {},
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H7"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            return [TextContent(
                                type="text",
                                text=json.dumps({
                                    "error": "Workspace folder not configured. Please set workspace folder first."
                                }, indent=2)
                            )]
                        
                        title = arguments.get("title")
                        
                        # Create presentation
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:before_create",
                                    "message": "Before creating presentation",
                                    "data": {"title": title},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        presentation = slides_service.presentations().create(
                            body={"title": title}
                        ).execute()
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:presentation_created",
                                    "message": "Presentation created",
                                    "data": {"presentation_id": presentation.get('presentationId')},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        presentation_id = presentation.get('presentationId')
                        
                        # Move to workspace folder
                        if folder_id:
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_create:before_move",
                                        "message": "Before moving to folder",
                                        "data": {"presentation_id": presentation_id, "folder_id": folder_id},
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H7"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            
                            file_info = drive_service.files().get(
                                fileId=presentation_id,
                                fields="parents"
                            ).execute()
                            previous_parents = ",".join(file_info.get('parents', []))
                            drive_service.files().update(
                                fileId=presentation_id,
                                addParents=folder_id,
                                removeParents=previous_parents,
                                fields="id, parents"
                            ).execute()
                            
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_create:after_move",
                                        "message": "After moving to folder",
                                        "data": {},
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H7"
                                    }) + "\n")
                            except: pass
                            # #endregion
                        
                        # Get presentation URL
                        pres_file = drive_service.files().get(
                            fileId=presentation_id,
                            fields="webViewLink"
                        ).execute()
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:success",
                                    "message": "slides_create completed successfully",
                                    "data": {"presentation_id": presentation_id, "url": pres_file.get('webViewLink')},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "presentationId": presentation_id,
                                "title": title,
                                "url": pres_file.get('webViewLink')
                            }, indent=2)
                        )]
                    except Exception as create_error:
                        # #region agent log
                        try:
                            import traceback
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_create:error",
                                    "message": "Error in slides_create",
                                    "data": {
                                        "error_type": type(create_error).__name__,
                                        "error_message": str(create_error),
                                        "error_traceback": traceback.format_exc()[:1000]
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H7"
                                }) + "\n")
                        except: pass
                        # #endregion
                        raise  # Re-raise to be handled by outer exception handler
                
                elif name == "slides_get":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    
                    presentation = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    
                    slides_info = []
                    for slide in presentation.get('slides', []):
                        slide_id = slide.get('objectId')
                        page_elements = slide.get('pageElements', [])
                        slides_info.append({
                            "slideId": slide_id,
                            "pageElementsCount": len(page_elements)
                        })
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "title": presentation.get('title'),
                            "slides": slides_info,
                            "slidesCount": len(slides_info)
                        }, indent=2)
                    )]
                
                elif name == "slides_create_slide":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    layout = arguments.get("layout", "TITLE_AND_BODY")
                    insertion_index = arguments.get("insertionIndex")
                    
                    # Get layout ID
                    presentation = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    
                    layouts = presentation.get('layouts', [])
                    layout_id = None
                    for layout_obj in layouts:
                        if layout_obj.get('layoutProperties', {}).get('name') == layout:
                            layout_id = layout_obj.get('objectId')
                            break
                    
                    if not layout_id and layouts:
                        # Use first available layout
                        layout_id = layouts[0].get('objectId')
                    
                    # Generate a short objectId (Google Slides API requires max 50 characters)
                    # Use hash of presentation_id + timestamp to create unique short ID
                    import hashlib
                    import time as time_module
                    unique_str = f"{presentation_id}_{time_module.time()}_{insertion_index or 0}"
                    object_id_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    object_id = f"slide_{object_id_hash}"
                    
                    create_slide_request = {
                        "objectId": object_id,
                        "slideLayoutReference": {
                            "layoutId": layout_id
                        } if layout_id else None
                    }
                    
                    # Only include insertionIndex if it's not None
                    if insertion_index is not None:
                        create_slide_request["insertionIndex"] = insertion_index
                    
                    requests = [{
                        "createSlide": create_slide_request
                    }]
                    
                    # Remove None values for slideLayoutReference
                    if not requests[0]["createSlide"]["slideLayoutReference"]:
                        del requests[0]["createSlide"]["slideLayoutReference"]
                    
                    response = slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    slide_id = response.get('replies', [{}])[0].get('createSlide', {}).get('objectId')
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "slideId": slide_id,
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "slides_insert_text":
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_insert_text:entry",
                                "message": "slides_insert_text handler called",
                                "data": {
                                    "arguments": arguments,
                                    "presentation_id": arguments.get("presentationId"),
                                    "page_id": arguments.get("pageId"),
                                    "text_preview": str(arguments.get("text", ""))[:50]
                                },
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H5"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    text = arguments.get("text")
                    insert_index = arguments.get("insertIndex", -1)
                    
                    # If element_id not provided, find first text box
                    if not element_id:
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_insert_text:before_find_textbox",
                                    "message": "Before finding text box",
                                    "data": {"page_id": page_id, "presentation_id": presentation_id},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H6"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        presentation = slides_service.presentations().get(
                            presentationId=presentation_id
                        ).execute()
                        
                        # #region agent log
                        try:
                            slides_found = [s.get('objectId') for s in presentation.get('slides', [])]
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_insert_text:after_get_presentation",
                                    "message": "After get presentation",
                                    "data": {
                                        "slides_count": len(presentation.get('slides', [])),
                                        "slide_ids": slides_found,
                                        "looking_for_page_id": page_id
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H6"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        for slide in presentation.get('slides', []):
                            if slide.get('objectId') == page_id:
                                # #region agent log
                                try:
                                    elements_count = len(slide.get('pageElements', []))
                                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                        f.write(json.dumps({
                                            "location": "google_slides_server.py:slides_insert_text:slide_found",
                                            "message": "Slide found, searching for text box",
                                            "data": {"elements_count": elements_count},
                                            "timestamp": int(__import__('time').time() * 1000),
                                            "sessionId": "debug-session",
                                            "runId": "run1",
                                            "hypothesisId": "H6"
                                        }) + "\n")
                                except: pass
                                # #endregion
                                
                                for element in slide.get('pageElements', []):
                                    if 'shape' in element and element['shape'].get('shapeType') == 'TEXT_BOX':
                                        element_id = element.get('objectId')
                                        # #region agent log
                                        try:
                                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                                f.write(json.dumps({
                                                    "location": "google_slides_server.py:slides_insert_text:textbox_found",
                                                    "message": "Text box found",
                                                    "data": {"element_id": element_id},
                                                    "timestamp": int(__import__('time').time() * 1000),
                                                    "sessionId": "debug-session",
                                                    "runId": "run1",
                                                    "hypothesisId": "H6"
                                                }) + "\n")
                                        except: pass
                                        # #endregion
                                        break
                                break
                        
                        if not element_id:
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_insert_text:no_textbox",
                                        "message": "No text box found",
                                        "data": {"page_id": page_id},
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H6"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            return [TextContent(
                                type="text",
                                text=json.dumps({"error": "No text box found in slide"}, indent=2)
                            )]
                    
                    # Get current text to determine insert index
                    if insert_index == -1:
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_insert_text:before_compute_index",
                                    "message": "Before computing insert index",
                                    "data": {"element_id": element_id, "page_id": page_id},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H5"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        try:
                            presentation = slides_service.presentations().get(
                                presentationId=presentation_id,
                                fields="slides(pageElements(objectId,shape(text(textElements))))"
                            ).execute()
                            
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_insert_text:got_presentation_for_index",
                                        "message": "Got presentation for index computation",
                                        "data": {"slides_count": len(presentation.get('slides', []))},
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H5"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            
                            for slide in presentation.get('slides', []):
                                if slide.get('objectId') == page_id:
                                    for element in slide.get('pageElements', []):
                                        if element.get('objectId') == element_id:
                                            shape = element.get('shape', {})
                                            text_obj = shape.get('text', {})
                                            text_elements = text_obj.get('textElements', [])
                                            # Calculate total length
                                            insert_index = sum(
                                                len(elem.get('textRun', {}).get('content', ''))
                                                for elem in text_elements
                                            )
                                            # #region agent log
                                            try:
                                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                                    f.write(json.dumps({
                                                        "location": "google_slides_server.py:slides_insert_text:index_computed",
                                                        "message": "Insert index computed",
                                                        "data": {
                                                            "insert_index": insert_index,
                                                            "text_elements_count": len(text_elements),
                                                            "text_lengths": [len(elem.get('textRun', {}).get('content', '')) for elem in text_elements]
                                                        },
                                                        "timestamp": int(__import__('time').time() * 1000),
                                                        "sessionId": "debug-session",
                                                        "runId": "run1",
                                                        "hypothesisId": "H5"
                                                    }) + "\n")
                                            except: pass
                                            # #endregion
                                            break
                                    break
                        except Exception as index_error:
                            # #region agent log
                            try:
                                import traceback
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({
                                        "location": "google_slides_server.py:slides_insert_text:index_error",
                                        "message": "Error computing insert index",
                                        "data": {
                                            "error_type": type(index_error).__name__,
                                            "error_message": str(index_error),
                                            "error_traceback": traceback.format_exc()[:500]
                                        },
                                        "timestamp": int(__import__('time').time() * 1000),
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H5"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            # If error computing index, default to 0
                            insert_index = 0
                    
                    # Ensure insert_index is valid (>= 0)
                    if insert_index < 0:
                        insert_index = 0
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_insert_text:after_index_check",
                                "message": "After index validation",
                                "data": {"final_insert_index": insert_index},
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H5"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    requests = [{
                        "insertText": {
                            "objectId": element_id,
                            "insertionIndex": insert_index,
                            "text": text
                        }
                    }]
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_insert_text:before_api_call",
                                "message": "Before batchUpdate API call",
                                "data": {
                                    "presentation_id": presentation_id,
                                    "page_id": page_id,
                                    "element_id": element_id,
                                    "insert_index": insert_index,
                                    "requests": requests
                                },
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H5"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    try:
                        response = slides_service.presentations().batchUpdate(
                            presentationId=presentation_id,
                            body={"requests": requests}
                        ).execute()
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_insert_text:after_api_call",
                                    "message": "After batchUpdate API call",
                                    "data": {
                                        "response_keys": list(response.keys()) if isinstance(response, dict) else None,
                                        "response_preview": str(response)[:200] if response else None
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H5"
                                }) + "\n")
                        except: pass
                        # #endregion
                    except Exception as api_error:
                        # #region agent log
                        try:
                            import traceback
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_insert_text:api_error",
                                    "message": "API call failed",
                                    "data": {
                                        "error_type": type(api_error).__name__,
                                        "error_message": str(api_error),
                                        "error_traceback": traceback.format_exc()[:500]
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H5"
                                }) + "\n")
                        except: pass
                        # #endregion
                        raise
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "elementId": element_id,
                            "status": "inserted"
                        }, indent=2)
                    )]
                
                elif name == "slides_format_text":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    
                    requests = []
                    
                    # Build text style
                    text_style = {}
                    style_fields = []
                    
                    if "bold" in arguments:
                        text_style["bold"] = arguments["bold"]
                        style_fields.append("bold")
                    if "italic" in arguments:
                        text_style["italic"] = arguments["italic"]
                        style_fields.append("italic")
                    if "foregroundColor" in arguments:
                        fg_color = arguments["foregroundColor"].copy() if isinstance(arguments["foregroundColor"], dict) else arguments["foregroundColor"]
                        # Remove alpha from rgbColor (alpha not supported in rgbColor)
                        rgb_color = {k: v for k, v in fg_color.items() if k != "alpha"}
                        text_style["foregroundColor"] = {
                            "opaqueColor": {
                                "rgbColor": rgb_color
                            }
                        }
                        style_fields.append("foregroundColor")
                    if "fontSize" in arguments:
                        # Font size is in points, need to convert to dimension
                        text_style["fontSize"] = {
                            "magnitude": arguments["fontSize"],
                            "unit": "PT"
                        }
                        style_fields.append("fontSize")
                    if "fontFamily" in arguments:
                        text_style["fontFamily"] = arguments["fontFamily"]
                        style_fields.append("fontFamily")
                    if "underline" in arguments:
                        text_style["underline"] = arguments["underline"]
                        style_fields.append("underline")
                    if "strikethrough" in arguments:
                        text_style["strikethrough"] = arguments["strikethrough"]
                        style_fields.append("strikethrough")
                    if "backgroundColor" in arguments:
                        bg_color = arguments["backgroundColor"].copy() if isinstance(arguments["backgroundColor"], dict) else arguments["backgroundColor"]
                        # Remove alpha from rgbColor
                        rgb_color = {k: v for k, v in bg_color.items() if k != "alpha"}
                        text_style["backgroundColor"] = {
                            "opaqueColor": {
                                "rgbColor": rgb_color
                            }
                        }
                        style_fields.append("backgroundColor")
                    
                    if text_style:
                        requests.append({
                            "updateTextStyle": {
                                "objectId": element_id,
                                "style": text_style,
                                "textRange": {
                                    "type": "FIXED_RANGE",
                                    "startIndex": start_index,
                                    "endIndex": end_index
                                },
                                "fields": ",".join(style_fields)
                            }
                        })
                    
                    if not requests:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "No formatting options provided"}, indent=2)
                        )]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "status": "formatted"
                        }, indent=2)
                    )]
                
                elif name == "slides_add_image":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    image_url = arguments.get("imageUrl")
                    x = int(arguments.get("x"))
                    y = int(arguments.get("y"))
                    width = int(arguments.get("width"))
                    height = int(arguments.get("height"))
                    
                    # Generate unique object ID
                    import hashlib
                    import time as time_module
                    unique_str = f"{presentation_id}_{page_id}_{time_module.time()}_image"
                    object_id_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    object_id = f"img_{object_id_hash}"
                    
                    requests = [{
                        "createImage": {
                            "objectId": object_id,
                            "url": image_url,
                            "elementProperties": {
                                "pageObjectId": page_id,
                                "size": {
                                    "height": {"magnitude": height, "unit": "EMU"},
                                    "width": {"magnitude": width, "unit": "EMU"}
                                },
                                "transform": {
                                    "scaleX": 1.0,
                                    "scaleY": 1.0,
                                    "translateX": x,
                                    "translateY": y,
                                    "unit": "EMU"
                                }
                            }
                        }
                    }]
                    
                    response = slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    image_id = response.get('replies', [{}])[0].get('createImage', {}).get('objectId')
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "imageId": image_id,
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "slides_create_shape":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    shape_type = arguments.get("shapeType")
                    x = int(arguments.get("x"))
                    y = int(arguments.get("y"))
                    width = int(arguments.get("width"))
                    height = int(arguments.get("height"))
                    
                    # Generate unique object ID
                    import hashlib
                    import time as time_module
                    unique_str = f"{presentation_id}_{page_id}_{time_module.time()}_shape"
                    object_id_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    object_id = f"shape_{object_id_hash}"
                    
                    # Build shape properties
                    shape_properties = {
                        "pageObjectId": page_id,
                        "size": {
                            "height": {"magnitude": height, "unit": "EMU"},
                            "width": {"magnitude": width, "unit": "EMU"}
                        },
                        "transform": {
                            "scaleX": 1.0,
                            "scaleY": 1.0,
                            "translateX": x,
                            "translateY": y,
                            "unit": "EMU"
                        }
                    }
                    
                    shape_request = {
                        "createShape": {
                            "objectId": object_id,
                            "shapeType": shape_type,
                            "elementProperties": shape_properties
                        }
                    }
                    
                    requests = [shape_request]
                    
                    # Add formatting requests if colors provided
                    if "fillColor" in arguments or "borderColor" in arguments:
                        update_requests = []
                        
                        if "fillColor" in arguments:
                            fill_color = arguments["fillColor"].copy() if isinstance(arguments["fillColor"], dict) else arguments["fillColor"]
                            # Remove alpha from rgbColor (alpha not supported in Google Slides API for shapes)
                            rgb_color = {k: v for k, v in fill_color.items() if k != "alpha"}
                            
                            update_requests.append({
                                "updateShapeProperties": {
                                    "objectId": object_id,
                                    "shapeProperties": {
                                        "shapeBackgroundFill": {
                                            "solidFill": {
                                                "color": {
                                                    "rgbColor": rgb_color
                                                }
                                            }
                                        }
                                    },
                                    "fields": "shapeBackgroundFill"
                                }
                            })
                        
                        if "borderColor" in arguments:
                            border_color = arguments["borderColor"].copy() if isinstance(arguments["borderColor"], dict) else arguments["borderColor"]
                            # Remove alpha from rgbColor
                            rgb_color = {k: v for k, v in border_color.items() if k != "alpha"}
                            border_weight = arguments.get("borderWeight", 1.0)
                            
                            update_requests.append({
                                "updateLineProperties": {
                                    "objectId": object_id,
                                    "lineProperties": {
                                        "lineFill": {
                                            "solidFill": {
                                                "color": {
                                                    "rgbColor": rgb_color
                                                }
                                            }
                                        },
                                        "weight": {
                                            "magnitude": border_weight,
                                            "unit": "PT"
                                        }
                                    },
                                    "fields": "lineFill,weight"
                                }
                            })
                        
                        requests.extend(update_requests)
                    
                    response = slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    shape_id = response.get('replies', [{}])[0].get('createShape', {}).get('objectId')
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "shapeId": shape_id,
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "slides_set_background":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    
                    requests = []
                    
                    if "solidColor" in arguments:
                        solid_color = arguments["solidColor"].copy() if isinstance(arguments["solidColor"], dict) else arguments["solidColor"]
                        # Remove alpha from rgbColor
                        rgb_color = {k: v for k, v in solid_color.items() if k != "alpha"}
                        requests.append({
                            "updatePageProperties": {
                                "objectId": page_id,
                                "pageProperties": {
                                    "pageBackgroundFill": {
                                        "solidFill": {
                                            "color": {
                                                "rgbColor": rgb_color
                                            }
                                        }
                                    }
                                },
                                "fields": "pageBackgroundFill"
                            }
                        })
                    elif "imageUrl" in arguments:
                        image_url = arguments["imageUrl"]
                        requests.append({
                            "updatePageProperties": {
                                "objectId": page_id,
                                "pageProperties": {
                                    "pageBackgroundFill": {
                                        "stretchedPictureFill": {
                                            "contentUrl": image_url
                                        }
                                    }
                                },
                                "fields": "pageBackgroundFill"
                            }
                        })
                    else:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "Either solidColor or imageUrl must be provided"}, indent=2)
                        )]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "status": "background_updated"
                        }, indent=2)
                    )]
                
                elif name == "slides_create_table":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    rows = int(arguments.get("rows"))
                    columns = int(arguments.get("columns"))
                    x = int(arguments.get("x"))
                    y = int(arguments.get("y"))
                    width = int(arguments.get("width"))
                    height = int(arguments.get("height"))
                    
                    # Generate unique object ID
                    import hashlib
                    import time as time_module
                    unique_str = f"{presentation_id}_{page_id}_{time_module.time()}_table"
                    object_id_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    object_id = f"table_{object_id_hash}"
                    
                    requests = [{
                        "createTable": {
                            "objectId": object_id,
                            "elementProperties": {
                                "pageObjectId": page_id,
                                "size": {
                                    "height": {"magnitude": height, "unit": "EMU"},
                                    "width": {"magnitude": width, "unit": "EMU"}
                                },
                                "transform": {
                                    "scaleX": 1.0,
                                    "scaleY": 1.0,
                                    "translateX": x,
                                    "translateY": y,
                                    "unit": "EMU"
                                }
                            },
                            "rows": rows,
                            "columns": columns
                        }
                    }]
                    
                    response = slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    table_id = response.get('replies', [{}])[0].get('createTable', {}).get('objectId')
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "tableId": table_id,
                            "rows": rows,
                            "columns": columns,
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "slides_update_table_cell":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    table_id = arguments.get("tableId")
                    row_index = int(arguments.get("rowIndex"))
                    column_index = int(arguments.get("columnIndex"))
                    text = arguments.get("text")
                    
                    # First clear the cell, then insert new text
                    # Get current cell text to delete it
                    presentation = slides_service.presentations().get(
                        presentationId=presentation_id,
                        fields=f"slides(pageElements(objectId,table))"
                    ).execute()
                    
                    cell_text_length = 0
                    for slide in presentation.get('slides', []):
                        for element in slide.get('pageElements', []):
                            if element.get('objectId') == table_id:
                                if 'table' in element:
                                    table = element['table']
                                    table_rows = table.get('tableRows', [])
                                    if row_index < len(table_rows):
                                        row = table_rows[row_index]
                                        cells = row.get('tableCells', [])
                                        if column_index < len(cells):
                                            cell = cells[column_index]
                                            cell_content = cell.get('content', [])
                                            # Calculate text length in cell
                                            for content_elem in cell_content:
                                                if 'paragraph' in content_elem:
                                                    para = content_elem['paragraph']
                                                    for para_elem in para.get('elements', []):
                                                        if 'textRun' in para_elem:
                                                            cell_text_length += len(para_elem['textRun'].get('content', ''))
                                break
                    
                    requests = []
                    
                    # Delete existing text if any
                    if cell_text_length > 0:
                        requests.append({
                            "deleteText": {
                                "objectId": table_id,
                                "cellLocation": {
                                    "rowIndex": row_index,
                                    "columnIndex": column_index
                                },
                                "textRange": {
                                    "type": "FIXED_RANGE",
                                    "startIndex": 0,
                                    "endIndex": cell_text_length
                                }
                            }
                        })
                    
                    # Insert new text
                    requests.append({
                        "insertText": {
                            "objectId": table_id,
                            "cellLocation": {
                                "rowIndex": row_index,
                                "columnIndex": column_index
                            },
                            "text": text
                        }
                    })
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "tableId": table_id,
                            "rowIndex": row_index,
                            "columnIndex": column_index,
                            "status": "updated"
                        }, indent=2)
                    )]
                
                elif name == "slides_create_chart":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    spreadsheet_id = arguments.get("spreadsheetId")
                    chart_id = int(arguments.get("chartId"))
                    x = int(arguments.get("x"))
                    y = int(arguments.get("y"))
                    width = int(arguments.get("width"))
                    height = int(arguments.get("height"))
                    linking_mode = arguments.get("linkingMode", "LINKED")
                    
                    # Generate unique object ID
                    import hashlib
                    import time as time_module
                    unique_str = f"{presentation_id}_{page_id}_{time_module.time()}_chart"
                    object_id_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    object_id = f"chart_{object_id_hash}"
                    
                    requests = [{
                        "createSheetsChart": {
                            "spreadsheetId": spreadsheet_id,
                            "chartId": chart_id,
                            "linkingMode": linking_mode,
                            "elementProperties": {
                                "pageObjectId": page_id,
                                "size": {
                                    "height": {"magnitude": height, "unit": "EMU"},
                                    "width": {"magnitude": width, "unit": "EMU"}
                                },
                                "transform": {
                                    "scaleX": 1.0,
                                    "scaleY": 1.0,
                                    "translateX": x,
                                    "translateY": y,
                                    "unit": "EMU"
                                }
                            },
                            "objectId": object_id
                        }
                    }]
                    
                    response = slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    created_chart_id = response.get('replies', [{}])[0].get('createSheetsChart', {}).get('objectId')
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "chartId": created_chart_id,
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "slides_format_paragraph":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    
                    paragraph_style = {}
                    style_fields = []
                    
                    if "alignment" in arguments:
                        alignment = arguments["alignment"]
                        paragraph_style["alignment"] = alignment
                        style_fields.append("alignment")
                    
                    if "lineSpacing" in arguments:
                        line_spacing = arguments["lineSpacing"]
                        paragraph_style["lineSpacing"] = {
                            "spacingMode": "MULTIPLE",
                            "spacingMultiple": line_spacing
                        }
                        style_fields.append("lineSpacing")
                    
                    if "spaceAbove" in arguments:
                        space_above = arguments["spaceAbove"]
                        paragraph_style["spaceAbove"] = {
                            "magnitude": space_above,
                            "unit": "PT"
                        }
                        style_fields.append("spaceAbove")
                    
                    if "spaceBelow" in arguments:
                        space_below = arguments["spaceBelow"]
                        paragraph_style["spaceBelow"] = {
                            "magnitude": space_below,
                            "unit": "PT"
                        }
                        style_fields.append("spaceBelow")
                    
                    if not paragraph_style:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "No paragraph formatting options provided"}, indent=2)
                        )]
                    
                    requests = [{
                        "updateParagraphStyle": {
                            "objectId": element_id,
                            "style": paragraph_style,
                            "textRange": {
                                "type": "FIXED_RANGE",
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "fields": ",".join(style_fields)
                        }
                    }]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "status": "paragraph_formatted"
                        }, indent=2)
                    )]
                
                elif name == "slides_create_bullets":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    bullet_preset = arguments.get("bulletPreset", "BULLET_DISC_CIRCLE_SQUARE")
                    
                    requests = [{
                        "createParagraphBullets": {
                            "objectId": element_id,
                            "textRange": {
                                "type": "FIXED_RANGE",
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "bulletPreset": bullet_preset
                        }
                    }]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "status": "bullets_created"
                        }, indent=2)
                    )]
                
                elif name == "slides_update_element_transform":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    
                    # Get current transform
                    presentation = slides_service.presentations().get(
                        presentationId=presentation_id,
                        fields=f"slides(pageElements(objectId,transform))"
                    ).execute()
                    
                    current_transform = None
                    for slide in presentation.get('slides', []):
                        if slide.get('objectId') == page_id:
                            for element in slide.get('pageElements', []):
                                if element.get('objectId') == element_id:
                                    current_transform = element.get('transform', {})
                                    break
                            break
                    
                    if not current_transform:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "Element not found"}, indent=2)
                        )]
                    
                    # Build new transform
                    new_transform = current_transform.copy()
                    if "translateX" in arguments:
                        new_transform["translateX"] = int(arguments["translateX"])
                    if "translateY" in arguments:
                        new_transform["translateY"] = int(arguments["translateY"])
                    if "scaleX" in arguments:
                        new_transform["scaleX"] = arguments["scaleX"]
                    if "scaleY" in arguments:
                        new_transform["scaleY"] = arguments["scaleY"]
                    if "rotation" in arguments:
                        rotation_rad = arguments["rotation"] * 3.141592653589793 / 180.0
                        new_transform["rotation"] = rotation_rad
                    
                    requests = [{
                        "updatePageElementTransform": {
                            "objectId": element_id,
                            "transform": new_transform
                        }
                    }]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "elementId": element_id,
                            "status": "transform_updated"
                        }, indent=2)
                    )]
                
                elif name == "slides_delete_element":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    element_id = arguments.get("elementId")
                    
                    requests = [{
                        "deleteObject": {
                            "objectId": element_id
                        }
                    }]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "elementId": element_id,
                            "status": "deleted"
                        }, indent=2)
                    )]
                
                elif name == "slides_get_masters":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    
                    presentation = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    
                    masters = []
                    for layout in presentation.get('layouts', []):
                        layout_props = layout.get('layoutProperties', {})
                        masters.append({
                            "layoutId": layout.get('objectId'),
                            "name": layout_props.get('name', 'Unknown'),
                            "displayName": layout_props.get('displayName', '')
                        })
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "masters": masters,
                            "count": len(masters)
                        }, indent=2)
                    )]
                
                elif name == "slides_apply_layout":
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    layout_id = arguments.get("layoutId")
                    
                    requests = [{
                        "updateSlideProperties": {
                            "objectId": page_id,
                            "slideProperties": {
                                "layoutObjectId": layout_id
                            },
                            "fields": "layoutObjectId"
                        }
                    }]
                    
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "pageId": page_id,
                            "layoutId": layout_id,
                            "status": "layout_applied"
                        }, indent=2)
                    )]
                
                elif name == "slides_create_presentation_from_doc":
                    docs_service = self._get_docs_service()
                    slides_service = self._get_slides_service()
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    presentation_title = arguments.get("presentationTitle")
                    slides_per_paragraph = arguments.get("slidesPerParagraph", True)
                    
                    # Read document
                    document = docs_service.documents().get(documentId=document_id).execute()
                    doc_title = document.get('title', 'Untitled')
                    if not presentation_title:
                        presentation_title = f"{doc_title} (Presentation)"
                    
                    content = document.get('body', {}).get('content', [])
                    full_text = self._extract_text_from_docs_content(content)
                    
                    # Create presentation
                    presentation = slides_service.presentations().create(
                        body={"title": presentation_title}
                    ).execute()
                    presentation_id = presentation.get('presentationId')
                    
                    # Move to workspace folder
                    file_info = drive_service.files().get(
                        fileId=presentation_id,
                        fields="parents"
                    ).execute()
                    previous_parents = ",".join(file_info.get('parents', []))
                    drive_service.files().update(
                        fileId=presentation_id,
                        addParents=folder_id,
                        removeParents=previous_parents,
                        fields="id, parents"
                    ).execute()
                    
                    # Get layout IDs
                    presentation_obj = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    layouts = presentation_obj.get('layouts', [])
                    title_layout_id = None
                    body_layout_id = None
                    
                    for layout in layouts:
                        layout_name = layout.get('layoutProperties', {}).get('name', '')
                        if layout_name == 'TITLE':
                            title_layout_id = layout.get('objectId')
                        elif layout_name == 'TITLE_AND_BODY':
                            body_layout_id = layout.get('objectId')
                    
                    if not body_layout_id and layouts:
                        body_layout_id = layouts[0].get('objectId')
                    
                    # Split text into paragraphs
                    paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
                    if not paragraphs:
                        paragraphs = [full_text] if full_text.strip() else ["Empty document"]
                    
                    requests = []
                    
                    # Create title slide
                    if title_layout_id:
                        requests.append({
                            "createSlide": {
                                "objectId": f"slide_title_{presentation_id}",
                                "slideLayoutReference": {"layoutId": title_layout_id}
                            }
                        })
                    
                    # Create slides for content
                    for i, paragraph in enumerate(paragraphs):
                        slide_id = f"slide_{presentation_id}_{i}"
                        requests.append({
                            "createSlide": {
                                "objectId": slide_id,
                                "slideLayoutReference": {"layoutId": body_layout_id}
                            }
                        })
                    
                    # Execute batch create slides
                    if requests:
                        batch_response = slides_service.presentations().batchUpdate(
                            presentationId=presentation_id,
                            body={"requests": requests}
                        ).execute()
                        
                        # Get created slide IDs
                        slide_ids = []
                        for reply in batch_response.get('replies', []):
                            if 'createSlide' in reply:
                                slide_ids.append(reply['createSlide'].get('objectId'))
                        
                        # Insert text into slides
                        text_requests = []
                        slide_index = 0
                        
                        # Insert title if we created title slide
                        if title_layout_id and slide_ids:
                            # Find title text box in first slide
                            presentation_obj = slides_service.presentations().get(
                                presentationId=presentation_id
                            ).execute()
                            title_slide_id = slide_ids[0]
                            for slide in presentation_obj.get('slides', []):
                                if slide.get('objectId') == title_slide_id:
                                    for element in slide.get('pageElements', []):
                                        if 'shape' in element:
                                            shape_type = element['shape'].get('shapeType')
                                            if shape_type == 'TEXT_BOX':
                                                text_requests.append({
                                                    "insertText": {
                                                        "objectId": element.get('objectId'),
                                                        "text": doc_title
                                                    }
                                                })
                                                break
                                    break
                            slide_index = 1
                        
                        # Insert paragraph text into body slides
                        for para_idx, paragraph in enumerate(paragraphs):
                            if slide_index < len(slide_ids):
                                slide_id = slide_ids[slide_index]
                                # Get slide and find text box
                                presentation_obj = slides_service.presentations().get(
                                    presentationId=presentation_id
                                ).execute()
                                for slide in presentation_obj.get('slides', []):
                                    if slide.get('objectId') == slide_id:
                                        for element in slide.get('pageElements', []):
                                            if 'shape' in element:
                                                shape_type = element['shape'].get('shapeType')
                                                if shape_type == 'TEXT_BOX':
                                                    text_requests.append({
                                                        "insertText": {
                                                            "objectId": element.get('objectId'),
                                                            "text": paragraph
                                                        }
                                                    })
                                                    break
                                        break
                                slide_index += 1
                        
                        # Execute text insertion
                        if text_requests:
                            slides_service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": text_requests}
                            ).execute()
                    
                    # Get presentation URL
                    pres_file = drive_service.files().get(
                        fileId=presentation_id,
                        fields="webViewLink"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "title": presentation_title,
                            "url": pres_file.get('webViewLink'),
                            "slidesCreated": len(paragraphs) + (1 if title_layout_id else 0)
                        }, indent=2)
                    )]
                
                else:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2)
                    )]
                    
            except HttpError as e:
                error_msg = json.loads(e.content.decode()).get('error', {}).get('message', str(e))
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"API error: {error_msg}"}, indent=2)
                )]
            except Exception as e:
                logger.exception(f"Error executing tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, indent=2)
                )]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Google Slides MCP Server")
    parser.add_argument(
        "--token-path",
        type=str,
        default="config/google_workspace_token.json",
        help="Path to OAuth token file"
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/workspace_config.json",
        help="Path to workspace config file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = GoogleSlidesMCPServer(Path(args.token_path), config_path=Path(args.config_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

