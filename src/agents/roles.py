"""
Описания ролей агентов в мультиагентной системе.
Каждая роль имеет свои цели, инструменты и стратегии работы.
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class AgentRole(ABC):
    """Базовый класс для роли агента."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tools: List[str] = []
        self.capabilities: List[str] = []
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Возвращает системный промпт для агента с этой ролью.
        
        Returns:
            Системный промпт
        """
        pass
        
    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет задачу согласно роли.
        
        Args:
            task: Описание задачи
            
        Returns:
            Результат выполнения
        """
        pass


class AnalystAgent(AgentRole):
    """
    Агент-аналитик.
    
    Отвечает за:
    - Анализ требований и спецификаций
    - Исследование предметной области
    - Сбор и структурирование информации
    - Выявление зависимостей и ограничений
    """
    
    def __init__(self):
        super().__init__(
            name="Analyst",
            description="Анализирует требования и исследует предметную область"
        )
        self.capabilities = [
            "requirements_analysis",
            "domain_research",
            "data_gathering",
            "constraint_identification"
        ]
        
    def get_system_prompt(self) -> str:
        return """
        Вы - агент-аналитик в мультиагентной системе разработки.
        
        Ваши задачи:
        - Глубокий анализ требований заказчика
        - Исследование предметной области и контекста
        - Выявление скрытых зависимостей и ограничений
        - Структурирование и документирование собранной информации
        
        Подход: методичный, детальный, фокус на понимании проблемы.
        """
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Реализовать логику аналитика
        return {"status": "analyzed", "insights": []}


class ArchitectAgent(AgentRole):
    """
    Агент-архитектор.
    
    Отвечает за:
    - Проектирование архитектуры системы
    - Выбор технологий и паттернов
    - Определение структуры компонентов
    - Планирование масштабирования и производительности
    """
    
    def __init__(self):
        super().__init__(
            name="Architect",
            description="Проектирует архитектуру и выбирает технические решения"
        )
        self.capabilities = [
            "system_design",
            "technology_selection",
            "pattern_recommendation",
            "scalability_planning"
        ]
        
    def get_system_prompt(self) -> str:
        return """
        Вы - агент-архитектор в мультиагентной системе разработки.
        
        Ваши задачи:
        - Проектирование масштабируемой и надёжной архитектуры
        - Выбор оптимальных технологий и паттернов
        - Определение взаимодействия компонентов
        - Учёт нефункциональных требований (производительность, безопасность)
        
        Подход: системное мышление, best practices, долгосрочное планирование.
        """
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Реализовать логику архитектора
        return {"status": "designed", "architecture": {}}


class PlannerAgent(AgentRole):
    """
    Агент-планировщик.
    
    Отвечает за:
    - Разбиение задач на подзадачи
    - Создание плана выполнения
    - Оценку сроков и ресурсов
    - Управление зависимостями
    """
    
    def __init__(self):
        super().__init__(
            name="Planner",
            description="Создаёт детальные планы выполнения задач"
        )
        self.capabilities = [
            "task_decomposition",
            "timeline_estimation",
            "resource_allocation",
            "dependency_management"
        ]
        
    def get_system_prompt(self) -> str:
        return """
        Вы - агент-планировщик в мультиагентной системе разработки.
        
        Ваши задачи:
        - Разбиение сложных задач на управляемые подзадачи
        - Создание оптимального плана выполнения
        - Реалистичная оценка сроков и ресурсов
        - Определение критического пути и зависимостей
        
        Подход: структурированный, прагматичный, учёт рисков.
        """
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Реализовать логику планировщика
        return {"status": "planned", "plan": []}


class ExecutorAgent(AgentRole):
    """
    Агент-исполнитель.
    
    Отвечает за:
    - Написание кода
    - Реализацию функциональности
    - Интеграцию компонентов
    - Отладку и исправление багов
    """
    
    def __init__(self):
        super().__init__(
            name="Executor",
            description="Реализует код и функциональность"
        )
        self.capabilities = [
            "code_writing",
            "feature_implementation",
            "component_integration",
            "debugging"
        ]
        
    def get_system_prompt(self) -> str:
        return """
        Вы - агент-исполнитель в мультиагентной системе разработки.
        
        Ваши задачи:
        - Написание чистого, эффективного кода
        - Точная реализация спецификаций
        - Следование архитектурным решениям и паттернам
        - Отладка и исправление проблем
        
        Подход: практичный, внимание к деталям, качество кода.
        """
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Реализовать логику исполнителя
        return {"status": "implemented", "code": ""}


class ReviewerAgent(AgentRole):
    """
    Агент-ревьюер.
    
    Отвечает за:
    - Проверку качества кода
    - Поиск ошибок и уязвимостей
    - Проверку соответствия требованиям
    - Предложение улучшений
    """
    
    def __init__(self):
        super().__init__(
            name="Reviewer",
            description="Проверяет качество и корректность решений"
        )
        self.capabilities = [
            "code_review",
            "quality_assurance",
            "security_audit",
            "improvement_suggestions"
        ]
        
    def get_system_prompt(self) -> str:
        return """
        Вы - агент-ревьюер в мультиагентной системе разработки.
        
        Ваши задачи:
        - Тщательная проверка кода на ошибки и уязвимости
        - Оценка соответствия требованиям и архитектуре
        - Проверка качества, читаемости и maintainability
        - Конструктивные предложения по улучшению
        
        Подход: критический, но конструктивный; фокус на качестве.
        """
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Реализовать логику ревьюера
        return {"status": "reviewed", "issues": [], "suggestions": []}


# Реестр доступных ролей
AVAILABLE_ROLES = {
    "analyst": AnalystAgent,
    "architect": ArchitectAgent,
    "planner": PlannerAgent,
    "executor": ExecutorAgent,
    "reviewer": ReviewerAgent
}


def create_agent(role_type: str, **kwargs) -> AgentRole:
    """
    Создаёт агента с указанной ролью.
    
    Args:
        role_type: Тип роли агента
        **kwargs: Дополнительные параметры
        
    Returns:
        Экземпляр агента с указанной ролью
    """
    if role_type not in AVAILABLE_ROLES:
        raise ValueError(f"Unknown role type: {role_type}")
        
    return AVAILABLE_ROLES[role_type](**kwargs)









