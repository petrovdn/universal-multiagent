"""
Python Code Execution Tool for dynamic data transformations.
Allows AI to generate and execute Python code for data processing tasks.
"""

from typing import Optional, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
import math
import statistics
from datetime import datetime
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from src.utils.exceptions import ToolExecutionError


class PythonCodeExecutionInput(BaseModel):
    """Input schema for Python code execution tool."""
    
    code: str = Field(description="Python code to execute")
    input_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Input data available as 'data' variable in code"
    )
    timeout: int = Field(default=30, description="Execution timeout in seconds")


class PythonCodeExecutionTool(BaseTool):
    """
    Tool for safe Python code execution.
    Allows AI to generate and run Python code for data transformations.
    """
    
    name: str = "execute_python_code"
    description: str = """
    Execute Python code for data transformations and computations.
    
    Use this when you need to:
    - Transform spreadsheet data (currency conversion, calculations, etc.)
    - Perform complex mathematical operations
    - Process arrays/lists with custom logic
    - Generate data based on patterns
    - Analyze data and create visualizations (chartData)
    
    ⚠️ ВАЖНО: Доступные библиотеки ТОЛЬКО:
    - math (математические функции)
    - datetime (работа с датами)
    - json (работа с JSON)
    - statistics (статистические функции: mean, median, stdev, etc.)
    
    ❌ НЕ используй pandas, numpy, matplotlib, seaborn - они НЕ доступны!
    ✅ Используй встроенные типы Python: list, dict, set, tuple
    ✅ Используй statistics для статистических расчетов
    ✅ Используй math для математических операций
    
    Input:
    - code: Python code to execute
    - input_data: Optional dict with input data (accessible as 'data' variable)
    - timeout: Execution timeout (default: 30s)
    
    The code should assign result to 'result' variable.
    
    Example for data analysis:
    ```python
    import json
    import statistics
    
    # Parse sheets data
    sheets_data = data.get("sheets", [])
    # ... analysis code ...
    result = {
        "chartData": [...],  # For visualizations
        "analysis": {...}    # Text analysis results
    }
    ```
    """
    args_schema: type = PythonCodeExecutionInput
    
    async def _arun(
        self,
        code: str,
        input_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> str:
        """Execute Python code in controlled environment."""
        # #region agent log
        try:
            import time as _time_module
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                sheets_list = input_data.get('sheets', []) if input_data else []
                sheets_count = len(sheets_list)
                # Debug: структура каждого sheet + уникальные значения в колонках
                sheets_info = []
                for sheet in sheets_list[:3]:  # Первые 3 листа
                    if isinstance(sheet, dict):
                        data_rows = sheet.get('data', [])
                        headers = sheet.get('headers', [])
                        # Собираем уникальные значения для каждой колонки (для диагностики фильтров)
                        unique_vals = {}
                        for h in headers[:5]:
                            vals = set()
                            for row in data_rows[:10]:
                                if isinstance(row, dict) and h in row:
                                    vals.add(str(row[h]))
                            unique_vals[h] = list(vals)[:5]
                        sheets_info.append({
                            "name": sheet.get('name', 'unknown'),
                            "headers": headers,
                            "rows_count": len(data_rows),
                            "unique_values_sample": unique_vals
                        })
                f.write(json.dumps({
                    "timestamp": int(_time_module.time() * 1000),
                    "location": "code_execution_tools.py:_arun:entry",
                    "message": "execute_python_code called",
                    "data": {
                        "has_input_data": input_data is not None,
                        "sheets_count": sheets_count,
                        "sheets_info": sheets_info,
                        "code_length": len(code),
                        "code_full": code  # Полный код для анализа
                    },
                    "sessionId": "debug-session",
                    "hypothesisId": "CODE1"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        try:
            # Prepare execution environment
            # Only allow safe built-ins and libraries
            safe_globals = {
                '__builtins__': {
                    '__import__': __import__,  # Needed for 'import' statements
                    'abs': abs,
                    'all': all,
                    'any': any,
                    'bool': bool,
                    'dict': dict,
                    'enumerate': enumerate,
                    'float': float,
                    'int': int,
                    'len': len,
                    'list': list,
                    'max': max,
                    'min': min,
                    'print': print,  # Added for debugging and output
                    'range': range,
                    'round': round,
                    'sorted': sorted,
                    'str': str,
                    'sum': sum,
                    'tuple': tuple,
                    'zip': zip,
                    'map': map,
                    'filter': filter,
                    'iter': iter,
                    'next': next,
                    'reversed': reversed,
                    'set': set,
                    'frozenset': frozenset,
                },
                'math': math,
                'datetime': datetime,
                'json': json,
                'statistics': statistics,  # For mean, median, stdev, etc.
                'data': input_data or {},
                'input_data': input_data or {},  # Alias for compatibility
                'result': None
            }
            
            # Capture output
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            
            # Execute with timeout
            def execute_code():
                # #region agent log
                try:
                    import time as _time_module
                    import traceback as _tb
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({
                            "timestamp": int(_time_module.time() * 1000),
                            "location": "code_execution_tools.py:execute_code:before_exec",
                            "message": "About to exec code",
                            "data": {
                                "data_in_globals": "data" in safe_globals,
                                "data_type": type(safe_globals.get('data')).__name__,
                                "data_is_dict": isinstance(safe_globals.get('data'), dict),
                                "data_keys": list(safe_globals.get('data', {}).keys()) if isinstance(safe_globals.get('data'), dict) else None,
                                "sheets_type": type(safe_globals.get('data', {}).get('sheets')).__name__ if isinstance(safe_globals.get('data'), dict) else None,
                                "sheets_len": len(safe_globals.get('data', {}).get('sheets', [])) if isinstance(safe_globals.get('data'), dict) else None
                            },
                            "sessionId": "debug-session",
                            "hypothesisId": "CODE_EXEC1"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    try:
                        exec(code, safe_globals)
                    except Exception as exec_error:
                        # #region agent log
                        try:
                            import time as _time_module
                            import traceback as _tb
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "timestamp": int(_time_module.time() * 1000),
                                    "location": "code_execution_tools.py:execute_code:exec_error",
                                    "message": "Exec raised exception",
                                    "data": {
                                        "error": str(exec_error),
                                        "error_type": type(exec_error).__name__,
                                        "traceback": _tb.format_exc()[:500]
                                    },
                                    "sessionId": "debug-session",
                                    "hypothesisId": "CODE_EXEC2"
                                }) + "\n")
                        except Exception:
                            pass
                        # #endregion
                        raise
                return safe_globals.get('result')
            
            # Run with timeout using asyncio
            try:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, execute_code),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                raise ToolExecutionError(
                    f"Code execution timeout after {timeout} seconds",
                    tool_name=self.name
                )
            
            # Get captured output
            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()
            
            # Auto-fallback: если result не присвоен, проверяем safe_globals
            if result is None:
                # Пытаемся найти что-то полезное в safe_globals (кроме служебных переменных)
                excluded_keys = {'__builtins__', '__name__', '__doc__', '__package__', 'data', 'result'}
                useful_vars = {k: v for k, v in safe_globals.items() 
                              if k not in excluded_keys 
                              and not k.startswith('_')
                              and v is not None}
                if useful_vars:
                    # Если есть полезные переменные, используем их как результат
                    result = useful_vars if len(useful_vars) > 1 else list(useful_vars.values())[0]
            
            # Format response
            response_parts = []
            
            if result is not None:
                # Try to serialize result
                try:
                    if isinstance(result, (list, dict, str, int, float, bool)):
                        # For simple types, try JSON serialization
                        try:
                            result_str = json.dumps(result, ensure_ascii=False, indent=2)
                            response_parts.append(f"Result:\n{result_str}")
                        except (TypeError, ValueError):
                            result_str = str(result)
                            response_parts.append(f"Result:\n{result_str}")
                    else:
                        result_str = str(result)
                        response_parts.append(f"Result:\n{result_str}")
                except Exception as e:
                    response_parts.append(f"Result: {str(result)} (serialization warning: {e})")
            
            if stdout_text:
                response_parts.append(f"Output:\n{stdout_text}")
            
            if stderr_text:
                response_parts.append(f"Errors:\n{stderr_text}")
            
            if not response_parts:
                response_parts.append("Code executed successfully (no result returned - make sure to assign result to 'result' variable)")
            
            final_response = "\n\n".join(response_parts)
            
            # #region agent log
            try:
                import time as _time_module
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    chart_data_info = []
                    if isinstance(result, dict) and 'chartData' in result:
                        for i, chart in enumerate(result['chartData'][:8]):
                            chart_info = {
                                "index": i,
                                "title": chart.get('title', 'no title'),
                                "chartType": chart.get('chartType', 'unknown'),
                                "series_count": len(chart.get('series', [])),
                            }
                            # Для bar/line - проверяем data в series
                            if isinstance(chart.get('series'), list) and len(chart.get('series', [])) > 0:
                                series0 = chart['series'][0]
                                if isinstance(series0, dict):
                                    chart_info["series0_name"] = series0.get('name')
                                    chart_info["series0_data"] = series0.get('data', [])[:5]
                                    chart_info["series0_data_len"] = len(series0.get('data', []))
                                else:
                                    # pie/donut - series is array of values
                                    chart_info["series_values"] = chart['series'][:5]
                            chart_data_info.append(chart_info)
                    f.write(json.dumps({
                        "timestamp": int(_time_module.time() * 1000),
                        "location": "code_execution_tools.py:_arun:success",
                        "message": "execute_python_code completed",
                        "data": {
                            "has_result": result is not None,
                            "result_type": type(result).__name__ if result else "None",
                            "chartData_count": len(result.get('chartData', [])) if isinstance(result, dict) else 0,
                            "charts_info": chart_data_info,
                            "response_length": len(final_response)
                        },
                        "sessionId": "debug-session",
                        "hypothesisId": "CODE2"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            return final_response
            
        except ToolExecutionError:
            # Re-raise tool execution errors
            raise
        except Exception as e:
            # #region agent log
            try:
                import time as _time_module
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "timestamp": int(_time_module.time() * 1000),
                        "location": "code_execution_tools.py:_arun:error",
                        "message": "execute_python_code failed",
                        "data": {
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "has_input_data": input_data is not None,
                            "sheets_count": len(input_data.get('sheets', [])) if input_data else 0
                        },
                        "sessionId": "debug-session",
                        "hypothesisId": "CODE3"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            raise ToolExecutionError(
                f"Code execution failed: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_code_execution_tools() -> list:
    """
    Get code execution tools.
    
    Returns:
        List of code execution tool instances
    """
    return [PythonCodeExecutionTool()]

