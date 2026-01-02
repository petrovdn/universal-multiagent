"""
Google Workspace MCP tool wrappers for LangChain.
Provides validated interfaces to Google Drive, Docs, and Sheets operations.
"""

import json
import re
from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError
from src.utils.retry import retry_on_mcp_error
from src.utils.validators import validate_spreadsheet_range


# ========== HELPER FUNCTIONS ==========

async def _try_case_variations_for_list_files(
    query: str,
    mime_type: Optional[str],
    max_results: int
) -> List[Dict[str, Any]]:
    """
    Try searching with multiple case variations and return combined unique results.
    
    Args:
        query: Search query string (simple text, not Drive API format)
        mime_type: Optional MIME type filter
        max_results: Maximum number of results per search
        
    Returns:
        List of unique file dictionaries (deduplicated by ID)
    """
    mcp_manager = get_mcp_manager()
    
    # Generate case variations: original, lowercase, capitalize, uppercase
    variations = [
        query,  # Original
        query.lower(),
        query.capitalize(),
        query.upper()
    ]
    
    # Remove duplicates while preserving order
    seen_variations = set()
    unique_variations = []
    for var in variations:
        if var not in seen_variations:
            seen_variations.add(var)
            unique_variations.append(var)
    
    # Try each variation and collect results
    all_files = {}
    seen_file_ids = set()
    
    for variation in unique_variations:
        try:
            args = {"maxResults": max_results, "query": variation}
            if mime_type:
                args["mimeType"] = mime_type
            
            result = await mcp_manager.call_tool("workspace_list_files", args, server_name="google_workspace")
            
            if isinstance(result, str):
                result = json.loads(result)
            
            # Handle both dict and list results
            if isinstance(result, dict):
                files = result.get("files", [])
            elif isinstance(result, list):
                files = result
            else:
                files = []
            
            # Deduplicate by file ID
            for f in files:
                if isinstance(f, dict):
                    file_id = f.get('id')
                    if file_id and file_id not in seen_file_ids:
                        seen_file_ids.add(file_id)
                        all_files[file_id] = f
        
        except Exception:
            # Continue with next variation if one fails
            continue
    
    return list(all_files.values())


async def _try_case_variations_for_search_files(
    query: str,
    mime_type: Optional[str],
    max_results: int
) -> List[Dict[str, Any]]:
    """
    Try searching with multiple case variations for search_files tool.
    Handles queries that may already be in Drive API format (e.g., 'name contains "term"') or simple text.
    Generates variations for case (тест2 → Тест2, test2) and symbols (тест2 → тест_2, тест-2).
    
    Args:
        query: Search query (may be Drive API format or simple text)
        mime_type: Optional MIME type filter
        max_results: Maximum number of results per search
        
    Returns:
        List of unique file dictionaries (deduplicated by ID)
    """
    mcp_manager = get_mcp_manager()
    
    # Try to extract search term from Drive API query format
    # Pattern: name contains "term" or name contains 'term'
    match = re.search(r'name\s+contains\s+["\'](.+?)["\']', query, re.IGNORECASE)
    
    if match:
        # Extract the term and generate variations
        search_term = match.group(1)
    else:
        # Not in Drive API format - treat as simple text
        search_term = query.strip()
    
    # Generate variations: case and symbol variations
    variations = set()
    
    # Original
    variations.add(search_term)
    
    # Case variations
    variations.add(search_term.lower())
    variations.add(search_term.upper())
    variations.add(search_term.capitalize())
    if search_term:
        # Title case (first letter of each word)
        variations.add(search_term.title())
    
    # Symbol variations (if term contains alphanumeric characters)
    if re.search(r'[a-zA-Zа-яА-Я0-9]', search_term):
        # Try with underscore, hyphen, space
        base_term = re.sub(r'[_\-\s]+', '', search_term)  # Remove existing separators
        if base_term:
            variations.add(f"{base_term[0].upper()}{base_term[1:]}" if len(base_term) > 1 else base_term.upper())
            variations.add(f"{base_term[0].lower()}{base_term[1:]}" if len(base_term) > 1 else base_term.lower())
            # Add separators
            if len(base_term) > 1:
                variations.add(f"{base_term[0]}_{base_term[1:]}")
                variations.add(f"{base_term[0]}-{base_term[1:]}")
                variations.add(f"{base_term[0]} {base_term[1:]}")
                variations.add(f"{base_term[0].upper()}_{base_term[1:]}")
                variations.add(f"{base_term[0].upper()}-{base_term[1:]}")
                variations.add(f"{base_term[0].upper()} {base_term[1:]}")
    
    # Remove duplicates and convert to list
    unique_variations = list(variations)
    
    # Generate queries for each variation (max 10 variations to avoid too many API calls)
    query_variations = [f'name contains "{var}"' for var in unique_variations[:10]]
    
    # Try each variation and collect results
    all_files = {}
    seen_file_ids = set()
    
    # #region agent log
    import time
    try:
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:start","message":"Starting search with variations","data":{"query":query,"query_variations_count":len(query_variations),"query_variations":query_variations[:5],"max_results":max_results},"timestamp":int(time.time()*1000)})+'\n')
    except: pass
    # #endregion
    
    for query_var in query_variations:
        try:
            args = {"query": query_var, "maxResults": max_results}
            if mime_type:
                args["mimeType"] = mime_type
            
            # #region agent log
            import time
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"workspace_tools.py:_try_case_variations_for_search_files","message":"Trying search query variation","data":{"query_variation":query_var,"mime_type":mime_type,"max_results":max_results},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            result = await mcp_manager.call_tool("workspace_search_files", args, server_name="google_workspace")
            
            # #region agent log
            try:
                result_for_log = result
                result_raw_str = str(result)[:500]
                if isinstance(result, list) and len(result) > 0:
                    first_item = result[0]
                    if hasattr(first_item, 'text'):
                        result_for_log = first_item.text
                        result_raw_str = str(first_item.text)[:500]
                    elif isinstance(first_item, dict) and 'text' in first_item:
                        result_for_log = first_item['text']
                        result_raw_str = str(first_item['text'])[:500]
                if isinstance(result_for_log, str):
                    try:
                        result_for_log = json.loads(result_for_log)
                    except:
                        pass
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    # Extract files count from result for logging
                    files_count_in_result = 0
                    file_names_in_result = []
                    if isinstance(result_for_log, dict):
                        files_count_in_result = len(result_for_log.get("files", []))
                        file_names_in_result = [f.get('name') for f in result_for_log.get("files", [])[:5]]
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:result_received","message":"Search result received from MCP","data":{"query_variation":query_var,"result_type":type(result).__name__,"files_in_result":files_count_in_result,"file_names":file_names_in_result,"result_raw_preview":result_raw_str},"timestamp":int(time.time()*1000)})+'\n')
            except Exception as log_err:
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:log_error","message":"Error logging result","data":{"error":str(log_err),"result_type":type(result).__name__},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
            # #endregion
            
            # Parse result - handle TextContent list
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:before_parse","message":"Before parsing result","data":{"result_type":type(result).__name__,"is_list":isinstance(result, list),"list_len":len(result) if isinstance(result, list) else 0},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:after_text_extraction","message":"After text extraction","data":{"result_type":type(result).__name__,"result_preview":str(result)[:200] if isinstance(result, str) else "not_string"},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError as e:
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:json_decode_error","message":"JSON decode error","data":{"error":str(e),"result_preview":result[:500]},"timestamp":int(time.time()*1000)})+'\n')
                    except: pass
                    # #endregion
                    raise
            
            # Handle both dict and list results
            if isinstance(result, dict):
                files = result.get("files", [])
            elif isinstance(result, list):
                files = result
            else:
                files = []
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:files_parsed","message":"Files parsed from result","data":{"query_variation":query_var,"files_count":len(files),"file_names":[f.get('name') for f in files[:5]],"file_ids":[f.get('id') for f in files[:5]]},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            # Deduplicate by file ID and collect ALL files (don't stop after first match)
            for f in files:
                if isinstance(f, dict):
                    file_id = f.get('id')
                    if file_id and file_id not in seen_file_ids:
                        seen_file_ids.add(file_id)
                        all_files[file_id] = f
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"workspace_tools.py:_try_case_variations_for_search_files:after_collection","message":"Files collected after variation","data":{"query_variation":query_var,"files_collected":len(all_files),"file_ids":list(all_files.keys()),"file_names":[all_files[fid].get('name') for fid in list(all_files.keys())[:10]]},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
        
        except Exception as e:
            # #region agent log
            try:
                import traceback
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"workspace_tools.py:_try_case_variations_for_search_files:exception","message":"Exception during search variation","data":{"query_variation":query_var,"error_type":type(e).__name__,"error_message":str(e),"traceback":traceback.format_exc()[:1000]},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            # Continue with next variation if one fails
            continue
    
    # #region agent log
    try:
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H","location":"workspace_tools.py:_try_case_variations_for_search_files:final","message":"Final files collection","data":{"total_files":len(all_files),"file_ids":list(all_files.keys()),"file_names":[all_files[fid].get('name') for fid in list(all_files.keys())[:10]]},"timestamp":int(time.time()*1000)})+'\n')
    except: pass
    # #endregion
    
    result_files = list(all_files.values())
    
    # #region agent log
    try:
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H","location":"workspace_tools.py:_try_case_variations_for_search_files:return","message":"Returning files","data":{"return_count":len(result_files),"return_file_ids":[f.get('id') for f in result_files[:10]],"return_file_names":[f.get('name') for f in result_files[:10]]},"timestamp":int(time.time()*1000)})+'\n')
    except: pass
    # #endregion
    
    return result_files


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
    - query: Optional search query for file names (case-insensitive search)
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
            # If query is provided, use case-insensitive search with variations
            if query:
                files = await _try_case_variations_for_list_files(query, mime_type, max_results)
                count = len(files)
            else:
                # No query - just list all files
                args = {"maxResults": max_results}
                if mime_type:
                    args["mimeType"] = mime_type
                
                mcp_manager = get_mcp_manager()
                result = await mcp_manager.call_tool("workspace_list_files", args, server_name="google_workspace")
                if isinstance(result, str):
                    result = json.loads(result)
                # Handle both dict and list results
                if isinstance(result, dict):
                    files = result.get("files", [])
                    count = result.get("count", len(files))
                elif isinstance(result, list):
                    # If result is a list, treat it as the files list directly
                    files = result
                    count = len(files)
                else:
                    files = []
                    count = 0
            
            if count == 0:
                if query:
                    return f"No files found matching '{query}' in workspace folder."
                else:
                    return "No files found in workspace folder."
            
            file_list = "\n".join([
                f"- {f.get('name') if isinstance(f, dict) else str(f)} ({f.get('mimeType', 'unknown type') if isinstance(f, dict) else 'unknown'}) - ID: {f.get('id') if isinstance(f, dict) else 'N/A'}"
                for f in files[:20]  # Limit to first 20 for readability
            ])
            
            if count > 20:
                file_list += f"\n... and {count - 20} more files"
            
            if query:
                return f"Found {count} file(s) matching '{query}' in workspace folder:\n{file_list}"
            else:
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
            
            # MCP returns list of TextContent, extract first item
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = json.loads(first_item['text'])
                else:
                    result = first_item
            elif isinstance(result, str):
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
            
            # MCP returns list of TextContent, extract first item
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = json.loads(first_item['text'])
                else:
                    result = first_item
            elif isinstance(result, str):
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
    Search for files in the workspace folder (configured in workspace settings).
    
    Input parameters:
    - query: Search query string (simple text, e.g., "Рабочая таблица"). Search is case-insensitive and handles variations.
    - mime_type: Optional filter by MIME type (e.g., "application/vnd.google-apps.spreadsheet")
    - max_results: Maximum number of results (default: 100)
    
    NOTE: folder_id is NOT a parameter - the workspace folder is configured automatically.
    The search is performed in the configured workspace folder only.
    """
    args_schema: type = SearchFilesInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        query: str,
        mime_type: Optional[str] = None,
        max_results: int = 100,  # Increased to find all files with same name
        **kwargs  # Accept extra kwargs to ignore unknown parameters like folder_id
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # #region agent log
            import time
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"workspace_tools.py:SearchFilesTool._arun:entry","message":"SearchFilesTool called","data":{"query":query,"mime_type":mime_type,"max_results":max_results},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            # Use case-insensitive search with variations
            files = await _try_case_variations_for_search_files(query, mime_type, max_results)
            count = len(files)
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"workspace_tools.py:SearchFilesTool._arun:after_search","message":"Search completed","data":{"query":query,"files_count":count,"file_ids":[f.get('id') for f in files[:5]],"file_names":[f.get('name') for f in files[:5]]},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            if count == 0:
                return f"No files found matching query: {query}"
            
            # If multiple files found, return format for user assistance request
            if count > 1:
                options = []
                for i, f in enumerate(files, 1):
                    file_name = f.get('name', 'Unknown')
                    file_id = f.get('id', '')
                    file_type = f.get('mimeType', '')
                    created_time = f.get('createdTime', '')
                    modified_time = f.get('modifiedTime', '')
                    file_type_display = "Google Sheets" if "spreadsheet" in file_type else "Google Document" if "document" in file_type else "File"
                    
                    # Format date for display
                    date_display = ""
                    if created_time:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                            date_display = dt.strftime("%d.%m.%Y %H:%M")
                        except:
                            date_display = created_time[:10] if len(created_time) >= 10 else created_time
                    
                    # Create label with distinguishing attributes (date, ID)
                    if date_display:
                        label = f"{file_name} ({file_type_display}, создан: {date_display}, ID: {file_id[:20]}...)"
                    else:
                        label = f"{file_name} ({file_type_display}, ID: {file_id})"
                    
                    options.append({
                        "id": str(i),
                        "label": label,
                        "description": f"Файл {file_name}, тип: {file_type_display}, создан: {date_display or 'неизвестно'}, изменен: {modified_time[:10] if modified_time else 'неизвестно'}",
                        "data": {
                            "file_id": file_id,
                            "file_name": file_name,
                            "file_type": file_type,
                            "mimeType": file_type,
                            "createdTime": created_time,
                            "modifiedTime": modified_time
                        }
                    })
                
                # Return format for user assistance request (JSON format)
                # Include context text so LLM understands this is a result that requires user assistance
                assistance_json = json.dumps({
                    "🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ": {
                        "question": f"Найдено несколько файлов, соответствующих запросу '{query}'. Какой файл использовать?",
                        "options": options,
                        "context": {
                            "action": "file_search",
                            "query": query
                        }
                    }
                }, ensure_ascii=False, indent=2)
                
                # Return with context so LLM understands this requires user assistance
                # The JSON must be included as-is for parsing
                return f"""Найдено {count} файл(ов), соответствующих запросу '{query}'. Требуется выбор пользователя:

{assistance_json}"""
            
            # Single file found - return it directly
            file = files[0]
            file_name = file.get('name', 'Unknown')
            file_id = file.get('id', '')
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"workspace_tools.py:SearchFilesTool._arun:single_file_found","message":"Single file found, returning result","data":{"query":query,"file_name":file_name,"file_id":file_id,"return_text":f"Found 1 file matching '{query}': {file_name} (ID: {file_id})"},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            return f"Found 1 file matching '{query}': {file_name} (ID: {file_id})"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to search files: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class OpenFileInput(BaseModel):
    """Input schema for open_file tool."""
    
    file_id: str = Field(description="File ID or URL")
    max_rows: int = Field(default=100, description="Maximum rows to read for spreadsheets (0 = all rows)")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name for spreadsheets (default: first sheet)")


class OpenFileTool(BaseTool):
    """Tool for opening and reading a file."""
    
    name: str = "open_file"
    description: str = """
    Open and read a file by ID. Automatically detects file type (document or spreadsheet) and reads its content.
    For spreadsheets, reads the first sheet with up to 100 rows by default.
    
    Input:
    - file_id: File ID or URL
    - max_rows: Maximum rows to read for spreadsheets (default: 100, use 0 for all rows)
    - sheet_name: Optional sheet name for spreadsheets
    """
    args_schema: type = OpenFileInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        file_id: str,
        max_rows: int = 100,
        sheet_name: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # #region agent log
            import time
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"workspace_tools.py:OpenFileTool._arun:entry","message":"OpenFileTool called","data":{"file_id":file_id,"max_rows":max_rows,"sheet_name":sheet_name,"file_id_length":len(file_id) if file_id else 0},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            args = {"fileId": file_id, "maxRows": max_rows}
            if sheet_name:
                args["sheetName"] = sheet_name
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_open_file", args, server_name="google_workspace")
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    result_preview = str(result)[:200] if result else "None"
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"workspace_tools.py:OpenFileTool._arun:after_mcp_call","message":"MCP call completed","data":{"file_id":file_id,"result_type":type(result).__name__,"result_preview":result_preview},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                result = json.loads(result)
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"workspace_tools.py:OpenFileTool._arun:result_parsed","message":"Result parsed from MCP","data":{"file_id":file_id,"result_keys":list(result.keys()) if isinstance(result,dict) else "not_dict","has_error":"error" in result if isinstance(result,dict) else "unknown"},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            file_type = result.get("type", "unknown")
            file_name = result.get("fileName", "Unknown")
            
            if "error" in result:
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"workspace_tools.py:OpenFileTool._arun:error_in_result","message":"Error found in result","data":{"file_id":file_id,"file_name":file_name,"error":result.get("error")},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                return f"Error opening file '{file_name}': {result['error']}"
            
            if file_type == "document":
                content = result.get("content", "")
                title = result.get("title", file_name)
                return f"Document: {title}\n\n{content}"
            
            elif file_type == "spreadsheet":
                values = result.get("values", [])
                sheet_name = result.get("sheetName", "Sheet1")
                row_count = result.get("rowCount", 0)
                col_count = result.get("columnCount", 0)
                
                if not values:
                    return f"Spreadsheet '{file_name}' (sheet '{sheet_name}') is empty"
                
                # Format as readable text
                rows_text = []
                for row in values:
                    rows_text.append(" | ".join(str(cell) for cell in row))
                
                return f"Spreadsheet: {file_name}\nSheet: {sheet_name}\nRows: {row_count}, Columns: {col_count}\n\n" + "\n".join(rows_text)
            
            else:
                return f"File '{file_name}' opened. Type: {file_type}. URL: {result.get('url', 'N/A')}"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to open file: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class FindAndOpenFileInput(BaseModel):
    """Input schema for find_and_open_file tool."""
    
    query: str = Field(description="Search query for file name (case-insensitive)")
    mime_type: Optional[str] = Field(default=None, description="Filter by MIME type")
    max_results: int = Field(default=5, description="Maximum number of files to search")
    max_rows: int = Field(default=100, description="Maximum rows to read for spreadsheets")


class FindAndOpenFileTool(BaseTool):
    """Tool for finding and opening a file."""
    
    name: str = "find_and_open_file"
    description: str = """
    Search for a file by name and automatically open it. Returns file content if found.
    This is a convenient tool that combines search and open operations.
    
    Input:
    - query: Search query for file name (case-insensitive)
    - mime_type: Optional filter by MIME type
    - max_results: Maximum number of files to search (default: 5)
    - max_rows: Maximum rows to read for spreadsheets (default: 100)
    """
    args_schema: type = FindAndOpenFileInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        query: str,
        mime_type: Optional[str] = None,
        max_results: int = 5,
        max_rows: int = 100
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"query": query, "maxResults": max_results, "maxRows": max_rows}
            if mime_type:
                args["mimeType"] = mime_type
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("workspace_find_and_open_file", args, server_name="google_workspace")
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                result = json.loads(result)
            
            if "error" in result and result.get("filesFound", 0) == 0:
                return f"No files found matching query: {query}"
            
            file_type = result.get("type", "unknown")
            file_name = result.get("fileName", "Unknown")
            files_found = result.get("filesFound", 0)
            all_matches = result.get("allMatches", [])
            
            response_parts = []
            
            if files_found > 1:
                response_parts.append(f"Found {files_found} matching file(s). Opening the first one:\n")
                response_parts.append("All matches:")
                for match in all_matches:
                    response_parts.append(f"  - {match.get('name')} (ID: {match.get('id')})")
                response_parts.append("")
            
            if "error" in result:
                return "\n".join(response_parts) + f"Error opening file '{file_name}': {result['error']}"
            
            if file_type == "document":
                content = result.get("content", "")
                title = result.get("title", file_name)
                response_parts.append(f"Document: {title}\n\n{content}")
            
            elif file_type == "spreadsheet":
                values = result.get("values", [])
                sheet_name = result.get("sheetName", "Sheet1")
                row_count = result.get("rowCount", 0)
                col_count = result.get("columnCount", 0)
                
                if not values:
                    response_parts.append(f"Spreadsheet '{file_name}' (sheet '{sheet_name}') is empty")
                else:
                    rows_text = []
                    for row in values:
                        rows_text.append(" | ".join(str(cell) for cell in row))
                    
                    response_parts.append(f"Spreadsheet: {file_name}\nSheet: {sheet_name}\nRows: {row_count}, Columns: {col_count}\n\n" + "\n".join(rows_text))
            
            else:
                response_parts.append(f"File '{file_name}' found. Type: {file_type}. URL: {result.get('url', 'N/A')}")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to find and open file: {e}",
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
            
            # MCP returns list of TextContent, extract first item
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = json.loads(first_item['text'])
                else:
                    result = first_item
            elif isinstance(result, str):
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
            
            # MCP returns list of TextContent, extract first item
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = json.loads(first_item.text)
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = json.loads(first_item['text'])
                else:
                    result = first_item
            elif isinstance(result, str):
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

# Sheets tools removed - use sheets_tools.py instead
# All spreadsheet operations should go through sheets MCP server, not workspace MCP


def get_workspace_tools() -> List[BaseTool]:
    """
    Get Google Workspace tools for file navigation and management.
    
    NOTE: Spreadsheet operations are handled by sheets_tools.py (uses sheets MCP server).
    This module only provides file search, navigation, and document operations.
    
    Returns:
        List of BaseTool instances for workspace operations:
        - Drive: file search, navigation, folder management
        - Docs: document creation and editing
    """
    return [
        # Drive tools - file navigation and management
        ListFilesTool(),
        GetFileInfoTool(),
        CreateFolderTool(),
        DeleteFileTool(),
        SearchFilesTool(),
        OpenFileTool(),
        FindAndOpenFileTool(),
        # Docs tools - document operations
        CreateDocumentTool(),
        ReadDocumentTool(),
        UpdateDocumentTool(),
        AppendToDocumentTool(),
        # NOTE: Sheets tools are in sheets_tools.py (uses sheets MCP server)
    ]

