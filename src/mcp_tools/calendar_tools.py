"""
Google Calendar MCP tool wrappers for LangChain.
Provides validated interfaces to calendar operations with timezone handling.
"""

import json
import pytz
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
    
    start_time: Optional[str] = Field(
        default=None, 
        description="Start of time range. Supports natural language: 'сегодня' (today), 'завтра' (tomorrow), 'на неделе' (this week), 'на прошлой неделе' (previous calendar week Mon-Sun), 'за прошлые две недели' (past two weeks), ISO 8601 format, or 'YYYY-MM-DD HH:MM'. Timezone is automatically handled."
    )
    end_time: Optional[str] = Field(
        default=None, 
        description="End of time range. Supports natural language: 'сегодня' (today), 'завтра' (tomorrow), 'на неделе' (this week), 'на прошлой неделе' (previous calendar week Mon-Sun), 'за прошлые две недели' (past two weeks), ISO 8601 format, or 'YYYY-MM-DD HH:MM'. Timezone is automatically handled."
    )
    max_results: int = Field(default=10, description="Maximum number of events")


class GetCalendarEventsTool(BaseTool):
    """Tool for retrieving calendar events."""
    
    name: str = "get_calendar_events"
    description: str = """
    Get calendar events for a time range.
    
    IMPORTANT: You can use natural language for dates:
    - 'сегодня' (today) - events for today
    - 'завтра' (tomorrow) - events for tomorrow
    - 'на неделе' or 'на этой неделе' (this week) - events for current week (Monday to Sunday)
    - 'за прошлую неделю' or 'на прошлой неделе' (last week) - events for previous calendar week (Monday to Sunday)
    - 'за прошлые две недели' or 'за последние две недели' (past two weeks) - events for past 14 days
    - ISO 8601 format: '2024-01-15T14:30:00+03:00'
    - Simple format: '2024-01-15 14:30'
    
    The system automatically handles timezone conversion. You don't need to worry about timezone - just use natural expressions like 'сегодня', 'завтра', 'на неделе', 'на прошлой неделе', 'за прошлые две недели'.
    
    Examples:
    - start_time='сегодня', end_time='завтра' - events from today to tomorrow
    - start_time='на неделе' - events for this week (automatically calculates Monday-Sunday range)
    - start_time='на прошлой неделе' - events for previous calendar week (Monday-Sunday)
    - start_time='за прошлые две недели' - events for past 14 days (automatically calculates range)
    - start_time='2024-01-15 09:00', end_time='2024-01-15 18:00' - events for specific day
    """
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
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            args = {"maxResults": max_results}
            
            # Handle "за прошлую неделю" / "на прошлой неделе" / "past week" / "last week" - previous calendar week (Mon-Sun)
            start_lower = start_time.lower() if start_time else ""
            if start_time and ("за прошлую неделю" in start_lower or "за последнюю неделю" in start_lower or "на прошлой неделе" in start_lower or "past week" in start_lower or "last week" in start_lower):
                # Calculate previous calendar week (Monday to Sunday)
                days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
                current_week_monday = now - timedelta(days=days_since_monday)
                last_week_monday = current_week_monday - timedelta(days=7)
                last_week_monday = last_week_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                last_week_sunday = last_week_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
                
                args["timeMin"] = last_week_monday.isoformat()
                
                # If end_time not specified, set to end of last week (Sunday)
                if not end_time:
                    args["timeMax"] = last_week_sunday.isoformat()
                else:
                    end_dt = parse_datetime(end_time, timezone)
                    args["timeMax"] = end_dt.isoformat()
            # Handle "за прошлые две недели" / "past two weeks" - automatically set range
            elif start_time and ("за прошлые две недели" in start_time.lower() or "за последние две недели" in start_time.lower() or "past two weeks" in start_time.lower() or "last two weeks" in start_time.lower()):
                # Calculate start of two weeks ago
                days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
                two_weeks_ago = now - timedelta(days=14)
                two_weeks_ago_start = two_weeks_ago.replace(hour=0, minute=0, second=0, microsecond=0)
                args["timeMin"] = two_weeks_ago_start.isoformat()
                
                # If end_time not specified, set to now (end of range)
                if not end_time:
                    args["timeMax"] = now.isoformat()
                else:
                    end_dt = parse_datetime(end_time, timezone)
                    args["timeMax"] = end_dt.isoformat()
            # Handle "на неделе" / "this week" - automatically set week range
            elif start_time and ("на неделе" in start_time.lower() or "на этой неделе" in start_time.lower() or "this week" in start_time.lower()):
                # Calculate start of current week (Monday)
                days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
                week_start = now - timedelta(days=days_since_monday)
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                args["timeMin"] = week_start.isoformat()
                
                # If end_time not specified, set to end of week
                if not end_time:
                    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    args["timeMax"] = week_end.isoformat()
                else:
                    end_dt = parse_datetime(end_time, timezone)
                    args["timeMax"] = end_dt.isoformat()
            elif start_time:
                start_dt = parse_datetime(start_time, timezone)
                args["timeMin"] = start_dt.isoformat()
                
                # If end_time not specified and start_time is "сегодня" or "завтра", set end to end of that day
                if not end_time:
                    if "сегодня" in start_time.lower() or "today" in start_time.lower():
                        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
                        args["timeMax"] = end_dt.isoformat()
                    elif "завтра" in start_time.lower() or "tomorrow" in start_time.lower():
                        tomorrow = now + timedelta(days=1)
                        end_dt = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
                        args["timeMax"] = end_dt.isoformat()
            
            if end_time and not ("на неделе" in start_time.lower() if start_time else False):
                end_dt = parse_datetime(end_time, timezone)
                args["timeMax"] = end_dt.isoformat()
            
            mcp_manager = get_mcp_manager()# Fix: Use "list_events" instead of "get_calendar_events" to match MCP server
            result = await mcp_manager.call_tool("list_events", args, server_name="calendar")# Handle MCP result format (TextContent list or dict)
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
            
            # If no events, return simple message
            if count == 0:
                return "Found 0 events"
            
            # If we have events but no details in items, return count with suggestion
            if isinstance(events, list) and len(events) == 0:
                return f"Found {count} events (details not available in current response)"
            
            # Build detailed response with event information
            response_parts = [f"Found {count} event(s):"]
            
            for i, event in enumerate(events[:max_results], 1):
                if isinstance(event, dict):
                    summary = event.get("summary", event.get("title", "No title"))
                    start = event.get("start", {})
                    end = event.get("end", {})
                    
                    # Parse datetime
                    start_time = start.get("dateTime") or start.get("date", "Unknown")
                    end_time = end.get("dateTime") or end.get("date", "Unknown")
                    
                    # Format time for display
                    try:
                        if "T" in start_time:
                            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                            formatted_start = dt.strftime("%Y-%m-%d %H:%M")
                        else:
                            formatted_start = start_time
                    except:
                        formatted_start = start_time
                    
                    try:
                        if "T" in end_time:
                            dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                            formatted_end = dt.strftime("%Y-%m-%d %H:%M")
                        else:
                            formatted_end = end_time
                    except:
                        formatted_end = end_time
                    
                    location = event.get("location", "")
                    attendees = event.get("attendees", [])
                    description = event.get("description", "")
                    
                    event_info = f"\n{i}. {summary}"
                    event_info += f"\n   Время: {formatted_start} - {formatted_end}"
                    
                    if location:
                        event_info += f"\n   Место: {location}"
                    
                    if attendees:
                        attendee_names = [a.get("displayName") or a.get("email", "") for a in attendees if isinstance(a, dict)]
                        if attendee_names:
                            event_info += f"\n   Участники: {', '.join(attendee_names[:5])}"
                            if len(attendee_names) > 5:
                                event_info += f" (и еще {len(attendee_names) - 5})"
                    
                    if description:
                        desc_preview = description[:100] + "..." if len(description) > 100 else description
                        event_info += f"\n   Описание: {desc_preview}"
                    
                    response_parts.append(event_info)
                else:
                    response_parts.append(f"\n{i}. {str(event)}")
            
            if count > max_results:
                response_parts.append(f"\n... и еще {count - max_results} событие(ий)")
            
            return "\n".join(response_parts)
            
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

