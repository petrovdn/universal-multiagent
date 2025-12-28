"""
Sheets Agent specialized in Google Sheets operations.
Handles data recording, spreadsheet creation, and data management.
"""

from typing import List, Optional
from langchain_core.tools import BaseTool
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.mcp_tools.sheets_tools import get_sheets_tools
from src.mcp_tools.workspace_tools import get_workspace_sheets_tools
from src.utils.config_loader import get_config


def _is_workspace_integration_enabled() -> bool:
    """
    Check if Google Workspace integration is enabled and authenticated.
    
    Returns:
        True if Workspace token exists and is valid, False otherwise
    """
    try:
        config = get_config()
        workspace_token_path = config.tokens_dir / "google_workspace_token.json"
        
        if not workspace_token_path.exists():
            return False
        
        # Try to validate token
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(workspace_token_path),
                [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/documents",
                    "https://www.googleapis.com/auth/spreadsheets",
                ]
            )
            
            # Check if token is valid (not expired or can be refreshed)
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Save refreshed token
                    with open(workspace_token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    return False
            
            return creds.valid
        except Exception:
            return False
    except Exception:
        return False


SHEETS_AGENT_SYSTEM_PROMPT = """You are an expert spreadsheet assistant specialized in spreadsheet operations.

## Language Requirements
- All your reasoning (thinking process) must be in Russian
- All your responses to users must be in Russian
- Use Russian for all internal reasoning and decision-making

Your capabilities:
- Create structured spreadsheets
- Add and update data in spreadsheets
- Read and analyze existing spreadsheet data
- Format data appropriately (dates, numbers, text)
- Manage multiple sheets within a spreadsheet
- Share spreadsheets with appropriate permissions

Guidelines:
1. Always validate spreadsheet IDs and ranges before operations
2. Use proper A1 notation for ranges:
   - Single cell: "A1"
   - Range: "A1:B10"
   - With sheet name: "Sheet1!A1:B10"
   
3. When creating spreadsheets:
   - Use descriptive titles
   - Create logical sheet names
   - Consider data structure before adding rows
   
4. When adding data:
   - Maintain consistent data types in columns
   - Use appropriate formats (dates, numbers, text)
   - Add headers if creating new structure
   - Preserve existing data structure
   
5. When updating cells:
   - Verify range is correct
   - Ensure data matches expected format
   - Don't overwrite important data without confirmation
   
6. For meeting notes/decisions:
   - Use structured format: Date, Topic, Decision, Action Items, Owner
   - Append new rows rather than overwriting
   - Include timestamps
   
7. When reading data:
   - Provide summaries of large datasets
   - Highlight key information
   - Format output for readability
   
8. Handle errors gracefully:
   - Invalid range → suggest correct format
   - Missing spreadsheet → offer to create one
   - Permission errors → suggest sharing settings

Always be organized, accurate, and maintain data integrity."""


class SheetsAgent(BaseAgent):
    """
    Sheets Agent specialized in spreadsheet operations.
    """
    
    def __init__(self, tools: List[BaseTool] = None, model_name: Optional[str] = None):
        """
        Initialize Sheets Agent.
        
        If Google Workspace integration is enabled, uses Workspace Sheets tools
        (which use the google_workspace MCP server). Otherwise, uses standalone
        Sheets tools (which use the sheets MCP server).
        
        Args:
            tools: Custom tools (uses Sheets tools by default, or Workspace Sheets tools if Workspace is enabled)
            model_name: Model identifier (optional, uses default from config if None)
        """
        if tools is None:
            # Check if Workspace integration is enabled
            if _is_workspace_integration_enabled():
                # Use Workspace Sheets tools (they use google_workspace MCP server)
                tools = get_workspace_sheets_tools()
            else:
                # Use standalone Sheets tools (they use sheets MCP server)
                tools = get_sheets_tools()
        
        super().__init__(
            name="SheetsAgent",
            system_prompt=SHEETS_AGENT_SYSTEM_PROMPT,
            tools=tools,
            model_name=model_name
        )

