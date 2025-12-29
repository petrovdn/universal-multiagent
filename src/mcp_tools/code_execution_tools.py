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
    
    Available libraries: math, datetime, json
    
    Input:
    - code: Python code to execute
    - input_data: Optional dict with input data (accessible as 'data' variable)
    - timeout: Execution timeout (default: 30s)
    
    The code should assign result to 'result' variable.
    
    Example:
    ```python
    # Convert prices from USD to RUB with VAT
    prices_usd = data['prices']
    rate = 95
    vat = 1.2
    result = [round(price * rate * vat, 2) for price in prices_usd]
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
                'data': input_data or {},
                'result': None
            }
            
            # Capture output
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            
            # Execute with timeout
            def execute_code():
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, safe_globals)
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
            
            return "\n\n".join(response_parts)
            
        except ToolExecutionError:
            # Re-raise tool execution errors
            raise
        except Exception as e:
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

