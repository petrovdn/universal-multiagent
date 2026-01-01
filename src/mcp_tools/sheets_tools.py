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
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


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
            
            # Convert sheet_name to range format (e.g., "Sheet1!A:A")
            range_str = f"{sheet_name}!A:A"
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": range_str,
                "values": values
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_append_rows", args, server_name="sheets")
            
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
            result = await mcp_manager.call_tool("sheets_write_range", args, server_name="sheets")
            
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
            logger.info(f"[CreateSpreadsheet] Creating spreadsheet '{title}' with sheets: {sheet_names}")
            args = {"title": title}
            
            if sheet_names:
                args["sheetNames"] = sheet_names
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_create_spreadsheet", args, server_name="sheets")
            
            logger.info(f"[CreateSpreadsheet] Tool call completed, processing result...")
            
            # Handle result - it might be a string (JSON) or dict
            if isinstance(result, str):
                import json
                result = json.loads(result)
            elif isinstance(result, list) and len(result) > 0:
                # MCP returns TextContent list
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    import json
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    import json
                    result = json.loads(first_item['text'])
            
            spreadsheet_id = result.get("spreadsheetId", "unknown")
            url = result.get("url", result.get("spreadsheetUrl", ""))
            sheets = result.get("sheets", [])
            sheet_names = [sheet if isinstance(sheet, str) else sheet.get("title", sheet.get("name", "")) for sheet in sheets] if sheets else ["Sheet1"]
            
            logger.info(f"[CreateSpreadsheet] Successfully created spreadsheet '{title}': ID={spreadsheet_id}, URL={url}, Sheets={sheet_names}")
            # Make sheet names very explicit for LLM - put it at the beginning
            sheets_info = f"Sheet name(s): {', '.join(sheet_names)}. " if sheet_names else ""
            return f"Spreadsheet '{title}' created successfully. {sheets_info}ID: {spreadsheet_id}. URL: {url}"
            
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
            
            # If sheet_name is provided and not in range, prepend it
            if sheet_name and '!' not in validated_range:
                validated_range = f"{sheet_name}!{validated_range}"
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": validated_range
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_read_range", args, server_name="sheets")
            
            # Handle result - it might be a string (JSON) or dict
            if isinstance(result, str):
                import json
                result = json.loads(result)
            elif isinstance(result, list) and len(result) > 0:
                # MCP returns TextContent list
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    import json
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    import json
                    result = json.loads(first_item['text'])
            
            values = result.get("values", [])
            return f"Retrieved {len(values)} row(s) from range '{validated_range}'"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get sheet data: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetSpreadsheetInfoInput(BaseModel):
    """Input schema for get_spreadsheet_info tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID or URL")


class GetSpreadsheetInfoTool(BaseTool):
    """Tool for getting spreadsheet metadata including sheet IDs."""
    
    name: str = "get_spreadsheet_info"
    description: str = """
    Get metadata about a Google Sheets spreadsheet including all sheets with their IDs.
    This is REQUIRED before using format_cells or other formatting tools that need sheet_id.
    
    Input:
    - spreadsheet_id: The ID or URL of the spreadsheet
    
    Returns information about all sheets including:
    - sheetId: Required for formatting operations (use this, not sheet name!)
    - title: Sheet name
    - rowCount, columnCount: Dimensions
    """
    args_schema: type = GetSpreadsheetInfoInput
    
    @retry_on_mcp_error()
    async def _arun(self, spreadsheet_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"spreadsheetId": spreadsheet_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_get_spreadsheet_info", args, server_name="sheets")
            
            # Handle result - it might be a string (JSON) or dict
            if isinstance(result, str):
                import json
                result = json.loads(result)
            elif isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    import json
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    import json
                    result = json.loads(first_item['text'])
            
            spreadsheet_title = result.get("title", "Unknown")
            sheets = result.get("sheets", [])
            sheets_info = "\n".join([
                f"  - Sheet '{s.get('title')}': ID={s.get('sheetId')}, "
                f"Rows={s.get('rowCount')}, Cols={s.get('columnCount')}"
                for s in sheets
            ])
            
            return f"Spreadsheet '{spreadsheet_title}':\n{sheets_info}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get spreadsheet info: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FormatCellsInput(BaseModel):
    """Input schema for format_cells tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_id: int = Field(description="Sheet ID (integer, get from get_spreadsheet_info, NOT sheet name!)")
    start_row_index: int = Field(description="Start row index (0-based, inclusive)")
    end_row_index: int = Field(description="End row index (0-based, exclusive)")
    start_column_index: int = Field(description="Start column index (0-based, inclusive)")
    end_column_index: int = Field(description="End column index (0-based, exclusive)")
    bold: Optional[bool] = Field(default=None, description="Make text bold")
    italic: Optional[bool] = Field(default=None, description="Make text italic")
    background_color: Optional[Dict[str, float]] = Field(
        default=None,
        description="Background color as RGB object: {'red': 0.0-1.0, 'green': 0.0-1.0, 'blue': 0.0-1.0, 'alpha': 0.0-1.0}"
    )
    text_color: Optional[Dict[str, float]] = Field(
        default=None,
        description="Text color as RGB object: {'red': 0.0-1.0, 'green': 0.0-1.0, 'blue': 0.0-1.0, 'alpha': 0.0-1.0}"
    )


class FormatCellsTool(BaseTool):
    """Tool for formatting cells in a spreadsheet."""
    
    name: str = "format_cells"
    description: str = """
    Format cells in Google Sheets (bold, italic, colors, borders).
    
    IMPORTANT: You MUST first call get_spreadsheet_info to get the sheet_id (integer).
    Do NOT use sheet name - use the numeric sheet_id from get_spreadsheet_info!
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - sheet_id: Sheet ID (integer from get_spreadsheet_info, NOT sheet name!)
    - start_row_index, end_row_index: Row range (0-based, end exclusive)
    - start_column_index, end_column_index: Column range (0-based, end exclusive)
    - bold: Optional boolean to make text bold
    - italic: Optional boolean to make text italic
    - background_color: Optional dict with 'red', 'green', 'blue', 'alpha' (0.0-1.0)
    - text_color: Optional dict with 'red', 'green', 'blue', 'alpha' (0.0-1.0)
    
    Example colors:
    - Red background: {'red': 1.0, 'green': 0.0, 'blue': 0.0, 'alpha': 1.0}
    - Blue text: {'red': 0.0, 'green': 0.0, 'blue': 1.0, 'alpha': 1.0}
    - Light gray: {'red': 0.9, 'green': 0.9, 'blue': 0.9, 'alpha': 1.0}
    """
    args_schema: type = FormatCellsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_row_index: int,
        end_row_index: int,
        start_column_index: int,
        end_column_index: int,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        background_color: Optional[Dict[str, float]] = None,
        text_color: Optional[Dict[str, float]] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "spreadsheetId": spreadsheet_id,
                "sheetId": sheet_id,
                "startRowIndex": start_row_index,
                "endRowIndex": end_row_index,
                "startColumnIndex": start_column_index,
                "endColumnIndex": end_column_index
            }
            
            # Add optional formatting parameters
            if bold is not None:
                args["bold"] = bold
            if italic is not None:
                args["italic"] = italic
            if background_color:
                args["backgroundColor"] = background_color
            if text_color:
                args["textColor"] = text_color
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_format_cells", args, server_name="sheets")
            
            # Build description of applied formats
            formats = []
            if bold:
                formats.append("bold")
            if italic:
                formats.append("italic")
            if background_color:
                formats.append("background color")
            if text_color:
                formats.append("text color")
            
            format_desc = ", ".join(formats) if formats else "formatting"
            return f"Successfully applied {format_desc} to cells in range (rows {start_row_index}-{end_row_index-1}, cols {start_column_index}-{end_column_index-1})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to format cells: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class AutoResizeColumnsInput(BaseModel):
    """Input schema for auto_resize_columns tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_id: int = Field(description="Sheet ID (integer from get_spreadsheet_info)")
    start_column_index: int = Field(description="Start column index (0-based)")
    end_column_index: int = Field(description="End column index (exclusive)")


class AutoResizeColumnsTool(BaseTool):
    """Tool for auto-resizing columns to fit content."""
    
    name: str = "auto_resize_columns"
    description: str = """
    Auto-resize columns in Google Sheets to fit their content.
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - sheet_id: Sheet ID (integer from get_spreadsheet_info)
    - start_column_index: Start column index (0-based)
    - end_column_index: End column index (exclusive)
    """
    args_schema: type = AutoResizeColumnsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_column_index: int,
        end_column_index: int
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "spreadsheetId": spreadsheet_id,
                "sheetId": sheet_id,
                "startColumnIndex": start_column_index,
                "endColumnIndex": end_column_index
            }
            
            mcp_manager = get_mcp_manager()
            await mcp_manager.call_tool("sheets_auto_resize_columns", args, server_name="sheets")
            
            return f"Successfully auto-resized columns {start_column_index} to {end_column_index-1}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to auto-resize columns: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class MergeCellsInput(BaseModel):
    """Input schema for merge_cells tool."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_id: int = Field(description="Sheet ID (integer from get_spreadsheet_info)")
    start_row_index: int = Field(description="Start row index (0-based)")
    end_row_index: int = Field(description="End row index (exclusive)")
    start_column_index: int = Field(description="Start column index (0-based)")
    end_column_index: int = Field(description="End column index (exclusive)")
    merge_type: Optional[str] = Field(
        default="MERGE_ALL",
        description="Merge type: MERGE_ALL (default), MERGE_COLUMNS, or MERGE_ROWS"
    )


class MergeCellsTool(BaseTool):
    """Tool for merging cells in a spreadsheet."""
    
    name: str = "merge_cells"
    description: str = """
    Merge a range of cells in Google Sheets.
    
    Input:
    - spreadsheet_id: The ID of the spreadsheet
    - sheet_id: Sheet ID (integer from get_spreadsheet_info)
    - start_row_index, end_row_index: Row range (0-based, end exclusive)
    - start_column_index, end_column_index: Column range (0-based, end exclusive)
    - merge_type: Optional - MERGE_ALL (default), MERGE_COLUMNS, or MERGE_ROWS
    """
    args_schema: type = MergeCellsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_row_index: int,
        end_row_index: int,
        start_column_index: int,
        end_column_index: int,
        merge_type: Optional[str] = "MERGE_ALL"
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "spreadsheetId": spreadsheet_id,
                "sheetId": sheet_id,
                "startRowIndex": start_row_index,
                "endRowIndex": end_row_index,
                "startColumnIndex": start_column_index,
                "endColumnIndex": end_column_index,
                "mergeType": merge_type
            }
            
            mcp_manager = get_mcp_manager()
            await mcp_manager.call_tool("sheets_merge_cells", args, server_name="sheets")
            
            return f"Successfully merged cells in range (rows {start_row_index}-{end_row_index-1}, cols {start_column_index}-{end_column_index-1})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to merge cells: {e}",
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
        GetSpreadsheetInfoTool(),  # Required for getting sheet_id for formatting
        FormatCellsTool(),  # Formatting: bold, italic, colors
        AutoResizeColumnsTool(),  # Auto-resize columns
        MergeCellsTool(),  # Merge cells
    ]

