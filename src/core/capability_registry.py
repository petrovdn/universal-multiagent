"""
Capability Registry - central registry for all capabilities from all providers.
Provides unified access regardless of underlying provider type (MCP tools or A2A agents).
"""

from typing import Dict, List, Optional, Tuple, Any
from src.core.action_provider import (
    ActionProvider,
    ActionCapability,
    CapabilityCategory
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CapabilityRegistry:
    """
    Central registry for all capabilities from all providers.
    Provides unified access regardless of underlying provider type.
    
    The registry:
    - Indexes capabilities from all registered providers
    - Allows filtering by category (READ/WRITE) and service
    - Routes execution requests to appropriate providers
    - Provides capability metadata lookup
    """
    
    def __init__(self):
        """Initialize empty capability registry."""
        self.providers: List[ActionProvider] = []
        self._capability_map: Dict[str, Tuple[ActionProvider, ActionCapability]] = {}
        logger.info("[CapabilityRegistry] Initialized")
    
    def register_provider(self, provider: ActionProvider) -> None:
        """
        Register a new provider and index its capabilities.
        
        Args:
            provider: ActionProvider instance to register
        """
        self.providers.append(provider)
        
        # Index all capabilities from this provider
        capabilities = provider.get_capabilities()
        for cap in capabilities:
            if cap.name in self._capability_map:
                existing_provider, existing_cap = self._capability_map[cap.name]
                logger.warning(
                    f"[CapabilityRegistry] Capability '{cap.name}' already registered "
                    f"by {existing_provider.provider_type.value}. "
                    f"Overwriting with {provider.provider_type.value}."
                )
            
            self._capability_map[cap.name] = (provider, cap)
        
        logger.info(
            f"[CapabilityRegistry] Registered provider {provider.provider_type.value} "
            f"with {len(capabilities)} capabilities. "
            f"Total capabilities: {len(self._capability_map)}"
        )
    
    def get_capabilities(
        self, 
        categories: Optional[List[CapabilityCategory]] = None,
        services: Optional[List[str]] = None
    ) -> List[ActionCapability]:
        """
        Get capabilities filtered by category and/or service.
        
        Args:
            categories: Optional list of categories to filter by (READ, WRITE)
            services: Optional list of services to filter by (gmail, sheets, etc.)
            
        Returns:
            List of ActionCapability objects matching filters
        """
        result = []
        
        for provider, cap in self._capability_map.values():
            # Filter by category
            if categories and cap.category not in categories:
                continue
            
            # Filter by service
            if services and cap.service not in services:
                continue
            
            result.append(cap)
        
        return result
    
    def get_read_capabilities(self) -> List[ActionCapability]:
        """
        Get all READ capabilities.
        
        Returns:
            List of ActionCapability objects with READ category
        """
        return self.get_capabilities(categories=[CapabilityCategory.READ])
    
    def get_write_capabilities(self) -> List[ActionCapability]:
        """
        Get all WRITE capabilities.
        
        Returns:
            List of ActionCapability objects with WRITE category
        """
        return self.get_capabilities(categories=[CapabilityCategory.WRITE])
    
    async def execute(
        self, 
        capability_name: str, 
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute capability through appropriate provider.
        
        Args:
            capability_name: Name of the capability to execute
            arguments: Arguments for the capability
            context: Optional execution context
            
        Returns:
            Result from capability execution
            
        Raises:
            ValueError: If capability is not found
        """
        if capability_name not in self._capability_map:
            available = list(self._capability_map.keys())[:10]  # Show first 10
            raise ValueError(
                f"Unknown capability: {capability_name}. "
                f"Available capabilities: {available}..."
            )
        
        provider, cap = self._capability_map[capability_name]
        
        logger.debug(
            f"[CapabilityRegistry] Executing '{capability_name}' "
            f"via {provider.provider_type.value} provider"
        )
        
        try:
            result = await provider.execute(capability_name, arguments, context)
            return result
        except Exception as e:
            logger.error(
                f"[CapabilityRegistry] Execution failed for '{capability_name}': {e}",
                exc_info=True
            )
            raise
    
    def get_capability_info(self, name: str) -> Optional[ActionCapability]:
        """
        Get capability metadata.
        
        Args:
            name: Capability name
            
        Returns:
            ActionCapability object if found, None otherwise
        """
        if name in self._capability_map:
            return self._capability_map[name][1]
        return None
    
    def get_provider_for_capability(self, name: str) -> Optional[ActionProvider]:
        """
        Get the provider that handles a specific capability.
        
        Args:
            name: Capability name
            
        Returns:
            ActionProvider instance if found, None otherwise
        """
        if name in self._capability_map:
            return self._capability_map[name][0]
        return None
    
    def get_all_capabilities(self) -> List[ActionCapability]:
        """
        Get all registered capabilities.
        
        Returns:
            List of all ActionCapability objects
        """
        return [cap for _, cap in self._capability_map.values()]
    
    def get_capabilities_by_service(self, service: str) -> List[ActionCapability]:
        """
        Get all capabilities for a specific service.
        
        Args:
            service: Service identifier (gmail, sheets, etc.)
            
        Returns:
            List of ActionCapability objects for the service
        """
        return self.get_capabilities(services=[service])
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all registered providers.
        
        Returns:
            Dictionary mapping provider type to health status
        """
        health_status = {}
        for provider in self.providers:
            try:
                is_healthy = await provider.health_check()
                health_status[provider.provider_type.value] = is_healthy
            except Exception as e:
                logger.error(
                    f"[CapabilityRegistry] Health check failed for "
                    f"{provider.provider_type.value}: {e}"
                )
                health_status[provider.provider_type.value] = False
        
        return health_status

