"""
TDD tests for TaskDecomposer - Phase 2, Step 1.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import will fail initially - that's expected in TDD
from src.core.task_decomposer import TaskDecomposer, SubTask, DecompositionResult


class TestTaskDecomposer:
    """Test suite for TaskDecomposer."""
    
    @pytest.fixture
    def decomposer(self):
        """Fixture for TaskDecomposer."""
        return TaskDecomposer()
    
    @pytest.mark.asyncio
    async def test_decompose_multi_source_query(self, decomposer):
        """Test: Decompose query with multiple data sources."""
        result = await decomposer.decompose("Покажи мне фокус на сегодня")
        
        assert isinstance(result, DecompositionResult)
        assert len(result.subtasks) >= 3  # Gmail, Calendar, Drive минимум
        
        # Проверка наличия подзадач для разных источников
        tool_names = [st.tool_name.lower() for st in result.subtasks]
        assert any("email" in name or "gmail" in name for name in tool_names)
        assert any("calendar" in name or "event" in name for name in tool_names)
        
        # Проверка синтеза
        synthesis_tasks = [st for st in result.subtasks if st.is_synthesis]
        assert len(synthesis_tasks) == 1
        
        synthesis = synthesis_tasks[0]
        assert len(synthesis.dependencies) >= 2  # Зависит от всех источников
    
    @pytest.mark.asyncio
    async def test_decompose_identifies_parallel_tasks(self, decomposer):
        """Test: Identify tasks that can be executed in parallel."""
        result = await decomposer.decompose("Проверь почту, календарь и последние файлы")
        
        # Задачи без зависимостей можно выполнять параллельно
        parallel_tasks = [st for st in result.subtasks if not st.dependencies and not st.is_synthesis]
        assert len(parallel_tasks) >= 3  # Все источники независимы
    
    @pytest.mark.asyncio
    async def test_decompose_handles_single_tool_query(self, decomposer):
        """Test: Handle single tool query (should not decompose unnecessarily)."""
        result = await decomposer.decompose("Покажи письма")
        
        # Для простого запроса должна быть 1 подзадача + синтез
        assert len(result.subtasks) >= 1
        assert len(result.subtasks) <= 3  # Не должно быть избыточной декомпозиции
    
    @pytest.mark.asyncio
    async def test_decompose_creates_valid_subtask_structure(self, decomposer):
        """Test: Created subtasks have valid structure."""
        result = await decomposer.decompose("Проверь почту и календарь")
        
        for subtask in result.subtasks:
            assert subtask.task_id is not None
            assert len(subtask.task_id) > 0
            assert subtask.description is not None
            assert len(subtask.description) > 0
            assert subtask.tool_name is not None
            assert isinstance(subtask.arguments, dict)
            assert isinstance(subtask.dependencies, list)
            assert isinstance(subtask.is_synthesis, bool)
            assert isinstance(subtask.priority, int)
    
    @pytest.mark.asyncio
    async def test_decompose_synthesis_depends_on_all_sources(self, decomposer):
        """Test: Synthesis task depends on all source tasks."""
        result = await decomposer.decompose("Покажи фокус: почта, календарь, файлы")
        
        synthesis = next(st for st in result.subtasks if st.is_synthesis)
        source_tasks = [st for st in result.subtasks if not st.is_synthesis]
        
        # Синтез должен зависеть от всех источников
        assert len(synthesis.dependencies) == len(source_tasks)
        assert set(synthesis.dependencies) == {st.task_id for st in source_tasks}
    
    @pytest.mark.asyncio
    async def test_decompose_handles_empty_query(self, decomposer):
        """Test: Handle edge case with empty query."""
        result = await decomposer.decompose("")
        
        # Должен вернуть валидный результат (может быть пустым или с дефолтной задачей)
        assert isinstance(result, DecompositionResult)
        assert isinstance(result.subtasks, list)
