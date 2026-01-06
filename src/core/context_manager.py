"""
Context manager for maintaining conversation state across turns.
Tracks pending confirmations, attendee lists, meeting references, and sheet IDs.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from src.utils.config_loader import get_config
from src.core.entity_memory import EntityMemory, extract_entities_from_tool_result


class ConversationContext:
    """
    Manages conversation context for a single session.
    Tracks state across multiple turns.
    """
    
    def __init__(self, session_id: str):
        """
        Initialize conversation context.
        
        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []
        self.pending_confirmations: Dict[str, Any] = {}
        self.attendee_lists: Dict[str, List[str]] = {}
        self.meeting_references: Dict[str, Dict[str, Any]] = {}
        self.sheet_references: Dict[str, str] = {}
        self.execution_mode: str = "instant"  # "instant" or "approval"
        self.uploaded_files: Dict[str, Dict[str, Any]] = {}  # file_id -> file_data
        self.metadata: Dict[str, Any] = {}  # General metadata (e.g., username)
        self.open_files: List[Dict[str, Any]] = []  # Currently open files in workspace panel
        config = get_config()
        self.model_name: Optional[str] = config.default_model  # Model name for LLM
        
        # NEW: Entity tracking for reference resolution
        self.entity_memory: EntityMemory = EntityMemory()
        
        # NEW: Context window settings for demo
        self.short_term_window: int = 10  # Last 10 messages for planning
        
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to conversation history.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
    
    def get_recent_messages(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent messages from conversation.
        
        Args:
            n: Number of messages to retrieve
            
        Returns:
            List of recent messages
        """
        return self.messages[-n:]
    
    def get_context_for_planning(self) -> List[Dict[str, Any]]:
        """
        Get context for planning (complex tasks).
        Includes: last 10 messages + entity memory
        
        Returns:
            List of recent messages for planning
        """
        return self.get_recent_messages(self.short_term_window)
    
    def get_context_for_simple_task(self) -> List[Dict[str, Any]]:
        """
        Get minimal context for simple tasks.
        Includes: last 4 messages (2 pairs of user-assistant)
        
        Returns:
            List of recent messages for simple tasks
        """
        return self.get_recent_messages(4)
    
    def add_entity_from_tool_result(
        self,
        tool_name: str,
        tool_result: Any,
        turn_number: Optional[int] = None
    ) -> None:
        """
        Automatically extract entities from tool execution results.
        
        Args:
            tool_name: Name of the tool that was executed
            tool_result: Result from tool execution
            turn_number: Turn number (if None, uses current message count)
        """
        if not hasattr(self, 'entity_memory'):
            # Backward compatibility: create entity_memory if it doesn't exist
            self.entity_memory = EntityMemory()
        
        # Extract entities from tool result
        entities = extract_entities_from_tool_result(tool_name, tool_result)
        
        # Add to entity memory
        turn = turn_number if turn_number is not None else len(self.messages)
        for entity in entities:
            self.entity_memory.add_reference(
                entity_type=entity.entity_type,
                entity_id=entity.entity_id,
                name=entity.name,
                metadata=entity.metadata,
                mentioned_at_turn=turn
            )
        
        self.updated_at = datetime.now().isoformat()
    
    def add_pending_confirmation(
        self,
        confirmation_id: str,
        plan: Dict[str, Any]
    ) -> None:
        """
        Add a pending confirmation request.
        
        Args:
            confirmation_id: Unique confirmation ID
            plan: Plan details requiring confirmation
        """
        self.pending_confirmations[confirmation_id] = {
            "plan": plan,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        self.updated_at = datetime.now().isoformat()
    
    def resolve_confirmation(
        self,
        confirmation_id: str,
        approved: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a pending confirmation.
        
        Args:
            confirmation_id: Confirmation ID
            approved: Whether plan was approved
            
        Returns:
            Plan details if found, None otherwise
        """
        if confirmation_id not in self.pending_confirmations:
            return None
        
        confirmation = self.pending_confirmations[confirmation_id]
        confirmation["status"] = "approved" if approved else "rejected"
        confirmation["resolved_at"] = datetime.now().isoformat()
        
        plan = confirmation["plan"]
        del self.pending_confirmations[confirmation_id]
        self.updated_at = datetime.now().isoformat()
        
        return plan if approved else None
    
    def store_attendee_list(self, meeting_id: str, attendees: List[str]) -> None:
        """
        Store attendee list for a meeting.
        
        Args:
            meeting_id: Meeting identifier
            attendees: List of attendee emails
        """
        self.attendee_lists[meeting_id] = attendees
        self.updated_at = datetime.now().isoformat()
    
    def get_attendee_list(self, meeting_id: str) -> Optional[List[str]]:
        """
        Get attendee list for a meeting.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            List of attendees or None
        """
        return self.attendee_lists.get(meeting_id)
    
    def store_meeting_reference(
        self,
        meeting_id: str,
        meeting_data: Dict[str, Any]
    ) -> None:
        """
        Store meeting reference.
        
        Args:
            meeting_id: Meeting identifier
            meeting_data: Meeting details
        """
        self.meeting_references[meeting_id] = meeting_data
        self.updated_at = datetime.now().isoformat()
    
    def get_meeting_reference(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get meeting reference.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Meeting data or None
        """
        return self.meeting_references.get(meeting_id)
    
    def store_sheet_reference(
        self,
        sheet_name: str,
        spreadsheet_id: str
    ) -> None:
        """
        Store spreadsheet reference.
        
        Args:
            sheet_name: Logical name for the sheet
            spreadsheet_id: Google Sheets spreadsheet ID
        """
        self.sheet_references[sheet_name] = spreadsheet_id
        self.updated_at = datetime.now().isoformat()
    
    def get_sheet_reference(self, sheet_name: str) -> Optional[str]:
        """
        Get spreadsheet reference.
        
        Args:
            sheet_name: Logical name for the sheet
            
        Returns:
            Spreadsheet ID or None
        """
        return self.sheet_references.get(sheet_name)
    
    def add_file(self, file_id: str, file_data: Dict[str, Any]) -> None:
        """
        Store uploaded file data.
        
        Args:
            file_id: Unique file identifier
            file_data: File metadata and content
        """
        self.uploaded_files[file_id] = {
            **file_data,
            "uploaded_at": datetime.now().isoformat()
        }
        self.updated_at = datetime.now().isoformat()
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve file data.
        
        Args:
            file_id: File identifier
            
        Returns:
            File data dictionary or None
        """
        return self.uploaded_files.get(file_id)
    
    def set_open_files(self, open_files: List[Dict[str, Any]]) -> None:
        """
        Store currently open files in workspace panel.
        
        Args:
            open_files: List of open file dictionaries with type, title, url, spreadsheet_id, document_id, etc.
        """
        self.open_files = open_files
        self.updated_at = datetime.now().isoformat()
    
    def get_open_files(self) -> List[Dict[str, Any]]:
        """
        Get currently open files.
        
        Returns:
            List of open file dictionaries
        """
        return self.open_files
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "pending_confirmations": self.pending_confirmations,
            "attendee_lists": self.attendee_lists,
            "meeting_references": self.meeting_references,
            "sheet_references": self.sheet_references,
            "execution_mode": self.execution_mode,
            "uploaded_files": getattr(self, "uploaded_files", {}),  # Backward compatibility
            "model_name": getattr(self, "model_name", None),  # Backward compatibility
            "metadata": getattr(self, "metadata", {}),  # Backward compatibility
            "open_files": getattr(self, "open_files", []),  # Backward compatibility
            "entity_memory": self.entity_memory.to_dict() if hasattr(self, 'entity_memory') and self.entity_memory else None,
            "short_term_window": getattr(self, "short_term_window", 10),  # Backward compatibility
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create context from dictionary."""
        context = cls(data["session_id"])
        context.messages = data.get("messages", [])
        context.pending_confirmations = data.get("pending_confirmations", {})
        context.attendee_lists = data.get("attendee_lists", {})
        context.meeting_references = data.get("meeting_references", {})
        context.sheet_references = data.get("sheet_references", {})
        context.execution_mode = data.get("execution_mode", "instant")
        context.uploaded_files = data.get("uploaded_files", {})  # Load uploaded files
        context.metadata = data.get("metadata", {})  # Load metadata
        context.open_files = data.get("open_files", [])  # Load open files
        # Load model_name if exists, otherwise use default from config
        if "model_name" in data:
            context.model_name = data["model_name"]
        # Load entity_memory if exists
        if "entity_memory" in data and data["entity_memory"]:
            context.entity_memory = EntityMemory.from_dict(data["entity_memory"])
        # Load short_term_window if exists
        if "short_term_window" in data:
            context.short_term_window = data["short_term_window"]
        context.created_at = data.get("created_at", datetime.now().isoformat())
        context.updated_at = data.get("updated_at", datetime.now().isoformat())
        return context


class PersistentStorage:
    """
    Handles persistence of conversation contexts to disk.
    """
    
    def __init__(self, storage_dir: Path = Path("data/sessions")):
        """
        Initialize persistent storage.
        
        Args:
            storage_dir: Directory for storing session data
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_context(self, context: ConversationContext) -> None:
        """
        Save conversation context to disk.
        
        Args:
            context: Conversation context to save
        """
        file_path = self.storage_dir / f"{context.session_id}.json"
        with open(file_path, "w") as f:
            json.dump(context.to_dict(), f, indent=2)
    
    def load_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Load conversation context from disk.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Conversation context or None if not found
        """
        file_path = self.storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return ConversationContext.from_dict(data)
        except Exception:
            return None
    
    def delete_context(self, session_id: str) -> None:
        """
        Delete conversation context from disk.
        
        Args:
            session_id: Session identifier
        """
        file_path = self.storage_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()





