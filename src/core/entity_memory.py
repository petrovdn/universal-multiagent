"""
Entity Memory for tracking mentioned entities in conversation.
Enables reference resolution (e.g., "this file", "that meeting").
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class EntityReference:
    """Reference to a mentioned entity in the conversation."""
    
    entity_type: str  # "file", "meeting", "email", "sheet"
    entity_id: str
    name: str
    mentioned_at_turn: int  # Turn number when entity was mentioned
    metadata: Dict[str, Any]  # Additional entity data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityReference":
        """Create from dictionary."""
        return cls(
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            name=data.get("name", ""),
            mentioned_at_turn=data.get("mentioned_at_turn", 0),
            metadata=data.get("metadata", {})
        )


class EntityMemory:
    """
    Tracks entities mentioned in conversation for reference resolution.
    
    Stores recent entities (last 5 of each type) to enable understanding
    of references like "this file", "that meeting", "send him an email".
    """
    
    def __init__(self):
        """Initialize entity memory."""
        # Store entities by type, keeping only last 5 of each type
        self._entities: Dict[str, List[EntityReference]] = {
            "file": [],
            "meeting": [],
            "email": [],
            "sheet": []
        }
        self._max_entities_per_type = 5  # For demo: keep last 5 of each type
    
    def add_reference(
        self,
        entity_type: str,
        entity_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        mentioned_at_turn: Optional[int] = None
    ) -> None:
        """
        Add a reference to an entity.
        
        Args:
            entity_type: Type of entity ("file", "meeting", "email", "sheet")
            entity_id: Unique identifier for the entity
            name: Display name of the entity
            metadata: Additional entity data
            mentioned_at_turn: Turn number (if None, will be set automatically)
        """
        if entity_type not in self._entities:
            # Unknown type - create new list for it
            self._entities[entity_type] = []
        
        # Create reference
        reference = EntityReference(
            entity_type=entity_type,
            entity_id=entity_id,
            name=name,
            mentioned_at_turn=mentioned_at_turn or len(self._entities[entity_type]),
            metadata=metadata or {}
        )
        
        # Add to list
        self._entities[entity_type].append(reference)
        
        # Keep only last N entities of this type
        if len(self._entities[entity_type]) > self._max_entities_per_type:
            self._entities[entity_type] = self._entities[entity_type][-self._max_entities_per_type:]
        
    
    def get_latest(self, entity_type: str) -> Optional[EntityReference]:
        """
        Get the most recently mentioned entity of a given type.
        
        Args:
            entity_type: Type of entity to retrieve
            
        Returns:
            Most recent EntityReference or None if no entities of this type
        """
        if entity_type not in self._entities:
            return None
        
        entities = self._entities[entity_type]
        if not entities:
            return None
        
        # Return the last one (most recent)
        return entities[-1]
    
    def has_recent_entities(self) -> bool:
        """
        Check if there are any recent entities in memory.
        
        Returns:
            True if any entities exist, False otherwise
        """
        return any(len(entities) > 0 for entities in self._entities.values())
    
    def has_entities_of_type(self, entity_type: str) -> bool:
        """
        Check if there are entities of a specific type.
        
        Args:
            entity_type: Type to check
            
        Returns:
            True if entities of this type exist
        """
        return entity_type in self._entities and len(self._entities[entity_type]) > 0
    
    def to_context_string(self) -> str:
        """
        Format entities for inclusion in LLM context.
        
        Returns:
            Formatted string describing mentioned entities
        """
        if not self.has_recent_entities():
            return ""
        
        parts = []
        
        # Files
        if self.has_entities_of_type("file"):
            files = self._entities["file"]
            file_list = []
            for file_ref in files[-3:]:  # Show last 3 files
                file_info = f"- {file_ref.name}"
                if file_ref.entity_id:
                    file_info += f" (ID: {file_ref.entity_id})"
                file_list.append(file_info)
            if file_list:
                # Mark most recent one
                if len(files) > 0:
                    latest = files[-1]
                    parts.append(f"Файлы:\n" + "\n".join(file_list) + f"\n  [Последний: {latest.name}]")
                else:
                    parts.append("Файлы:\n" + "\n".join(file_list))
        
        # Meetings
        if self.has_entities_of_type("meeting"):
            meetings = self._entities["meeting"]
            meeting_list = []
            for meeting_ref in meetings[-3:]:  # Show last 3 meetings
                meeting_info = f"- {meeting_ref.name}"
                if meeting_ref.entity_id:
                    meeting_info += f" (ID: {meeting_ref.entity_id})"
                meeting_list.append(meeting_info)
            if meeting_list:
                if len(meetings) > 0:
                    latest = meetings[-1]
                    parts.append(f"Встречи:\n" + "\n".join(meeting_list) + f"\n  [Последняя: {latest.name}]")
                else:
                    parts.append("Встречи:\n" + "\n".join(meeting_list))
        
        # Sheets
        if self.has_entities_of_type("sheet"):
            sheets = self._entities["sheet"]
            sheet_list = []
            for sheet_ref in sheets[-3:]:  # Show last 3 sheets
                sheet_info = f"- {sheet_ref.name}"
                if sheet_ref.entity_id:
                    sheet_info += f" (ID: {sheet_ref.entity_id})"
                sheet_list.append(sheet_info)
            if sheet_list:
                if len(sheets) > 0:
                    latest = sheets[-1]
                    parts.append(f"Таблицы:\n" + "\n".join(sheet_list) + f"\n  [Последняя: {latest.name}]")
                else:
                    parts.append("Таблицы:\n" + "\n".join(sheet_list))
        
        # Emails
        if self.has_entities_of_type("email"):
            emails = self._entities["email"]
            email_list = []
            for email_ref in emails[-3:]:  # Show last 3 emails
                email_info = f"- {email_ref.name}"
                if email_ref.entity_id:
                    email_info += f" (ID: {email_ref.entity_id})"
                email_list.append(email_info)
            if email_list:
                if len(emails) > 0:
                    latest = emails[-1]
                    parts.append(f"Письма:\n" + "\n".join(email_list) + f"\n  [Последнее: {latest.name}]")
                else:
                    parts.append("Письма:\n" + "\n".join(email_list))
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)
    
    def to_brief_string(self) -> str:
        """
        Get brief summary of entities for minimal context.
        
        Returns:
            Brief string with entity counts
        """
        counts = []
        for entity_type, entities in self._entities.items():
            if entities:
                counts.append(f"{len(entities)} {entity_type}(s)")
        
        if not counts:
            return "Нет упомянутых объектов"
        
        return ", ".join(counts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entities": {
                entity_type: [ref.to_dict() for ref in refs]
                for entity_type, refs in self._entities.items()
            },
            "max_entities_per_type": self._max_entities_per_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityMemory":
        """Create from dictionary."""
        memory = cls()
        
        if "entities" in data:
            for entity_type, refs_data in data["entities"].items():
                memory._entities[entity_type] = [
                    EntityReference.from_dict(ref_data)
                    for ref_data in refs_data
                ]
        
        if "max_entities_per_type" in data:
            memory._max_entities_per_type = data["max_entities_per_type"]
        
        return memory


def extract_entities_from_tool_result(
    tool_name: str,
    tool_result: Any
) -> List[EntityReference]:
    """
    Extract entities from tool execution results.
    
    Args:
        tool_name: Name of the tool that was executed
        tool_result: Result from tool execution (can be string, dict, or list)
        
    Returns:
        List of extracted EntityReference objects
    """
    entities = []
    
    
    # Handle string results (may contain JSON or formatted text)
    if isinstance(tool_result, str):
        # Try to parse JSON if it looks like JSON
        import json
        try:
            # Check if result contains JSON
            if tool_result.strip().startswith("{") or tool_result.strip().startswith("["):
                parsed = json.loads(tool_result)
                # Recursively process parsed JSON
                nested_entities = extract_entities_from_tool_result(tool_name, parsed)
                if nested_entities:
                    return nested_entities
                tool_result = parsed
        except (json.JSONDecodeError, ValueError):
            # Not JSON, try to extract from text format
            import re
            
            # Pattern 1: "Found 1 file matching 'query': file_name (ID: file_id)"
            # Example: "Found 1 file matching 'test2': Тест2 (ID: 1RFrX9Hoj-nyQwelJyNHvAPWsXNE9xJktRlr2KZuXKUQ)"
            file_match1 = re.search(r'Found\s+\d+\s+file.*?:\s*([^(]+)\s*\(ID:\s*([\w\-]+)\)', tool_result, re.IGNORECASE)
            if file_match1:
                name = file_match1.group(1).strip()
                entity_id = file_match1.group(2).strip()
                entities.append(EntityReference(
                    entity_type="file",
                    entity_id=entity_id,
                    name=name,
                    mentioned_at_turn=0,
                    metadata={"extracted_from": tool_result, "tool_name": tool_name}
                ))
                return entities
            
            # Pattern 2: Generic "name (ID: id)" pattern
            file_match2 = re.search(r'([\w\s\-\.]+?)\s*\(ID:\s*([\w\-]+)\)', tool_result)
            if file_match2:
                name = file_match2.group(1).strip()
                entity_id = file_match2.group(2).strip()
                # Only add if it looks like a file (not just any ID reference)
                if tool_name in ("search_workspace_files", "search_files", "find_and_open_file", "open_file"):
                    entities.append(EntityReference(
                        entity_type="file",
                        entity_id=entity_id,
                        name=name,
                        mentioned_at_turn=0,
                        metadata={"extracted_from": tool_result, "tool_name": tool_name}
                    ))
                    return entities
            
            # Pattern 3: Extract from find_and_open_file results
            # Look for file information in the result text
            if tool_name in ("find_and_open_file", "open_file", "workspace_find_and_open_file"):
                # Try multiple patterns to extract file info
                # Pattern 3a: "Document: title" or "Spreadsheet: file_name"
                doc_match = re.search(r'(?:Document|Spreadsheet):\s*([^\n]+)', tool_result, re.IGNORECASE)
                # Pattern 3b: "File 'file_name' found" or "File 'file_name' (ID: ...)"
                file_match = re.search(r"File\s+['\"]?([^'\"]+)['\"]?\s*(?:found|\(ID:)", tool_result, re.IGNORECASE)
                # Pattern 3c: Look for ID in "All matches:" section
                all_matches_section = re.search(r'All matches:.*?-\s*([^(]+)\s*\(ID:\s*([\w\-]+)\)', tool_result, re.DOTALL | re.IGNORECASE)
                
                name = None
                entity_id = None
                
                if all_matches_section:
                    # Extract from "All matches:" section (first match)
                    name = all_matches_section.group(1).strip()
                    entity_id = all_matches_section.group(2).strip()
                elif doc_match:
                    name = doc_match.group(1).strip()
                    # Try to find ID in the text
                    id_match = re.search(r'\(ID:\s*([\w\-]+)\)', tool_result)
                    if id_match:
                        entity_id = id_match.group(1).strip()
                elif file_match:
                    name = file_match.group(1).strip()
                    # Try to find ID
                    id_match = re.search(r'\(ID:\s*([\w\-]+)\)', tool_result)
                    if id_match:
                        entity_id = id_match.group(1).strip()
                
                if name and entity_id:
                    entities.append(EntityReference(
                        entity_type="file",
                        entity_id=entity_id,
                        name=name,
                        mentioned_at_turn=0,
                        metadata={"extracted_from": tool_result, "tool_name": tool_name}
                    ))
                    return entities
                elif name:
                    # If we have name but no ID, still add it (ID might be in metadata later)
                    entities.append(EntityReference(
                        entity_type="file",
                        entity_id="",  # Will be filled from metadata if available
                        name=name,
                        mentioned_at_turn=0,
                        metadata={"extracted_from": tool_result, "tool_name": tool_name, "needs_id": True}
                    ))
                    return entities
            
            return entities
    
    # Handle list results (e.g., search_files returns list of files)
    if isinstance(tool_result, list):
        if tool_name in ("search_workspace_files", "search_files", "list_files"):
            # File search results
            for item in tool_result[:3]:  # Max 3 files
                if isinstance(item, dict):
                    file_id = item.get("id") or item.get("file_id", "")
                    file_name = item.get("name") or item.get("file_name", "")
                    if file_id and file_name:
                        entities.append(EntityReference(
                            entity_type="file",
                            entity_id=str(file_id),
                            name=str(file_name),
                            mentioned_at_turn=0,
                            metadata=item
                        ))
        elif tool_name in ("list_events", "get_calendar_events"):
            # Calendar event results
            for item in tool_result[:3]:  # Max 3 events
                if isinstance(item, dict):
                    event_id = item.get("id", "")
                    event_summary = item.get("summary") or item.get("title", "")
                    if event_id and event_summary:
                        entities.append(EntityReference(
                            entity_type="meeting",
                            entity_id=str(event_id),
                            name=str(event_summary),
                            mentioned_at_turn=0,
                            metadata=item
                        ))
    
    # Handle dict results
    elif isinstance(tool_result, dict):
        if tool_name == "create_event":
            # Created event
            event_id = tool_result.get("id", "")
            event_summary = tool_result.get("summary") or tool_result.get("title", "")
            if event_id and event_summary:
                entities.append(EntityReference(
                    entity_type="meeting",
                    entity_id=str(event_id),
                    name=str(event_summary),
                    mentioned_at_turn=0,
                    metadata=tool_result
                ))
        elif tool_name in ("create_sheet", "create_spreadsheet"):
            # Created spreadsheet
            sheet_id = tool_result.get("id") or tool_result.get("spreadsheet_id", "")
            sheet_name = tool_result.get("name") or tool_result.get("title", "")
            if sheet_id and sheet_name:
                entities.append(EntityReference(
                    entity_type="sheet",
                    entity_id=str(sheet_id),
                    name=str(sheet_name),
                    mentioned_at_turn=0,
                    metadata=tool_result
                ))
        elif tool_name == "send_email":
            # Sent email
            email_id = tool_result.get("id") or tool_result.get("message_id", "")
            email_subject = tool_result.get("subject") or tool_result.get("summary", "")
            if email_id and email_subject:
                entities.append(EntityReference(
                    entity_type="email",
                    entity_id=str(email_id),
                    name=str(email_subject),
                    mentioned_at_turn=0,
                    metadata=tool_result
                ))
        elif "file_id" in tool_result or "id" in tool_result:
            # Generic file result
            file_id = tool_result.get("file_id") or tool_result.get("id", "")
            file_name = tool_result.get("file_name") or tool_result.get("name", "")
            if file_id and file_name:
                entities.append(EntityReference(
                    entity_type="file",
                    entity_id=str(file_id),
                    name=str(file_name),
                    mentioned_at_turn=0,
                    metadata=tool_result
                ))
    
    return entities

