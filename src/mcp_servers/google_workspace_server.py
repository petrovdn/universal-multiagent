"""
Google Workspace MCP Server.
Provides MCP tools for Google Drive, Google Docs, and Google Sheets operations via OAuth2.
Unified integration for working with files in a designated workspace folder.
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

# Google Workspace API scopes
WORKSPACE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleWorkspaceMCPServer:
    """MCP Server for Google Workspace operations (Drive, Docs, Sheets)."""
    
    def __init__(self, token_path: Path, config_path: Optional[Path] = None):
        """
        Initialize Google Workspace MCP Server.
        
        Args:
            token_path: Path to OAuth token file
            config_path: Path to workspace configuration file (contains folder_id)
        """
        self.token_path = Path(token_path)
        self.config_path = config_path or Path("config/workspace_config.json")
        self._drive_service = None
        self._docs_service = None
        self._sheets_service = None
        self._workspace_folder_id = None
        self.server = Server("google-workspace-mcp")
        self._setup_tools()
    
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
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    import json as json_lib
                    f.write(json_lib.dumps({"location": "google_workspace_server.py:69", "message": "_get_workspace_folder_id", "data": {"folder_id": self._workspace_folder_id, "config_keys": list(config.keys())}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            # #endregion
        return self._workspace_folder_id
    
    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth credentials."""
        if not self.token_path.exists():
            raise ValueError(
                f"OAuth token not found at {self.token_path}. "
                "Please complete OAuth flow first."
            )
        
        creds = Credentials.from_authorized_user_file(
            str(self.token_path),
            WORKSPACE_SCOPES
        )
        
        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def _get_drive_service(self):
        """Get or create Google Drive API service."""
        if self._drive_service is None:
            creds = self._get_credentials()
            self._drive_service = build('drive', 'v3', credentials=creds)
        return self._drive_service
    
    def _get_docs_service(self):
        """Get or create Google Docs API service."""
        if self._docs_service is None:
            creds = self._get_credentials()
            self._docs_service = build('docs', 'v1', credentials=creds)
        return self._docs_service
    
    def _get_sheets_service(self):
        """Get or create Google Sheets API service."""
        if self._sheets_service is None:
            creds = self._get_credentials()
            self._sheets_service = build('sheets', 'v4', credentials=creds)
        return self._sheets_service
    
    @staticmethod
    def _extract_file_id(file_id_or_url: str) -> str:
        """Extract file ID from URL or return as-is if already an ID."""
        # Pattern for Google Drive/Docs/Sheets URLs
        patterns = [
            r'/file/d/([a-zA-Z0-9-_]+)',
            r'/document/d/([a-zA-Z0-9-_]+)',
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'/presentation/d/([a-zA-Z0-9-_]+)',
            r'docs\.google\.com.*[?&]id=([a-zA-Z0-9-_]+)',
            r'drive\.google\.com.*[?&]id=([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_id_or_url)
            if match:
                return match.group(1)
        
        # If no pattern matched, assume it's already an ID
        return file_id_or_url
    
    @staticmethod
    def _extract_spreadsheet_id(spreadsheet_id_or_url: str) -> str:
        """Extract spreadsheet ID from URL or return as-is if already an ID."""
        return GoogleWorkspaceMCPServer._extract_file_id(spreadsheet_id_or_url)
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                # ========== DRIVE OPERATIONS ==========
                Tool(
                    name="workspace_list_files",
                    description="List files in the workspace folder. Returns files with metadata (name, type, ID, modified time).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "mimeType": {
                                "type": "string",
                                "description": "Filter by MIME type (e.g., 'application/vnd.google-apps.document', 'application/vnd.google-apps.spreadsheet')"
                            },
                            "fileType": {
                                "type": "string",
                                "description": "Filter by file type: 'docs' (Google Docs), 'sheets' (Google Sheets), 'folders' (folders), or 'all' (default)",
                                "enum": ["all", "docs", "sheets", "folders"],
                                "default": "all"
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query for file names"
                            },
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 50, max: 100)",
                                "default": 50
                            }
                        }
                    }
                ),
                Tool(
                    name="workspace_get_file_info",
                    description="Get detailed information about a file (metadata, type, size, etc.).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fileId": {
                                "type": "string",
                                "description": "File ID or URL"
                            }
                        },
                        "required": ["fileId"]
                    }
                ),
                Tool(
                    name="workspace_create_folder",
                    description="Create a new folder inside the workspace folder.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the new folder"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="workspace_delete_file",
                    description="Delete a file or folder from Google Drive.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fileId": {
                                "type": "string",
                                "description": "File ID or URL"
                            }
                        },
                        "required": ["fileId"]
                    }
                ),
                Tool(
                    name="workspace_move_file",
                    description="Move a file to a different folder (within workspace).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fileId": {
                                "type": "string",
                                "description": "File ID or URL"
                            },
                            "targetFolderId": {
                                "type": "string",
                                "description": "Target folder ID (must be within workspace)"
                            }
                        },
                        "required": ["fileId", "targetFolderId"]
                    }
                ),
                Tool(
                    name="workspace_search_files",
                    description="Search for files in the workspace folder by name or content.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g., 'name contains \"report\"', 'fullText contains \"meeting\"')"
                            },
                            "mimeType": {
                                "type": "string",
                                "description": "Filter by MIME type"
                            },
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 20)",
                                "default": 20
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="workspace_get_folder_path",
                    description="Get the current workspace folder ID and path.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="workspace_find_file_by_name",
                    description="Find a file by name in the workspace folder. Returns file ID and URL if found.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fileName": {
                                "type": "string",
                                "description": "Name of the file to find (exact match or partial match)"
                            },
                            "exactMatch": {
                                "type": "boolean",
                                "description": "Whether to require exact name match (default: false, uses contains)",
                                "default": False
                            },
                            "fileType": {
                                "type": "string",
                                "description": "Filter by file type: 'docs', 'sheets', 'folders', or 'all' (default)",
                                "enum": ["all", "docs", "sheets", "folders"],
                                "default": "all"
                            }
                        },
                        "required": ["fileName"]
                    }
                ),
                Tool(
                    name="workspace_get_folder_contents",
                    description="Get contents of the workspace folder grouped by type (documents, spreadsheets, folders).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results per type (default: 50)",
                                "default": 50
                            }
                        }
                    }
                ),
                
                # ========== DOCS OPERATIONS ==========
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
                    description="Format text in a Google Docs document (bold, italic, underline, etc.).",
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
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="docs_format_heading",
                    description="Format text as a heading (H1-H6) in a Google Docs document.",
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
                            "headingLevel": {
                                "type": "integer",
                                "description": "Heading level (1-6, where 1 is largest)",
                                "minimum": 1,
                                "maximum": 6
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex", "headingLevel"]
                    }
                ),
                Tool(
                    name="docs_create_list",
                    description="Create a bulleted or numbered list in a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start character index where list begins (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End character index where list ends (exclusive)"
                            },
                            "listType": {
                                "type": "string",
                                "description": "Type of list: 'BULLET' for bulleted list, 'NUMBERED' for numbered list",
                                "enum": ["BULLET", "NUMBERED"]
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex", "listType"]
                    }
                ),
                Tool(
                    name="docs_set_alignment",
                    description="Set paragraph alignment in a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start character index of paragraph (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End character index of paragraph (exclusive)"
                            },
                            "alignment": {
                                "type": "string",
                                "description": "Text alignment: 'START' (left), 'CENTER', 'END' (right), 'JUSTIFY'",
                                "enum": ["START", "CENTER", "END", "JUSTIFY"]
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex", "alignment"]
                    }
                ),
                Tool(
                    name="docs_apply_named_style",
                    description="Apply a named style to text in a Google Docs document (e.g., 'Heading 1', 'Heading 2', 'Title', 'Normal Text').",
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
                            "style": {
                                "type": "string",
                                "description": "Named style: 'NORMAL_TEXT', 'HEADING_1', 'HEADING_2', 'HEADING_3', 'HEADING_4', 'HEADING_5', 'HEADING_6', 'TITLE', 'SUBTITLE'",
                                "enum": ["NORMAL_TEXT", "HEADING_1", "HEADING_2", "HEADING_3", "HEADING_4", "HEADING_5", "HEADING_6", "TITLE", "SUBTITLE"]
                            }
                        },
                        "required": ["documentId", "startIndex", "endIndex", "style"]
                    }
                ),
                Tool(
                    name="docs_insert_pagebreak",
                    description="Insert a page break at a specific position in a Google Docs document.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "documentId": {
                                "type": "string",
                                "description": "Document ID or URL"
                            },
                            "index": {
                                "type": "integer",
                                "description": "Character index where to insert page break (0-based)"
                            }
                        },
                        "required": ["documentId", "index"]
                    }
                ),
                
                # ========== SHEETS OPERATIONS ==========
                # Reuse existing Sheets tools but adapt for workspace context
                Tool(
                    name="sheets_create_spreadsheet",
                    description="Create a new Google Sheets spreadsheet in the workspace folder.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the spreadsheet"
                            },
                            "sheetNames": {
                                "type": "array",
                                "description": "Names of sheets to create (default: ['Sheet1'])",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["title"]
                    }
                ),
                Tool(
                    name="sheets_read_range",
                    description="Read data from a range of cells in a spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "Spreadsheet ID or URL"
                            },
                            "range": {
                                "type": "string",
                                "description": "A1 notation range (e.g., 'Sheet1!A1:D10')"
                            },
                            "valueRenderOption": {
                                "type": "string",
                                "description": "How values should be rendered: FORMATTED_VALUE, UNFORMATTED_VALUE, or FORMULA",
                                "default": "FORMATTED_VALUE"
                            }
                        },
                        "required": ["spreadsheetId", "range"]
                    }
                ),
                Tool(
                    name="sheets_write_range",
                    description="Write data to a range of cells in a spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "Spreadsheet ID or URL"
                            },
                            "range": {
                                "type": "string",
                                "description": "A1 notation range (e.g., 'Sheet1!A1:D10')"
                            },
                            "values": {
                                "type": "array",
                                "description": "2D array of values (rows of cells)",
                                "items": {
                                    "type": "array",
                                    "items": {}
                                }
                            },
                            "valueInputOption": {
                                "type": "string",
                                "description": "How input should be interpreted: RAW or USER_ENTERED",
                                "default": "USER_ENTERED"
                            }
                        },
                        "required": ["spreadsheetId", "range", "values"]
                    }
                ),
                Tool(
                    name="sheets_append_rows",
                    description="Append rows to the end of a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "Spreadsheet ID or URL"
                            },
                            "range": {
                                "type": "string",
                                "description": "A1 notation range to search for data (e.g., 'Sheet1!A:A')"
                            },
                            "values": {
                                "type": "array",
                                "description": "2D array of values to append",
                                "items": {
                                    "type": "array",
                                    "items": {}
                                }
                            },
                            "valueInputOption": {
                                "type": "string",
                                "description": "How input should be interpreted: RAW or USER_ENTERED",
                                "default": "USER_ENTERED"
                            }
                        },
                        "required": ["spreadsheetId", "range", "values"]
                    }
                ),
                Tool(
                    name="sheets_get_info",
                    description="Get metadata about a spreadsheet (sheets, properties, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "Spreadsheet ID or URL"
                            }
                        },
                        "required": ["spreadsheetId"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                # ========== DRIVE OPERATIONS ==========
                if name == "workspace_list_files":
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    query_parts = [f"'{folder_id}' in parents", "trashed=false"]
                    
                    # Handle fileType filter
                    file_type = arguments.get("fileType", "all")
                    if file_type == "docs":
                        query_parts.append("mimeType='application/vnd.google-apps.document'")
                    elif file_type == "sheets":
                        query_parts.append("mimeType='application/vnd.google-apps.spreadsheet'")
                    elif file_type == "folders":
                        query_parts.append("mimeType='application/vnd.google-apps.folder'")
                    
                    # mimeType parameter takes precedence if provided
                    mime_type = arguments.get("mimeType")
                    if mime_type:
                        query_parts.append(f"mimeType='{mime_type}'")
                    
                    search_query = arguments.get("query")
                    if search_query:
                        query_parts.append(f"name contains '{search_query}'")
                    
                    query = " and ".join(query_parts)
                    max_results = min(arguments.get("maxResults", 50), 100)
                    
                    results = drive_service.files().list(
                        q=query,
                        pageSize=max_results,
                        fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink, size)",
                        orderBy="modifiedTime desc"
                    ).execute()
                    
                    files = results.get('files', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "files": [
                                {
                                    "id": f.get('id'),
                                    "name": f.get('name'),
                                    "mimeType": f.get('mimeType'),
                                    "createdTime": f.get('createdTime'),
                                    "modifiedTime": f.get('modifiedTime'),
                                    "url": f.get('webViewLink'),
                                    "size": f.get('size')
                                }
                                for f in files
                            ],
                            "count": len(files)
                        }, indent=2)
                    )]
                
                elif name == "workspace_get_file_info":
                    drive_service = self._get_drive_service()
                    file_id = self._extract_file_id(arguments.get("fileId"))
                    
                    file_info = drive_service.files().get(
                        fileId=file_id,
                        fields="id, name, mimeType, createdTime, modifiedTime, webViewLink, size, parents, owners, shared"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps(file_info, indent=2, default=str)
                    )]
                
                elif name == "workspace_create_folder":
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    folder_name = arguments.get("name")
                    folder_metadata = {
                        "name": folder_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [folder_id]
                    }
                    
                    folder = drive_service.files().create(
                        body=folder_metadata,
                        fields="id, name, webViewLink"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "id": folder.get('id'),
                            "name": folder.get('name'),
                            "url": folder.get('webViewLink')
                        }, indent=2)
                    )]
                
                elif name == "workspace_delete_file":
                    drive_service = self._get_drive_service()
                    file_id = self._extract_file_id(arguments.get("fileId"))
                    
                    drive_service.files().delete(fileId=file_id).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({"status": "deleted", "fileId": file_id}, indent=2)
                    )]
                
                elif name == "workspace_move_file":
                    drive_service = self._get_drive_service()
                    file_id = self._extract_file_id(arguments.get("fileId"))
                    target_folder_id = self._extract_file_id(arguments.get("targetFolderId"))
                    
                    # Get current parents
                    file_info = drive_service.files().get(
                        fileId=file_id,
                        fields="parents"
                    ).execute()
                    
                    previous_parents = ",".join(file_info.get('parents', []))
                    
                    # Move file
                    drive_service.files().update(
                        fileId=file_id,
                        addParents=target_folder_id,
                        removeParents=previous_parents,
                        fields="id, parents"
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({"status": "moved", "fileId": file_id, "newParentId": target_folder_id}, indent=2)
                    )]
                
                elif name == "workspace_search_files":
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    search_query = arguments.get("query")
                    query_parts = [f"'{folder_id}' in parents", "trashed=false", search_query]
                    
                    mime_type = arguments.get("mimeType")
                    if mime_type:
                        query_parts.append(f"mimeType='{mime_type}'")
                    
                    query = " and ".join(query_parts)
                    max_results = min(arguments.get("maxResults", 20), 100)
                    
                    results = drive_service.files().list(
                        q=query,
                        pageSize=max_results,
                        fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink)",
                        orderBy="modifiedTime desc"
                    ).execute()
                    
                    files = results.get('files', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "query": search_query,
                            "files": [
                                {
                                    "id": f.get('id'),
                                    "name": f.get('name'),
                                    "mimeType": f.get('mimeType'),
                                    "createdTime": f.get('createdTime'),
                                    "modifiedTime": f.get('modifiedTime'),
                                    "url": f.get('webViewLink')
                                }
                                for f in files
                            ],
                            "count": len(files)
                        }, indent=2)
                    )]
                
                elif name == "workspace_get_folder_path":
                    folder_id = self._get_workspace_folder_id()
                    config = self._load_config()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured",
                                "folderId": None,
                                "folderName": None
                            }, indent=2)
                        )]
                    
                    # Get folder name from Drive
                    try:
                        drive_service = self._get_drive_service()
                        folder_info = drive_service.files().get(
                            fileId=folder_id,
                            fields="id, name, webViewLink"
                        ).execute()
                        
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "folderId": folder_id,
                                "folderName": folder_info.get('name'),
                                "url": folder_info.get('webViewLink')
                            }, indent=2)
                        )]
                    except Exception as e:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "folderId": folder_id,
                                "folderName": config.get("folder_name"),
                                "error": str(e)
                            }, indent=2)
                        )]
                
                elif name == "workspace_find_file_by_name":
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    file_name = arguments.get("fileName")
                    exact_match = arguments.get("exactMatch", False)
                    file_type = arguments.get("fileType", "all")
                    
                    query_parts = [f"'{folder_id}' in parents", "trashed=false"]
                    
                    # Build name query
                    if exact_match:
                        query_parts.append(f"name='{file_name}'")
                    else:
                        query_parts.append(f"name contains '{file_name}'")
                    
                    # Add file type filter
                    if file_type == "docs":
                        query_parts.append("mimeType='application/vnd.google-apps.document'")
                    elif file_type == "sheets":
                        query_parts.append("mimeType='application/vnd.google-apps.spreadsheet'")
                    elif file_type == "folders":
                        query_parts.append("mimeType='application/vnd.google-apps.folder'")
                    
                    query = " and ".join(query_parts)
                    
                    results = drive_service.files().list(
                        q=query,
                        pageSize=10,
                        fields="files(id, name, mimeType, webViewLink)",
                        orderBy="modifiedTime desc"
                    ).execute()
                    
                    files = results.get('files', [])
                    
                    if not files:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "found": False,
                                "fileName": file_name,
                                "message": f"No file found with name '{file_name}'"
                            }, indent=2)
                        )]
                    
                    # Return first match
                    file = files[0]
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "found": True,
                            "fileName": file.get('name'),
                            "fileId": file.get('id'),
                            "mimeType": file.get('mimeType'),
                            "url": file.get('webViewLink'),
                            "matches": len(files)
                        }, indent=2)
                    )]
                
                elif name == "workspace_get_folder_contents":
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    if not folder_id:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "error": "Workspace folder not configured. Please set workspace folder first."
                            }, indent=2)
                        )]
                    
                    max_results = min(arguments.get("maxResults", 50), 100)
                    
                    # Get all files
                    query = f"'{folder_id}' in parents and trashed=false"
                    results = drive_service.files().list(
                        q=query,
                        pageSize=max_results,
                        fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink)",
                        orderBy="modifiedTime desc"
                    ).execute()
                    
                    all_files = results.get('files', [])
                    
                    # Group by type
                    documents = []
                    spreadsheets = []
                    folders = []
                    other = []
                    
                    for f in all_files:
                        mime_type = f.get('mimeType', '')
                        file_info = {
                            "id": f.get('id'),
                            "name": f.get('name'),
                            "mimeType": mime_type,
                            "createdTime": f.get('createdTime'),
                            "modifiedTime": f.get('modifiedTime'),
                            "url": f.get('webViewLink')
                        }
                        
                        if mime_type == 'application/vnd.google-apps.document':
                            documents.append(file_info)
                        elif mime_type == 'application/vnd.google-apps.spreadsheet':
                            spreadsheets.append(file_info)
                        elif mime_type == 'application/vnd.google-apps.folder':
                            folders.append(file_info)
                        else:
                            other.append(file_info)
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "documents": documents,
                            "spreadsheets": spreadsheets,
                            "folders": folders,
                            "other": other,
                            "total": len(all_files),
                            "counts": {
                                "documents": len(documents),
                                "spreadsheets": len(spreadsheets),
                                "folders": len(folders),
                                "other": len(other)
                            }
                        }, indent=2)
                    )]
                
                # ========== DOCS OPERATIONS ==========
                elif name == "docs_create":
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
                
                elif name == "docs_format_heading":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    heading_level = arguments.get("headingLevel")
                    
                    # Map heading level to named style
                    style_map = {
                        1: "HEADING_1",
                        2: "HEADING_2",
                        3: "HEADING_3",
                        4: "HEADING_4",
                        5: "HEADING_5",
                        6: "HEADING_6"
                    }
                    named_style = style_map.get(heading_level, "HEADING_1")
                    
                    requests = [{
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "paragraphStyle": {
                                "namedStyleType": named_style
                            },
                            "fields": "namedStyleType"
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "heading_formatted",
                            "documentId": document_id,
                            "headingLevel": heading_level
                        }, indent=2)
                    )]
                
                elif name == "docs_create_list":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    list_type = arguments.get("listType")
                    
                    requests = [{
                        "createParagraphBullets": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE" if list_type == "BULLET" else "NUMBERED_DECIMAL_ALPHA_ROMAN"
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "list_created",
                            "documentId": document_id,
                            "listType": list_type
                        }, indent=2)
                    )]
                
                elif name == "docs_set_alignment":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    alignment = arguments.get("alignment")
                    
                    requests = [{
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "paragraphStyle": {
                                "alignment": alignment
                            },
                            "fields": "alignment"
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "alignment_set",
                            "documentId": document_id,
                            "alignment": alignment
                        }, indent=2)
                    )]
                
                elif name == "docs_apply_named_style":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    start_index = arguments.get("startIndex")
                    end_index = arguments.get("endIndex")
                    style = arguments.get("style")
                    
                    requests = [{
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index
                            },
                            "paragraphStyle": {
                                "namedStyleType": style
                            },
                            "fields": "namedStyleType"
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "style_applied",
                            "documentId": document_id,
                            "style": style
                        }, indent=2)
                    )]
                
                elif name == "docs_insert_pagebreak":
                    docs_service = self._get_docs_service()
                    document_id = self._extract_file_id(arguments.get("documentId"))
                    index = arguments.get("index")
                    
                    requests = [{
                        "insertPageBreak": {
                            "location": {
                                "index": index
                            }
                        }
                    }]
                    
                    docs_service.documents().batchUpdate(
                        documentId=document_id,
                        body={"requests": requests}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "pagebreak_inserted",
                            "documentId": document_id,
                            "index": index
                        }, indent=2)
                    )]
                
                # ========== SHEETS OPERATIONS ==========
                elif name == "sheets_create_spreadsheet":
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:979", "message": "sheets_create_spreadsheet entry", "data": {"title": arguments.get("title"), "sheetNames": arguments.get("sheetNames")}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
                    except: pass
                    # #endregion
                    sheets_service = self._get_sheets_service()
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:984", "message": "folder_id retrieved", "data": {"folder_id": folder_id, "is_none": folder_id is None}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}) + "\n")
                    except: pass
                    # #endregion
                    
                    title = arguments.get("title")
                    sheet_names = arguments.get("sheetNames", ["Sheet1"])
                    
                    spreadsheet_body = {
                        "properties": {"title": title},
                        "sheets": [
                            {"properties": {"title": name}}
                            for name in sheet_names
                        ]
                    }
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:996", "message": "before spreadsheet.create", "data": {"title": title}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
                    except: pass
                    # #endregion
                    spreadsheet = sheets_service.spreadsheets().create(
                        body=spreadsheet_body
                    ).execute()
                    
                    spreadsheet_id = spreadsheet.get('spreadsheetId')
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:1001", "message": "spreadsheet created", "data": {"spreadsheet_id": spreadsheet_id, "folder_id": folder_id}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
                    except: pass
                    # #endregion
                    
                    # Move to workspace folder
                    if folder_id:
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                import json as json_lib
                                f.write(json_lib.dumps({"location": "google_workspace_server.py:1006", "message": "before move to folder", "data": {"spreadsheet_id": spreadsheet_id, "folder_id": folder_id}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
                        except: pass
                        # #endregion
                        try:
                            file_info = drive_service.files().get(
                                fileId=spreadsheet_id,
                                fields="parents"
                            ).execute()
                            previous_parents = ",".join(file_info.get('parents', []))
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    import json as json_lib
                                    f.write(json_lib.dumps({"location": "google_workspace_server.py:1011", "message": "before drive.files().update", "data": {"previous_parents": previous_parents, "target_folder_id": folder_id}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
                            except: pass
                            # #endregion
                            drive_service.files().update(
                                fileId=spreadsheet_id,
                                addParents=folder_id,
                                removeParents=previous_parents,
                                fields="id, parents"
                            ).execute()
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    import json as json_lib
                                    f.write(json_lib.dumps({"location": "google_workspace_server.py:1018", "message": "after drive.files().update", "data": {"spreadsheet_id": spreadsheet_id}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
                            except: pass
                            # #endregion
                        except Exception as move_error:
                            # #region agent log
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                    import json as json_lib
                                    f.write(json_lib.dumps({"location": "google_workspace_server.py:1020", "message": "error moving to folder", "data": {"error": str(move_error), "error_type": type(move_error).__name__}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "F"}) + "\n")
                            except: pass
                            # #endregion
                            raise
                    else:
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                import json as json_lib
                                f.write(json_lib.dumps({"location": "google_workspace_server.py:1024", "message": "folder_id is None, skipping move", "data": {}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}) + "\n")
                        except: pass
                        # #endregion
                    
                    # Get spreadsheet URL
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:1029", "message": "before get webViewLink", "data": {"spreadsheet_id": spreadsheet_id}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
                    except: pass
                    # #endregion
                    sheet_file = drive_service.files().get(
                        fileId=spreadsheet_id,
                        fields="webViewLink"
                    ).execute()
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            import json as json_lib
                            f.write(json_lib.dumps({"location": "google_workspace_server.py:1036", "message": "sheets_create_spreadsheet success", "data": {"spreadsheet_id": spreadsheet_id, "url": sheet_file.get('webViewLink')}, "timestamp": __import__('time').time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "H"}) + "\n")
                    except: pass
                    # #endregion
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet_id,
                            "title": title,
                            "url": sheet_file.get('webViewLink')
                        }, indent=2)
                    )]
                
                elif name == "sheets_read_range":
                    sheets_service = self._get_sheets_service()
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_name = arguments.get("range")
                    value_render_option = arguments.get("valueRenderOption", "FORMATTED_VALUE")
                    
                    result = sheets_service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueRenderOption=value_render_option
                    ).execute()
                    
                    values = result.get('values', [])
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet_id,
                            "range": range_name,
                            "values": values
                        }, indent=2)
                    )]
                
                elif name == "sheets_write_range":
                    sheets_service = self._get_sheets_service()
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_name = arguments.get("range")
                    values = arguments.get("values")
                    value_input_option = arguments.get("valueInputOption", "USER_ENTERED")
                    
                    body = {
                        "values": values
                    }
                    
                    result = sheets_service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueInputOption=value_input_option,
                        body=body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet_id,
                            "updatedCells": result.get('updatedCells'),
                            "updatedRows": result.get('updatedRows'),
                            "updatedColumns": result.get('updatedColumns'),
                            "updatedRange": result.get('updatedRange')
                        }, indent=2)
                    )]
                
                elif name == "sheets_append_rows":
                    sheets_service = self._get_sheets_service()
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_name = arguments.get("range")
                    values = arguments.get("values")
                    value_input_option = arguments.get("valueInputOption", "USER_ENTERED")
                    
                    body = {
                        "values": values
                    }
                    
                    result = sheets_service.spreadsheets().values().append(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueInputOption=value_input_option,
                        body=body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet_id,
                            "updatedCells": result.get('updates', {}).get('updatedCells'),
                            "updatedRows": result.get('updates', {}).get('updatedRows'),
                            "updatedColumns": result.get('updates', {}).get('updatedColumns'),
                            "updatedRange": result.get('updates', {}).get('updatedRange')
                        }, indent=2)
                    )]
                
                elif name == "sheets_get_info":
                    sheets_service = self._get_sheets_service()
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    
                    spreadsheet = sheets_service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id
                    ).execute()
                    
                    sheets_info = [
                        {
                            "sheetId": sheet['properties']['sheetId'],
                            "title": sheet['properties']['title'],
                            "index": sheet['properties']['index'],
                            "rowCount": sheet['properties']['gridProperties']['rowCount'],
                            "columnCount": sheet['properties']['gridProperties']['columnCount']
                        }
                        for sheet in spreadsheet.get('sheets', [])
                    ]
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet.get('spreadsheetId'),
                            "title": spreadsheet.get('properties', {}).get('title'),
                            "sheets": sheets_info
                        }, indent=2)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            
            except HttpError as e:
                error_msg = f"Google API error: {e.content.decode() if e.content else str(e)}"
                logger.error(error_msg)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2)
                )]
            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2)
                )]
    
    def _extract_text_from_docs_content(self, content: List[Dict]) -> str:
        """Extract plain text from Google Docs content structure."""
        text_parts = []
        
        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                elements = paragraph.get('elements', [])
                for elem in elements:
                    if 'textRun' in elem:
                        text_parts.append(elem['textRun'].get('content', ''))
            elif 'table' in element:
                # Handle tables - extract cell text
                table = element['table']
                for row in table.get('tableRows', []):
                    row_texts = []
                    for cell in row.get('tableCells', []):
                        cell_content = cell.get('content', [])
                        cell_text = self._extract_text_from_docs_content(cell_content)
                        row_texts.append(cell_text.strip())
                    text_parts.append("\t".join(row_texts))
                text_parts.append("\n")
            elif 'sectionBreak' in element:
                text_parts.append("\n\n")
        
        return "".join(text_parts)
    
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
    
    parser = argparse.ArgumentParser(description="Google Workspace MCP Server")
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
        help="Path to workspace configuration file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = GoogleWorkspaceMCPServer(
        Path(args.token_path),
        Path(args.config_path) if args.config_path else None
    )
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

