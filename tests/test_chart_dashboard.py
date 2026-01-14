"""
Tests for chart_dashboard WebSocket event.
"""
# Import conftest first to mock config_loader
import test_chart_dashboard_conftest  # noqa: F401

import pytest
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock langchain_openai before import to avoid SSL issues in sandbox
mock_langchain_openai = MagicMock()
mock_chat_openai = MagicMock()
mock_langchain_openai.ChatOpenAI = mock_chat_openai
sys.modules['langchain_openai'] = mock_langchain_openai
sys.modules['langchain_openai.chat_models'] = mock_langchain_openai


@pytest.mark.asyncio
async def test_execute_python_sends_chart_dashboard():
    """
    Тест: execute_python_code с chartData должен отправить chart_dashboard событие.
    """
    # Test the _handle_workspace_events method directly without full AgentWrapper initialization
    from src.api.agent_wrapper import AgentWrapper
    from src.api.websocket_manager import WebSocketManager
    
    # Create mock WebSocket manager
    mock_ws = MagicMock(spec=WebSocketManager)
    mock_ws.send_event = AsyncMock()
    
    # Create minimal AgentWrapper (we'll patch __init__ to avoid full initialization)
    with patch.object(AgentWrapper, '__init__', return_value=None):
        wrapper = AgentWrapper.__new__(AgentWrapper)
        wrapper.ws_manager = mock_ws
        wrapper._sent_workspace_events = {}
    
    # Mock tool result with chartData
    # Result format from execute_python_code: "Result:\n{...}"
    chart_data = {
        "chartData": [
            {
                "title": "Зарплата по месяцам",
                "chartType": "bar",
                "series": [{"name": "Зарплата", "data": [100, 200, 300]}],
                "options": {"xaxis": {"categories": ["Янв", "Фев", "Мар"]}}
            },
            {
                "title": "Выработка по месяцам",
                "chartType": "line",
                "series": [{"name": "Выработка", "data": [101, 114, 127]}],
                "options": {"xaxis": {"categories": ["Янв", "Фев", "Мар"]}}
            }
        ]
    }
    tool_result = f"Result:\n{json.dumps(chart_data, indent=2)}"
    
    # Simulate tool execution result
    tool_name = "execute_python_code"
    tool_args = {
        "code": "result = {'chartData': [...]}",
        "input_data": {}
    }
    
    # Call the handler
    await wrapper._handle_workspace_events(
        session_id="test-session",
        tool_name=tool_name,
        result=tool_result,
        tool_args=tool_args
    )
    
    # Verify chart_dashboard event was sent
    chart_calls = [
        call for call in mock_ws.send_event.call_args_list
        if len(call[0]) >= 2 and call[0][1] == "chart_dashboard"
    ]
    
    assert len(chart_calls) > 0, "chart_dashboard event should be sent"
    
    # Verify event data structure
    call_args = chart_calls[0][0]
    assert call_args[0] == "test-session"  # session_id
    assert call_args[1] == "chart_dashboard"  # event_type
    
    event_data = call_args[2]
    assert "title" in event_data
    assert "charts" in event_data
    assert len(event_data["charts"]) == 2
    
    # Verify chart structure
    chart1 = event_data["charts"][0]
    assert chart1["title"] == "Зарплата по месяцам"
    assert chart1["chartType"] == "bar"
    assert "series" in chart1
    assert "options" in chart1


@pytest.mark.asyncio
async def test_execute_python_without_chartdata_no_event():
    """
    Тест: execute_python_code без chartData НЕ должен отправлять chart_dashboard.
    """
    from src.api.agent_wrapper import AgentWrapper
    from src.api.websocket_manager import WebSocketManager
    
    mock_ws = MagicMock(spec=WebSocketManager)
    mock_ws.send_event = AsyncMock()
    
    # Create minimal AgentWrapper
    with patch.object(AgentWrapper, '__init__', return_value=None):
        wrapper = AgentWrapper.__new__(AgentWrapper)
        wrapper.ws_manager = mock_ws
        wrapper._sent_workspace_events = {}
    
    # Tool result without chartData
    tool_result = json.dumps({
        "result": [1, 2, 3]
    })
    
    await wrapper._handle_workspace_events(
        session_id="test-session",
        tool_name="execute_python_code",
        result=tool_result,
        tool_args={"code": "result = [1, 2, 3]"}
    )
    
    # Should NOT send chart_dashboard
    chart_calls = [
        call for call in mock_ws.send_event.call_args_list
        if len(call[0]) >= 2 and call[0][1] == "chart_dashboard"
    ]
    
    assert len(chart_calls) == 0, "chart_dashboard should NOT be sent when no chartData"
