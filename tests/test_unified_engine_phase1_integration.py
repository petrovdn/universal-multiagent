"""
Integration tests for Phase 1 features in UnifiedReActEngine.

Tests ToolExplanationGenerator and SourceTracker integration.
"""
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import MockWebSocketManager, create_test_engine
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import ActionCapability, CapabilityCategory


class MockTool:
    """Mock tool for testing."""
    
    def __init__(self, name: str, result: Any = "Success"):
        self.name = name
        self.result = result
    
    async def ainvoke(self, args: dict):
        return self.result


@pytest.fixture
def registry_with_capability():
    """Fixture for registry with mock capability."""
    registry = CapabilityRegistry()
    # Mock the execute method
    async def mock_execute(capability_name: str, arguments: dict):
        if capability_name == "list_emails":
            return {"emails": [{"id": "1", "subject": "Test"}]}
        return {"result": "success"}
    
    registry.execute = AsyncMock(side_effect=mock_execute)
    return registry


@pytest.mark.asyncio
async def test_tool_explanation_generator_initialized(mock_ws_manager, registry_with_capability):
    """Test: ToolExplanationGenerator is initialized in engine."""
    engine = create_test_engine(mock_ws_manager, registry_with_capability)
    
    # Check that tool_explanation_generator is initialized
    assert engine.tool_explanation_generator is not None
    assert engine.source_tracker is not None


@pytest.mark.asyncio
async def test_source_tracking_integration(mock_ws_manager, registry_with_capability):
    """Test: Source tracking is integrated and sends events."""
    engine = create_test_engine(mock_ws_manager, registry_with_capability)
    
    # Check that source_tracker is initialized
    assert engine.source_tracker is not None
    
    # Test source tracking directly
    source_id = await engine.source_tracker.track_source(
        source_name="Gmail",
        tool_name="list_emails",
        preview_data="Проверяю письма",
        intent_id="intent-1"
    )
    
    assert source_id is not None
    
    # Check that source_loading event was sent
    source_loading_events = [e for e in mock_ws_manager.events if e["type"] == "source_loading"]
    assert len(source_loading_events) == 1
    assert source_loading_events[0]["data"]["source"]["name"] == "Gmail"
    
    # Test source completion
    await engine.source_tracker.update_source_complete(
        source_id=source_id,
        result={"emails": [{"id": "1"}]},
        intent_id="intent-1"
    )
    
    # Check that source_completed event was sent
    source_completed_events = [e for e in mock_ws_manager.events if e["type"] == "source_completed"]
    assert len(source_completed_events) == 1
    assert source_completed_events[0]["data"]["source"]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_source_name_method(mock_ws_manager, registry_with_capability):
    """Test: _get_source_name correctly maps tool names to service names."""
    engine = create_test_engine(mock_ws_manager, registry_with_capability)
    
    # Test known tools
    assert engine._get_source_name("list_emails") == "Gmail"
    assert engine._get_source_name("get_sheet_data") == "Google Sheets"
    assert engine._get_source_name("get_calendar_events") == "Google Calendar"
    
    # Test fallback
    source_name = engine._get_source_name("unknown_tool")
    assert source_name is not None
    assert isinstance(source_name, str)
