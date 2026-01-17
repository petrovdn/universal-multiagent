"""
DependencyAnalyzer - Analyzes dependencies between subtasks and creates execution plan.

Phase 2, Step 2: Uses topological sort to determine which tasks can run in parallel
and which must run sequentially.
"""

from typing import List, Dict, Set
from dataclasses import dataclass

from src.core.task_decomposer import SubTask
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionPlan:
    """Execution plan with groups of tasks."""
    execution_groups: List[List[str]]  # task_ids grouped by execution order
    group_types: List[str]  # "parallel" or "sequential" for each group


class DependencyAnalyzer:
    """Analyzes dependencies and creates execution plan."""
    
    def analyze(self, subtasks: List[SubTask]) -> ExecutionPlan:
        """
        Analyze dependencies and create execution plan.
        
        Uses topological sort (Kahn's algorithm) to determine execution order.
        
        Args:
            subtasks: List of subtasks with dependencies
            
        Returns:
            ExecutionPlan with groups for parallel/sequential execution
        """
        if not subtasks:
            return ExecutionPlan(execution_groups=[], group_types=[])
        
        # Build task dictionary
        task_dict: Dict[str, SubTask] = {task.task_id: task for task in subtasks}
        
        # Calculate in-degrees (number of dependencies)
        in_degree: Dict[str, int] = {task_id: 0 for task_id in task_dict.keys()}
        
        for task in subtasks:
            for dep_id in task.dependencies:
                if dep_id in in_degree:
                    in_degree[task.task_id] += 1
        
        # Kahn's algorithm for topological sort
        execution_groups: List[List[str]] = []
        group_types: List[str] = []
        
        # Start with tasks that have no dependencies
        queue: List[str] = [task_id for task_id, degree in in_degree.items() if degree == 0]
        
        while queue:
            # Current group: all tasks ready to execute
            current_group = list(queue)
            queue = []  # Clear queue for next iteration
            
            # Determine group type
            if len(current_group) > 1:
                group_type = "parallel"
            else:
                group_type = "sequential"
            
            execution_groups.append(current_group)
            group_types.append(group_type)
            
            # Process each task in current group
            for task_id in current_group:
                task = task_dict[task_id]
                
                # Find tasks that depend on this one
                for dependent_task in subtasks:
                    if task_id in dependent_task.dependencies:
                        in_degree[dependent_task.task_id] -= 1
                        
                        # If all dependencies are satisfied, add to queue
                        if in_degree[dependent_task.task_id] == 0:
                            queue.append(dependent_task.task_id)
        
        # Handle remaining tasks (cycles or missing dependencies)
        remaining = [task_id for task_id in task_dict.keys() 
                    if task_id not in [tid for group in execution_groups for tid in group]]
        
        if remaining:
            # Add remaining tasks as separate sequential groups
            for task_id in remaining:
                execution_groups.append([task_id])
                group_types.append("sequential")
            logger.warning(f"[DependencyAnalyzer] Found {len(remaining)} tasks with unresolved dependencies")
        
        return ExecutionPlan(
            execution_groups=execution_groups,
            group_types=group_types
        )
