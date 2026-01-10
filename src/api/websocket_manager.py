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
    
    async def send_operation_start(
        self,
        session_id: str,
        operation_id: str,
        title: str,
        streaming_title: str,
        operation_type: str = "read",
        file_id: Optional[str] = None,
        file_url: Optional[str] = None,
        file_type: Optional[str] = None,
        intent_id: Optional[str] = None
    ) -> None:
        """
        Send operation start event.
        
        Args:
            session_id: Session identifier
            operation_id: Unique operation identifier
            title: Operation title (e.g., "Записываем послесловие")
            streaming_title: Title for streaming window (e.g., "Сказка.docx")
            operation_type: Type of operation (read | search | write | create | update)
            file_id: Optional file ID for opening in panel
            file_url: Optional file URL
            file_type: Optional file type (sheets | docs | slides | calendar | gmail)
            intent_id: Optional intent ID this operation belongs to
        """
        await self.send_event(session_id, "operation_start", {
            "operation_id": operation_id,
            "intent_id": intent_id,
            "title": title,
            "streaming_title": streaming_title,
            "operation_type": operation_type,
            "file_id": file_id,
            "file_url": file_url,
            "file_type": file_type
        })
    
    async def send_operation_data(
        self,
        session_id: str,
        operation_id: str,
        data: str
    ) -> None:
        """
        Send operation data event (streaming).
        
        Args:
            session_id: Session identifier
            operation_id: Operation identifier
            data: Data string to stream
        """
        await self.send_event(session_id, "operation_data", {
            "operation_id": operation_id,
            "data": data
        })
    
    async def send_operation_end(
        self,
        session_id: str,
        operation_id: str,
        summary: str
    ) -> None:
        """
        Send operation end event.
        
        Args:
            session_id: Session identifier
            operation_id: Operation identifier
            summary: Summary text (e.g., "Получено 10 встреч")
        """
        await self.send_event(session_id, "operation_end", {
            "operation_id": operation_id,
            "summary": summary
        })


# Global WebSocket manager
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get global WebSocket manager."""
    global _websocket_manager
    
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    
    return _websocket_manager



