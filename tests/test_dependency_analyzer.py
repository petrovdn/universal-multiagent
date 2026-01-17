"""
TDD tests for DependencyAnalyzer - Phase 2, Step 2.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
from src.core.task_decomposer import SubTask
from src.core.dependency_analyzer import DependencyAnalyzer, ExecutionPlan


class TestDependencyAnalyzer:
    """Test suite for DependencyAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Fixture for DependencyAnalyzer."""
        return DependencyAnalyzer()
    
    def test_analyze_creates_parallel_groups(self, analyzer):
        """Test: Create groups for parallel execution."""
        subtasks = [
            SubTask("t1", "Read Gmail", "list_emails", {}, [], False, 1),
            SubTask("t2", "Read Calendar", "get_calendar_events", {}, [], False, 1),
            SubTask("t3", "Read Drive", "list_files", {}, [], False, 1),
            SubTask("t4", "Synthesize", "synthesize", {}, ["t1", "t2", "t3"], True, 2)
        ]
        
        result = analyzer.analyze(subtasks)
        
        assert isinstance(result, ExecutionPlan)
        # Должно быть 2 группы: параллельная (t1,t2,t3) и зависимая (t4)
        assert len(result.execution_groups) == 2
        assert set(result.execution_groups[0]) == {"t1", "t2", "t3"}
        assert result.execution_groups[1] == ["t4"]
        
        # Типы групп
        assert result.group_types[0] == "parallel"
        assert result.group_types[1] == "sequential"
    
    def test_analyze_handles_sequential_dependencies(self, analyzer):
        """Test: Handle sequential dependencies."""
        subtasks = [
            SubTask("t1", "Search file", "search_files", {}, [], False, 1),
            SubTask("t2", "Read file", "read_document", {}, ["t1"], False, 2),
            SubTask("t3", "Summarize", "summarize", {}, ["t2"], True, 3)
        ]
        
        result = analyzer.analyze(subtasks)
        
        # Все задачи последовательные
        assert len(result.execution_groups) == 3
        assert all(len(group) == 1 for group in result.execution_groups)
        assert result.execution_groups[0] == ["t1"]
        assert result.execution_groups[1] == ["t2"]
        assert result.execution_groups[2] == ["t3"]
        
        # Все группы sequential
        assert all(gt == "sequential" for gt in result.group_types)
    
    def test_analyze_handles_mixed_dependencies(self, analyzer):
        """Test: Handle mixed parallel and sequential dependencies."""
        subtasks = [
            SubTask("t1", "Read Gmail", "list_emails", {}, [], False, 1),
            SubTask("t2", "Read Calendar", "get_calendar_events", {}, [], False, 1),
            SubTask("t3", "Process Gmail", "process_emails", {}, ["t1"], False, 2),
            SubTask("t4", "Synthesize", "synthesize", {}, ["t2", "t3"], True, 3)
        ]
        
        result = analyzer.analyze(subtasks)
        
        # Группа 1: t1, t2 параллельно
        # Группа 2: t3 последовательно (зависит от t1)
        # Группа 3: t4 последовательно (зависит от t2, t3)
        assert len(result.execution_groups) == 3
        assert set(result.execution_groups[0]) == {"t1", "t2"}
        assert result.execution_groups[1] == ["t3"]
        assert result.execution_groups[2] == ["t4"]
        
        assert result.group_types[0] == "parallel"
        assert result.group_types[1] == "sequential"
        assert result.group_types[2] == "sequential"
    
    def test_analyze_handles_no_dependencies(self, analyzer):
        """Test: Handle tasks with no dependencies."""
        subtasks = [
            SubTask("t1", "Task 1", "tool1", {}, [], False, 1),
            SubTask("t2", "Task 2", "tool2", {}, [], False, 1),
            SubTask("t3", "Task 3", "tool3", {}, [], False, 1)
        ]
        
        result = analyzer.analyze(subtasks)
        
        # Все задачи должны быть в одной параллельной группе
        assert len(result.execution_groups) == 1
        assert set(result.execution_groups[0]) == {"t1", "t2", "t3"}
        assert result.group_types[0] == "parallel"
    
    def test_analyze_handles_circular_dependencies(self, analyzer):
        """Test: Handle circular dependencies gracefully."""
        subtasks = [
            SubTask("t1", "Task 1", "tool1", {}, ["t3"], False, 1),  # Зависит от t3
            SubTask("t2", "Task 2", "tool2", {}, ["t1"], False, 2),  # Зависит от t1
            SubTask("t3", "Task 3", "tool3", {}, ["t2"], False, 3)   # Зависит от t2 (цикл!)
        ]
        
        result = analyzer.analyze(subtasks)
        
        # Должен обработать циклические зависимости (может быть разный порядок)
        assert isinstance(result, ExecutionPlan)
        assert len(result.execution_groups) > 0
        # Все задачи должны быть включены
        all_task_ids = {tid for group in result.execution_groups for tid in group}
        assert all_task_ids == {"t1", "t2", "t3"}
    
    def test_analyze_handles_empty_subtasks(self, analyzer):
        """Test: Handle empty subtasks list."""
        result = analyzer.analyze([])
        
        assert isinstance(result, ExecutionPlan)
        assert len(result.execution_groups) == 0
        assert len(result.group_types) == 0
