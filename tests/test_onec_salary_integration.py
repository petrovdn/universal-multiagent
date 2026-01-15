"""
Integration tests for 1C salary data retrieval (TDD approach).
Tests for getting salary data by employee and month from 1C accounting entries.

TDD: Эти тесты должны падать (Red) до реализации функционала.
"""
import pytest
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Mock config_loader BEFORE any imports to prevent PermissionError
mock_config_obj = MagicMock()
mock_config_obj.timezone = "UTC"
mock_config_obj.anthropic_api_key = "test-key"
mock_config_obj.openai_api_key = "test-key"
mock_config_obj.default_model = "gpt-4o"

mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader


@pytest.mark.asyncio
async def test_onec_salary_tool_exists():
    """
    Тест 1: Tool GetSalaryByEmployeeMonthTool должен существовать.
    
    ОЖИДАЕТСЯ: Провал - tool еще не создан.
    """
    from src.mcp_tools.onec_tools import GetSalaryByEmployeeMonthTool
    
    tool = GetSalaryByEmployeeMonthTool()
    assert tool.name == "onec_get_salary_by_employee_month"
    assert "salary" in tool.description.lower() or "зарплата" in tool.description.lower()


@pytest.mark.asyncio
async def test_onec_salary_tool_aggregates_by_month():
    """
    Тест: LangChain tool агрегирует проводки по месяцам и сотрудникам.
    
    Проверяем:
    - Группировка по месяцу (YYYY-MM)
    - Группировка по сотруднику (Employee_Key -> ФИО)
    - Суммирование Amount
    """
    from src.mcp_tools.onec_tools import GetSalaryByEmployeeMonthTool
    
    # Mock MCP manager
    mock_mcp_manager = AsyncMock()
    mock_result_data = {
        "period": {"from": "2025-01-01", "to": "2025-12-31"},
        "total_records": 2,
        "salary_by_employee_month": [
            {"month": "2025-01", "employee_name": "Иванов", "salary": 50000.0},
            {"month": "2025-01", "employee_name": "Петров", "salary": 45000.0}
        ]
    }
    
    # call_tool возвращает dict или строку JSON
    mock_mcp_manager.call_tool = AsyncMock(return_value=mock_result_data)
    
    tool = GetSalaryByEmployeeMonthTool()
    
    with patch('src.mcp_tools.onec_tools.get_mcp_manager', return_value=mock_mcp_manager):
        # Act
        result = await tool._arun(
            from_date="2025-01-01",
            to_date="2025-12-31"
        )
        
        # Assert
        assert isinstance(result, str)
        assert "2025-01" in result
        assert "Иванов" in result or "ivanov" in result.lower()
        assert "50000" in result or "50,000" in result
        
        # Проверяем, что MCP tool был вызван
        mock_mcp_manager.call_tool.assert_called_once()
        call_args = mock_mcp_manager.call_tool.call_args
        assert call_args[0][0] == "onec_salary_by_employee_month"
        assert call_args[0][1]["from"] == "2025-01-01"
        assert call_args[0][1]["to"] == "2025-12-31"
        assert call_args[1]["server_name"] == "onec"


@pytest.mark.asyncio
async def test_salary_to_sheets_workflow():
    """
    Тест: Полный workflow - из 1С в Google Sheets.
    
    Проверяем:
    - Агент получает данные из 1С
    - Агент создает Google Sheets с правильной структурой
    - Данные корректно записаны
    
    Примечание: Этот тест может быть реализован позже, после интеграции с SheetsAgent.
    Пока что оставляем как placeholder для будущей реализации.
    """
    # Arrange
    from tests.conftest import MockWebSocketManager
    
    mock_ws = MockWebSocketManager()
    
    # Act
    # TODO: Реализовать полный workflow через MainAgent после интеграции
    # result = await agent.process(
    #     "Выгрузи зарплату сотрудников за 2025 год в таблицу",
    #     mock_ws
    # )
    
    # Assert
    # assert "spreadsheet" in result
    # assert result["spreadsheet"]["url"].startswith("https://docs.google.com/spreadsheets")
    
    # Пока что просто проверяем, что тест запускается
    assert mock_ws is not None
