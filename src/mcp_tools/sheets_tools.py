"""
Google Sheets MCP tool wrappers for LangChain.
Provides validated interfaces to spreadsheet operations.
"""

from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.validators import validate_spreadsheet_range
from src.utils.exceptions import ToolExecutionError, ValidationError
from src.utils.retry import retry_on_mcp_error


class AddRowsInput(BaseModel):
    """Input schema for add_rows tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Sheet name within spreadsheet")
    values: List[List[Any]] = Field(description="Rows of data to add (list of lists)")


class AddRowsTool(BaseTool):
    """Tool for adding rows to a spreadsheet."""
    
    name: str = "add_rows"
    description: str = """
    Add rows of data to a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - sheet_name: Name of the sheet within the spreadsheet
    - values: List of rows, where each row is a list of cell values
    """
    args_schema: type = AddRowsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        values: List[List[Any]]
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not values:
                raise ValidationError("No values provided to add")
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "sheetName": sheet_name,
                "values": values
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("add_rows", args, server_name="sheets")
            
            rows_added = len(values)
            return f"Successfully added {rows_added} row(s) to sheet '{sheet_name}'"
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to add rows: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class UpdateCellsInput(BaseModel):
    """Input schema for update_cells tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    range: str = Field(description="Cell range in A1 notation (e.g., 'A1:B10')")
    values: List[List[Any]] = Field(description="Values to write (list of lists)")


class UpdateCellsTool(BaseTool):
    """Tool for updating cells in a spreadsheet."""
    
    name: str = "update_cells"
    description: str = """
    Update cells in a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - range: Cell range in A1 notation (e.g., 'A1:B10', 'Sheet1!A1:B10')
    - values: Values to write (list of rows, where each row is a list of cell values)
    """
    args_schema: type = UpdateCellsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        range: str,
        values: List[List[Any]]
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # Validate range
            validated_range = validate_spreadsheet_range(range)
            
            if not values:
                raise ValidationError("No values provided to update")
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": validated_range,
                "values": values
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("update_cells", args, server_name="sheets")
            
            return f"Successfully updated cells in range '{validated_range}'"
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to update cells: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateSpreadsheetInput(BaseModel):
    """Input schema for create_spreadsheet tool."""
    
    title: str = Field(description="Spreadsheet title")
    sheet_names: Optional[List[str]] = Field(default=None, description="Initial sheet names")


class CreateSpreadsheetTool(BaseTool):
    """Tool for creating a new spreadsheet."""
    
    name: str = "create_spreadsheet"
    description: str = """
    Create a new Google Sheets spreadsheet.
    
    Input:
    - title: Title of the spreadsheet
    - sheet_names: Optional list of initial sheet names (default: ['Sheet1'])
    """
    args_schema: type = CreateSpreadsheetInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        title: str,
        sheet_names: Optional[List[str]] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            
            if sheet_names:
                args["sheetNames"] = sheet_names
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("create_spreadsheet", args, server_name="sheets")
            
            spreadsheet_id = result.get("spreadsheetId", "unknown")
            url = result.get("url", "")
            
            return f"Spreadsheet '{title}' created successfully. ID: {spreadsheet_id}. URL: {url}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create spreadsheet: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetSheetDataInput(BaseModel):
    """Input schema for get_sheet_data tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    range: str = Field(description="Cell range in A1 notation")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name (if not in range)")


class GetSheetDataTool(BaseTool):
    """Tool for reading data from a spreadsheet."""
    
    name: str = "get_sheet_data"
    description: str = """
    Read data from a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - range: Cell range in A1 notation (e.g., 'A1:B10', 'Sheet1!A1:B10')
    - sheet_name: Optional sheet name (if not included in range)
    """
    args_schema: type = GetSheetDataInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        range: str,
        sheet_name: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            validated_range = validate_spreadsheet_range(range)
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": validated_range
            }
            
            if sheet_name:
                args["sheetName"] = sheet_name
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("get_sheet_data", args, server_name="sheets")
            
            values = result.get("values", [])
            return f"Retrieved {len(values)} row(s) from range '{validated_range}'"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get sheet data: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_sheets_tools() -> List[BaseTool]:
    """
    Get all Sheets tools.
    
    Returns:
        List of Sheets tool instances
    """
    return [
        AddRowsTool(),
        UpdateCellsTool(),
        CreateSpreadsheetTool(),
        GetSheetDataTool(),
    ]

