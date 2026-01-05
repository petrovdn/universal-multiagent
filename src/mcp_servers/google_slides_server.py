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
    
    def _extract_structured_content(self, content: List[Dict], inline_objects: Dict = None) -> List[Dict]:
        """
        Extract structured content from Google Docs document.
        Returns list of elements with type, level, text, and metadata.
        
        Args:
            content: Document body content
            inline_objects: Dictionary of inline objects (images) from document
            
        Returns:
            List of structured elements:
            - {'type': 'heading', 'level': 1-6, 'text': str}
            - {'type': 'text', 'text': str, 'is_bullet': bool}
            - {'type': 'image', 'object_id': str, 'uri': str}
        """
        result = []
        inline_objects = inline_objects or {}
        
        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                style = paragraph.get('paragraphStyle', {})
                named_style = style.get('namedStyleType', 'NORMAL_TEXT')
                
                # Check if this is a list item
                is_bullet = 'bullet' in paragraph
                
                # Extract text from paragraph elements
                text_parts = []
                for elem in paragraph.get('elements', []):
                    if 'textRun' in elem:
                        text_parts.append(elem['textRun'].get('content', ''))
                    elif 'inlineObjectElement' in elem:
                        # Found an image
                        obj_id = elem['inlineObjectElement'].get('inlineObjectId')
                        if obj_id and obj_id in inline_objects:
                            obj_props = inline_objects[obj_id].get('inlineObjectProperties', {})
                            embedded = obj_props.get('embeddedObject', {})
                            image_uri = embedded.get('imageProperties', {}).get('contentUri', '')
                            if image_uri:
                                result.append({
                                    'type': 'image',
                                    'object_id': obj_id,
                                    'uri': image_uri
                                })
                
                text = ''.join(text_parts).strip()
                if text:
                    # Determine heading level
                    if named_style.startswith('HEADING_'):
                        try:
                            level = int(named_style.split('_')[1])
                        except (ValueError, IndexError):
                            level = 1
                        result.append({
                            'type': 'heading',
                            'level': level,
                            'text': text
                        })
                    elif named_style == 'TITLE':
                        result.append({
                            'type': 'heading',
                            'level': 0,  # Title is level 0
                            'text': text
                        })
                    else:
                        result.append({
                            'type': 'text',
                            'text': text,
                            'is_bullet': is_bullet
                        })
                        
            elif 'table' in element:
                # Extract table as text
                table = element['table']
                table_text = []
                for row in table.get('tableRows', []):
                    row_text = []
                    for cell in row.get('tableCells', []):
                        cell_content = cell.get('content', [])
                        cell_text = self._extract_text_from_docs_content(cell_content)
                        row_text.append(cell_text.strip())
                    if row_text:
                        table_text.append(' | '.join(row_text))
                if table_text:
                    result.append({
                        'type': 'table',
                        'text': '\n'.join(table_text)
                    })
        
        return result
    
    def _group_content_into_slides(self, structured_content: List[Dict], doc_title: str) -> List[Dict]:
        """
        Group structured content into slides.
        
        Args:
            structured_content: List from _extract_structured_content
            doc_title: Document title for the title slide
            
        Returns:
            List of slide definitions:
            - {'layout': str, 'title': str, 'subtitle': str, 'content': list, 'images': list}
        """
        slides = []
        
        # Create title slide
        title_slide = {
            'layout': 'TITLE',
            'title': doc_title,
            'subtitle': '',
            'content': [],
            'images': []
        }
        slides.append(title_slide)
        
        current_slide = None
        
        for item in structured_content:
            if item['type'] == 'heading':
                level = item['level']
                
                if level == 0:
                    # Document title - update title slide subtitle or skip
                    if item['text'] != doc_title:
                        slides[0]['subtitle'] = item['text']
                        
                elif level == 1:
                    # H1 - Section header slide
                    if current_slide:
                        slides.append(current_slide)
                    current_slide = {
                        'layout': 'SECTION_HEADER',
                        'title': item['text'],
                        'subtitle': '',
                        'content': [],
                        'images': []
                    }
                    
                elif level == 2:
                    # H2 - New content slide with title
                    if current_slide:
                        slides.append(current_slide)
                    current_slide = {
                        'layout': 'TITLE_AND_BODY',
                        'title': item['text'],
                        'subtitle': '',
                        'content': [],
                        'images': []
                    }
                    
                else:
                    # H3+ - Add as bold content to current slide
                    if current_slide is None:
                        current_slide = {
                            'layout': 'TITLE_AND_BODY',
                            'title': '',
                            'subtitle': '',
                            'content': [],
                            'images': []
                        }
                    current_slide['content'].append({
                        'type': 'subheading',
                        'text': item['text']
                    })
                    
            elif item['type'] == 'text':
                if current_slide is None:
                    current_slide = {
                        'layout': 'TITLE_AND_BODY',
                        'title': '',
                        'subtitle': '',
                        'content': [],
                        'images': []
                    }
                current_slide['content'].append({
                    'type': 'bullet' if item.get('is_bullet') else 'text',
                    'text': item['text']
                })
                
            elif item['type'] == 'image':
                if current_slide is None:
                    current_slide = {
                        'layout': 'TITLE_AND_BODY',
                        'title': '',
                        'subtitle': '',
                        'content': [],
                        'images': []
                    }
                current_slide['images'].append({
                    'uri': item['uri'],
                    'object_id': item.get('object_id')
                })
                
            elif item['type'] == 'table':
                if current_slide is None:
                    current_slide = {
                        'layout': 'TITLE_AND_BODY',
                        'title': '',
                        'subtitle': '',
                        'content': [],
                        'images': []
                    }
                current_slide['content'].append({
                    'type': 'table',
                    'text': item['text']
                })
        
        # Don't forget the last slide
        if current_slide:
            slides.append(current_slide)
        
        return slides
    
    def _get_template_id(self, theme: str) -> Optional[str]:
        """
        Get template presentation ID for the given theme.
        
        Args:
            theme: Theme name (professional, creative, minimal, dark)
            
        Returns:
            Template presentation ID or None if not configured
        """
        config = self._load_config()
        templates = config.get('presentation_templates', {})
        theme_config = templates.get(theme, {})
        template_id = theme_config.get('id', '')
        return template_id if template_id else None
    
    def _get_available_themes(self) -> Dict[str, str]:
        """
        Get available themes with their descriptions.
        
        Returns:
            Dict of theme_name -> description
        """
        config = self._load_config()
        templates = config.get('presentation_templates', {})
        return {
            name: data.get('description', '')
            for name, data in templates.items()
        }
    
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
                    description="""Create a professional presentation from a Google Docs document.
                    
The document structure is automatically analyzed:
- H1 headings create section divider slides
- H2 headings create content slides with titles
- Regular text becomes bullet points
- Images from the document are included

Choose an appropriate theme based on the document content:
- professional: Business presentations, reports, formal documents (blue accents, white background)
- creative: Marketing, startups, creative projects (bright colors, unique fonts)
- minimal: Academic, technical presentations (clean, lots of whitespace)
- dark: IT, technology presentations (dark background, light text)""",
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
                            "theme": {
                                "type": "string",
                                "description": "Presentation theme. Choose based on content: professional (business), creative (marketing), minimal (academic), dark (tech)",
                                "enum": ["professional", "creative", "minimal", "dark"],
                                "default": "professional"
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
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_format_text:entry",
                                "message": "slides_format_text handler called",
                                "data": {"arguments": arguments},
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H8"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
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
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_format_text:no_requests",
                                    "message": "No formatting requests generated",
                                    "data": {"text_style": text_style, "style_fields": style_fields},
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H8"
                                }) + "\n")
                        except: pass
                        # #endregion
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "No formatting options provided"}, indent=2)
                        )]
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "location": "google_slides_server.py:slides_format_text:before_api",
                                "message": "Before batchUpdate API call",
                                "data": {
                                    "presentation_id": presentation_id,
                                    "element_id": element_id,
                                    "start_index": start_index,
                                    "end_index": end_index,
                                    "text_style": text_style,
                                    "style_fields": style_fields,
                                    "requests": requests
                                },
                                "timestamp": int(__import__('time').time() * 1000),
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H8"
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
                                    "location": "google_slides_server.py:slides_format_text:after_api",
                                    "message": "After batchUpdate API call",
                                    "data": {
                                        "response_keys": list(response.keys()) if isinstance(response, dict) else None,
                                        "response_preview": str(response)[:200] if response else None
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H8"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "presentationId": presentation_id,
                                "status": "formatted"
                            }, indent=2)
                        )]
                    except Exception as format_error:
                        # #region agent log
                        try:
                            import traceback
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "location": "google_slides_server.py:slides_format_text:api_error",
                                    "message": "API call failed",
                                    "data": {
                                        "error_type": type(format_error).__name__,
                                        "error_message": str(format_error),
                                        "error_traceback": traceback.format_exc()[:1000]
                                    },
                                    "timestamp": int(__import__('time').time() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H8"
                                }) + "\n")
                        except: pass
                        # #endregion
                        raise  # Re-raise to be handled by outer exception handler
                
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
                    theme = arguments.get("theme", "professional")
                    
                    logger.info(f"Creating presentation from doc: {document_id}, theme: {theme}")
                    
                    # Read document with full structure
                    document = docs_service.documents().get(documentId=document_id).execute()
                    doc_title = document.get('title', 'Untitled')
                    if not presentation_title:
                        presentation_title = doc_title
                    
                    content = document.get('body', {}).get('content', [])
                    inline_objects = document.get('inlineObjects', {})
                    
                    logger.info(f"Document '{doc_title}' has {len(content)} content elements")
                    
                    # Extract structured content (headings, text, images)
                    structured_content = self._extract_structured_content(content, inline_objects)
                    logger.info(f"Extracted {len(structured_content)} structured elements")
                    
                    # Group into slides
                    slide_definitions = self._group_content_into_slides(structured_content, doc_title)
                    logger.info(f"Grouped into {len(slide_definitions)} slides")
                    
                    # Try to copy template if available, otherwise create empty
                    template_id = self._get_template_id(theme)
                    
                    if template_id:
                        # Copy template presentation
                        new_file = drive_service.files().copy(
                            fileId=template_id,
                            body={
                                "name": presentation_title,
                                "parents": [folder_id]
                            }
                        ).execute()
                        presentation_id = new_file.get('id')
                        
                        # Get presentation and delete all slides except first
                        presentation_obj = slides_service.presentations().get(
                            presentationId=presentation_id
                        ).execute()
                        existing_slides = presentation_obj.get('slides', [])
                        
                        # Delete all slides except the first one (we'll use it for title)
                        if len(existing_slides) > 1:
                            delete_requests = []
                            for slide in existing_slides[1:]:
                                delete_requests.append({
                                    "deleteObject": {"objectId": slide.get('objectId')}
                                })
                            if delete_requests:
                                slides_service.presentations().batchUpdate(
                                    presentationId=presentation_id,
                                    body={"requests": delete_requests}
                                ).execute()
                    else:
                        # Create new empty presentation
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
                    
                    # Get current presentation state and layout IDs
                    presentation_obj = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    
                    layouts = presentation_obj.get('layouts', [])
                    layout_ids = {}
                    for layout in layouts:
                        layout_name = layout.get('layoutProperties', {}).get('name', '')
                        layout_ids[layout_name] = layout.get('objectId')
                    
                    # Get first slide ID (use it for title slide)
                    existing_slides = presentation_obj.get('slides', [])
                    first_slide_id = existing_slides[0].get('objectId') if existing_slides else None
                    
                    # Create slides based on definitions
                    create_requests = []
                    slide_id_map = {}  # Map definition index to slide ID
                    
                    for i, slide_def in enumerate(slide_definitions):
                        if i == 0 and first_slide_id:
                            # Use the existing first slide for title
                            slide_id_map[i] = first_slide_id
                            # Apply title layout to first slide if needed
                            if 'TITLE' in layout_ids:
                                create_requests.append({
                                    "updateSlideProperties": {
                                        "objectId": first_slide_id,
                                        "slideProperties": {
                                            "layoutObjectId": layout_ids['TITLE']
                                        },
                                        "fields": "layoutObjectId"
                                    }
                                })
                        else:
                            # Create new slide
                            slide_id = f"slide_{presentation_id}_{i}"
                            slide_id_map[i] = slide_id
                            
                            # Choose layout based on slide type
                            layout_name = slide_def.get('layout', 'TITLE_AND_BODY')
                            layout_id = layout_ids.get(layout_name) or layout_ids.get('TITLE_AND_BODY') or layouts[0].get('objectId')
                            
                            create_requests.append({
                                "createSlide": {
                                    "objectId": slide_id,
                                    "slideLayoutReference": {"layoutId": layout_id}
                                }
                            })
                    
                    # Execute slide creation
                    logger.info(f"Creating {len(create_requests)} slide requests")
                    if create_requests:
                        try:
                            slides_service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": create_requests}
                            ).execute()
                            logger.info("Slides created successfully")
                        except Exception as e:
                            logger.error(f"Error creating slides: {e}")
                            raise
                    
                    # Refresh presentation to get all elements
                    presentation_obj = slides_service.presentations().get(
                        presentationId=presentation_id
                    ).execute()
                    logger.info(f"Presentation now has {len(presentation_obj.get('slides', []))} slides")
                    
                    # Build a map of slide ID -> slide data
                    slide_data_map = {}
                    for slide in presentation_obj.get('slides', []):
                        slide_data_map[slide.get('objectId')] = slide
                    
                    # Insert text and apply formatting
                    text_requests = []
                    format_requests = []
                    
                    for i, slide_def in enumerate(slide_definitions):
                        slide_id = slide_id_map.get(i)
                        if not slide_id or slide_id not in slide_data_map:
                            logger.warning(f"Slide {i} not found in slide_data_map, skipping")
                            continue
                        
                        slide_data = slide_data_map[slide_id]
                        logger.info(f"Processing slide {i}: layout={slide_def.get('layout')}, title='{slide_def.get('title', '')[:30]}...'")
                        
                        # Find text boxes in this slide
                        title_element_id = None
                        body_element_id = None
                        subtitle_element_id = None
                        
                        for element in slide_data.get('pageElements', []):
                            if 'shape' in element:
                                placeholder = element['shape'].get('placeholder', {})
                                placeholder_type = placeholder.get('type', '')
                                element_id = element.get('objectId')
                                
                                if placeholder_type in ['TITLE', 'CENTERED_TITLE']:
                                    title_element_id = element_id
                                elif placeholder_type == 'SUBTITLE':
                                    subtitle_element_id = element_id
                                elif placeholder_type == 'BODY':
                                    body_element_id = element_id
                                elif element['shape'].get('shapeType') == 'TEXT_BOX' and not title_element_id:
                                    # Fallback: use first text box as title
                                    title_element_id = element_id
                        
                        logger.info(f"Slide {i} elements: title={title_element_id}, body={body_element_id}, subtitle={subtitle_element_id}")
                        
                        # Insert title
                        if slide_def.get('title') and title_element_id:
                            title_text = slide_def['title']
                            text_requests.append({
                                "insertText": {
                                    "objectId": title_element_id,
                                    "text": title_text
                                }
                            })
                            # Format title: bold, larger font
                            format_requests.append({
                                "updateTextStyle": {
                                    "objectId": title_element_id,
                                    "style": {
                                        "bold": True,
                                        "fontSize": {"magnitude": 32, "unit": "PT"}
                                    },
                                    "textRange": {"type": "ALL"},
                                    "fields": "bold,fontSize"
                                }
                            })
                        
                        # Insert subtitle if present
                        if slide_def.get('subtitle') and subtitle_element_id:
                            text_requests.append({
                                "insertText": {
                                    "objectId": subtitle_element_id,
                                    "text": slide_def['subtitle']
                                }
                            })
                        
                        # Insert body content
                        if slide_def.get('content') and body_element_id:
                            body_text_parts = []
                            bullet_ranges = []  # Track which ranges need bullets
                            current_pos = 0
                            
                            for content_item in slide_def['content']:
                                item_text = content_item.get('text', '')
                                item_type = content_item.get('type', 'text')
                                
                                if item_type == 'subheading':
                                    # Add as bold text with newline
                                    body_text_parts.append(item_text + '\n')
                                elif item_type in ['bullet', 'text']:
                                    # Add text with newline
                                    start_pos = sum(len(p) for p in body_text_parts)
                                    body_text_parts.append(item_text + '\n')
                                    end_pos = sum(len(p) for p in body_text_parts)
                                    if item_type == 'bullet':
                                        bullet_ranges.append((start_pos, end_pos))
                                elif item_type == 'table':
                                    body_text_parts.append(item_text + '\n\n')
                            
                            if body_text_parts:
                                full_body_text = ''.join(body_text_parts).rstrip('\n')
                                text_requests.append({
                                    "insertText": {
                                        "objectId": body_element_id,
                                        "text": full_body_text
                                    }
                                })
                                
                                # Apply bullet formatting
                                for start, end in bullet_ranges:
                                    format_requests.append({
                                        "createParagraphBullets": {
                                            "objectId": body_element_id,
                                            "textRange": {
                                                "type": "FIXED_RANGE",
                                                "startIndex": start,
                                                "endIndex": min(end, len(full_body_text))
                                            },
                                            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                                        }
                                    })
                    
                    # Execute text insertion first
                    if text_requests:
                        slides_service.presentations().batchUpdate(
                            presentationId=presentation_id,
                            body={"requests": text_requests}
                        ).execute()
                    
                    # Then apply formatting
                    if format_requests:
                        try:
                            slides_service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": format_requests}
                            ).execute()
                        except Exception as format_error:
                            logger.warning(f"Some formatting failed: {format_error}")
                    
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
                            "slidesCreated": len(slide_definitions),
                            "theme": theme,
                            "templateUsed": template_id is not None
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

