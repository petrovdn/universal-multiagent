"""
MCP (Model Context Protocol) client manager.
Handles connections to multiple MCP servers and tool discovery.
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.utils.exceptions import MCPConnectionError, MCPError
from src.utils.config_loader import MCPConfig, MCPServerConfig
from src.utils.retry import retry_on_mcp_error, CircuitBreaker

logger = logging.getLogger(__name__)


class MCPConnection:
    """Represents a connection to a single MCP server."""
    
    def __init__(self, config: MCPServerConfig):
        """
        Initialize MCP connection.
        
        Args:
            config: MCP server configuration
        """
        self.config = config
        self.session: Optional[ClientSession] = None
        self._stdio_client = None
        self._read_stream = None
        self._write_stream = None
        self._connection_task: Optional[asyncio.Task] = None
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.connected = False
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            expected_exception=MCPError
        )
    
    async def connect(self) -> bool:
        """
        Connect to MCP server.
        
        Returns:
            True if connection successful
            
        Raises:
            MCPConnectionError: If connection fails
        """
        if self.connected and self.session:
            return True
        
        try:
            if self.config.transport == "stdio":
                # STDIO transport - запуск через npx
                env = os.environ.copy()
                
                if self.config.name == "gmail":
                    # Используем собственный локальный MCP сервер для Gmail
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем путь к токену из конфига
                    config = get_config()
                    token_path = config.tokens_dir / "gmail_token.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Gmail token not found. "
                            "Please enable Gmail integration first via /api/integrations/gmail/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "gmail_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Gmail MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Gmail MCP server: {command} {' '.join(args)}")
                elif self.config.name == "calendar":
                    # Используем собственный локальный MCP сервер для Google Calendar
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем путь к токену из конфига
                    config = get_config()
                    token_path = config.tokens_dir / "google_calendar_token.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Google Calendar token not found. "
                            "Please enable Google Calendar integration first via /api/integrations/google-calendar/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "google_calendar_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Calendar MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Calendar MCP server: {command} {' '.join(args)}")
                elif self.config.name == "sheets":
                    # Используем собственный локальный MCP сервер для Google Sheets
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем путь к токену из конфига
                    config = get_config()
                    token_path = config.tokens_dir / "google_sheets_token.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Google Sheets token not found. "
                            "Please enable Google Sheets integration first via /api/integrations/google-sheets/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "google_sheets_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Google Sheets MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Google Sheets MCP server: {command} {' '.join(args)}")
                elif self.config.name == "google_workspace":
                    # Используем собственный локальный MCP сервер для Google Workspace
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем пути из конфига
                    app_config = get_config()
                    token_path = app_config.tokens_dir / "google_workspace_token.json"
                    config_path = app_config.config_dir / "workspace_config.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Google Workspace token not found. "
                            "Please enable Google Workspace integration first via /api/integrations/google-workspace/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "google_workspace_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Google Workspace MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute()),
                        "--config-path",
                        str(config_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Google Workspace MCP server: {command} {' '.join(args)}")
                elif self.config.name == "docs":
                    # Используем собственный локальный MCP сервер для Google Docs
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем пути из конфига
                    app_config = get_config()
                    token_path = app_config.tokens_dir / "google_workspace_token.json"
                    config_path = app_config.config_dir / "workspace_config.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Google Workspace token not found. "
                            "Please enable Google Workspace integration first via /api/integrations/google-workspace/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "google_docs_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Google Docs MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute()),
                        "--config-path",
                        str(config_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Google Docs MCP server: {command} {' '.join(args)}")
                elif self.config.name == "slides":
                    # Используем собственный локальный MCP сервер для Google Slides
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем пути из конфига
                    app_config = get_config()
                    token_path = app_config.tokens_dir / "google_workspace_token.json"
                    config_path = app_config.config_dir / "workspace_config.json"
                    if not token_path.exists():
                        raise MCPConnectionError(
                            "Google Workspace token not found. "
                            "Please enable Google Workspace integration first via /api/integrations/google-workspace/enable",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "google_slides_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Google Slides MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--token-path",
                        str(token_path.absolute()),
                        "--config-path",
                        str(config_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Google Slides MCP server: {command} {' '.join(args)}")
                elif self.config.name == "onec":
                    # Используем собственный локальный MCP сервер для 1C:Бухгалтерия
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем путь к конфигу из конфига
                    app_config = get_config()
                    config_path = app_config.config_dir / "onec_config.json"
                    if not config_path.exists():
                        raise MCPConnectionError(
                            "1C config not found. "
                            "Please configure 1C OData connection first via /api/integrations/onec/config",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "onec_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"1C MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--config-path",
                        str(config_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local 1C MCP server: {command} {' '.join(args)}")
                elif self.config.name == "projectlad":
                    # Project Lad MCP server
                    from pathlib import Path
                    import sys
                    from src.utils.config_loader import get_config
                    
                    # Получаем путь к конфигу из конфига
                    app_config = get_config()
                    config_path = app_config.config_dir / "projectlad_config.json"
                    if not config_path.exists():
                        raise MCPConnectionError(
                            "Project Lad config not found. "
                            "Please configure Project Lad connection first via /api/integrations/projectlad/config",
                            server_name=self.config.name
                        )
                    
                    # Запускаем локальный Python MCP сервер
                    project_root = Path(__file__).parent.parent.parent
                    server_script = project_root / "src" / "mcp_servers" / "projectlad_server.py"
                    
                    if not server_script.exists():
                        raise MCPConnectionError(
                            f"Project Lad MCP server script not found at {server_script}",
                            server_name=self.config.name
                        )
                    
                    command = sys.executable
                    args = [
                        str(server_script),
                        "--config-path",
                        str(config_path.absolute())
                    ]
                    logger.info(f"[MCPConnection] Starting local Project Lad MCP server: {command} {' '.join(args)}")
                else:
                    raise MCPConnectionError(f"Unknown MCP server: {self.config.name}")
                
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )
                
                # Create stdio client and keep it alive
                self._stdio_client = stdio_client(server_params)
                self._read_stream, self._write_stream = await self._stdio_client.__aenter__()
                
                # Create session and keep it alive
                self.session = ClientSession(self._read_stream, self._write_stream)
                await self.session.__aenter__()
                
                await self._initialize()
                self.connected = True
                logger.info(f"Connected to MCP server: {self.config.name} with {len(self.tools)} tools")
                # Log tools for debugging
                if self.tools:
                    logger.info(f"[MCPConnection] Tools available: {list(self.tools.keys())[:5]}...")
                else:
                    logger.warning(f"[MCPConnection] No tools discovered for {self.config.name}. This may indicate a connection issue.")
                return True
            else:
                # HTTP/SSE transport
                # For SSE transport, we connect to HTTP endpoint
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Try health check first
                    try:
                        health_url = f"{self.config.endpoint}/health"
                        response = await client.get(health_url)
                        if response.status_code == 200:
                            logger.info(f"Health check passed for {self.config.name}")
                    except Exception as e:
                        logger.warning(f"Health check failed for {self.config.name}: {e}, continuing anyway")
                    
                    # For SSE transport, we don't create a session like stdio
                    # Instead, we'll use HTTP endpoints directly
                    self.connected = True
                    logger.info(f"Connected to MCP server: {self.config.name} via {self.config.transport} transport")
                    
                    # Try to discover tools via HTTP endpoint
                    try:
                        tools_url = f"{self.config.endpoint}/tools"
                        response = await client.get(tools_url)
                        if response.status_code == 200:
                            tools_data = response.json()
                            if isinstance(tools_data, list):
                                for tool in tools_data:
                                    tool_name = tool.get('name')
                                    if tool_name:
                                        self.tools[tool_name] = {
                                            "name": tool_name,
                                            "description": tool.get('description', ''),
                                            "inputSchema": tool.get('inputSchema', {})
                                        }
                                logger.info(f"Discovered {len(self.tools)} tools from {self.config.name} via HTTP")
                    except Exception as e:
                        logger.warning(f"Failed to discover tools via HTTP for {self.config.name}: {e}")
                        # Tools will be discovered on first call if needed
                    
                    return True
                        
        except Exception as e:
            logger.error(f"Failed to connect to {self.config.name}: {e}")
            raise MCPConnectionError(
                f"Connection failed: {e}",
                server_name=self.config.name
            ) from e
    
    async def _initialize(self) -> None:
        """Initialize MCP session and discover tools."""
        if not self.session:
            return
        
        try:
            # Initialize the session first (required by MCP protocol)
            await self.session.initialize()
            
            # List available tools
            result = await self.session.list_tools()
            
            # Handle different result formats
            tools_list = []
            if hasattr(result, 'tools'):
                tools_list = result.tools
            elif isinstance(result, dict) and 'tools' in result:
                tools_list = result['tools']
            elif isinstance(result, list):
                tools_list = result
            else:
                logger.warning(f"Unexpected result format from list_tools: {type(result)}")
                return
            
            for tool in tools_list:
                # Handle different tool object formats
                tool_name = None
                tool_description = ""
                tool_schema = {}
                
                if hasattr(tool, 'name'):
                    tool_name = tool.name
                    tool_description = getattr(tool, 'description', '')
                    tool_schema = getattr(tool, 'inputSchema', {})
                elif isinstance(tool, dict):
                    tool_name = tool.get('name')
                    tool_description = tool.get('description', '')
                    tool_schema = tool.get('inputSchema', {})
                
                if tool_name:
                    self.tools[tool_name] = {
                        "name": tool_name,
                        "description": tool_description,
                        "inputSchema": tool_schema
                    }
            
            logger.info(f"Discovered {len(self.tools)} tools from {self.config.name}: {list(self.tools.keys())}")
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to discover tools from {self.config.name}: {e}\n{traceback.format_exc()}")
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPToolError: If tool execution fails
        """
        # Log current state
        logger.info(f"[MCPConnection] call_tool called for {tool_name} on {self.config.name}")
        logger.info(f"[MCPConnection] connected={self.connected}, session={self.session is not None}, tools_count={len(self.tools)}")
        
        if not self.connected or not self.session:
            logger.warning(f"[MCPConnection] Not connected or session lost, reconnecting...")
            await self.connect()
        
        # If tools not discovered yet, try to discover them
        if not self.tools:
            logger.warning(f"[MCPConnection] Tools not discovered for {self.config.name}, attempting discovery...")
            if self.session:
                await self._initialize()
            else:
                logger.error(f"[MCPConnection] Cannot discover tools: session is None")
                raise MCPError(
                    f"Cannot discover tools: session is not available",
                    server_name=self.config.name,
                    tool_name=tool_name
                )
        
        if tool_name not in self.tools:
            available_tools = list(self.tools.keys()) if self.tools else []
            error_msg = (
                f"Tool '{tool_name}' not found in {self.config.name}. "
                f"Available tools: {available_tools if available_tools else 'none (tools not discovered)'}"
            )
            logger.error(f"[MCPConnection] {error_msg}")
            logger.error(f"[MCPConnection] Current tools: {list(self.tools.keys())}")
            raise MCPError(
                error_msg,
                server_name=self.config.name,
                tool_name=tool_name
            )
        
        try:
            if self.config.transport == "stdio" and self.session:
                # #region agent log - H3: Before session.call_tool
                import time as _time
                import json as _json
                _session_call_start = _time.time()
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "mcp_loader:before_session_call", "message": "Before session.call_tool", "data": {"tool_name": tool_name, "server": self.config.name, "arguments": str(arguments)[:200]}, "timestamp": int(_session_call_start*1000), "sessionId": "debug-session", "hypothesisId": "H3"}) + '\n')
                # #endregion
                
                try:
                    result = await self.session.call_tool(tool_name, arguments)
                    
                    # #region agent log - H3: After session.call_tool SUCCESS
                    _session_call_end = _time.time()
                    open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "mcp_loader:after_session_call_SUCCESS", "message": "After session.call_tool SUCCESS", "data": {"tool_name": tool_name, "server": self.config.name, "duration_ms": int((_session_call_end - _session_call_start)*1000), "result_type": type(result).__name__}, "timestamp": int(_session_call_end*1000), "sessionId": "debug-session", "hypothesisId": "H3"}) + '\n')
                    # #endregion
                    
                except Exception as mcp_exception:
                    # #region agent log - H3,H4: session.call_tool ERROR
                    _session_call_end = _time.time()
                    open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "mcp_loader:session_call_ERROR", "message": "SESSION CALL ERROR", "data": {"tool_name": tool_name, "server": self.config.name, "duration_ms": int((_session_call_end - _session_call_start)*1000), "error": str(mcp_exception), "error_type": type(mcp_exception).__name__}, "timestamp": int(_session_call_end*1000), "sessionId": "debug-session", "hypothesisId": "H3,H4"}) + '\n')
                    # #endregion
                    # MCP call raised an exception
                    error_msg = str(mcp_exception) if str(mcp_exception) else f"MCP call failed: {type(mcp_exception).__name__}"
                    logger.error(
                        f"Tool execution failed: {tool_name} on {self.config.name}. "
                        f"Exception: {error_msg}. Arguments: {arguments}"
                    )
                    raise MCPError(
                        f"Tool execution failed: {error_msg}",
                        server_name=self.config.name,
                        tool_name=tool_name
                    ) from mcp_exception
                
                # Check for errors in MCP result
                if hasattr(result, 'isError') and result.isError:
                    error_msg = "Unknown error"
                    if hasattr(result, 'content') and result.content:
                        # Extract error message from content
                        if isinstance(result.content, list) and len(result.content) > 0:
                            first_item = result.content[0]
                            if isinstance(first_item, dict):
                                error_msg = first_item.get('text', str(first_item))
                            else:
                                error_msg = str(first_item)
                        else:
                            error_msg = str(result.content)
                    elif hasattr(result, 'error'):
                        error_msg = str(result.error)
                    
                    logger.error(
                        f"Tool execution failed: {tool_name} on {self.config.name}. "
                        f"Error: {error_msg}. Arguments: {arguments}"
                    )
                    raise MCPError(
                        f"Tool execution failed: {error_msg}",
                        server_name=self.config.name,
                        tool_name=tool_name
                    )
                
                # Extract content from result
                if hasattr(result, 'content'):
                    content = result.content
                    # Handle list of content items
                    if isinstance(content, list) and len(content) > 0:
                        # Extract text from content items
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict):
                                if 'text' in item:
                                    text_parts.append(item['text'])
                                elif 'type' in item and item.get('type') == 'text':
                                    text_parts.append(item.get('text', ''))
                            elif isinstance(item, str):
                                text_parts.append(item)
                        if text_parts:
                            return '\n'.join(text_parts)
                    return content
                else:
                    return result
            else:
                # HTTP/SSE transport
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # Prepare headers
                    headers = {}
                    if self.config.api_key:
                        headers["Authorization"] = f"Bearer {self.config.api_key}"
                    headers["Content-Type"] = "application/json"
                    
                    # Call tool via HTTP endpoint
                    tool_url = f"{self.config.endpoint}/tools/{tool_name}"
                    logger.info(f"[MCPConnection] Calling {tool_name} via HTTP: {tool_url}")
                    
                    response = await client.post(
                        tool_url,
                        json=arguments,
                        headers=headers
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Handle different response formats
                    if isinstance(result, dict):
                        # Check for error in response
                        if "error" in result:
                            raise MCPError(
                                f"Tool execution failed: {result.get('error', 'Unknown error')}",
                                server_name=self.config.name,
                                tool_name=tool_name
                            )
                        # Extract content if present
                        if "content" in result:
                            return result["content"]
                        return result
                    return result
                    
        except MCPError:
            # Re-raise MCP errors as-is
            raise
        except Exception as e:
            # Log full error details including traceback
            import traceback
            error_details = traceback.format_exc()
            logger.error(
                f"Tool execution failed: {tool_name} on {self.config.name}: {e}\n"
                f"Arguments: {arguments}\n"
                f"Traceback: {error_details}"
            )
            raise MCPError(
                f"Tool execution failed: {str(e) or 'Unknown error'}",
                server_name=self.config.name,
                tool_name=tool_name
            ) from e
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        try:
            if self.session:
                try:
                    await self.session.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")
                self.session = None
            if self._stdio_client:
                try:
                    await self._stdio_client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing stdio client: {e}")
                self._stdio_client = None
            self._read_stream = None
            self._write_stream = None
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
        finally:
            self.connected = False
            self.tools = {}  # Clear tools on disconnect
            logger.info(f"Disconnected from MCP server: {self.config.name}")
    
    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available tools."""
        return self.tools.copy()


class MCPServerManager:
    """
    Manager for multiple MCP server connections.
    Provides unified interface for tool discovery and execution.
    """
    
    def __init__(self, config: Optional[MCPConfig] = None):
        """
        Initialize MCP server manager.
        
        Args:
            config: MCP configuration (uses global config if None)
        """
        if config is None:
            try:
                from src.utils.config_loader import get_config
                app_config = get_config()
                config = app_config.mcp
            except Exception as e:
                # Fallback if config fails to load
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load config in MCPServerManager: {e}. Using defaults.")
                from src.utils.config_loader import MCPConfig, MCPServerConfig
                config = MCPConfig.from_env()
        
        self.config = config
        self.connections: Dict[str, MCPConnection] = {}
        
        # Initialize connections
        self.connections["gmail"] = MCPConnection(config.gmail)
        self.connections["calendar"] = MCPConnection(config.calendar)
        self.connections["sheets"] = MCPConnection(config.sheets)
        self.connections["google_workspace"] = MCPConnection(config.google_workspace)
        self.connections["docs"] = MCPConnection(config.docs)
        self.connections["slides"] = MCPConnection(config.slides)
        self.connections["onec"] = MCPConnection(config.onec)
        self.connections["projectlad"] = MCPConnection(config.projectlad)
    
    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect to all configured MCP servers.
        
        Returns:
            Dictionary mapping server names to connection status
        """
        results = {}
        connected_connections = set()  # Track which connection objects we've already connected
        
        for name, connection in self.connections.items():
            if not connection.config.enabled:
                results[name] = False
                continue
            
            # If this connection object was already connected (e.g., sheets shares calendar connection)
            if connection in connected_connections:
                results[name] = connection.connected
                continue
            
            try:
                results[name] = await connection.connect()
                if results[name]:
                    connected_connections.add(connection)
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
                results[name] = False
        
        return results
    
    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for connection in self.connections.values():
            try:
                await connection.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool definition by name.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool definition or None if not found
        """
        for connection in self.connections.values():
            if tool_name in connection.tools:
                return connection.tools[tool_name]
        return None
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available tools from all servers.
        
        Returns:
            Dictionary mapping tool names to tool definitions
        """
        all_tools = {}
        for connection in self.connections.values():
            all_tools.update(connection.tools)
        return all_tools
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None
    ) -> Any:
        """
        Call a tool by name.
        
        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments
            server_name: Optional server name (auto-detect if not provided)
            
        Returns:
            Tool execution result
            
        Raises:
            MCPError: If tool not found or execution fails
        """
        
        logger.info(f"[MCPServerManager] call_tool called: tool={tool_name}, server={server_name}")
        
        if server_name:
            if server_name not in self.connections:
                raise MCPError(f"Server '{server_name}' not found")
            connection = self.connections[server_name]
            logger.info(f"[MCPServerManager] Using connection for {server_name}: connected={connection.connected}, tools_count={len(connection.tools)}")
            
            # Check if connection is alive and has tools
            if not connection.connected or not connection.session:
                logger.warning(f"[MCPServerManager] Connection {server_name} not connected, reconnecting...")
                await connection.connect()
            
            if not connection.tools:
                logger.warning(f"[MCPServerManager] Connection {server_name} has no tools, attempting discovery...")
                if connection.session:
                    await connection._initialize()
        else:
            # Find tool in any server
            connection = None
            for conn in self.connections.values():
                if tool_name in conn.tools:
                    connection = conn
                    break
            
            if not connection:
                # Try to find by checking all connections (even if tools not discovered)
                for conn in self.connections.values():
                    # Try to reconnect and discover tools
                    if not conn.connected or not conn.tools:
                        try:
                            await conn.connect()
                        except Exception as e:
                            logger.warning(f"Failed to reconnect {conn.config.name}: {e}")
                    if tool_name in conn.tools:
                        connection = conn
                        break
            
            if not connection:
                raise MCPError(
                    f"Tool '{tool_name}' not found in any MCP server",
                    tool_name=tool_name
                )
        
        
        result = await connection.call_tool(tool_name, arguments)
        
        
        return result
    
    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all MCP servers.
        
        Returns:
            Dictionary mapping server names to health status
        """
        health = {}
        
        for name, connection in self.connections.items():
            health[name] = {
                "enabled": connection.config.enabled,
                "connected": connection.connected,
                "tools_count": len(connection.tools)
            }
        
        return health


# Global MCP manager instance
_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """
    Get the global MCP server manager.
    
    Returns:
        MCPServerManager instance
    """
    global _mcp_manager
    
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    
    return _mcp_manager

