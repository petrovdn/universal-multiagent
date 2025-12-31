"""
Модуль планирования действий.
Разбивает сложные задачи на подзадачи и создаёт план выполнения.
Интегрирован с LangChain для LLM-powered декомпозиции.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from src.utils.config_loader import get_config


class TaskPriority(Enum):
    """Приоритет задачи."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Task:
    """Представление задачи в системе."""
    
    def __init__(
        self,
        task_id: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None
    ):
        self.task_id = task_id
        self.description = description
        self.priority = priority
        self.dependencies = dependencies or []
        self.status = "pending"
        

class Planner:
    """
    Планировщик задач для мультиагентной системы.
    
    Функции:
    - Декомпозиция сложных задач на подзадачи
    - Определение зависимостей между задачами
    - Приоритизация задач
    - Создание оптимального плана выполнения
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.execution_plan: List[Task] = []
        config = get_config()
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",  # Correct model
            api_key=config.anthropic_api_key,
            temperature=0.3
        )
        
    async def decompose_task(self, task_description: str) -> List[Task]:
        """
        Разбивает сложную задачу на последовательность подзадач с помощью LLM.
        
        Args:
            task_description: Описание исходной задачи
            
        Returns:
            Список подзадач
        """
        def _escape_langchain_fstring_template(text: str) -> str:
            return (text or "").replace("{", "{{").replace("}", "}}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a task decomposition expert. Break down complex tasks into 
            smaller, actionable subtasks. Return a JSON array of subtasks, each with:
            - task_id: unique identifier
            - description: what needs to be done
            - priority: LOW, MEDIUM, HIGH, or CRITICAL
            - dependencies: list of task_ids this depends on (empty if none)
            
            Focus on Google Workspace operations: Gmail, Calendar, Sheets."""),
            ("user", "Decompose this task: " + _escape_langchain_fstring_template(task_description))
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({})
        
        # Parse LLM response (simplified - in production, use structured output)
        # For now, return empty list and let agent handle it
        subtasks = []
        return subtasks
        
    def create_execution_plan(self, tasks: List[Task]) -> List[Task]:
        """
        Создаёт оптимальный план выполнения с учётом зависимостей.
        Использует топологическую сортировку.
        
        Args:
            tasks: Список задач для планирования
            
        Returns:
            Упорядоченный список задач для выполнения
        """
        # Topological sort based on dependencies
        task_dict = {task.task_id: task for task in tasks}
        in_degree = {task_id: 0 for task_id in task_dict.keys()}
        
        # Calculate in-degrees
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in in_degree:
                    in_degree[task.task_id] += 1
        
        # Kahn's algorithm for topological sort
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        plan = []
        
        while queue:
            # Sort by priority
            queue.sort(key=lambda tid: task_dict[tid].priority.value, reverse=True)
            task_id = queue.pop(0)
            plan.append(task_dict[task_id])
            
            # Update in-degrees
            for task in tasks:
                if task_id in task.dependencies:
                    in_degree[task.task_id] -= 1
                    if in_degree[task.task_id] == 0:
                        queue.append(task.task_id)
        
        # Add any remaining tasks (cycles or missing dependencies)
        remaining = [task for task in tasks if task not in plan]
        plan.extend(remaining)
        
        return plan
        
    def prioritize_tasks(self, tasks: List[Task]) -> List[Task]:
        """
        Сортирует задачи по приоритету.
        
        Args:
            tasks: Список задач
            
        Returns:
            Отсортированный список задач
        """
        return sorted(tasks, key=lambda t: t.priority.value, reverse=True)
        
    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Обновляет статус задачи.
        
        Args:
            task_id: Идентификатор задачи
            status: Новый статус (pending, in_progress, completed, failed)
        """
        if task_id in self.tasks:
            self.tasks[task_id].status = status

