"""
Integration test for spreadsheet analysis with charts.
Tests the full flow: get_all_sheets_data -> execute_python_code -> chart_dashboard.
"""
import pytest
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock config_loader BEFORE any imports to prevent PermissionError
mock_config_obj = MagicMock()
mock_config_obj.timezone = "UTC"  # Must be string, not MagicMock
mock_config_obj.anthropic_api_key = "test-key"
mock_config_obj.openai_api_key = "test-key"
mock_config_obj.default_model = "gpt-4o"

mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader

# Mock langchain_openai before import to avoid SSL issues in sandbox
mock_langchain_openai = MagicMock()
mock_chat_openai = MagicMock()
mock_langchain_openai.ChatOpenAI = mock_chat_openai
sys.modules['langchain_openai'] = mock_langchain_openai
sys.modules['langchain_openai.chat_models'] = mock_langchain_openai


@pytest.mark.asyncio
async def test_full_analysis_flow_with_charts():
    """
    Тест: Полный flow анализа таблицы с двумя вкладками и созданием диаграмм.
    
    Проверяет:
    1. get_all_sheets_data вызывается для чтения всех вкладок
    2. execute_python_code вызывается с данными
    3. chart_dashboard событие отправляется
    """
    from src.mcp_tools.sheets_tools import GetAllSheetsDataTool
    from src.mcp_tools.code_execution_tools import PythonCodeExecutionTool
    from src.api.agent_wrapper import AgentWrapper
    from src.api.websocket_manager import WebSocketManager
    
    # Mock MCP manager
    mock_mcp_manager = AsyncMock()
    
    # Mock response from sheets_read_all_sheets
    mock_sheets_response = {
        "spreadsheetTitle": "Анализ данных",
        "sheets": [
            {
                "name": "Зарплата",
                "values": [
                    ["Сотрудник", "Месяц", "Зарплата"],
                    ["Иванов", "Январь", "100"],
                    ["Петров", "Январь", "200"],
                    ["Сидорова", "Январь", "300"],
                ],
                "rowCount": 4,
                "columnCount": 3
            },
            {
                "name": "Выработка",
                "values": [
                    ["Сотрудник", "Месяц", "Выработка"],
                    ["Иванов", "Январь", "101"],
                    ["Петров", "Январь", "114"],
                    ["Сидорова", "Январь", "121"],
                ],
                "rowCount": 4,
                "columnCount": 3
            }
        ]
    }
    
    # Mock MCP call result
    from mcp.types import TextContent
    mock_mcp_manager.call_tool.return_value = [
        TextContent(type="text", text=json.dumps(mock_sheets_response))
    ]
    
    # Mock WebSocket manager
    mock_ws = MagicMock(spec=WebSocketManager)
    mock_ws.send_event = AsyncMock()
    
    # Patch MCP manager
    with patch('src.mcp_tools.sheets_tools.get_mcp_manager', return_value=mock_mcp_manager):
        # Step 1: Test get_all_sheets_data
        get_all_tool = GetAllSheetsDataTool()
        result = await get_all_tool._arun(
            spreadsheet_id="TEST_SPREADSHEET_ID",
            max_rows=1000
        )
        
        # Verify get_all_sheets_data was called
        mock_mcp_manager.call_tool.assert_called_with(
            "sheets_read_all_sheets",
            {"spreadsheetId": "TEST_SPREADSHEET_ID", "maxRows": 1000},
            server_name="sheets"
        )
        
        # Verify result contains both sheets
        assert "Зарплата" in result
        assert "Выработка" in result
        assert "Анализ данных" in result
        
        # Step 2: Test execute_python_code with chartData
        code_tool = PythonCodeExecutionTool()
        
        # Python code that creates chartData
        analysis_code = '''
import json

# Parse sheets data (simulating what agent would do)
sheets_data = data.get("sheets", [])
zarplata_sheet = next((s for s in sheets_data if s["name"] == "Зарплата"), None)
vyrabotka_sheet = next((s for s in sheets_data if s["name"] == "Выработка"), None)

# Simple analysis: average salary and output
if zarplata_sheet and vyrabotka_sheet:
    zarplata_values = zarplata_sheet.get("values", [])[1:]  # Skip header
    vyrabotka_values = vyrabotka_sheet.get("values", [])[1:]  # Skip header
    
    # Calculate averages
    salaries = [float(row[2]) for row in zarplata_values if len(row) > 2]
    outputs = [float(row[2]) for row in vyrabotka_values if len(row) > 2]
    
    avg_salary = sum(salaries) / len(salaries) if salaries else 0
    avg_output = sum(outputs) / len(outputs) if outputs else 0
    
    result = {
        "chartData": [
            {
                "title": "Средняя зарплата",
                "chartType": "bar",
                "series": [{"name": "Зарплата", "data": [avg_salary]}],
                "options": {"xaxis": {"categories": ["Среднее"]}}
            },
            {
                "title": "Средняя выработка",
                "chartType": "bar",
                "series": [{"name": "Выработка", "data": [avg_output]}],
                "options": {"xaxis": {"categories": ["Среднее"]}}
            }
        ]
    }
else:
    result = {"error": "Sheets not found"}
'''
        
        # Execute code with sheets data
        code_result = await code_tool._arun(
            code=analysis_code,
            input_data={"sheets": mock_sheets_response["sheets"]}
        )
        
        # Verify code executed and contains chartData
        assert "chartData" in code_result or "Result:" in code_result
        
        # Step 3: Test AgentWrapper sends chart_dashboard event
        with patch.object(AgentWrapper, '__init__', return_value=None):
            wrapper = AgentWrapper.__new__(AgentWrapper)
            wrapper.ws_manager = mock_ws
            wrapper._sent_workspace_events = {}
            
            # Format result as execute_python_code would return it
            formatted_result = f"Result:\n{json.dumps({'chartData': mock_sheets_response['sheets']})}"
            
            await wrapper._handle_workspace_events(
                session_id="test-session",
                tool_name="execute_python_code",
                result=formatted_result,
                tool_args={"code": analysis_code}
            )
            
            # Verify chart_dashboard event was sent
            chart_calls = [
                call for call in mock_ws.send_event.call_args_list
                if len(call[0]) >= 2 and call[0][1] == "chart_dashboard"
            ]
            
            assert len(chart_calls) > 0, "chart_dashboard event should be sent"
            
            # Verify event structure
            call_args = chart_calls[0][0]
            assert call_args[1] == "chart_dashboard"
            event_data = call_args[2]
            assert "charts" in event_data


@pytest.mark.asyncio
async def test_agent_has_get_all_sheets_data_tool():
    """
    Тест: Проверяет, что get_all_sheets_data доступен в SheetsAgent.
    """
    from src.agents.sheets_agent import SheetsAgent
    
    # Create agent (will use mocked config)
    agent = SheetsAgent()
    tools = agent.get_tools()
    tool_names = [t.name for t in tools]
    
    # Verify get_all_sheets_data is available
    assert "get_all_sheets_data" in tool_names, f"get_all_sheets_data not found in tools: {tool_names}"
    assert "execute_python_code" in tool_names, f"execute_python_code not found in tools: {tool_names}"


@pytest.mark.asyncio
async def test_main_agent_has_all_required_tools():
    """
    Тест: Проверяет, что MainAgent имеет все необходимые инструменты.
    """
    from src.agents.main_agent import MainAgent
    
    # Create agent
    agent = MainAgent()
    tools = agent.get_tools()
    tool_names = [t.name for t in tools]
    
    # Verify required tools
    assert "get_all_sheets_data" in tool_names, f"get_all_sheets_data not in MainAgent tools"
    assert "execute_python_code" in tool_names, f"execute_python_code not in MainAgent tools"
    
    print(f"\nMainAgent has {len(tool_names)} tools total")
    print(f"Sheets-related tools: {[n for n in tool_names if 'sheet' in n.lower()]}")
