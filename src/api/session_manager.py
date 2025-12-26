"""
Session manager for tracking user sessions and conversation history.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.context_manager import ConversationContext, PersistentStorage
from src.utils.config_loader import get_config


class SessionManager:
    """
    Manages user sessions and conversation contexts.
    """
    
    def __init__(self):
        """Initialize session manager."""
        self.sessions: Dict[str, ConversationContext] = {}
        self.storage = PersistentStorage()
        self.config = get_config()
        self.timeout_minutes = self.config.session_timeout_minutes
    
    def create_session(self, execution_mode: str = "instant") -> str:
        """
        Create a new session.
        
        Args:
            execution_mode: Execution mode (instant or approval)
            
        Returns:
            Session ID
        """
        session_id = str(uuid4())
        context = ConversationContext(session_id)
        context.execution_mode = execution_mode
        self.sessions[session_id] = context
        self.storage.save_context(context)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get session context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Conversation context or None if not found
        """
        # Try memory first
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try storage
        context = self.storage.load_context(session_id)
        if context:
            self.sessions[session_id] = context
            return context
        
        return None
    
    def update_session(self, session_id: str, context: ConversationContext) -> None:
        """
        Update session context.
        
        Args:
            session_id: Session identifier
            context: Updated context
        """
        self.sessions[session_id] = context
        self.storage.save_context(context)
    
    def delete_session(self, session_id: str) -> None:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
        self.storage.delete_context(session_id)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        expired = []
        cutoff = datetime.now() - timedelta(minutes=self.timeout_minutes)
        
        for session_id, context in self.sessions.items():
            try:
                updated = datetime.fromisoformat(context.updated_at)
                if updated < cutoff:
                    expired.append(session_id)
            except Exception:
                expired.append(session_id)
        
        for session_id in expired:
            self.delete_session(session_id)
        
        return len(expired)
    
    def get_all_sessions(self) -> Dict[str, ConversationContext]:
        """Get all active sessions."""
        return self.sessions.copy()


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager."""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager()
    
    return _session_manager



