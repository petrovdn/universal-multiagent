"""
Action Provider abstraction layer for unified access to MCP tools and future A2A agents.
Provides a common interface regardless of underlying provider type.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class ProviderType(Enum):
    """Type of action provider"""
    MCP_TOOL = "mcp_tool"
    A2A_AGENT = "a2a_agent"  # Future
    LOCAL_FUNCTION = "local"  # Future


class CapabilityCategory(Enum):
    """Category of capability - determines access in different modes"""
    READ = "read"
    WRITE = "write"


@dataclass
class ActionCapability:
    """
    Universal capability descriptor - works for MCP tools and A2A agents.
    Describes what actions are available, regardless of provider type.
    """
    name: str
    description: str
    category: CapabilityCategory
    provider_type: ProviderType
    input_schema: Dict[str, Any]
    service: str  # gmail, sheets, calendar, etc.
    
    # A2A-specific fields (optional, for future)
    agent_card_url: Optional[str] = None
    skills: Optional[List[str]] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    estimated_duration_ms: Optional[int] = None


class ActionProvider(ABC):
    """
    Abstract interface for any action executor (MCP tool or A2A agent).
    
    This abstraction allows the system to work with different types of providers
    transparently, enabling future support for A2A agents without refactoring
    the core ReAct engine.
    """
    
    @abstractmethod
    async def execute(
        self, 
        capability_name: str, 
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a capability.
        
        Args:
            capability_name: Name of the capability to execute
            arguments: Arguments for the capability
            context: Optional execution context
            
        Returns:
            Result of execution
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[ActionCapability]:
        """
        Return list of capabilities this provider offers.
        
        Returns:
            List of ActionCapability objects
        """
        pass
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """
        Return provider type.
        
        Returns:
            ProviderType enum value
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is available and healthy.
        
        Returns:
            True if provider is available, False otherwise
        """
        pass

