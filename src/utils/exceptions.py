"""
Custom exception classes for the multi-agent system.
Provides specific error types for better error handling and user feedback.
"""

from typing import Optional, Dict, Any


class MultiAgentError(Exception):
    """Base exception for all multi-agent system errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class MCPError(MultiAgentError):
    """Base exception for MCP-related errors."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize MCP error.
        
        Args:
            message: Error message
            server_name: Name of MCP server
            tool_name: Name of tool that failed
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, **kwargs)
        self.server_name = server_name
        self.tool_name = tool_name


class MCPConnectionError(MCPError):
    """Raised when MCP server connection fails."""
    pass


class MCPToolError(MCPError):
    """Raised when MCP tool execution fails."""
    pass


class RateLimitError(MultiAgentError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "API rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="RATE_LIMIT", **kwargs)
        self.retry_after = retry_after


class ValidationError(MultiAgentError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Name of invalid field
            value: Invalid value
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        self.field = field
        self.value = value


class AuthenticationError(MultiAgentError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str,
        auth_method: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize authentication error.
        
        Args:
            message: Error message
            auth_method: Authentication method that failed (service_account, oauth)
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="AUTH_ERROR", **kwargs)
        self.auth_method = auth_method


class ToolExecutionError(MultiAgentError):
    """Raised when tool execution fails."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize tool execution error.
        
        Args:
            message: Error message
            tool_name: Name of tool that failed
            tool_args: Arguments passed to tool
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="TOOL_EXECUTION_ERROR", **kwargs)
        self.tool_name = tool_name
        self.tool_args = tool_args


class AgentError(MultiAgentError):
    """Raised when agent operation fails."""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize agent error.
        
        Args:
            message: Error message
            agent_name: Name of agent that failed
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="AGENT_ERROR", **kwargs)
        self.agent_name = agent_name


class ConfigurationError(MultiAgentError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Name of missing/invalid config key
            **kwargs: Additional arguments for MultiAgentError
        """
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)
        self.config_key = config_key




