"""
Debug test for parallel execution - Phase 2, Step 3.

Tests if parallel execution actually works and logs timing information.
"""
import pytest
import asyncio
import time
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import MockWebSocketManager, create_test_engine
from src.core.context_manager import ConversationContext
from src.core.capability_registry import CapabilityRegistry
from src.core.task_decomposer import TaskDecomposer, SubTask
from src.core.dependency_analyzer import DependencyAnalyzer
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Debug log path
DEBUG_LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"


def _write_log(msg: str, data: dict = None):
    """Helper to write debug log."""
    try:
        import json
        log_entry = {
            "id": f"log_{int(time.time()*1000)}",
            "timestamp": int(time.time()*1000),
            "location": "test_parallel_execution_debug.py",
            "message": msg,
            "data": data or {},
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.warning(f"Failed to write debug log: {e}")


@pytest.fixture
def mock_registry_with_slow_tools():
    """Registry with tools that take time to execute (to test parallelism)."""
    registry = CapabilityRegistry()
    
    async def mock_list_emails(capability_name: str, arguments: dict):
        _write_log("list_emails started", {"capability": capability_name})
        start_time = time.time()
        await asyncio.sleep(1.0)  # Simulate 1 second delay
        duration = time.time() - start_time
        _write_log("list_emails completed", {"duration": duration})
        return {"emails": [{"id": "1", "subject": "Test"}]}
    
    async def mock_get_calendar_events(capability_name: str, arguments: dict):
        _write_log("get_calendar_events started", {"capability": capability_name})
        start_time = time.time()
        await asyncio.sleep(1.0)  # Simulate 1 second delay
        duration = time.time() - start_time
        _write_log("get_calendar_events completed", {"duration": duration})
        return {"events": [{"id": "1", "title": "Meeting"}]}
    
    async def mock_list_files(capability_name: str, arguments: dict):
        _write_log("list_files started", {"capability": capability_name})
        start_time = time.time()
        await asyncio.sleep(1.0)  # Simulate 1 second delay
        duration = time.time() - start_time
        _write_log("list_files completed", {"duration": duration})
        return {"files": [{"id": "1", "name": "test.docx"}]}
    
    async def mock_execute(capability_name: str, arguments: dict):
        if capability_name == "list_emails":
            return await mock_list_emails(capability_name, arguments)
        elif capability_name == "get_calendar_events":
            return await mock_get_calendar_events(capability_name, arguments)
        elif capability_name == "list_files":
            return await mock_list_files(capability_name, arguments)
        else:
            return {"result": "success"}
    
    registry.execute = mock_execute
    return registry


def _write_log(msg: str, data: dict = None):
    """Helper to write debug log."""
    try:
        import json
        log_entry = {
            "id": f"log_{int(time.time()*1000)}",
            "timestamp": int(time.time()*1000),
            "location": "test_parallel_execution_debug.py",
            "message": msg,
            "data": data or {},
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.warning(f"Failed to write debug log: {e}")


@pytest.mark.asyncio
async def test_parallel_execution_timing(mock_ws_manager, mock_registry_with_slow_tools):
    """Test: Parallel execution should be faster than sequential."""
    _write_log("test_start", {"query": "Покажи фокус на сегодня"})
    
    engine = create_test_engine(mock_ws_manager, mock_registry_with_slow_tools)
    context = ConversationContext(session_id="test-session")
    
    # Test decomposition
    decomposer = engine.task_decomposer
    decomposition = await decomposer.decompose("Покажи фокус на сегодня")
    
    _write_log("decomposition_result", {
        "subtasks_count": len(decomposition.subtasks),
        "subtasks": [{"id": st.task_id, "tool": st.tool_name, "deps": st.dependencies} for st in decomposition.subtasks]
    })
    
    # Test dependency analysis
    analyzer = engine.dependency_analyzer
    execution_plan = analyzer.analyze(decomposition.subtasks)
    
    _write_log("execution_plan", {
        "groups_count": len(execution_plan.execution_groups),
        "groups": execution_plan.execution_groups,
        "types": execution_plan.group_types
    })
    
    # Test parallel execution if method exists
    if hasattr(engine, '_execute_parallel_subtasks'):
        _write_log("parallel_exec_start", {})
        
        # Get parallel group subtasks
        if execution_plan.execution_groups:
            first_group = execution_plan.execution_groups[0]
            parallel_subtasks = [st for st in decomposition.subtasks if st.task_id in first_group and not st.is_synthesis]
            
            if len(parallel_subtasks) >= 2:
                _write_log("before_parallel_exec", {
                    "subtasks_count": len(parallel_subtasks),
                    "subtask_tools": [st.tool_name for st in parallel_subtasks]
                })
                
                start_time = time.time()
                results = await engine._execute_parallel_subtasks(parallel_subtasks, context)
                duration = time.time() - start_time
                
                _write_log("parallel_exec_end", {
                    "duration": duration,
                    "tasks_count": len(parallel_subtasks),
                    "results_count": len(results),
                    "expected_max_duration": 2.0
                })
                
                # Parallel execution should be ~1x slower than single task, not Nx
                # If 3 tasks each take 1s, parallel should be ~1s, sequential would be ~3s
                print(f"\n[TEST] Parallel execution duration: {duration:.2f}s for {len(parallel_subtasks)} tasks")
                print(f"[TEST] Expected: <2.0s (if sequential would be ~{len(parallel_subtasks)}s)")
                
                assert duration < 2.0, f"Parallel execution took {duration}s, expected <2s for {len(parallel_subtasks)} tasks (sequential would be ~{len(parallel_subtasks)}s)"
                assert len(results) == len(parallel_subtasks)
    else:
        _write_log("no_parallel_method", {"hasattr": hasattr(engine, '_execute_parallel_subtasks')})


@pytest.mark.asyncio
async def test_is_multi_tool_query_detection(mock_ws_manager):
    """Test: _is_multi_tool_query correctly detects multi-tool queries."""
    engine = create_test_engine(mock_ws_manager, CapabilityRegistry())
    
    _write_log("test_detection_start", {})
    
    # Test queries
    test_queries = [
        ("Покажи фокус на сегодня", True),
        ("Проверь почту и календарь", True),
        ("Покажи письма", False),
        ("Сводка: почта и календарь", True),
    ]
    
    for query, expected in test_queries:
        result = engine._is_multi_tool_query(query)
        _write_log("query_check", {"query": query, "expected": expected, "actual": result})
        assert result == expected, f"Query '{query}' detection failed: expected {expected}, got {result}"
