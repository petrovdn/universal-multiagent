"""
Audit trail for MCP operations and agent actions.
Logs all operations with timestamps, user info, and results.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from src.utils.logging_config import get_logger


class AuditLogger:
    """
    Audit logger for tracking all system operations.
    Provides structured logging for compliance and debugging.
    """
    
    def __init__(self):
        """Initialize audit logger."""
        self.logger = get_logger("audit")
    
    def log_mcp_operation(
        self,
        operation: str,
        tool_name: str,
        server_name: str,
        parameters: Dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log an MCP tool operation.
        
        Args:
            operation: Operation type (call, result, error)
            tool_name: Name of tool
            server_name: MCP server name
            parameters: Tool parameters
            result: Tool result (if successful)
            error: Error message (if failed)
            duration_ms: Operation duration in milliseconds
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Audit log entry ID
        """
        log_id = str(uuid4())
        
        # Redact sensitive data
        safe_parameters = self._redact_sensitive_data(parameters)
        safe_result = self._redact_sensitive_data(result) if result else None
        
        log_entry = {
            "audit_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "type": "mcp_tool",
            "tool_name": tool_name,
            "server_name": server_name,
            "parameters": safe_parameters,
            "result": safe_result,
            "error": error,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "session_id": session_id
        }
        
        self.logger.info("MCP operation", extra={"extra_data": log_entry})
        return log_id
    
    def log_agent_action(
        self,
        agent_name: str,
        action: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log an agent action.
        
        Args:
            agent_name: Name of agent
            action: Action performed
            details: Action details
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Audit log entry ID
        """
        log_id = str(uuid4())
        
        log_entry = {
            "audit_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "agent_action",
            "agent_name": agent_name,
            "action": action,
            "details": self._redact_sensitive_data(details),
            "user_id": user_id,
            "session_id": session_id
        }
        
        self.logger.info("Agent action", extra={"extra_data": log_entry})
        return log_id
    
    def log_user_interaction(
        self,
        interaction_type: str,
        content: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log a user interaction.
        
        Args:
            interaction_type: Type of interaction (message, approval, rejection)
            content: Interaction content
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Audit log entry ID
        """
        log_id = str(uuid4())
        
        log_entry = {
            "audit_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "user_interaction",
            "interaction_type": interaction_type,
            "content": self._redact_sensitive_data(content),
            "user_id": user_id,
            "session_id": session_id
        }
        
        self.logger.info("User interaction", extra={"extra_data": log_entry})
        return log_id
    
    def _redact_sensitive_data(self, data: Any) -> Any:
        """
        Redact sensitive data from log entries.
        
        Args:
            data: Data to redact
            
        Returns:
            Data with sensitive fields redacted
        """
        if isinstance(data, dict):
            redacted = {}
            sensitive_keys = {
                "password", "secret", "token", "api_key", "client_secret",
                "private_key", "authorization", "email_body", "email_content"
            }
            
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    redacted[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)):
                    redacted[key] = self._redact_sensitive_data(value)
                else:
                    redacted[key] = value
            
            return redacted
        elif isinstance(data, list):
            return [self._redact_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            # Redact email addresses in strings
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            return re.sub(email_pattern, "[EMAIL_REDACTED]", data)
        else:
            return data


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger.
    
    Returns:
        AuditLogger instance
    """
    global _audit_logger
    
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    
    return _audit_logger









