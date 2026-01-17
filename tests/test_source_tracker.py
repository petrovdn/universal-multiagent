"""
TDD tests for SourceTracker - Phase 1, Step 1.2.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Import will fail initially - that's expected in TDD
from src.core.source_tracker import SourceTracker


class MockWebSocketManager:
    """Mock WebSocket manager that captures all events."""
    
    def __init__(self):
        self.events = []
    
    async def send_event(self, session_id: str, event_type: str, data: Any) -> None:
        """Capture event for testing."""
        self.events.append({
            "type": event_type,
            "data": data,
            "session_id": session_id
        })
    
    def clear_events(self):
        """Clear captured events."""
        self.events.clear()


@pytest.fixture
def mock_ws_manager():
    """Fixture for MockWebSocketManager."""
    return MockWebSocketManager()


@pytest.fixture
def source_tracker(mock_ws_manager):
    """Fixture for SourceTracker."""
    return SourceTracker(mock_ws_manager, "test-session")


class TestSourceTracker:
    """Test suite for SourceTracker."""
    
    @pytest.mark.asyncio
    async def test_track_source_sends_loading_event(self, source_tracker, mock_ws_manager):
        """Test: track_source sends source_loading event."""
        source_id = await source_tracker.track_source(
            source_name="Gmail",
            tool_name="list_emails",
            preview_data="Проверяю непрочитанные письма",
            intent_id="intent-1"
        )
        
        assert source_id is not None
        assert len(mock_ws_manager.events) == 1
        event = mock_ws_manager.events[0]
        assert event["type"] == "source_loading"
        assert event["data"]["source"]["name"] == "Gmail"
        assert event["data"]["source"]["status"] == "loading"
        assert event["data"]["intent_id"] == "intent-1"
    
    @pytest.mark.asyncio
    async def test_track_source_auto_guesses_icon(self, source_tracker, mock_ws_manager):
        """Test: track_source auto-guesses icon based on source name."""
        await source_tracker.track_source(
            source_name="Gmail",
            tool_name="list_emails",
            preview_data="Проверяю письма",
            intent_id="intent-1"
        )
        
        event = mock_ws_manager.events[0]
        source = event["data"]["source"]
        assert "icon" in source
        # Gmail should have email icon
        assert source["icon"] in ["📧", "email", "mail"]
    
    @pytest.mark.asyncio
    async def test_update_source_complete_sends_completed_event(self, source_tracker, mock_ws_manager):
        """Test: update_source_complete sends source_completed event."""
        source_id = await source_tracker.track_source(
            source_name="Google Sheets",
            tool_name="get_sheet_data",
            preview_data="Получаю данные",
            intent_id="intent-1"
        )
        
        mock_ws_manager.clear_events()
        
        result = {
            "rows": [
                ["Name", "Value"],
                ["Item 1", "100"],
                ["Item 2", "200"]
            ]
        }
        
        await source_tracker.update_source_complete(
            source_id=source_id,
            result=result,
            intent_id="intent-1"
        )
        
        assert len(mock_ws_manager.events) == 1
        event = mock_ws_manager.events[0]
        assert event["type"] == "source_completed"
        assert event["data"]["source"]["status"] == "completed"
        assert event["data"]["source"]["id"] == source_id
    
    @pytest.mark.asyncio
    async def test_update_source_complete_extracts_item_count(self, source_tracker, mock_ws_manager):
        """Test: update_source_complete extracts item count from result."""
        source_id = await source_tracker.track_source(
            source_name="Gmail",
            tool_name="list_emails",
            preview_data="Проверяю письма",
            intent_id="intent-1"
        )
        
        mock_ws_manager.clear_events()
        
        # Result with emails list
        result = {
            "emails": [
                {"id": "1", "subject": "Email 1"},
                {"id": "2", "subject": "Email 2"},
                {"id": "3", "subject": "Email 3"}
            ]
        }
        
        await source_tracker.update_source_complete(
            source_id=source_id,
            result=result,
            intent_id="intent-1"
        )
        
        event = mock_ws_manager.events[0]
        source = event["data"]["source"]
        # Should extract count (3 emails)
        assert "item_count" in source or "count" in source or "items" in source
    
    @pytest.mark.asyncio
    async def test_update_source_error_sends_error_event(self, source_tracker, mock_ws_manager):
        """Test: update_source_error sends source_error event."""
        source_id = await source_tracker.track_source(
            source_name="Google Calendar",
            tool_name="get_calendar_events",
            preview_data="Проверяю встречи",
            intent_id="intent-1"
        )
        
        mock_ws_manager.clear_events()
        
        error_message = "Ошибка доступа к календарю"
        await source_tracker.update_source_error(
            source_id=source_id,
            error=error_message,
            intent_id="intent-1"
        )
        
        assert len(mock_ws_manager.events) == 1
        event = mock_ws_manager.events[0]
        assert event["type"] == "source_error"
        assert event["data"]["source"]["status"] == "error"
        assert event["data"]["source"]["id"] == source_id
        assert error_message in str(event["data"])
    
    @pytest.mark.asyncio
    async def test_track_source_generates_unique_ids(self, source_tracker):
        """Test: Each track_source call generates unique source_id."""
        source_id_1 = await source_tracker.track_source(
            source_name="Gmail",
            tool_name="list_emails",
            preview_data="Проверяю письма",
            intent_id="intent-1"
        )
        
        source_id_2 = await source_tracker.track_source(
            source_name="Calendar",
            tool_name="get_calendar_events",
            preview_data="Проверяю встречи",
            intent_id="intent-1"
        )
        
        assert source_id_1 != source_id_2
        assert source_id_1 is not None
        assert source_id_2 is not None
    
    @pytest.mark.asyncio
    async def test_track_source_handles_unknown_source_name(self, source_tracker, mock_ws_manager):
        """Test: track_source handles unknown source names gracefully."""
        source_id = await source_tracker.track_source(
            source_name="Unknown System",
            tool_name="unknown_tool",
            preview_data="Выполняю действие",
            intent_id="intent-1"
        )
        
        assert source_id is not None
        event = mock_ws_manager.events[0]
        source = event["data"]["source"]
        # Should have some default icon
        assert "icon" in source
