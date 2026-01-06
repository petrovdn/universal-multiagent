"""
MCP Tool Provider - wraps existing MCP/LangChain tools as ActionProvider.
Loads all MCP tools and classifies them as READ or WRITE capabilities.
"""

from typing import Dict, List
from langchain_core.tools import BaseTool

from src.core.action_provider import (
    ActionProvider,
    ActionCapability,
    ProviderType,
    CapabilityCategory
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MCPToolProvider(ActionProvider):
    """
    Wraps existing MCP/LangChain tools as ActionProvider.
    Loads all tools from MCP tool modules and classifies them.
    """
    
    def __init__(self):
        """Initialize MCP tool provider and load all tools."""
        self.tools: Dict[str, BaseTool] = {}
        self._load_all_tools()
        logger.info(f"[MCPToolProvider] Loaded {len(self.tools)} MCP tools")
    
    def _load_all_tools(self):
        """Load all MCP tools from tool modules."""
        tools = []
        
        try:
            # Load workspace tools
            from src.mcp_tools.workspace_tools import get_workspace_tools
            tools.extend(get_workspace_tools())
            
            # Load sheets tools
            from src.mcp_tools.sheets_tools import get_sheets_tools
            tools.extend(get_sheets_tools())
            
            # Load gmail tools
            from src.mcp_tools.gmail_tools import get_gmail_tools
            tools.extend(get_gmail_tools())
            
            # Load calendar tools
            from src.mcp_tools.calendar_tools import get_calendar_tools
            tools.extend(get_calendar_tools())
            
            # Load slides tools
            from src.mcp_tools.slides_tools import get_slides_tools
            tools.extend(get_slides_tools())
            
            # Load docs tools
            from src.mcp_tools.docs_tools import get_docs_tools
            tools.extend(get_docs_tools())
            
            # Load 1C tools
            try:
                from src.mcp_tools.onec_tools import get_onec_tools
                tools.extend(get_onec_tools())
            except ImportError:
                logger.debug("[MCPToolProvider] 1C tools not available")
            
            # Load Project Lad tools
            try:
                from src.mcp_tools.projectlad_tools import get_projectlad_tools
                tools.extend(get_projectlad_tools())
            except ImportError:
                logger.debug("[MCPToolProvider] ProjectLad tools not available")
            
            # Load code execution tools
            try:
                from src.mcp_tools.code_execution_tools import get_code_execution_tools
                tools.extend(get_code_execution_tools())
            except ImportError:
                logger.debug("[MCPToolProvider] Code execution tools not available")
            
            # Remove duplicates by name
            seen_names = set()
            for tool in tools:
                if tool.name not in seen_names:
                    seen_names.add(tool.name)
                    self.tools[tool.name] = tool
                else:
                    logger.warning(f"[MCPToolProvider] Duplicate tool name: {tool.name}")
                    
        except Exception as e:
            logger.error(f"[MCPToolProvider] Failed to load some tools: {e}", exc_info=True)
    
    def get_capabilities(self) -> List[ActionCapability]:
        """Return list of capabilities from all loaded MCP tools."""
        capabilities = []
        
        for name, tool in self.tools.items():
            try:
                # Get input schema
                input_schema = {}
                if tool.args_schema:
                    try:
                        input_schema = tool.args_schema.schema()
                    except Exception as e:
                        logger.debug(f"[MCPToolProvider] Failed to get schema for {name}: {e}")
                        input_schema = {}
                
                # Classify tool
                category = self._classify_tool(name)
                
                # Get service name
                service = self._get_service(name)
                
                capabilities.append(ActionCapability(
                    name=name,
                    description=tool.description or f"Tool: {name}",
                    category=category,
                    provider_type=ProviderType.MCP_TOOL,
                    input_schema=input_schema,
                    service=service,
                    tags=self._get_tags(name)
                ))
            except Exception as e:
                logger.error(f"[MCPToolProvider] Failed to create capability for {name}: {e}")
                continue
        
        logger.info(f"[MCPToolProvider] Created {len(capabilities)} capabilities")
        return capabilities
    
    async def execute(
        self, 
        capability_name: str, 
        arguments: Dict,
        context: Dict = None
    ):
        """Execute a capability through the underlying MCP tool."""
        tool = self.tools.get(capability_name)
        if not tool:
            raise ValueError(f"Unknown capability: {capability_name}")
        
        try:
            result = await tool.ainvoke(arguments)
            return result
        except Exception as e:
            logger.error(f"[MCPToolProvider] Execution failed for {capability_name}: {e}")
            raise
    
    @property
    def provider_type(self) -> ProviderType:
        """Return provider type."""
        return ProviderType.MCP_TOOL
    
    async def health_check(self) -> bool:
        """Check if MCP provider is healthy."""
        # MCP tools are considered healthy if they're loaded
        return len(self.tools) > 0
    
    def _classify_tool(self, name: str) -> CapabilityCategory:
        """
        Classify tool as READ or WRITE based on name patterns.
        
        Args:
            name: Tool name
            
        Returns:
            CapabilityCategory (READ or WRITE)
        """
        name_lower = name.lower()
        
        # Read patterns - tools that only read data
        read_patterns = [
            "get_", "search_", "list_", "read_", "find_", 
            "fetch_", "retrieve_", "query_", "lookup_",
            "get_", "read", "search", "list", "find"
        ]
        
        # Check if tool name starts with or contains read pattern
        for pattern in read_patterns:
            if name_lower.startswith(pattern) or f"_{pattern}" in name_lower:
                return CapabilityCategory.READ
        
        # Special cases - explicitly read-only tools
        read_only_tools = [
            "search_emails", "get_email", "get_labels",
            "get_sheet_data", "sheets_read_range",
            "get_events", "get_calendars",
            "search_files", "list_files", "workspace_search_files",
            "docs_read", "slides_get"
        ]
        
        if name in read_only_tools:
            return CapabilityCategory.READ
        
        # Default to WRITE for tools that modify state
        return CapabilityCategory.WRITE
    
    def _get_service(self, name: str) -> str:
        """
        Determine service name from tool name.
        
        Args:
            name: Tool name
            
        Returns:
            Service identifier (gmail, sheets, calendar, etc.)
        """
        name_lower = name.lower()
        
        # Service mapping based on tool name patterns
        if "gmail" in name_lower or "email" in name_lower:
            return "gmail"
        elif "sheet" in name_lower or "spreadsheet" in name_lower:
            return "sheets"
        elif "calendar" in name_lower or "event" in name_lower:
            return "calendar"
        elif "workspace" in name_lower or "file" in name_lower:
            return "workspace"
        elif "doc" in name_lower and "slide" not in name_lower:
            return "docs"
        elif "slide" in name_lower or "presentation" in name_lower:
            return "slides"
        elif "onec" in name_lower:
            return "onec"
        elif "projectlad" in name_lower:
            return "projectlad"
        elif "code" in name_lower or "python" in name_lower or "execute" in name_lower:
            return "code_execution"
        else:
            return "unknown"
    
    def _get_tags(self, name: str) -> List[str]:
        """
        Get tags for a tool based on its name and service.
        
        Args:
            name: Tool name
            
        Returns:
            List of tags
        """
        tags = []
        service = self._get_service(name)
        if service != "unknown":
            tags.append(service)
        
        category = self._classify_tool(name)
        tags.append(category.value)
        
        return tags

