"""
TDD: Тест для получения загрузки ресурсов из Project Lad.

Тест должен упасть на первом запуске (Red), потом мы реализуем код (Green).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.mcp_tools.projectlad_tools import GetResourceUtilizationTool


@pytest.mark.asyncio
async def test_get_resource_utilization_tool_exists():
    """
    Тест 1: Tool GetResourceUtilizationTool должен существовать.
    
    ОЖИДАЕТСЯ: Провал - tool еще не создан.
    """
    tool = GetResourceUtilizationTool()
    assert tool.name == "projectlad_get_resource_utilization"
    assert "resource" in tool.description.lower()


@pytest.mark.asyncio
async def test_get_resource_utilization_returns_data():
    """
    Тест 2: Tool должен вернуть данные о загрузке ресурсов.
    
    ОЖИДАЕТСЯ: Провал - метод _arun еще не реализован.
    """
    # Мокаем MCP manager
    mock_result = {
        "result": {
            "work_1": [
                {
                    "start_date": "2025-06-01T00:00:00.000Z",
                    "end_date": "2025-06-11T00:00:00.000Z",
                    "value": 8,
                    "resource_id": "res_123",
                    "analytics_element_id": "res_123"
                }
            ]
        }
    }
    
    tool = GetResourceUtilizationTool()
    
    # Мокаем вызов MCP
    with patch('src.mcp_tools.projectlad_tools.get_mcp_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.call_tool = AsyncMock(return_value=mock_result)
        mock_get_manager.return_value = mock_manager
        
        result = await tool._arun(
            project_id="test_project",
            version_id="test_version"
        )
        
        # Проверяем, что результат не пустой
        assert result is not None
        assert len(result) > 0
        # Проверяем, что в результате есть информация о ресурсах
        assert "resource" in result.lower() or "загрузка" in result.lower()


@pytest.mark.asyncio
async def test_get_resource_utilization_aggregates_by_month():
    """
    Тест 3: Tool должен агрегировать часы по месяцам.
    
    Входные данные:
    - Ресурс "Иванов": 8ч/день с 2025-06-01 по 2025-06-10 (10 дней = 80ч в июне)
    - Ресурс "Иванов": 8ч/день с 2025-07-01 по 2025-07-05 (5 дней = 40ч в июле)
    
    ОЖИДАЕТСЯ: Провал - логика агрегации еще не реализована.
    """
    mock_result = {
        "result": {
            "work_1": [
                {
                    "start_date": "2025-06-01T00:00:00.000Z",
                    "end_date": "2025-06-11T00:00:00.000Z",  # 10 дней
                    "value": 8,
                    "resource_id": "res_ivanov",
                    "analytics_element_id": "res_ivanov"
                },
                {
                    "start_date": "2025-07-01T00:00:00.000Z",
                    "end_date": "2025-07-06T00:00:00.000Z",  # 5 дней
                    "value": 8,
                    "resource_id": "res_ivanov",
                    "analytics_element_id": "res_ivanov"
                }
            ]
        }
    }
    
    # Мокаем также analytics для получения имен ресурсов
    mock_analytics = {
        "result": [
            {
                "indicator_title": "Ресурсы",
                "indicator_id": "ind_123",
                "analytics_element_id": "res_ivanov",
                "analytic_title": "Иванов Иван"
            }
        ]
    }
    
    tool = GetResourceUtilizationTool()
    
    with patch('src.mcp_tools.projectlad_tools.get_mcp_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        
        # Настраиваем мок для разных вызовов
        import json
        async def mock_call_tool(tool_name, args, server_name=None):
            if "resource-utilization" in tool_name or "resource_utilization" in tool_name:
                return json.dumps(mock_result)
            elif "indicator-analytics" in tool_name or "analytics" in tool_name:
                return json.dumps(mock_analytics)
            return json.dumps({})
        
        mock_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        mock_get_manager.return_value = mock_manager
        
        result = await tool._arun(
            project_id="test_project",
            version_id="test_version"
        )
        
        # Проверяем агрегацию по месяцам
        # Ожидаем: Иванов Иван - Июнь 2025: 80ч, Июль 2025: 40ч
        assert "Иванов Иван" in result or "Иванов" in result
        assert "Июнь" in result or "июнь" in result or "2025-06" in result
        assert "80" in result  # 10 дней * 8 часов
        assert "40" in result  # 5 дней * 8 часов


@pytest.mark.asyncio
async def test_get_resource_utilization_handles_cross_month_periods():
    """
    Тест 4: Tool должен правильно обрабатывать периоды на стыке месяцев.
    
    Входные данные:
    - Ресурс "Петров": 8ч/день с 2025-06-25 по 2025-07-05
      - В июне: 6 дней (25-30) = 48ч
      - В июле: 5 дней (1-5) = 40ч
    
    ОЖИДАЕТСЯ: Провал - логика split по месяцам еще не реализована.
    """
    mock_result = {
        "result": {
            "work_1": [
                {
                    "start_date": "2025-06-25T00:00:00.000Z",
                    "end_date": "2025-07-06T00:00:00.000Z",
                    "value": 8,
                    "resource_id": "res_petrov",
                    "analytics_element_id": "res_petrov"
                }
            ]
        }
    }
    
    mock_analytics = {
        "result": [
            {
                "indicator_title": "Ресурсы",
                "analytics_element_id": "res_petrov",
                "analytic_title": "Петров Петр"
            }
        ]
    }
    
    tool = GetResourceUtilizationTool()
    
    with patch('src.mcp_tools.projectlad_tools.get_mcp_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        
        import json
        async def mock_call_tool(tool_name, args, server_name=None):
            if "resource-utilization" in tool_name or "resource_utilization" in tool_name:
                return json.dumps(mock_result)
            elif "indicator-analytics" in tool_name or "analytics" in tool_name:
                return json.dumps(mock_analytics)
            return json.dumps({})
        
        mock_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        mock_get_manager.return_value = mock_manager
        
        result = await tool._arun(
            project_id="test_project",
            version_id="test_version"
        )
        
        # Проверяем split по месяцам
        assert "Петров" in result
        # В июне должно быть ~48 часов (6 дней * 8)
        # В июле должно быть ~40 часов (5 дней * 8)
        assert "48" in result or "40" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
