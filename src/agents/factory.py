"""
Agent factory for creating and managing agent instances.
Provides dependency injection and lifecycle management.
"""

from typing import Dict, Optional, List
from langchain_core.tools import BaseTool

from src.agents.base_agent import BaseAgent
from src.agents.email_agent import EmailAgent
from src.agents.calendar_agent import CalendarAgent
from src.agents.sheets_agent import SheetsAgent
from src.agents.workspace_agent import WorkspaceAgent
from src.mcp_tools.registry import get_tool_registry


class AgentFactory:
    """
    Factory for creating and managing agent instances.
    """
    
    def __init__(self):
        """Initialize agent factory."""
        self.agents: Dict[str, BaseAgent] = {}
        self.tool_registry = get_tool_registry()
    
    def create_email_agent(self, tools: Optional[List[BaseTool]] = None, model_name: Optional[str] = None) -> EmailAgent:
        """
        Create Email Agent instance.
        
        Args:
            tools: Custom tools (uses Gmail tools by default)
            model_name: Model identifier (optional)
            
        Returns:
            EmailAgent instance
        """
        # Use model_name in cache key if provided
        cache_key = f"EmailAgent-{model_name}" if model_name else "EmailAgent"
        if cache_key not in self.agents:
            self.agents[cache_key] = EmailAgent(tools=tools, model_name=model_name)
        return self.agents[cache_key]
    
    def create_calendar_agent(self, tools: Optional[List[BaseTool]] = None, model_name: Optional[str] = None) -> CalendarAgent:
        """
        Create Calendar Agent instance.
        
        Args:
            tools: Custom tools (uses Calendar tools by default)
            model_name: Model identifier (optional)
            
        Returns:
            CalendarAgent instance
        """
        cache_key = f"CalendarAgent-{model_name}" if model_name else "CalendarAgent"
        if cache_key not in self.agents:
            self.agents[cache_key] = CalendarAgent(tools=tools, model_name=model_name)
        return self.agents[cache_key]
    
    def create_sheets_agent(self, tools: Optional[List[BaseTool]] = None, model_name: Optional[str] = None) -> SheetsAgent:
        """
        Create Sheets Agent instance.
        
        Args:
            tools: Custom tools (uses Sheets tools by default)
            model_name: Model identifier (optional)
            
        Returns:
            SheetsAgent instance
        """
        cache_key = f"SheetsAgent-{model_name}" if model_name else "SheetsAgent"
        if cache_key not in self.agents:
            self.agents[cache_key] = SheetsAgent(tools=tools, model_name=model_name)
        return self.agents[cache_key]
    
    def create_workspace_agent(self, tools: Optional[List[BaseTool]] = None, model_name: Optional[str] = None) -> WorkspaceAgent:
        """
        Create Workspace Agent instance.
        
        Args:
            tools: Custom tools (uses Workspace tools by default)
            model_name: Model identifier (optional)
            
        Returns:
            WorkspaceAgent instance
        """
        cache_key = f"WorkspaceAgent-{model_name}" if model_name else "WorkspaceAgent"
        if cache_key not in self.agents:
            self.agents[cache_key] = WorkspaceAgent(tools=tools, model_name=model_name)
        return self.agents[cache_key]
    
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
        Create all available agents.
        
        Returns:
            Dictionary of all agents
        """
        self.create_email_agent()
        self.create_calendar_agent()
        self.create_sheets_agent()
        self.create_workspace_agent()
        return self.get_all_agents()


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

