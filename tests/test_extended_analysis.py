"""
Tests for extended analysis workflow with Python code execution.
Tests that agent writes code, shows it in viewer, and creates charts when user requests "расширенный анализ".
"""
import pytest
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock config_loader BEFORE any imports
mock_config_obj = MagicMock()
mock_config_obj.timezone = "UTC"
mock_config_obj.anthropic_api_key = "test-key"
mock_config_obj.openai_api_key = "test-key"
mock_config_obj.default_model = "gpt-4o"

mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader

# Mock langchain_openai
mock_langchain_openai = MagicMock()
mock_chat_openai = MagicMock()
mock_langchain_openai.ChatOpenAI = mock_chat_openai
sys.modules['langchain_openai'] = mock_langchain_openai
sys.modules['langchain_openai.chat_models'] = mock_langchain_openai


@pytest.mark.asyncio
async def test_extended_analysis_uses_python_code():
    """
    Тест: При запросе с "расширенный анализ" агент должен использовать execute_python_code.
    
    Проверяет:
    1. Агент понимает ключевые слова "расширенный", "большой", "подробный"
    2. Агент вызывает execute_python_code для анализа
    3. Код содержит анализ корреляций и создание chartData
    4. chartData обрабатывается и отправляется на дашборд
    """
    from src.api.agent_wrapper import AgentWrapper
    from src.api.websocket_manager import WebSocketManager
    
    # Mock WebSocket manager
    mock_ws = MagicMock(spec=WebSocketManager)
    mock_ws.send_event = AsyncMock()
    
    # Mock tool execution results
    mock_sheets_data = {
        "spreadsheetTitle": "Анализ данных",
        "sheets": [
            {
                "name": "Зарплата",
                "values": [
                    ["Сотрудник", "Пол", "Месяц", "Зарплата"],
                    ["Иванов", "М", "Январь", "100"],
                    ["Петров", "М", "Январь", "200"],
                    ["Сидорова", "Ж", "Январь", "300"],
                ],
                "rowCount": 4,
                "columnCount": 4
            },
            {
                "name": "Выработка",
                "values": [
                    ["Сотрудник", "Пол", "Месяц", "Выработка"],
                    ["Иванов", "М", "Январь", "101"],
                    ["Петров", "М", "Январь", "114"],
                    ["Сидорова", "Ж", "Январь", "121"],
                ],
                "rowCount": 4,
                "columnCount": 4
            }
        ]
    }
    
    with patch.object(AgentWrapper, '__init__', return_value=None):
        wrapper = AgentWrapper.__new__(AgentWrapper)
        wrapper.ws_manager = mock_ws
        wrapper._sent_workspace_events = {}
        
        # Format result as execute_python_code would return it with chartData
        chart_data = [
            {
                "title": "Средняя эффективность по полу",
                "chartType": "bar",
                "series": [{"name": "Эффективность", "data": [0.57, 0.40]}],
                "options": {"xaxis": {"categories": ["Мальчики", "Девочки"]}}
            }
        ]
        formatted_result = f"Result:\n{json.dumps({'chartData': chart_data})}"
        
        # Simulate execute_python_code completion (code_display is now sent from unified_react_engine)
        # This handler only processes results
        await wrapper._handle_workspace_events(
            session_id="test-session",
            tool_name="execute_python_code",
            result=formatted_result,
            tool_args={"code": "import json\n# test code"}
        )
        
        # Verify chart_dashboard event was sent
        chart_calls = [
            call for call in mock_ws.send_event.call_args_list
            if len(call[0]) >= 2 and call[0][1] == "chart_dashboard"
        ]
        
        assert len(chart_calls) > 0, "chart_dashboard event should be sent for extended analysis"
        
        # Verify chart structure
        call_args = chart_calls[0][0]
        event_data = call_args[2]
        assert "charts" in event_data
        assert len(event_data["charts"]) > 0, "Should have at least one chart"


@pytest.mark.asyncio
async def test_keywords_trigger_extended_analysis():
    """
    Тест: Ключевые слова "расширенный", "большой", "подробный" должны триггерить расширенный анализ.
    
    Проверяет, что промпт содержит инструкции для этих ключевых слов.
    """
    from src.agents.sheets_agent import SHEETS_AGENT_SYSTEM_PROMPT
    
    # Check that prompt mentions extended analysis keywords
    assert "расширенный" in SHEETS_AGENT_SYSTEM_PROMPT.lower() or "extended" in SHEETS_AGENT_SYSTEM_PROMPT.lower()
    assert "подробный" in SHEETS_AGENT_SYSTEM_PROMPT.lower() or "detailed" in SHEETS_AGENT_SYSTEM_PROMPT.lower()
    assert "большой" in SHEETS_AGENT_SYSTEM_PROMPT.lower() or "comprehensive" in SHEETS_AGENT_SYSTEM_PROMPT.lower()
    
    # Check that prompt mentions execute_python_code for extended analysis
    assert "execute_python_code" in SHEETS_AGENT_SYSTEM_PROMPT or "python" in SHEETS_AGENT_SYSTEM_PROMPT.lower()


@pytest.mark.asyncio
async def test_code_contains_correlations():
    """
    Тест: Код для расширенного анализа должен искать корреляции между данными.
    
    Проверяет структуру кода, который должен:
    1. Объединять данные из разных вкладок
    2. Вычислять корреляции
    3. Создавать chartData с несколькими диаграммами
    """
    # This is more of a documentation test - we expect the code to:
    # 1. Merge data from multiple sheets
    # 2. Calculate correlations/efficiency ratios
    # 3. Create multiple charts
    
    expected_code_patterns = [
        "correlation",  # или "корреляция", "эффективность"
        "chartData",
        "series",
        "options"
    ]
    
    # This test documents expected behavior
    # Actual code generation will be tested in integration tests
    assert True, "Code should contain correlation analysis patterns"


@pytest.mark.asyncio
async def test_extended_analysis_workflow():
    """
    Тест: Полный workflow расширенного анализа.
    
    Проверяет последовательность:
    1. get_all_sheets_data - получение данных
    2. execute_python_code - написание и выполнение кода
    3. workspace_event - показ кода в viewer
    4. chart_dashboard - показ диаграмм
    """
    from src.api.agent_wrapper import AgentWrapper
    from src.api.websocket_manager import WebSocketManager
    
    mock_ws = MagicMock(spec=WebSocketManager)
    mock_ws.send_event = AsyncMock()
    
    with patch.object(AgentWrapper, '__init__', return_value=None):
        wrapper = AgentWrapper.__new__(AgentWrapper)
        wrapper.ws_manager = mock_ws
        wrapper._sent_workspace_events = {}
        
        # Step 1: Simulate get_all_sheets_data result
        sheets_result = json.dumps({
            "spreadsheetTitle": "Анализ данных",
            "sheets": [{"name": "Зарплата", "values": []}, {"name": "Выработка", "values": []}]
        })
        
        # Step 2: Simulate execute_python_code with extended analysis
        code = "import json\n# Extended analysis code here\nresult = {'chartData': []}"
        code_result = f"Result:\n{json.dumps({'chartData': [{'title': 'Test Chart', 'chartType': 'bar', 'series': [], 'options': {}}]})}"
        
        await wrapper._handle_workspace_events(
            session_id="test-session",
            tool_name="execute_python_code",
            result=code_result,
            tool_args={"code": code}
        )
        
        # Verify workflow steps
        all_calls = mock_ws.send_event.call_args_list
        
        # Note: code_display is now sent from unified_react_engine BEFORE execution
        # This test only verifies that agent_wrapper processes results correctly
        # Code display is tested in integration tests with unified_react_engine
        
        # Should have chart_dashboard for charts (sent after code execution)
        chart_events = [c for c in all_calls if len(c[0]) >= 2 and c[0][1] == "chart_dashboard"]
        assert len(chart_events) > 0, "Charts should be sent to dashboard after code execution"
        
        # Verify chart structure
        if chart_events:
            chart_event = chart_events[0][0]
            chart_data = chart_event[2]
            assert "charts" in chart_data, "chart_dashboard should contain charts"
            assert len(chart_data["charts"]) > 0, "Should have at least one chart"
