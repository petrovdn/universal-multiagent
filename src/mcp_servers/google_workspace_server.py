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
                        orderBy="modifiedTime desc",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
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
                
                # ========== SHEETS OPERATIONS ==========
                elif name == "sheets_create_spreadsheet":
                    sheets_service = self._get_sheets_service()
                    drive_service = self._get_drive_service()
                    folder_id = self._get_workspace_folder_id()
                    
                    title = arguments.get("title")
                    sheet_names = arguments.get("sheetNames", ["Sheet1"])
                    
                    spreadsheet_body = {
                        "properties": {"title": title},
                        "sheets": [
                            {"properties": {"title": name}}
                            for name in sheet_names
                        ]
                    }
                    
                    spreadsheet = sheets_service.spreadsheets().create(
                        body=spreadsheet_body
                    ).execute()
                    
                    spreadsheet_id = spreadsheet.get('spreadsheetId')
                    
                    # Move to workspace folder
                    if folder_id:
                        file_info = drive_service.files().get(
                            fileId=spreadsheet_id,
                            fields="parents"
                        ).execute()
                        previous_parents = ",".join(file_info.get('parents', []))
                        drive_service.files().update(
                            fileId=spreadsheet_id,
                            addParents=folder_id,
                            removeParents=previous_parents,
                            fields="id, parents"
                        ).execute()
                    
                    # Get spreadsheet URL
                    sheet_file = drive_service.files().get(
                        fileId=spreadsheet_id,
                        fields="webViewLink"
                    ).execute()
                    
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

