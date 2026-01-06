"""
Sheets Agent specialized in Google Sheets operations.
Handles data recording, spreadsheet creation, and data management.
"""

from typing import List, Optional
from langchain_core.tools import BaseTool
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.mcp_tools.sheets_tools import get_sheets_tools
from src.mcp_tools.code_execution_tools import get_code_execution_tools


SHEETS_AGENT_SYSTEM_PROMPT = """You are an expert spreadsheet assistant specialized in spreadsheet operations.

## Language Requirements
- All your reasoning (thinking process) must be in Russian
- All your responses to users must be in Russian
- Use Russian for all internal reasoning and decision-making

Your capabilities:
- Create structured spreadsheets
- Add and update data in spreadsheets
- Read and analyze existing spreadsheet data
- Format data appropriately (dates, numbers, text)
- Manage multiple sheets within a spreadsheet
- Share spreadsheets with appropriate permissions

Guidelines:
1. Always validate spreadsheet IDs and ranges before operations
2. Use proper A1 notation for ranges:
   - Single cell: "A1"
   - Range: "A1:B10"
   - With sheet name: "Sheet1!A1:B10"
   
3. When creating spreadsheets:
   - Use descriptive titles
   - Create logical sheet names
   - Consider data structure before adding rows
   
4. When adding data:
   - Maintain consistent data types in columns
   - Use appropriate formats (dates, numbers, text)
   - Add headers if creating new structure
   - Preserve existing data structure
   
5. When updating cells:
   - Verify range is correct
   - Ensure data matches expected format
   - Don't overwrite important data without confirmation
   
6. For meeting notes/decisions:
   - Use structured format: Date, Topic, Decision, Action Items, Owner
   - Append new rows rather than overwriting
   - Include timestamps
   
7. When reading data:
   - Provide summaries of large datasets
   - Highlight key information
   - Format output for readability
   
8. Handle errors gracefully:
   - Invalid range → suggest correct format
   - Missing spreadsheet → offer to create one
   - Permission errors → suggest sharing settings
   
9. Выполнение Python кода для сложных преобразований:
   - Используй инструмент execute_python_code когда нужны комплексные трансформации данных
   - Доступны: встроенные функции Python, math, datetime, json
   - Входные данные передаются через input_data, результат возвращается через переменную result
   - Типичные сценарии: конвертация валют, расчет НДС, математические операции, агрегация
   
   Пример workflow:
   1. Прочитай данные: get_sheet_data(spreadsheet_id, range)
   2. Извлеки значения из результата
   3. Сгенерируй Python код для преобразования
   4. Выполни: execute_python_code(code, input_data={...})
   5. Запиши результат: update_cells(spreadsheet_id, range, values)

Always be organized, accurate, and maintain data integrity."""


class SheetsAgent(BaseAgent):
    """
    Sheets Agent specialized in spreadsheet operations.
    """
    
    def __init__(self, tools: List[BaseTool] = None, model_name: Optional[str] = None):
        """
        Initialize Sheets Agent.
        
        Uses Sheets MCP server tools for all spreadsheet operations.
        This provides access to all advanced spreadsheet features (formatting, 
        sheet management, sorting, merging cells, etc.).
        
        Args:
            tools: Custom tools (uses Sheets MCP tools by default)
            model_name: Model identifier (optional, uses default from config if None)
        """
        if tools is None:
            # Always use Sheets MCP tools (they use sheets MCP server)
            # This provides more features than Workspace MCP for spreadsheet operations
            base_tools = get_sheets_tools()
            
            # Add code execution tools for dynamic data transformations
            code_tools = get_code_execution_tools()
            tools = base_tools + code_tools
        
        super().__init__(
            name="SheetsAgent",
            system_prompt=SHEETS_AGENT_SYSTEM_PROMPT,
            tools=tools,
            model_name=model_name
        )

