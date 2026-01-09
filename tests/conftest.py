"""
Pytest fixtures for testing UnifiedReActEngine and related components.
"""
import pytest
import time
import os
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Mock config loader before importing anything that uses it
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('DEFAULT_MODEL', 'claude-3-haiku')

from src.core.context_manager import ConversationContext
from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.api.websocket_manager import WebSocketManager


class MockWebSocketManager:
    """Mock WebSocket manager that captures all events."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.connection_count: Dict[str, int] = {}
    
    async def send_event(self, session_id: str, event_type: str, data: Any) -> None:
        """Capture event for testing."""
        self.events.append({
            "type": event_type,
            "data": data,
            "session_id": session_id,
            "ts": time.time()
        })
    
    def get_connection_count(self, session_id: str) -> int:
        """Return connection count for session."""
        return self.connection_count.get(session_id, 1)  # Default to 1 for tests
    
    def clear_events(self):
        """Clear captured events."""
        self.events.clear()


class MockLLM:
    """Mock LLM that tracks call count."""
    
    def __init__(self, response: str = "ДА"):
        self.call_count = 0
        self.invoke_count = 0
        self.response = response
        self.last_messages = None
    
    async def ainvoke(self, messages):
        """Track LLM invocation."""
        self.call_count += 1
        self.invoke_count += 1
        self.last_messages = messages
        
        # Return mock response
        mock_response = MagicMock()
        mock_response.content = self.response
        return mock_response
    
    async def astream(self, messages):
        """Mock streaming."""
        self.call_count += 1
        self.last_messages = messages
        
        # Yield chunks
        for word in self.response.split():
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk


class MockResponse:
    """Mock LLM response."""
    
    def __init__(self, content: str):
        self.content = content


@pytest.fixture
def mock_ws_manager():
    """Fixture for MockWebSocketManager."""
    return MockWebSocketManager()


@pytest.fixture
def mock_llm():
    """Fixture for MockLLM."""
    return MockLLM()


@pytest.fixture
def empty_context():
    """Fixture for empty ConversationContext."""
    return ConversationContext(session_id="test-session")


@pytest.fixture
def mock_capability_registry():
    """Fixture for CapabilityRegistry with mock capabilities."""
    registry = CapabilityRegistry()
    # Add mock capabilities if needed
    return registry


@pytest.fixture
def test_react_config():
    """Fixture for ReActConfig."""
    return ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=10,
        show_plan_to_user=False,
        require_plan_approval=False,
        enable_alternatives=True
    )


def create_test_engine(
    ws_manager: MockWebSocketManager,
    registry: Optional[CapabilityRegistry] = None,
    model_name: Optional[str] = None
) -> UnifiedReActEngine:
    """
    Helper to create UnifiedReActEngine for testing.
    
    Args:
        ws_manager: Mock WebSocket manager
        registry: Optional capability registry (creates empty if None)
        model_name: Optional model name
        
    Returns:
        Configured UnifiedReActEngine instance
    """
    if registry is None:
        registry = CapabilityRegistry()
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5,  # Shorter for tests
        show_plan_to_user=False,
        require_plan_approval=False,
        enable_alternatives=True
    )
    
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=ws_manager,
        session_id="test-session",
        model_name=model_name
    )
    
    return engine


def create_test_engine_with_mock_llm(
    ws_manager: MockWebSocketManager,
    mock_llm: MockLLM,
    registry: Optional[CapabilityRegistry] = None
) -> UnifiedReActEngine:
    """
    Helper to create UnifiedReActEngine with mocked LLM.
    
    Args:
        ws_manager: Mock WebSocket manager
        mock_llm: Mock LLM instance
        registry: Optional capability registry
        
    Returns:
        Configured UnifiedReActEngine with mocked LLM
    """
    engine = create_test_engine(ws_manager, registry)
    
    # Replace fast_llm with mock
    engine.fast_llm = mock_llm
    
    return engine
