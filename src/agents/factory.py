"""
Agent factory for creating and managing agent instances.
Provides dependency injection and lifecycle management.
"""

from typing import Dict, Optional, List
from langchain_core.tools import BaseTool

from src.agents.base_agent import BaseAgent
# DEPRECATED: Специализированные агенты удалены - вся логика в skills
# from src.agents.email_agent import EmailAgent
# from src.agents.calendar_agent import CalendarAgent
# from src.agents.sheets_agent import SheetsAgent
# from src.agents.workspace_agent import WorkspaceAgent
from src.mcp_tools.registry import get_tool_registry


class AgentFactory:
    """
    Factory for creating and managing agent instances.
    """
    
    def __init__(self):
        """Initialize agent factory."""
        self.agents: Dict[str, BaseAgent] = {}
        self.tool_registry = get_tool_registry()
    
    # DEPRECATED: Специализированные агенты удалены - используй MainAgent с skills
    # def create_email_agent(self, ...):
    #     pass
    # def create_calendar_agent(self, ...):
    #     pass
    # def create_sheets_agent(self, ...):
    #     pass
    # def create_workspace_agent(self, ...):
    #     pass
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get agent by name.
        
        Args:
            agent_name: Name of agent
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(agent_name)
    
    def get_all_agents(self) -> Dict[str, BaseAgent]:
        """
        Get all created agents.
        
        Returns:
            Dictionary of agent name to agent instance
        """
        return self.agents.copy()
    
    def create_all_agents(self) -> Dict[str, BaseAgent]:
        """
        DEPRECATED: Специализированные агенты удалены.
        Используй MainAgent - он работает со всеми tools через skills.
        
        Returns:
            Пустой словарь (legacy метод для обратной совместимости)
        """
        # Все агенты теперь в MainAgent
        return {}


# Global factory instance
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """
    Get the global agent factory.
    
    Returns:
        AgentFactory instance
    """
    global _agent_factory
    
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    
    return _agent_factory

