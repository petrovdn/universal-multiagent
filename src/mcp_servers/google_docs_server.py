"""
Google Docs MCP Server.
Provides MCP tools for Google Docs operations via OAuth2.
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

# Docs API scopes
DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDocsMCPServer:
    """MCP Server for Google Docs operations."""
    
    def __init__(self, token_path: Path, config_path: Optional[Path] = None):
        """
        Initialize Google Docs MCP Server.
        
        Args:
            token_path: Path to OAuth token file
            config_path: Path to workspace config file (optional, defaults to config/workspace_config.json)
        """
        self.token_path = Path(token_path)
        self.config_path = config_path or Path("config/workspace_config.json")
        self._docs_service = None
        self._drive_service = None
        self._workspace_folder_id = None
        self.server = Server("google-docs-mcp")
        self._setup_tools()
    
    def _get_docs_service(self):
        """Get or create Google Docs API service."""
        if self._docs_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                DOCS_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self._docs_service = build('docs', 'v1', credentials=creds)
        
        return self._docs_service
    
    def _get_drive_service(self):
        """Get or create Google Drive API service for document operations."""
        if self._drive_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                DOCS_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self._drive_service = build('drive', 'v3', credentials=creds)
        
        return self._drive_service
    
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
            r'/document/d/([a-zA-Z0-9-_]+)',
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
                    name="docs_create",
                    description="Create a new Google Docs document in the workspace folder.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the document"
                            },
                            "initialText": {
                                "type": "string",
                                "description": "Initial text content (optional)"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                Tool(
                    name="docs_read",
                    description="Read the full content of a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            }
                        },
                        "required": ["documentId"]
                    }
                ),
                Tool(
                    name="docs_update",
                    description="Replace all content in a Google Docs document with new text.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "content": {
                                "type": "string",
                                "description": "New content to write"
                            }
                        },
                        "required": ["documentId", "content"]
                    }
                ),
                Tool(
                    name="docs_append",
                    description="Append text to the end of a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "content": {
                                "type": "string",
                                "description": "Text to append"
                            }
                        },
                        "required": ["documentId", "content"]
                    }
                ),
                Tool(
                    name="docs_insert",
                    description="Insert text at a specific position in a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "index": {
                                "type": "integer",
                                "description": "Character index where to insert (0-based)"
                            },
                            "content": {
                                "type": "string",
                                "description": "Text to insert"
                            }
                        },
                        "required": ["documentId", "index", "content"]
                    }
                ),
                Tool(
                    name="docs_format_text",
                    description="Format text in a Google Docs document (bold, italic, underline, colors).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
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
                            "underline": {
                                "type": "boolean",
                                "description": "Make text underlined"
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
                            "backgroundColor": {
                                "type": "object",
                                "description": "Background/highlight color as {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="docs_search_text",
                    description="Search for text in a Google Docs document and return matching positions.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "searchText": {
                                "type": "string",
                                "description": "Text to search for"
                            },
                            "matchCase": {
                                "type": "boolean",
                                "description": "Whether to match case (default: false)",
                                "default": False
                            }
                        },
                        "required": ["documentId", "searchText"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "docs_create":
                    drive_service = self._get_drive_service()
                    docs_service = self._get_docs_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    title = arguments.get("title")
                    initial_text = arguments.get("initialText", "")
                    
                    # Create document
                    document = docs_service.documents().create(
                        body={"title": title}
                    ).execute()
                    
                    document_id = document.get('documentId')
                    
                    # Move to workspace folder
                    if folder_id:
                        file_info = drive_service.files().get(
                            fileId=document_id,
                            fields="parents"
                        ).execute()
                        previous_parents = ",".join(file_info.get('parents', []))
                        drive_service.files().update(
                            fileId=document_id,
                            addParents=folder_id,
                            removeParents=previous_parents,
                            fields="id, parents"
                        ).execute()
                    
                    # Add initial text if provided
                    if initial_text:
                        docs_service.documents().batchUpdate(
                            documentId=document_id,
                            body={
                                "requests": [{
                                    "insertText": {
                                        "location": {"index": 1},
                                        "text": initial_text
                                    }
                                }]
                            }
                        ).execute()
                    
                    # Get document URL
                    doc_file = drive_service.files().get(
                        fileId=document_id,
                        fields="webViewLink"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "documentId": document_id,
                            "title": title,
                            "url": doc_file.get('webViewLink')
                        }, indent=2)
                    )]
                
                elif name == "docs_read":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    
                    document = docs_service.documents().get(documentId=document_id).execute()
                    
                    # Extract text content
                    content = document.get('body', {}).get('content', [])
                    text_content = self._extract_text_from_docs_content(content)
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "documentId": document_id,
                            "title": document.get('title'),
                            "content": text_content
                        }, indent=2)
                    )]
                
                elif name == "docs_update":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    content = arguments.get("content")
                    
                    # Get document to find end index
                    document = docs_service.documents().get(documentId=document_id).execute()
                    end_index = document.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
                    
                    # Delete existing content (except the last newline)
                    requests = []
                    if end_index > 1:
                        requests.append({
                            "deleteContentRange": {
                                "range": {
                                    "startIndex": 1,
                                    "endIndex": end_index - 1
                                }
                            }
                        })
                    
                    # Insert new content
                    if content:
                        requests.append({
                            "insertText": {
                                "location": {"index": 1},
                                "text": content
                            }
                        })
                    
                    if requests:
                        docs_service.documents().batchUpdate(
                            documentId=document_id,
                            body={"requests": requests}
                        ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "updated",
                            "documentId": document_id
                        }, indent=2)
                    )]
                
                elif name == "docs_append":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    content = arguments.get("content")
                    
                    # Get document to find end index
                    document = docs_service.documents().get(documentId=document_id).execute()
                    end_index = document.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
                    
                    # Insert at end (before the last newline)
                    insert_index = end_index - 1
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={
                            "requests": [{
                                "insertText": {
                                    "location": {"index": insert_index},
                                    "text": content
                                }
                            }]
                        }
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "appended",
                            "documentId": document_id
                        }, indent=2)
                    )]
                
                elif name == "docs_insert":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    index = arguments.get("index")
                    content = arguments.get("content")
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={
                            "requests": [{
                                "insertText": {
                                    "location": {"index": index},
                                    "text": content
                                }
                            }]
                        }
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "inserted",
                            "documentId": document_id,
                            "index": index
                        }, indent=2)
                    )]
                
                elif name == "docs_format_text":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    
                    update_mask = []
                    text_style = {}
                    
                    if "bold" in arguments:
                        text_style["bold"] = arguments["bold"]
                        update_mask.append("bold")
                    if "italic" in arguments:
                        text_style["italic"] = arguments["italic"]
                        update_mask.append("italic")
                    if "underline" in arguments:
                        text_style["underline"] = arguments["underline"]
                        update_mask.append("underline")
                    if "foregroundColor" in arguments:
                        text_style["foregroundColor"] = {
                            "color": {
                                "rgbColor": arguments["foregroundColor"]
                            }
                        }
                        update_mask.append("foregroundColor")
                    if "backgroundColor" in arguments:
                        text_style["backgroundColor"] = {
                            "color": {
                                "rgbColor": arguments["backgroundColor"]
                            }
                        }
                        update_mask.append("backgroundColor")
                    
                    if not update_mask:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "No formatting options provided"}, indent=2)
                        )]
                    
                    requests = [{
                        "updateTextStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "textStyle": text_style,
                            "fields": ",".join(update_mask)
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "formatted",
                            "documentId": document_id
                        }, indent=2)
                    )]
                
                elif name == "docs_search_text":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    search_text = arguments.get("searchText")
                    match_case = arguments.get("matchCase", False)
                    
                    # Read document
                    document = docs_service.documents().get(documentId=document_id).execute()
                    content = document.get('body', {}).get('content', [])
                    full_text = self._extract_text_from_docs_content(content)
                    
                    # Simple text search (Google Docs API doesn't have built-in search)
                    matches = []
                    search_lower = search_text.lower() if not match_case else search_text
                    text_lower = full_text.lower() if not match_case else full_text
                    
                    start = 0
                    while True:
                        pos = text_lower.find(search_lower, start)
                        if pos == -1:
                            break
                        matches.append({
                            "startIndex": pos,
                            "endIndex": pos + len(search_text)
                        })
                        start = pos + 1
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "documentId": document_id,
                            "searchText": search_text,
                            "matches": matches,
                            "matchCount": len(matches)
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
    
    parser = argparse.ArgumentParser(description="Google Docs MCP Server")
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
    
    server = GoogleDocsMCPServer(Path(args.token_path), config_path=Path(args.config_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

