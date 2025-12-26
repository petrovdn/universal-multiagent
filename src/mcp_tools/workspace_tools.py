"""
Google Workspace MCP tool wrappers for LangChain.
Provides validated interfaces to Google Drive, Docs, and Sheets operations.
"""

import json
from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError
from src.utils.retry import retry_on_mcp_error


# ========== DRIVE TOOLS ==========

class ListFilesInput(BaseModel):
    """Input schema for list_files tool."""
    
    mime_type: Optional[str] = Field(default=None, description="Filter by MIME type")
    query: Optional[str] = Field(default=None, description="Search query for file names")
    max_results: int = Field(default=50, description="Maximum number of results")


class ListFilesTool(BaseTool):
    """Tool for listing files in the workspace folder."""
    
    name: str = "list_workspace_files"
    description: str = """
    List files in the workspace folder.
    
    Input:
    - mime_type: Optional filter by MIME type (e.g., 'application/vnd.google-apps.document')
    - query: Optional search query for file names
    - max_results: Maximum number of results (default: 50)
    """
    args_schema: type = ListFilesInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        mime_type: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 50
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"maxResults": max_results}
            if mime_type:
                args["mimeType"] = mime_type
            if query:
                args["query"] = query
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_list_files", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            files = result.get("files", [])
            count = result.get("count", len(files))
            
            if count == 0:
                return "No files found in workspace folder."
            
            file_list = "\n".join([
                f"- {f.get('name')} ({f.get('mimeType', 'unknown type')}) - ID: {f.get('id')}"
                for f in files[:20]  # Limit to first 20 for readability
            ])
            
            if count > 20:
                file_list += f"\n... and {count - 20} more files"
            
            return f"Found {count} file(s) in workspace folder:\n{file_list}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to list files: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetFileInfoInput(BaseModel):
    """Input schema for get_file_info tool."""
    
    file_id: str = Field(description="File ID or URL")


class GetFileInfoTool(BaseTool):
    """Tool for getting file information."""
    
    name: str = "get_workspace_file_info"
    description: str = """
    Get detailed information about a file in Google Drive.
    
    Input:
    - file_id: File ID or URL
    """
    args_schema: type = GetFileInfoInput
    
    @retry_on_mcp_error()
    async def _arun(self, file_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"fileId": file_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_get_file_info", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            name = result.get("name", "Unknown")
            mime_type = result.get("mimeType", "unknown")
            modified_time = result.get("modifiedTime", "unknown")
            url = result.get("webViewLink", "")
            
            return f"File: {name}\nType: {mime_type}\nModified: {modified_time}\nURL: {url}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get file info: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class CreateFolderInput(BaseModel):
    """Input schema for create_folder tool."""
    
    name: str = Field(description="Folder name")


class CreateFolderTool(BaseTool):
    """Tool for creating a folder."""
    
    name: str = "create_workspace_folder"
    description: str = """
    Create a new folder in the workspace folder.
    
    Input:
    - name: Name of the folder to create
    """
    args_schema: type = CreateFolderInput
    
    @retry_on_mcp_error()
    async def _arun(self, name: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"name": name}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_create_folder", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            folder_id = result.get("id", "unknown")
            folder_name = result.get("name", name)
            url = result.get("url", "")
            
            return f"Folder '{folder_name}' created successfully. ID: {folder_id}. URL: {url}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create folder: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class DeleteFileInput(BaseModel):
    """Input schema for delete_file tool."""
    
    file_id: str = Field(description="File ID or URL")


class DeleteFileTool(BaseTool):
    """Tool for deleting a file."""
    
    name: str = "delete_workspace_file"
    description: str = """
    Delete a file or folder from Google Drive.
    
    Input:
    - file_id: File ID or URL
    """
    args_schema: type = DeleteFileInput
    
    @retry_on_mcp_error()
    async def _arun(self, file_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"fileId": file_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_delete_file", args, server_name="google_workspace")
            
            return f"File deleted successfully (ID: {file_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to delete file: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class SearchFilesInput(BaseModel):
    """Input schema for search_files tool."""
    
    query: str = Field(description="Search query")
    mime_type: Optional[str] = Field(default=None, description="Filter by MIME type")
    max_results: int = Field(default=20, description="Maximum number of results")


class SearchFilesTool(BaseTool):
    """Tool for searching files."""
    
    name: str = "search_workspace_files"
    description: str = """
    Search for files in the workspace folder.
    
    Input:
    - query: Search query (e.g., 'name contains \"report\"')
    - mime_type: Optional filter by MIME type
    - max_results: Maximum number of results (default: 20)
    """
    args_schema: type = SearchFilesInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        query: str,
        mime_type: Optional[str] = None,
        max_results: int = 20
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"query": query, "maxResults": max_results}
            if mime_type:
                args["mimeType"] = mime_type
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_search_files", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            files = result.get("files", [])
            count = result.get("count", len(files))
            
            if count == 0:
                return f"No files found matching query: {query}"
            
            file_list = "\n".join([
                f"- {f.get('name')} - ID: {f.get('id')}"
                for f in files
            ])
            
            return f"Found {count} file(s) matching '{query}':\n{file_list}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to search files: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


# ========== DOCS TOOLS ==========

class CreateDocumentInput(BaseModel):
    """Input schema for create_document tool."""
    
    title: str = Field(description="Document title")
    initial_text: Optional[str] = Field(default=None, description="Initial text content")


class CreateDocumentTool(BaseTool):
    """Tool for creating a Google Docs document."""
    
    name: str = "create_document"
    description: str = """
    Create a new Google Docs document in the workspace folder.
    
    Input:
    - title: Title of the document
    - initial_text: Optional initial text content
    """
    args_schema: type = CreateDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, title: str, initial_text: Optional[str] = None) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            if initial_text:
                args["initialText"] = initial_text
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_create", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            doc_id = result.get("documentId", "unknown")
            doc_title = result.get("title", title)
            url = result.get("url", "")
            
            return f"Document '{doc_title}' created successfully. ID: {doc_id}. URL: {url}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ReadDocumentInput(BaseModel):
    """Input schema for read_document tool."""
    
    document_id: str = Field(description="Document ID or URL")


class ReadDocumentTool(BaseTool):
    """Tool for reading a Google Docs document."""
    
    name: str = "read_document"
    description: str = """
    Read the full content of a Google Docs document.
    
    Input:
    - document_id: Document ID or URL
    """
    args_schema: type = ReadDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"documentId": document_id}
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_read", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            title = result.get("title", "Unknown")
            content = result.get("content", "")
            
            return f"Document: {title}\n\nContent:\n{content}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to read document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class UpdateDocumentInput(BaseModel):
    """Input schema for update_document tool."""
    
    document_id: str = Field(description="Document ID or URL")
    content: str = Field(description="New content to write")


class UpdateDocumentTool(BaseTool):
    """Tool for updating a Google Docs document."""
    
    name: str = "update_document"
    description: str = """
    Replace all content in a Google Docs document with new text.
    
    Input:
    - document_id: Document ID or URL
    - content: New content to write
    """
    args_schema: type = UpdateDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, content: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "content": content
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_update", args, server_name="google_workspace")
            
            return f"Document updated successfully (ID: {document_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to update document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class AppendToDocumentInput(BaseModel):
    """Input schema for append_to_document tool."""
    
    document_id: str = Field(description="Document ID or URL")
    content: str = Field(description="Text to append")


class AppendToDocumentTool(BaseTool):
    """Tool for appending text to a Google Docs document."""
    
    name: str = "append_to_document"
    description: str = """
    Append text to the end of a Google Docs document.
    
    Input:
    - document_id: Document ID or URL
    - content: Text to append
    """
    args_schema: type = AppendToDocumentInput
    
    @retry_on_mcp_error()
    async def _arun(self, document_id: str, content: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "documentId": document_id,
                "content": content
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("docs_append", args, server_name="google_workspace")
            
            return f"Text appended to document successfully (ID: {document_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to append to document: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


# ========== SHEETS TOOLS ==========

class CreateSpreadsheetInput(BaseModel):
    """Input schema for create_spreadsheet tool."""
    
    title: str = Field(description="Spreadsheet title")
    sheet_names: Optional[List[str]] = Field(default=None, description="Initial sheet names")


class CreateSpreadsheetTool(BaseTool):
    """Tool for creating a Google Sheets spreadsheet."""
    
    name: str = "create_spreadsheet"
    description: str = """
    Create a new Google Sheets spreadsheet in the workspace folder.
    
    Input:
    - title: Title of the spreadsheet
    - sheet_names: Optional list of initial sheet names (default: ['Sheet1'])
    """
    args_schema: type = CreateSpreadsheetInput
    
    @retry_on_mcp_error()
    async def _arun(self, title: str, sheet_names: Optional[List[str]] = None) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"title": title}
            if sheet_names:
                args["sheetNames"] = sheet_names
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_create_spreadsheet", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            spreadsheet_id = result.get("spreadsheetId", "unknown")
            spreadsheet_title = result.get("title", title)
            url = result.get("url", "")
            
            return f"Spreadsheet '{spreadsheet_title}' created successfully. ID: {spreadsheet_id}. URL: {url}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create spreadsheet: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ReadSpreadsheetInput(BaseModel):
    """Input schema for read_spreadsheet tool."""
    
    spreadsheet_id: str = Field(description="Spreadsheet ID or URL")
    range: str = Field(description="Cell range in A1 notation (e.g., 'Sheet1!A1:D10')")


class ReadSpreadsheetTool(BaseTool):
    """Tool for reading data from a spreadsheet."""
    
    name: str = "read_spreadsheet"
    description: str = """
    Read data from a range of cells in a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: Spreadsheet ID or URL
    - range: A1 notation range (e.g., 'Sheet1!A1:D10', 'A1:B5')
    """
    args_schema: type = ReadSpreadsheetInput
    
    @retry_on_mcp_error()
    async def _arun(self, spreadsheet_id: str, range: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": range
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_read_range", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            values = result.get("values", [])
            
            if not values:
                return f"No data found in range '{range}'"
            
            # Format as readable text
            rows_text = []
            for row in values:
                rows_text.append(" | ".join(str(cell) for cell in row))
            
            return f"Data from range '{range}' ({len(values)} row(s)):\n\n" + "\n".join(rows_text)
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to read spreadsheet: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class WriteSpreadsheetInput(BaseModel):
    """Input schema for write_spreadsheet tool."""
    
    spreadsheet_id: str = Field(description="Spreadsheet ID or URL")
    range: str = Field(description="Cell range in A1 notation")
    values: List[List[Any]] = Field(description="2D array of values (rows of cells)")


class WriteSpreadsheetTool(BaseTool):
    """Tool for writing data to a spreadsheet."""
    
    name: str = "write_spreadsheet"
    description: str = """
    Write data to a range of cells in a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: Spreadsheet ID or URL
    - range: A1 notation range (e.g., 'Sheet1!A1:D10')
    - values: 2D array of values (list of rows, where each row is a list of cell values)
    """
    args_schema: type = WriteSpreadsheetInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        range: str,
        values: List[List[Any]]
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not values:
                raise ValueError("No values provided to write")
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": range,
                "values": values
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_write_range", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            updated_cells = result.get("updatedCells", 0)
            updated_rows = result.get("updatedRows", 0)
            
            return f"Successfully wrote data to range '{range}'. Updated {updated_cells} cell(s) in {updated_rows} row(s)."
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to write spreadsheet: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class AppendRowsInput(BaseModel):
    """Input schema for append_rows tool."""
    
    spreadsheet_id: str = Field(description="Spreadsheet ID or URL")
    range: str = Field(description="A1 notation range (e.g., 'Sheet1!A:A')")
    values: List[List[Any]] = Field(description="2D array of values to append")


class AppendRowsTool(BaseTool):
    """Tool for appending rows to a spreadsheet."""
    
    name: str = "append_rows"
    description: str = """
    Append rows to the end of a sheet in a Google Sheets spreadsheet.
    
    Input:
    - spreadsheet_id: Spreadsheet ID or URL
    - range: A1 notation range (e.g., 'Sheet1!A:A')
    - values: 2D array of values to append
    """
    args_schema: type = AppendRowsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        spreadsheet_id: str,
        range: str,
        values: List[List[Any]]
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not values:
                raise ValueError("No values provided to append")
            
            args = {
                "spreadsheetId": spreadsheet_id,
                "range": range,
                "values": values
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("sheets_append_rows", args, server_name="google_workspace")
            
            rows_added = len(values)
            return f"Successfully appended {rows_added} row(s) to sheet"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to append rows: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_workspace_tools() -> List[BaseTool]:
    """
    Get all Google Workspace tools.
    
    Returns:
        List of BaseTool instances for workspace operations
    """
    return [
        # Drive tools
        ListFilesTool(),
        GetFileInfoTool(),
        CreateFolderTool(),
        DeleteFileTool(),
        SearchFilesTool(),
        # Docs tools
        CreateDocumentTool(),
        ReadDocumentTool(),
        UpdateDocumentTool(),
        AppendToDocumentTool(),
        # Sheets tools
        CreateSpreadsheetTool(),
        ReadSpreadsheetTool(),
        WriteSpreadsheetTool(),
        AppendRowsTool(),
    ]

