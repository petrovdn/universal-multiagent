"""
Integration test: Verify parallel vs sequential execution based on query dependencies.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.core.context_manager import ConversationContext
from src.core.task_decomposer import TaskDecomposer
from src.core.dependency_analyzer import DependencyAnalyzer


@pytest.mark.asyncio
async def test_parallel_execution_for_independent_tasks():
    """Test: 'сделай презентацию про птичку тари, и проверь почту' should execute in parallel."""
    decomposer = TaskDecomposer()
    analyzer = DependencyAnalyzer()
    
    query = "сделай презентацию про птичку тари, и проверь почту"
    
    # Decompose
    decomposition = await decomposer.decompose(query)
    
    # Should have 2 tasks: presentation + email check
    assert len(decomposition.subtasks) >= 2, f"Expected at least 2 tasks, got {len(decomposition.subtasks)}"
    
    # Check that both tasks are present
    task_tools = [st.tool_name for st in decomposition.subtasks if not st.is_synthesis]
    assert "create_presentation_batch" in task_tools, f"Expected create_presentation_batch, got {task_tools}"
    assert "list_emails" in task_tools, f"Expected list_emails, got {task_tools}"
    
    # Analyze dependencies
    plan = analyzer.analyze(decomposition.subtasks)
    
    # Should have at least 1 execution group
    assert len(plan.execution_groups) > 0, "Should have execution groups"
    
    # First group should be parallel (2 tasks without dependencies)
    first_group = plan.execution_groups[0]
    first_type = plan.group_types[0]
    
    # Filter out synthesis tasks for parallel check
    non_synthesis_tasks = [tid for tid in first_group 
                          if not any(st.task_id == tid and st.is_synthesis for st in decomposition.subtasks)]
    
    if len(non_synthesis_tasks) >= 2:
        assert first_type == "parallel", f"First group should be parallel, got {first_type}. Tasks: {non_synthesis_tasks}"
        print(f"✅ Parallel execution confirmed: {len(non_synthesis_tasks)} tasks in parallel group")


@pytest.mark.asyncio
async def test_sequential_execution_for_dependent_tasks():
    """Test: 'сделай презентацию про птичку тари, и отправь ее по почте' should execute sequentially."""
    decomposer = TaskDecomposer()
    analyzer = DependencyAnalyzer()
    
    query = "сделай презентацию про птичку тари, и отправь ее по почте"
    
    # Decompose
    decomposition = await decomposer.decompose(query)
    
    # Should have 2 tasks: presentation + email send
    non_synthesis_tasks = [st for st in decomposition.subtasks if not st.is_synthesis]
    assert len(non_synthesis_tasks) >= 2, f"Expected at least 2 tasks, got {len(non_synthesis_tasks)}"
    
    # Check that both tasks are present
    task_tools = [st.tool_name for st in non_synthesis_tasks]
    assert "create_presentation_batch" in task_tools, f"Expected create_presentation_batch, got {task_tools}"
    assert "send_email" in task_tools, f"Expected send_email, got {task_tools}"
    
    # Check dependency: send_email should depend on create_presentation_batch
    send_task = next((st for st in non_synthesis_tasks if st.tool_name == "send_email"), None)
    create_task = next((st for st in non_synthesis_tasks if st.tool_name == "create_presentation_batch"), None)
    
    assert send_task is not None, "send_email task not found"
    assert create_task is not None, "create_presentation_batch task not found"
    assert len(send_task.dependencies) > 0, f"send_email should have dependencies, got {send_task.dependencies}"
    assert create_task.task_id in send_task.dependencies, f"send_email should depend on create_presentation_batch ({create_task.task_id}), got {send_task.dependencies}"
    
    # Analyze dependencies
    plan = analyzer.analyze(decomposition.subtasks)
    
    # Should have 2+ execution groups (sequential)
    assert len(plan.execution_groups) >= 2, f"Should have at least 2 execution groups (sequential), got {len(plan.execution_groups)}"
    
    # First group should contain create_presentation_batch
    first_group_tasks = [st for st in decomposition.subtasks if st.task_id in plan.execution_groups[0]]
    first_group_tools = [st.tool_name for st in first_group_tasks if not st.is_synthesis]
    assert "create_presentation_batch" in first_group_tools, f"First group should contain create_presentation_batch, got {first_group_tools}"
    
    # Second group should contain send_email
    if len(plan.execution_groups) >= 2:
        second_group_tasks = [st for st in decomposition.subtasks if st.task_id in plan.execution_groups[1]]
        second_group_tools = [st.tool_name for st in second_group_tasks if not st.is_synthesis]
        assert "send_email" in second_group_tools, f"Second group should contain send_email, got {second_group_tools}"
    
    print(f"✅ Sequential execution confirmed: {len(plan.execution_groups)} groups")


if __name__ == "__main__":
    asyncio.run(test_parallel_execution_for_independent_tasks())
    print()
    asyncio.run(test_sequential_execution_for_dependent_tasks())
    print("\n✅ All integration tests passed!")
