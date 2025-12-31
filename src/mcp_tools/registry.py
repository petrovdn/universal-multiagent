"""
Central registry for all MCP tools.
Provides tool discovery, categorization, and metadata.
"""

from typing import Dict, List, Any, Optional
from enum import Enum

from langchain_core.tools import BaseTool

from src.mcp_tools.gmail_tools import get_gmail_tools
from src.mcp_tools.calendar_tools import get_calendar_tools
from src.mcp_tools.sheets_tools import get_sheets_tools
from src.mcp_tools.workspace_tools import get_workspace_tools
from src.mcp_tools.onec_tools import get_onec_tools


class ToolCategory(Enum):
    """Tool categories."""
    EMAIL = "email"
    CALENDAR = "calendar"
    SHEETS = "sheets"
    WORKSPACE = "workspace"
    ONEC = "onec"
    UTILITY = "utility"


class ToolRegistry:
    """
    Central registry for all available tools.
    Provides tool discovery and metadata.
    """
    
    def __init__(self):
        """Initialize tool registry."""
        self.tools: Dict[str, BaseTool] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        """Initialize all tools from MCP wrappers."""
        # Gmail tools
        for tool in get_gmail_tools():
            self.register_tool(tool, ToolCategory.EMAIL, "gmail")
        
        # Calendar tools
        for tool in get_calendar_tools():
            self.register_tool(tool, ToolCategory.CALENDAR, "calendar")
        
        # Sheets tools
        for tool in get_sheets_tools():
            self.register_tool(tool, ToolCategory.SHEETS, "sheets")
        
        # Workspace tools
        for tool in get_workspace_tools():
            self.register_tool(tool, ToolCategory.WORKSPACE, "google_workspace")
        
        # 1C tools
        for tool in get_onec_tools():
            self.register_tool(tool, ToolCategory.ONEC, "onec")
    
    def register_tool(
        self,
        tool: BaseTool,
        category: ToolCategory,
        server_name: str
    ) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance
            category: Tool category
            server_name: MCP server name
        """
        self.tools[tool.name] = tool
        self.tool_metadata[tool.name] = {
            "name": tool.name,
            "description": tool.description,
            "category": category.value,
            "server": server_name,
            "args_schema": tool.args_schema.schema() if tool.args_schema else None
        }
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """
        Get all tools in a category.
        
        Args:
            category: Tool category
            
        Returns:
            List of tool instances
        """
        return [
            tool for name, tool in self.tools.items()
            if self.tool_metadata[name]["category"] == category.value
        ]
    
    def get_tools_by_server(self, server_name: str) -> List[BaseTool]:
        """
        Get all tools from a specific MCP server.
        
        Args:
            server_name: MCP server name
            
        Returns:
            List of tool instances
        """
        return [
            tool for name, tool in self.tools.items()
            if self.tool_metadata[name]["server"] == server_name
        ]
    
    def get_all_tools(self) -> List[BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            List of all tool instances
        """
        return list(self.tools.values())
    
    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a tool.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool metadata or None if not found
        """
        return self.tool_metadata.get(tool_name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all tools with their metadata.
        
        Returns:
            List of tool metadata dictionaries
        """
        return list(self.tool_metadata.values())


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry.
    
    Returns:
        ToolRegistry instance
    """
    global _tool_registry
    
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    
    return _tool_registry

