"""
Pytest configuration and fixtures for testing.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from src.core.context_manager import ConversationContext
from src.utils.mcp_loader import MCPServerManager, MCPConnection
from src.utils.config_loader import MCPConfig, MCPServerConfig


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_context():
    """Create a mock conversation context."""
    return ConversationContext(session_id="test-session")


@pytest.fixture
def mock_mcp_connection():
    """Create a mock MCP connection."""
    connection = Mock(spec=MCPConnection)
    connection.connected = True
    connection.tools = {
        "test_tool": {
            "name": "test_tool",
            "description": "Test tool",
            "inputSchema": {}
        }
    }
    connection.call_tool = AsyncMock(return_value={"result": "success"})
    return connection


@pytest.fixture
def mock_mcp_manager(mock_mcp_connection):
    """Create a mock MCP manager."""
    manager = Mock(spec=MCPServerManager)
    manager.connections = {
        "gmail": mock_mcp_connection,
        "calendar": mock_mcp_connection,
        "sheets": mock_mcp_connection
    }
    manager.get_all_tools = Mock(return_value={})
    manager.call_tool = AsyncMock(return_value={"result": "success"})
    manager.health_check = AsyncMock(return_value={
        "gmail": {"connected": True},
        "calendar": {"connected": True},
        "sheets": {"connected": True}
    })
    return manager



