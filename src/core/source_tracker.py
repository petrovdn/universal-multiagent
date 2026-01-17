"""
SourceTracker - Tracks data sources for Perplexity-style UI.

Tracks sources (Gmail, Calendar, Sheets, etc.) and sends WebSocket events
for UI updates (loading, completed, error states).
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime


class SourceTracker:
    """Tracks data sources and sends WebSocket events for UI updates."""
    
    def __init__(self, ws_manager: Any, session_id: str):
        """
        Initialize SourceTracker.
        
        Args:
            ws_manager: WebSocket manager for sending events
            session_id: Session identifier
        """
        self.ws_manager = ws_manager
        self.session_id = session_id
        self._sources: Dict[str, Dict[str, Any]] = {}  # source_id -> source data
        
        # Icon mappings: source_name -> icon
        self.icon_mappings: Dict[str, str] = {
            "Gmail": "📧",
            "Google Calendar": "📅",
            "Google Sheets": "📊",
            "Google Docs": "📄",
            "Google Slides": "📽️",
            "Google Drive": "📁",
            "Calendar": "📅",
            "Sheets": "📊",
            "Docs": "📄",
            "Slides": "📽️",
            "Drive": "📁",
        }
    
    async def track_source(
        self,
        source_name: str,
        tool_name: str,
        preview_data: str,
        intent_id: str
    ) -> str:
        """
        Start tracking a data source and send loading event.
        
        Args:
            source_name: Human-readable source name (e.g., "Gmail", "Google Sheets")
            tool_name: Tool name that's being executed
            preview_data: Preview text to show while loading
            intent_id: Intent block ID
            
        Returns:
            Unique source ID
        """
        source_id = f"src-{uuid.uuid4().hex[:8]}"
        
        # Auto-guess icon
        icon = self._guess_icon(source_name)
        
        source_data = {
            "id": source_id,
            "name": source_name,
            "icon": icon,
            "tool_name": tool_name,
            "preview": preview_data,
            "status": "loading",
            "timestamp": datetime.now().isoformat()
        }
        
        self._sources[source_id] = source_data
        
        # Send loading event
        await self.ws_manager.send_event(
            self.session_id,
            "source_loading",
            {
                "intent_id": intent_id,
                "source": source_data
            }
        )
        
        return source_id
    
    async def update_source_complete(
        self,
        source_id: str,
        result: Any,
        intent_id: str
    ) -> None:
        """
        Mark source as completed and send completed event.
        
        Args:
            source_id: Source ID from track_source
            result: Tool execution result
            intent_id: Intent block ID
        """
        if source_id not in self._sources:
            return
        
        source_data = self._sources[source_id].copy()
        source_data["status"] = "completed"
        source_data["completed_at"] = datetime.now().isoformat()
        
        # Extract item count from result
        item_count = self._extract_item_count(result)
        if item_count is not None:
            source_data["item_count"] = item_count
        
        self._sources[source_id] = source_data
        
        # Send completed event
        await self.ws_manager.send_event(
            self.session_id,
            "source_completed",
            {
                "intent_id": intent_id,
                "source": source_data
            }
        )
    
    async def update_source_error(
        self,
        source_id: str,
        error: str,
        intent_id: str
    ) -> None:
        """
        Mark source as error and send error event.
        
        Args:
            source_id: Source ID from track_source
            error: Error message
            intent_id: Intent block ID
        """
        if source_id not in self._sources:
            return
        
        source_data = self._sources[source_id].copy()
        source_data["status"] = "error"
        source_data["error"] = error
        source_data["completed_at"] = datetime.now().isoformat()
        
        self._sources[source_id] = source_data
        
        # Send error event
        await self.ws_manager.send_event(
            self.session_id,
            "source_error",
            {
                "intent_id": intent_id,
                "source": source_data,
                "error": error
            }
        )
    
    def _guess_icon(self, source_name: str) -> str:
        """
        Auto-guess icon based on source name.
        
        Args:
            source_name: Source name
            
        Returns:
            Icon string (emoji or name)
        """
        # Check exact match first
        if source_name in self.icon_mappings:
            return self.icon_mappings[source_name]
        
        # Check partial matches
        source_lower = source_name.lower()
        for key, icon in self.icon_mappings.items():
            if key.lower() in source_lower or source_lower in key.lower():
                return icon
        
        # Default icon
        return "🔍"
    
    def _extract_item_count(self, result: Any) -> Optional[int]:
        """
        Extract item count from tool result.
        
        Args:
            result: Tool execution result (dict, list, or other)
            
        Returns:
            Item count or None if not found
        """
        if isinstance(result, dict):
            # Check common keys
            for key in ["emails", "events", "rows", "items", "results", "data"]:
                if key in result:
                    items = result[key]
                    if isinstance(items, list):
                        return len(items)
            
            # Check if result itself is a list-like structure
            if "count" in result:
                return result["count"]
        
        elif isinstance(result, list):
            return len(result)
        
        return None
