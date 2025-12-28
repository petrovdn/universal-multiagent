"""
Google Calendar MCP tool wrappers for LangChain.
Provides validated interfaces to calendar operations with timezone handling.
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.validators import (
    validate_email,
    validate_attendee_list,
    parse_datetime,
    validate_date_not_past,
    validate_duration
)
from src.utils.exceptions import ToolExecutionError, ValidationError
from src.utils.retry import retry_on_mcp_error
from src.utils.config_loader import get_config


class CreateEventInput(BaseModel):
    """Input schema for create_event tool."""
    
    title: str = Field(description="Event title/summary")
    start_time: str = Field(description="Start time (ISO 8601 or 'YYYY-MM-DD HH:MM')")
    end_time: Optional[str] = Field(default=None, description="End time (optional if duration provided)")
    duration: Optional[str] = Field(default=None, description="Duration (e.g., '1h', '30m')")
    attendees: Optional[List[str]] = Field(default=None, description="List of attendee emails")
    description: Optional[str] = Field(default=None, description="Event description")
    location: Optional[str] = Field(default=None, description="Event location")
    timezone: Optional[str] = Field(default=None, description="Timezone (default: from config)")


class CreateEventTool(BaseTool):
    """Tool for creating calendar events."""
    
    name: str = "create_event"
    description: str = """
    Create a calendar event in Google Calendar.
    
    Required:
    - title: Event title
    - start_time: Start time (ISO 8601 or 'YYYY-MM-DD HH:MM')
    
    Optional:
    - end_time: End time (or use duration)
    - duration: Event duration (e.g., '1h', '30m')
    - attendees: List of attendee email addresses
    - description: Event description
    - location: Event location
    - timezone: Timezone (default: Europe/Moscow)
    """
    args_schema: type = CreateEventInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        duration: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # Get timezone from config if not provided
            if not timezone:
                timezone = get_config().timezone
            
            # Parse start time
            start_dt = parse_datetime(start_time, timezone)
            validate_date_not_past(start_dt, "start_time")
            
            # Calculate end time
            if end_time:
                end_dt = parse_datetime(end_time, timezone)
            elif duration:
                duration_minutes = validate_duration(duration)
                end_dt = start_dt + timedelta(minutes=duration_minutes)
            else:
                # Default to 1 hour
                end_dt = start_dt + timedelta(hours=1)
            
            if end_dt <= start_dt:
                raise ValidationError("End time must be after start time")
            
            # Validate attendees
            attendee_emails = None
            if attendees:
                attendee_emails = validate_attendee_list(attendees)
            
            # Prepare arguments
            args = {
                "summary": title,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": timezone
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": timezone
                }
            }
            
            if attendee_emails:
                args["attendees"] = [{"email": email} for email in attendee_emails]
            
            if description:
                args["description"] = description
            
            if location:
                args["location"] = location
            
            # Call MCP tool
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("create_event", args, server_name="calendar")
            
            event_id = result.get("id", "unknown")
            return f"Event '{title}' created successfully. Event ID: {event_id}. Start: {start_dt.strftime('%Y-%m-%d %H:%M')}"
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"title": title, "start_time": start_time}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create event: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetNextAvailabilityInput(BaseModel):
    """Input schema for get_next_availability tool."""
    
    attendees: List[str] = Field(description="List of attendee emails")
    duration: str = Field(description="Duration of meeting (e.g., '1h', '30m')")
    start_time: Optional[str] = Field(default=None, description="Earliest start time to consider")


class GetNextAvailabilityTool(BaseTool):
    """Tool for finding next available time slot."""
    
    name: str = "get_next_availability"
    description: str = """
    Find the next available time slot for a group of attendees.
    
    Input:
    - attendees: List of attendee email addresses
    - duration: Meeting duration (e.g., '1h', '30m')
    - start_time: Optional earliest start time to consider
    """
    args_schema: type = GetNextAvailabilityInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        attendees: List[str],
        duration: str,
        start_time: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            attendee_emails = validate_attendee_list(attendees)
            duration_minutes = validate_duration(duration)
            
            timezone = get_config().timezone
            
            args = {
                "attendees": attendee_emails,
                "duration": duration_minutes
            }
            
            if start_time:
                start_dt = parse_datetime(start_time, timezone)
                args["timeMin"] = start_dt.isoformat()
            
            mcp_manager = get_mcp_manager()
            # Note: get_next_availability is not implemented in the MCP server yet
            # For now, return an error message suggesting to use list_events instead
            raise ToolExecutionError(
                "get_next_availability is not yet implemented. "
                "Please use get_calendar_events to check calendar availability manually.",
                tool_name=self.name
            )
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to find availability: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetCalendarEventsInput(BaseModel):
    """Input schema for get_calendar_events tool."""
    
    start_time: Optional[str] = Field(default=None, description="Start of time range")
    end_time: Optional[str] = Field(default=None, description="End of time range")
    max_results: int = Field(default=10, description="Maximum number of events")


class GetCalendarEventsTool(BaseTool):
    """Tool for retrieving calendar events."""
    
    name: str = "get_calendar_events"
    description: str = "Get calendar events for a time range."
    args_schema: type = GetCalendarEventsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            timezone = get_config().timezone
            
            args = {"maxResults": max_results}
            
            if start_time:
                start_dt = parse_datetime(start_time, timezone)
                args["timeMin"] = start_dt.isoformat()
            
            if end_time:
                end_dt = parse_datetime(end_time, timezone)
                args["timeMax"] = end_dt.isoformat()
            
            mcp_manager = get_mcp_manager()
            # #region agent log
            import os
            log_data = {
                "location": "calendar_tools.py:call_tool",
                "message": "Calling list_events MCP tool",
                "data": {"args": args, "server_name": "calendar"},
                "timestamp": int(os.times()[4] * 1000),
                "sessionId": "debug-session",
                "runId": "post-fix",
                "hypothesisId": "C"
            }
            try:
                with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                    import json as json_module
                    f.write(json_module.dumps(log_data) + "\n")
            except:
                pass
            # #endregion
            
            # Fix: Use "list_events" instead of "get_calendar_events" to match MCP server
            result = await mcp_manager.call_tool("list_events", args, server_name="calendar")
            
            # #region agent log
            log_data2 = {
                "location": "calendar_tools.py:call_tool_result",
                "message": "Received result from list_events",
                "data": {"result_type": type(result).__name__, "is_list": isinstance(result, list), "is_dict": isinstance(result, dict)},
                "timestamp": int(os.times()[4] * 1000),
                "sessionId": "debug-session",
                "runId": "post-fix",
                "hypothesisId": "C"
            }
            try:
                with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                    f.write(json_module.dumps(log_data2) + "\n")
            except:
                pass
            # #endregion
            
            # Handle MCP result format (TextContent list or dict)
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result_text = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result_text = first_item['text']
                else:
                    result_text = str(first_item)
                
                # Parse JSON string
                try:
                    result = json.loads(result_text)
                except:
                    result = {"items": [], "count": 0}
            elif isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    result = {"items": [], "count": 0}
            
            events = result.get("items", []) if isinstance(result, dict) else []
            count = result.get("count", len(events)) if isinstance(result, dict) else len(events) if isinstance(events, list) else 0
            
            return f"Found {count} events"
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get events: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_calendar_tools() -> List[BaseTool]:
    """
    Get all Calendar tools.
    
    Returns:
        List of Calendar tool instances
    """
    return [
        CreateEventTool(),
        GetNextAvailabilityTool(),
        GetCalendarEventsTool(),
    ]

