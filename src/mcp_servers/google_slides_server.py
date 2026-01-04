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
                    description="Format text in a slide (bold, italic, colors).",
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
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "slides_create":
                    drive_service = self._get_drive_service()
                    slides_service = self._get_slides_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    title = arguments.get("title")
                    
                    # Create presentation
                    presentation = slides_service.presentations().create(
                        body={"title": title}
                    ).execute()
                    
                    presentation_id = presentation.get('presentationId')
                    
                    # Move to workspace folder
                    if folder_id:
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
                    
                    # Get presentation URL
                    pres_file = drive_service.files().get(
                        fileId=presentation_id,
                        fields="webViewLink"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "presentationId": presentation_id,
                            "title": title,
                            "url": pres_file.get('webViewLink')
                        }, indent=2)
                    )]
                
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
                    slides_service = self._get_slides_service()
                    presentation_id = self._extract_file_id(arguments.get("presentationId"))
                    page_id = arguments.get("pageId")
                    element_id = arguments.get("elementId")
                    text = arguments.get("text")
                    insert_index = arguments.get("insertIndex", -1)
                    
                    # If element_id not provided, find first text box
                    if not element_id:
                        presentation = slides_service.presentations().get(
                            presentationId=presentation_id
                        ).execute()
                        
                        for slide in presentation.get('slides', []):
                            if slide.get('objectId') == page_id:
                                for element in slide.get('pageElements', []):
                                    if 'shape' in element and element['shape'].get('shapeType') == 'TEXT_BOX':
                                        element_id = element.get('objectId')
                                        break
                                break
                        
                        if not element_id:
                            return [TextContent(
                                type="text",
                                text=json.dumps({"error": "No text box found in slide"}, indent=2)
                            )]
                    
                    # Get current text to determine insert index
                    if insert_index == -1:
                        presentation = slides_service.presentations().get(
                            presentationId=presentation_id,
                            fields="slides(pageElements(objectId,shape(text(textElements)))"
                        ).execute()
                        
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
                                        break
                                break
                    
                    requests = [{
                        "insertText": {
                            "objectId": element_id,
                            "insertionIndex": insert_index,
                            "text": text
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
                        text_style["foregroundColor"] = {
                            "opaqueColor": {
                                "rgbColor": arguments["foregroundColor"]
                            }
                        }
                        style_fields.append("foregroundColor")
                    
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

