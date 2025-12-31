"""
Google Sheets MCP Server.
Provides MCP tools for Google Sheets operations via OAuth2.
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

# Sheets API scopes
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleSheetsMCPServer:
    """MCP Server for Google Sheets operations."""
    
    def __init__(self, token_path: Path):
        """
        Initialize Google Sheets MCP Server.
        
        Args:
            token_path: Path to OAuth token file
        """
        self.token_path = Path(token_path)
        self._sheets_service = None
        self._drive_service = None
        self.server = Server("google-sheets-mcp")
        self._setup_tools()
    
    def _get_sheets_service(self):
        """Get or create Google Sheets API service."""
        if self._sheets_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SHEETS_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self._sheets_service = build('sheets', 'v4', credentials=creds)
        
        return self._sheets_service
    
    def _get_drive_service(self):
        """Get or create Google Drive API service for spreadsheet creation."""
        if self._drive_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SHEETS_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self._drive_service = build('drive', 'v3', credentials=creds)
        
        return self._drive_service
    
    @staticmethod
    def _extract_spreadsheet_id(spreadsheet_id_or_url: str) -> str:
        """Extract spreadsheet ID from URL or return as-is if already an ID."""
        # Pattern for Google Sheets URLs
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'docs\.google\.com/spreadsheets.*[?&]id=([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, spreadsheet_id_or_url)
            if match:
                return match.group(1)
        
        # If no pattern matched, assume it's already an ID
        return spreadsheet_id_or_url
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="sheets_list_spreadsheets",
                    description="List recent spreadsheets accessible to the user",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 10)",
                                "default": 10
                            }
                        }
                    }
                ),
                Tool(
                    name="sheets_get_spreadsheet_info",
                    description="Get metadata about a spreadsheet (sheets, properties, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            }
                        },
                        "required": ["spreadsheetId"]
                    }
                ),
                Tool(
                    name="sheets_create_spreadsheet",
                    description="Create a new Google Spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the new spreadsheet"
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
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "range": {
                                "type": "string",
                                "description": "The A1 notation range (e.g., 'Sheet1!A1:D10', 'A1:B5')"
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
                    name="sheets_read_multiple_ranges",
                    description="Read data from multiple ranges in a spreadsheet at once",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "ranges": {
                                "type": "array",
                                "description": "List of A1 notation ranges",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["spreadsheetId", "ranges"]
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
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "range": {
                                "type": "string",
                                "description": "The A1 notation range (e.g., 'Sheet1!A1:D10')"
                            },
                            "values": {
                                "type": "array",
                                "description": "2D array of values to write (rows of cells)",
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
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "range": {
                                "type": "string",
                                "description": "The A1 notation of the range to search for data (e.g., 'Sheet1!A:A')"
                            },
                            "values": {
                                "type": "array",
                                "description": "2D array of values to append (rows of cells)",
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
                    name="sheets_clear_range",
                    description="Clear all values from a range of cells",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "range": {
                                "type": "string",
                                "description": "The A1 notation range to clear"
                            }
                        },
                        "required": ["spreadsheetId", "range"]
                    }
                ),
                Tool(
                    name="sheets_add_sheet",
                    description="Add a new sheet (tab) to an existing spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetTitle": {
                                "type": "string",
                                "description": "Title of the new sheet"
                            },
                            "rowCount": {
                                "type": "integer",
                                "description": "Number of rows (default: 1000)",
                                "default": 1000
                            },
                            "columnCount": {
                                "type": "integer",
                                "description": "Number of columns (default: 26)",
                                "default": 26
                            }
                        },
                        "required": ["spreadsheetId", "sheetTitle"]
                    }
                ),
                Tool(
                    name="sheets_delete_sheet",
                    description="Delete a sheet (tab) from a spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet to delete (from get_spreadsheet_info)"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId"]
                    }
                ),
                Tool(
                    name="sheets_rename_sheet",
                    description="Rename a sheet (tab) in a spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet to rename"
                            },
                            "newTitle": {
                                "type": "string",
                                "description": "New title for the sheet"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "newTitle"]
                    }
                ),
                Tool(
                    name="sheets_copy_sheet",
                    description="Copy a sheet to the same or different spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sourceSpreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the source spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet to copy"
                            },
                            "destinationSpreadsheetId": {
                                "type": "string",
                                "description": "The ID of the destination spreadsheet (optional, copies to same spreadsheet if not provided)"
                            }
                        },
                        "required": ["sourceSpreadsheetId", "sheetId"]
                    }
                ),
                Tool(
                    name="sheets_search",
                    description="Search for a value in a spreadsheet and return matching cells",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "searchValue": {
                                "type": "string",
                                "description": "Value to search for"
                            },
                            "range": {
                                "type": "string",
                                "description": "Optional range to search in (default: all sheets)"
                            },
                            "caseSensitive": {
                                "type": "boolean",
                                "description": "Whether search should be case sensitive",
                                "default": False
                            }
                        },
                        "required": ["spreadsheetId", "searchValue"]
                    }
                ),
                Tool(
                    name="sheets_format_cells",
                    description="Format cells (bold, italic, colors, borders, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startRowIndex": {
                                "type": "integer",
                                "description": "Start row index (0-based)"
                            },
                            "endRowIndex": {
                                "type": "integer",
                                "description": "End row index (exclusive)"
                            },
                            "startColumnIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endColumnIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            },
                            "bold": {
                                "type": "boolean",
                                "description": "Make text bold"
                            },
                            "italic": {
                                "type": "boolean",
                                "description": "Make text italic"
                            },
                            "backgroundColor": {
                                "type": "object",
                                "description": "Background color as {red, green, blue, alpha} (0-1)",
                                "properties": {
                                    "red": {"type": "number"},
                                    "green": {"type": "number"},
                                    "blue": {"type": "number"},
                                    "alpha": {"type": "number"}
                                }
                            },
                            "textColor": {
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
                        "required": ["spreadsheetId", "sheetId", "startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"]
                    }
                ),
                Tool(
                    name="sheets_auto_resize_columns",
                    description="Auto-resize columns to fit content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startColumnIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endColumnIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startColumnIndex", "endColumnIndex"]
                    }
                ),
                Tool(
                    name="sheets_insert_rows",
                    description="Insert empty rows at a specified position",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Row index where to insert (0-based)"
                            },
                            "numRows": {
                                "type": "integer",
                                "description": "Number of rows to insert",
                                "default": 1
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startIndex"]
                    }
                ),
                Tool(
                    name="sheets_delete_rows",
                    description="Delete rows from a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start row index (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End row index (exclusive)"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="sheets_insert_columns",
                    description="Insert empty columns at a specified position",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Column index where to insert (0-based)"
                            },
                            "numColumns": {
                                "type": "integer",
                                "description": "Number of columns to insert",
                                "default": 1
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startIndex"]
                    }
                ),
                Tool(
                    name="sheets_delete_columns",
                    description="Delete columns from a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startIndex", "endIndex"]
                    }
                ),
                Tool(
                    name="sheets_sort_range",
                    description="Sort data in a range by one or more columns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startRowIndex": {
                                "type": "integer",
                                "description": "Start row index (0-based)"
                            },
                            "endRowIndex": {
                                "type": "integer",
                                "description": "End row index (exclusive)"
                            },
                            "startColumnIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endColumnIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            },
                            "sortColumnIndex": {
                                "type": "integer",
                                "description": "Column index to sort by (0-based)"
                            },
                            "ascending": {
                                "type": "boolean",
                                "description": "Sort ascending (true) or descending (false)",
                                "default": True
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex", "sortColumnIndex"]
                    }
                ),
                Tool(
                    name="sheets_merge_cells",
                    description="Merge a range of cells",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startRowIndex": {
                                "type": "integer",
                                "description": "Start row index (0-based)"
                            },
                            "endRowIndex": {
                                "type": "integer",
                                "description": "End row index (exclusive)"
                            },
                            "startColumnIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endColumnIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            },
                            "mergeType": {
                                "type": "string",
                                "description": "Type of merge: MERGE_ALL, MERGE_COLUMNS, or MERGE_ROWS",
                                "default": "MERGE_ALL"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"]
                    }
                ),
                Tool(
                    name="sheets_unmerge_cells",
                    description="Unmerge previously merged cells",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheetId": {
                                "type": "string",
                                "description": "The ID or URL of the spreadsheet"
                            },
                            "sheetId": {
                                "type": "integer",
                                "description": "The ID of the sheet"
                            },
                            "startRowIndex": {
                                "type": "integer",
                                "description": "Start row index (0-based)"
                            },
                            "endRowIndex": {
                                "type": "integer",
                                "description": "End row index (exclusive)"
                            },
                            "startColumnIndex": {
                                "type": "integer",
                                "description": "Start column index (0-based)"
                            },
                            "endColumnIndex": {
                                "type": "integer",
                                "description": "End column index (exclusive)"
                            }
                        },
                        "required": ["spreadsheetId", "sheetId", "startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                service = self._get_sheets_service()
                
                if name == "sheets_list_spreadsheets":
                    drive_service = self._get_drive_service()
                    max_results = arguments.get("maxResults", 10)
                    
                    results = drive_service.files().list(
                        q="mimeType='application/vnd.google-apps.spreadsheet'",
                        pageSize=max_results,
                        fields="files(id, name, createdTime, modifiedTime, webViewLink)",
                        orderBy="modifiedTime desc"
                    ).execute()
                    
                    files = results.get('files', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheets": [
                                {
                                    "id": f.get('id'),
                                    "name": f.get('name'),
                                    "createdTime": f.get('createdTime'),
                                    "modifiedTime": f.get('modifiedTime'),
                                    "url": f.get('webViewLink')
                                }
                                for f in files
                            ],
                            "count": len(files)
                        }, indent=2)
                    )]
                
                elif name == "sheets_get_spreadsheet_info":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    
                    spreadsheet = service.spreadsheets().get(
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
                            "locale": spreadsheet.get('properties', {}).get('locale'),
                            "timeZone": spreadsheet.get('properties', {}).get('timeZone'),
                            "url": spreadsheet.get('spreadsheetUrl'),
                            "sheets": sheets_info
                        }, indent=2)
                    )]
                
                elif name == "sheets_create_spreadsheet":
                    title = arguments.get("title")
                    sheet_names = arguments.get("sheetNames", ["Sheet1"])
                    
                    spreadsheet_body = {
                        "properties": {"title": title},
                        "sheets": [
                            {"properties": {"title": name}}
                            for name in sheet_names
                        ]
                    }
                    
                    spreadsheet = service.spreadsheets().create(
                        body=spreadsheet_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "spreadsheetId": spreadsheet.get('spreadsheetId'),
                            "title": spreadsheet.get('properties', {}).get('title'),
                            "url": spreadsheet.get('spreadsheetUrl'),
                            "sheets": [
                                sheet['properties']['title']
                                for sheet in spreadsheet.get('sheets', [])
                            ],
                            "status": "created"
                        }, indent=2)
                    )]
                
                elif name == "sheets_read_range":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_notation = arguments.get("range")
                    value_render_option = arguments.get("valueRenderOption", "FORMATTED_VALUE")
                    
                    # #region agent log
                    import time
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"google_sheets_server.py:sheets_read_range","message":"Reading spreadsheet range","data":{"spreadsheet_id":spreadsheet_id,"range":range_notation,"original_id":arguments.get("spreadsheetId")},"timestamp":int(time.time()*1000)})+'\n')
                    except: pass
                    # #endregion
                    
                    result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=range_notation,
                        valueRenderOption=value_render_option
                    ).execute()
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"google_sheets_server.py:sheets_read_range","message":"Spreadsheet read result","data":{"spreadsheet_id":spreadsheet_id,"range":range_notation,"row_count":len(result.get('values', []))},"timestamp":int(time.time()*1000)})+'\n')
                    except: pass
                    # #endregion
                    
                    values = result.get('values', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "range": result.get('range'),
                            "values": values,
                            "rowCount": len(values),
                            "columnCount": max(len(row) for row in values) if values else 0
                        }, indent=2, default=str)
                    )]
                
                elif name == "sheets_read_multiple_ranges":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    ranges = arguments.get("ranges")
                    
                    result = service.spreadsheets().values().batchGet(
                        spreadsheetId=spreadsheet_id,
                        ranges=ranges
                    ).execute()
                    
                    value_ranges = result.get('valueRanges', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "ranges": [
                                {
                                    "range": vr.get('range'),
                                    "values": vr.get('values', [])
                                }
                                for vr in value_ranges
                            ]
                        }, indent=2, default=str)
                    )]
                
                elif name == "sheets_write_range":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_notation = arguments.get("range")
                    values = arguments.get("values")
                    value_input_option = arguments.get("valueInputOption", "USER_ENTERED")
                    
                    result = service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=range_notation,
                        valueInputOption=value_input_option,
                        body={"values": values}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "updatedRange": result.get('updatedRange'),
                            "updatedRows": result.get('updatedRows'),
                            "updatedColumns": result.get('updatedColumns'),
                            "updatedCells": result.get('updatedCells'),
                            "status": "written"
                        }, indent=2)
                    )]
                
                elif name == "sheets_append_rows":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_notation = arguments.get("range")
                    values = arguments.get("values")
                    value_input_option = arguments.get("valueInputOption", "USER_ENTERED")
                    
                    result = service.spreadsheets().values().append(
                        spreadsheetId=spreadsheet_id,
                        range=range_notation,
                        valueInputOption=value_input_option,
                        insertDataOption="INSERT_ROWS",
                        body={"values": values}
                    ).execute()
                    
                    updates = result.get('updates', {})
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "updatedRange": updates.get('updatedRange'),
                            "updatedRows": updates.get('updatedRows'),
                            "updatedColumns": updates.get('updatedColumns'),
                            "updatedCells": updates.get('updatedCells'),
                            "status": "appended"
                        }, indent=2)
                    )]
                
                elif name == "sheets_clear_range":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    range_notation = arguments.get("range")
                    
                    result = service.spreadsheets().values().clear(
                        spreadsheetId=spreadsheet_id,
                        range=range_notation
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "clearedRange": result.get('clearedRange'),
                            "status": "cleared"
                        }, indent=2)
                    )]
                
                elif name == "sheets_add_sheet":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_title = arguments.get("sheetTitle")
                    row_count = arguments.get("rowCount", 1000)
                    column_count = arguments.get("columnCount", 26)
                    
                    request_body = {
                        "requests": [{
                            "addSheet": {
                                "properties": {
                                    "title": sheet_title,
                                    "gridProperties": {
                                        "rowCount": row_count,
                                        "columnCount": column_count
                                    }
                                }
                            }
                        }]
                    }
                    
                    result = service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    replies = result.get('replies', [{}])
                    new_sheet = replies[0].get('addSheet', {}).get('properties', {})
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "sheetId": new_sheet.get('sheetId'),
                            "title": new_sheet.get('title'),
                            "status": "added"
                        }, indent=2)
                    )]
                
                elif name == "sheets_delete_sheet":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "deleteSheet": {
                                "sheetId": sheet_id
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "sheetId": sheet_id,
                            "status": "deleted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_rename_sheet":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    new_title = arguments.get("newTitle")
                    
                    request_body = {
                        "requests": [{
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": sheet_id,
                                    "title": new_title
                                },
                                "fields": "title"
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "sheetId": sheet_id,
                            "newTitle": new_title,
                            "status": "renamed"
                        }, indent=2)
                    )]
                
                elif name == "sheets_copy_sheet":
                    source_spreadsheet_id = self._extract_spreadsheet_id(arguments.get("sourceSpreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    dest_spreadsheet_id = arguments.get("destinationSpreadsheetId")
                    
                    if dest_spreadsheet_id:
                        dest_spreadsheet_id = self._extract_spreadsheet_id(dest_spreadsheet_id)
                    else:
                        dest_spreadsheet_id = source_spreadsheet_id
                    
                    result = service.spreadsheets().sheets().copyTo(
                        spreadsheetId=source_spreadsheet_id,
                        sheetId=sheet_id,
                        body={"destinationSpreadsheetId": dest_spreadsheet_id}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "newSheetId": result.get('sheetId'),
                            "newTitle": result.get('title'),
                            "destinationSpreadsheetId": dest_spreadsheet_id,
                            "status": "copied"
                        }, indent=2)
                    )]
                
                elif name == "sheets_search":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    search_value = arguments.get("searchValue")
                    range_notation = arguments.get("range")
                    case_sensitive = arguments.get("caseSensitive", False)
                    
                    # Get spreadsheet info to know all sheets
                    spreadsheet = service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id
                    ).execute()
                    
                    matches = []
                    
                    # If no range specified, search all sheets
                    if range_notation:
                        ranges_to_search = [range_notation]
                    else:
                        ranges_to_search = [
                            sheet['properties']['title']
                            for sheet in spreadsheet.get('sheets', [])
                        ]
                    
                    for search_range in ranges_to_search:
                        try:
                            result = service.spreadsheets().values().get(
                                spreadsheetId=spreadsheet_id,
                                range=search_range
                            ).execute()
                            
                            values = result.get('values', [])
                            actual_range = result.get('range', search_range)
                            
                            # Parse the sheet name from the range
                            sheet_name = actual_range.split('!')[0] if '!' in actual_range else search_range
                            
                            for row_idx, row in enumerate(values):
                                for col_idx, cell in enumerate(row):
                                    cell_str = str(cell)
                                    search_str = search_value
                                    
                                    if not case_sensitive:
                                        cell_str = cell_str.lower()
                                        search_str = search_str.lower()
                                    
                                    if search_str in cell_str:
                                        # Convert to A1 notation
                                        col_letter = chr(ord('A') + col_idx) if col_idx < 26 else f"{chr(ord('A') + col_idx // 26 - 1)}{chr(ord('A') + col_idx % 26)}"
                                        cell_ref = f"{sheet_name}!{col_letter}{row_idx + 1}"
                                        matches.append({
                                            "cell": cell_ref,
                                            "value": cell,
                                            "row": row_idx + 1,
                                            "column": col_idx + 1
                                        })
                        except HttpError:
                            continue  # Skip sheets that can't be read
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "searchValue": search_value,
                            "matches": matches,
                            "matchCount": len(matches)
                        }, indent=2, default=str)
                    )]
                
                elif name == "sheets_format_cells":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    cell_format = {}
                    
                    # Build text format
                    text_format = {}
                    if "bold" in arguments:
                        text_format["bold"] = arguments["bold"]
                    if "italic" in arguments:
                        text_format["italic"] = arguments["italic"]
                    if "textColor" in arguments:
                        text_format["foregroundColor"] = arguments["textColor"]
                    
                    if text_format:
                        cell_format["textFormat"] = text_format
                    
                    if "backgroundColor" in arguments:
                        cell_format["backgroundColor"] = arguments["backgroundColor"]
                    
                    fields = []
                    if "textFormat" in cell_format:
                        if "bold" in text_format:
                            fields.append("userEnteredFormat.textFormat.bold")
                        if "italic" in text_format:
                            fields.append("userEnteredFormat.textFormat.italic")
                        if "foregroundColor" in text_format:
                            fields.append("userEnteredFormat.textFormat.foregroundColor")
                    if "backgroundColor" in cell_format:
                        fields.append("userEnteredFormat.backgroundColor")
                    
                    request_body = {
                        "requests": [{
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": arguments.get("startRowIndex"),
                                    "endRowIndex": arguments.get("endRowIndex"),
                                    "startColumnIndex": arguments.get("startColumnIndex"),
                                    "endColumnIndex": arguments.get("endColumnIndex")
                                },
                                "cell": {
                                    "userEnteredFormat": cell_format
                                },
                                "fields": ",".join(fields)
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "formatted",
                            "appliedFormats": list(cell_format.keys())
                        }, indent=2)
                    )]
                
                elif name == "sheets_auto_resize_columns":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "autoResizeDimensions": {
                                "dimensions": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "startIndex": arguments.get("startColumnIndex"),
                                    "endIndex": arguments.get("endColumnIndex")
                                }
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "resized"
                        }, indent=2)
                    )]
                
                elif name == "sheets_insert_rows":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    start_index = arguments.get("startIndex")
                    num_rows = arguments.get("numRows", 1)
                    
                    request_body = {
                        "requests": [{
                            "insertDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": start_index,
                                    "endIndex": start_index + num_rows
                                },
                                "inheritFromBefore": start_index > 0
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "insertedRows": num_rows,
                            "startIndex": start_index,
                            "status": "inserted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_delete_rows":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": arguments.get("startIndex"),
                                    "endIndex": arguments.get("endIndex")
                                }
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "deletedRows": arguments.get("endIndex") - arguments.get("startIndex"),
                            "status": "deleted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_insert_columns":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    start_index = arguments.get("startIndex")
                    num_columns = arguments.get("numColumns", 1)
                    
                    request_body = {
                        "requests": [{
                            "insertDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "startIndex": start_index,
                                    "endIndex": start_index + num_columns
                                },
                                "inheritFromBefore": start_index > 0
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "insertedColumns": num_columns,
                            "startIndex": start_index,
                            "status": "inserted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_delete_columns":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "startIndex": arguments.get("startIndex"),
                                    "endIndex": arguments.get("endIndex")
                                }
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "deletedColumns": arguments.get("endIndex") - arguments.get("startIndex"),
                            "status": "deleted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_sort_range":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "sortRange": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": arguments.get("startRowIndex"),
                                    "endRowIndex": arguments.get("endRowIndex"),
                                    "startColumnIndex": arguments.get("startColumnIndex"),
                                    "endColumnIndex": arguments.get("endColumnIndex")
                                },
                                "sortSpecs": [{
                                    "dimensionIndex": arguments.get("sortColumnIndex"),
                                    "sortOrder": "ASCENDING" if arguments.get("ascending", True) else "DESCENDING"
                                }]
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "sortColumn": arguments.get("sortColumnIndex"),
                            "ascending": arguments.get("ascending", True),
                            "status": "sorted"
                        }, indent=2)
                    )]
                
                elif name == "sheets_merge_cells":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    merge_type = arguments.get("mergeType", "MERGE_ALL")
                    
                    request_body = {
                        "requests": [{
                            "mergeCells": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": arguments.get("startRowIndex"),
                                    "endRowIndex": arguments.get("endRowIndex"),
                                    "startColumnIndex": arguments.get("startColumnIndex"),
                                    "endColumnIndex": arguments.get("endColumnIndex")
                                },
                                "mergeType": merge_type
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "mergeType": merge_type,
                            "status": "merged"
                        }, indent=2)
                    )]
                
                elif name == "sheets_unmerge_cells":
                    spreadsheet_id = self._extract_spreadsheet_id(arguments.get("spreadsheetId"))
                    sheet_id = arguments.get("sheetId")
                    
                    request_body = {
                        "requests": [{
                            "unmergeCells": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": arguments.get("startRowIndex"),
                                    "endRowIndex": arguments.get("endRowIndex"),
                                    "startColumnIndex": arguments.get("startColumnIndex"),
                                    "endColumnIndex": arguments.get("endColumnIndex")
                                }
                            }
                        }]
                    }
                    
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "unmerged"
                        }, indent=2)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            
            except HttpError as e:
                error_msg = f"Google Sheets API error: {e.content.decode() if e.content else str(e)}"
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
    
    parser = argparse.ArgumentParser(description="Google Sheets MCP Server")
    parser.add_argument(
        "--token-path",
        type=str,
        default="config/google_sheets_token.json",
        help="Path to OAuth token file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = GoogleSheetsMCPServer(Path(args.token_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())



