"""
WebSocket manager for real-time communication with frontend.
Handles connections, message broadcasting, and event streaming.
"""

from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
import logging

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.
    """
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.logger = logger
    
    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """
        Accept WebSocket connection for a session.
        Closes any existing connections for the same session to prevent duplicates.
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
        """
        
        await websocket.accept()
        
        # Close any existing connections for this session to prevent duplicates
        # (e.g., from React StrictMode double-mounting or page refresh)
        if session_id in self.active_connections:
            old_connections = list(self.active_connections[session_id])
            for old_ws in old_connections:
                try:
                    self.logger.info(f"Closing old WebSocket connection for session {session_id}")
                    await old_ws.close(code=1000, reason="New connection established")
                except Exception as e:
                    self.logger.debug(f"Error closing old WebSocket: {e}")
            self.active_connections[session_id].clear()
        else:
            self.active_connections[session_id] = set()
        
        self.active_connections[session_id].add(websocket)
        self.logger.info(f"WebSocket connected for session {session_id} (total: 1)")
        
    
    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """
        Remove WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
        """
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        self.logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_personal_message(
        self,
        message: Dict[str, Any],
        websocket: WebSocket
    ) -> None:
        """
        Send message to a specific WebSocket connection.
        
        Args:
            message: Message to send
            websocket: WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            self.logger.error(f"Error sending WebSocket message: {e}")
    
    async def broadcast_to_session(
        self,
        session_id: str,
        message: Dict[str, Any]
    ) -> None:
        """
        Broadcast message to all connections in a session.
        
        Args:
            session_id: Session identifier
            message: Message to broadcast
        """
        if session_id not in self.active_connections:
            return
        
        disconnected = set()
        
        for websocket in self.active_connections[session_id]:
            try:
                
                await websocket.send_json(message)
                
            except Exception as e:
                self.logger.warning(f"Error broadcasting to session {session_id}: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket, session_id)
    
    async def send_event(
        self,
        session_id: str,
        event_type: str,
        data: Any
    ) -> None:
        """
        Send an event to session.
        
        Args:
            session_id: Session identifier
            event_type: Type of event (message, thinking, tool_call, etc.)
            data: Event data
        """
        message = {
            "type": event_type,
            "timestamp": asyncio.get_event_loop().time(),
            "data": data
        }
        
        connection_count = self.get_connection_count(session_id)
        
        if connection_count == 0:
            self.logger.warning(f"No active connections for session {session_id} when sending event '{event_type}'")
            return
        
        
        await self.broadcast_to_session(session_id, message)
        
    
    def get_connection_count(self, session_id: str) -> int:
        """
        Get number of active connections for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of connections
        """
        return len(self.active_connections.get(session_id, set()))


# Global WebSocket manager
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get global WebSocket manager."""
    global _websocket_manager
    
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    
    return _websocket_manager



