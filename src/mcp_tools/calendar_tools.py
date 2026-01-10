"""
Google Calendar MCP tool wrappers for LangChain.
Provides validated interfaces to calendar operations with timezone handling.
"""

import json
import pytz
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
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
        # #region agent log - H3: CreateEventTool entry
        import time as _time
        import json as _json
        _tool_start = _time.time()
        try:
            open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "create_event:ENTRY", "message": "CreateEventTool._arun entry", "data": {"title": title, "start_time": start_time, "duration": duration, "attendees": str(attendees)[:100] if attendees else None}, "timestamp": int(_tool_start*1000), "sessionId": "debug-session", "hypothesisId": "H3"}) + '\n')
        except Exception:
            pass
        # #endregion
        
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
            
            # #region agent log - H3: Before MCP call_tool
            _mcp_call_start = _time.time()
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "create_event:before_mcp_call", "message": "Before MCP call_tool", "data": {"args": str(args)[:300], "time_since_tool_start_ms": int((_mcp_call_start - _tool_start)*1000)}, "timestamp": int(_mcp_call_start*1000), "sessionId": "debug-session", "hypothesisId": "H3"}) + '\n')
            except Exception:
                pass
            # #endregion
            
            result = await mcp_manager.call_tool("create_event", args, server_name="calendar")
            
            # #region agent log - H3: After MCP call_tool
            _mcp_call_end = _time.time()
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "create_event:after_mcp_call", "message": "After MCP call_tool", "data": {"mcp_duration_ms": int((_mcp_call_end - _mcp_call_start)*1000), "result": str(result)[:200]}, "timestamp": int(_mcp_call_end*1000), "sessionId": "debug-session", "hypothesisId": "H3"}) + '\n')
            except Exception:
                pass
            # #endregion
            
            # Parse result - MCP returns list of TextContent objects
            event_id = "unknown"
            if isinstance(result, list) and len(result) > 0:
                # Extract text from TextContent and parse JSON
                text_content = result[0]
                if hasattr(text_content, 'text'):
                    try:
                        parsed = json.loads(text_content.text)
                        event_id = parsed.get("id", "unknown")
                    except (json.JSONDecodeError, AttributeError):
                        pass
            elif isinstance(result, dict):
                event_id = result.get("id", "unknown")
            
            return f"Event '{title}' created successfully. Event ID: {event_id}. Start: {start_dt.strftime('%Y-%m-%d %H:%M')}"
            
        except ValidationError as e:
            # #region agent log - H3,H4: CreateEventTool ValidationError
            _err_time = _time.time()
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "create_event:VALIDATION_ERROR", "message": "CreateEventTool ValidationError", "data": {"error": str(e), "title": title, "start_time": start_time}, "timestamp": int(_err_time*1000), "sessionId": "debug-session", "hypothesisId": "H3,H4"}) + '\n')
            except Exception:
                pass
            # #endregion
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"title": title, "start_time": start_time}
            ) from e
        except Exception as e:
            # #region agent log - H3,H4: CreateEventTool Exception
            _err_time = _time.time()
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "create_event:EXCEPTION", "message": "CreateEventTool Exception", "data": {"error": str(e), "error_type": type(e).__name__, "title": title, "start_time": start_time}, "timestamp": int(_err_time*1000), "sessionId": "debug-session", "hypothesisId": "H3,H4"}) + '\n')
            except Exception:
                pass
            # #endregion
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
    - duration: Meeting duration (e.g., '1h', '30m', '1.5h')
    - start_time: Optional earliest start time to consider (defaults to now)
    
    Returns the first available slot when all attendees are free.
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
            from src.core.meeting_scheduler import MeetingScheduler
            
            attendee_emails = validate_attendee_list(attendees)
            duration_minutes = validate_duration(duration)
            
            timezone = get_config().timezone
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # Parse start time or default to now
            if start_time:
                search_start = parse_datetime(start_time, timezone)
            else:
                search_start = now
            
            # Search for 7 days from start
            search_end = search_start + timedelta(days=7)
            
            # Use MeetingScheduler to find available slot
            scheduler = MeetingScheduler(use_mcp=True)
            slot = await scheduler.find_available_slot(
                participants=attendee_emails,
                duration_minutes=duration_minutes,
                search_start=search_start.replace(tzinfo=None),
                search_end=search_end.replace(tzinfo=None),
                buffer_minutes=10,  # 10 min buffer between meetings
                working_hours=(9, 18)  # 9am - 6pm
            )
            
            if slot:
                slot_start = slot["start"]
                slot_end = slot["end"]
                # Format result
                result = (
                    f"✅ Found available slot:\n"
                    f"   Start: {slot_start.strftime('%Y-%m-%d %H:%M')}\n"
                    f"   End: {slot_end.strftime('%H:%M')}\n"
                    f"   Duration: {duration_minutes} minutes\n"
                    f"   Attendees: {', '.join(attendee_emails)}\n\n"
                    f"You can now create the meeting using create_event with start_time=\"{slot_start.strftime('%Y-%m-%d %H:%M')}\"."
                )
                return result
            else:
                return (
                    f"❌ No available slot found in the next 7 days for all attendees: {', '.join(attendee_emails)}.\n"
                    f"Consider:\n"
                    f"- Extending the search period\n"
                    f"- Reducing meeting duration (requested: {duration_minutes} min)\n"
                    f"- Checking individual calendars with get_calendar_events"
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
                
                # Calculate end of week (Sunday 23:59:59)
                week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                
                # If end_time not specified OR end_time also contains "неделе" (LLM sometimes passes same value), use week end
                end_lower = end_time.lower() if end_time else ""
                if not end_time or "неделе" in end_lower or "week" in end_lower:
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
                end_time_lower = end_time.lower()
                # Check if end_time is a day-level expression without specific time
                # If so, set to end of that day (23:59:59) to get full day's events
                is_day_expression = any(day_word in end_time_lower for day_word in ["сегодня", "today", "завтра", "tomorrow", "послезавтра"])
                has_specific_time = "в " in end_time_lower or "at " in end_time_lower or ":" in end_time
                
                if is_day_expression and not has_specific_time:
                    # Set end to end of that day
                    end_dt = parse_datetime(end_time, timezone)
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
                else:
                    end_dt = parse_datetime(end_time, timezone)
                args["timeMax"] = end_dt.isoformat()
            
            # #region agent log - H13: Before calling list_events
            import time as _time
            import json as _json
            _list_events_start = _time.time()
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "get_calendar_events:before_list_events", "message": "Before calling list_events MCP tool", "data": {"start_time": start_time, "end_time": end_time, "max_results": max_results, "args": str(args)[:200]}, "timestamp": int(_list_events_start*1000), "sessionId": "debug-session", "hypothesisId": "H13"}) + '\n')
            except Exception:
                pass
            # #endregion
            
            mcp_manager = get_mcp_manager()# Fix: Use "list_events" instead of "get_calendar_events" to match MCP server
            result = await mcp_manager.call_tool("list_events", args, server_name="calendar")
            
            # #region agent log - H13: After calling list_events
            _list_events_end = _time.time()
            _result_type = type(result).__name__
            _result_preview = str(result)[:300] if result else "None"
            try:
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "get_calendar_events:after_list_events", "message": "After calling list_events MCP tool", "data": {"duration_ms": int((_list_events_end - _list_events_start)*1000), "result_type": _result_type, "result_preview": _result_preview, "is_list": isinstance(result, list), "list_length": len(result) if isinstance(result, list) else 0}, "timestamp": int(_list_events_end*1000), "sessionId": "debug-session", "hypothesisId": "H13"}) + '\n')
            except Exception:
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


class DeleteCalendarEventsInput(BaseModel):
    """Input schema for delete_calendar_events tool."""
    
    start_time: str = Field(description="Start of time range. Supports natural language: 'сегодня' (today), 'завтра' (tomorrow), ISO 8601 format, or 'YYYY-MM-DD HH:MM'")
    end_time: Optional[str] = Field(default=None, description="End of time range. If not provided, defaults to end of day for 'сегодня'/'завтра' or +24h for specific time")
    title_filter: Optional[str] = Field(default=None, description="Optional filter to match event titles (case-insensitive substring match)")
    event_ids: Optional[List[str]] = Field(default=None, description="Specific event IDs to delete. If provided, deletes only these events (used after user confirmation)")
    confirmed: bool = Field(default=False, description="Must be True to actually delete events. If False, returns list of events that would be deleted for user confirmation")


class DeleteCalendarEventsTool(BaseTool):
    """
    Tool for deleting calendar events with mandatory user confirmation.
    
    IMPORTANT: This tool requires explicit user confirmation before deleting events.
    On first call (confirmed=False), it returns a list of events that match the criteria.
    On second call (confirmed=True with event_ids), it performs the actual deletion.
    """
    
    name: str = "delete_calendar_events"
    description: str = """
    Delete calendar events with mandatory user confirmation.
    
    ⚠️ ВАЖНО: Этот инструмент ТРЕБУЕТ подтверждения пользователя перед удалением!
    
    ПРОЦЕСС ИСПОЛЬЗОВАНИЯ (ОБЯЗАТЕЛЬНЫЙ ДВУХШАГОВЫЙ ПРОЦЕСС):
    
    1️⃣ ПЕРВЫЙ ВЫЗОВ (поиск событий для удаления):
       - Вызови с confirmed=False (по умолчанию)
       - Укажи временной диапазон (start_time, end_time) и опционально title_filter
       - Инструмент вернет список найденных событий с их ID
       - ПОКАЖИ ПОЛЬЗОВАТЕЛЮ список событий и СПРОСИ подтверждение: "Найдено N встреч. Удалить все?"
    
    2️⃣ ОЖИДАНИЕ ПОДТВЕРЖДЕНИЯ:
       - Дождись явного подтверждения от пользователя ("да", "удаляй", "подтверждаю" и т.п.)
       - Если пользователь отказывается - НЕ вызывай инструмент повторно
    
    3️⃣ ВТОРОЙ ВЫЗОВ (удаление после подтверждения):
       - Вызови с confirmed=True и передай event_ids из первого вызова
       - Инструмент удалит указанные события
    
    Параметры:
    - start_time: Начало временного диапазона ('сегодня', 'завтра', ISO 8601, 'YYYY-MM-DD HH:MM')
    - end_time: Конец временного диапазона (опционально)
    - title_filter: Фильтр по названию события (опционально, поиск подстроки)
    - event_ids: Список ID событий для удаления (для второго вызова)
    - confirmed: Флаг подтверждения (False для поиска, True для удаления)
    
    Примеры использования:
    
    Пример 1: "Удали все встречи за сегодня"
    - 1-й вызов: delete_calendar_events(start_time="сегодня", confirmed=False)
    - Показать пользователю: "Найдено 5 встреч: [список]. Удалить все?"
    - После "Да": delete_calendar_events(event_ids=["id1", "id2", ...], confirmed=True)
    
    Пример 2: "Удали все встречи с названием 'Планерка' на этой неделе"
    - 1-й вызов: delete_calendar_events(start_time="на неделе", title_filter="Планерка", confirmed=False)
    - Показать пользователю список и запросить подтверждение
    - После подтверждения: удалить с confirmed=True
    """
    args_schema: type = DeleteCalendarEventsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        start_time: str,
        end_time: Optional[str] = None,
        title_filter: Optional[str] = None,
        event_ids: Optional[List[str]] = None,
        confirmed: bool = False
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            mcp_manager = get_mcp_manager()
            timezone = get_config().timezone
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # If confirmed=True and event_ids provided, delete the events
            if confirmed and event_ids:
                deleted_count = 0
                errors = []
                
                for event_id in event_ids:
                    try:
                        await mcp_manager.call_tool(
                            "delete_event",
                            {"eventId": event_id, "calendarId": "primary"},
                            server_name="calendar"
                        )
                        deleted_count += 1
                    except Exception as e:
                        errors.append(f"Ошибка при удалении события {event_id}: {str(e)}")
                
                if errors:
                    return f"✅ Удалено {deleted_count} из {len(event_ids)} событий.\n⚠️ Ошибки:\n" + "\n".join(errors)
                else:
                    return f"✅ Успешно удалено {deleted_count} событий из календаря."
            
            # Otherwise, search for events to show user for confirmation
            args = {"maxResults": 100}  # Get more events for deletion
            
            # Parse start_time
            start_lower = start_time.lower()
            
            # Handle "на неделе" / "this week"
            if "на неделе" in start_lower or "на этой неделе" in start_lower or "this week" in start_lower:
                days_since_monday = now.weekday()
                week_start = now - timedelta(days=days_since_monday)
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                args["timeMin"] = week_start.isoformat()
                args["timeMax"] = week_end.isoformat()
            elif "сегодня" in start_lower or "today" in start_lower:
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
                args["timeMin"] = day_start.isoformat()
                if not end_time:
                    args["timeMax"] = day_end.isoformat()
            elif "завтра" in start_lower or "tomorrow" in start_lower:
                tomorrow = now + timedelta(days=1)
                day_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
                args["timeMin"] = day_start.isoformat()
                if not end_time:
                    args["timeMax"] = day_end.isoformat()
            else:
                start_dt = parse_datetime(start_time, timezone)
                args["timeMin"] = start_dt.isoformat()
                if not end_time:
                    # Default to +24h if no end time specified
                    end_dt = start_dt + timedelta(hours=24)
                    args["timeMax"] = end_dt.isoformat()
            
            if end_time:
                end_dt = parse_datetime(end_time, timezone)
                args["timeMax"] = end_dt.isoformat()
            
            # Get events from MCP
            result = await mcp_manager.call_tool("list_events", args, server_name="calendar")
            
            # Parse result
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result_text = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result_text = first_item['text']
                else:
                    result_text = str(first_item)
                
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
            
            # Apply title filter if provided
            if title_filter:
                title_filter_lower = title_filter.lower()
                events = [
                    e for e in events
                    if title_filter_lower in e.get("summary", "").lower()
                ]
            
            if not events:
                return "❌ Не найдено событий для удаления за указанный период" + (f" с фильтром '{title_filter}'" if title_filter else "")
            
            # Build response with events list for user confirmation
            response_parts = [
                f"🔍 Найдено {len(events)} событий для удаления:",
                ""
            ]
            
            event_ids_for_deletion = []
            
            for i, event in enumerate(events, 1):
                event_id = event.get("id")
                summary = event.get("summary", "Без названия")
                start = event.get("start", {})
                end = event.get("end", {})
                
                start_time_str = start.get("dateTime") or start.get("date", "Unknown")
                end_time_str = end.get("dateTime") or end.get("date", "Unknown")
                
                # Format time
                try:
                    if "T" in str(start_time_str):
                        dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                        formatted_start = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        formatted_start = start_time_str
                except:
                    formatted_start = start_time_str
                
                try:
                    if "T" in str(end_time_str):
                        dt = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                        formatted_end = dt.strftime("%H:%M")
                    else:
                        formatted_end = end_time_str
                except:
                    formatted_end = end_time_str
                
                response_parts.append(f"{i}. **{summary}** ({formatted_start} - {formatted_end})")
                event_ids_for_deletion.append(event_id)
            
            response_parts.extend([
                "",
                "⚠️ **ТРЕБУЕТСЯ ПОДТВЕРЖДЕНИЕ**",
                "",
                f"Удалить все {len(events)} событий?",
                "",
                "Для удаления вызовите инструмент повторно с параметрами:",
                f"- confirmed=True",
                f"- event_ids={json.dumps(event_ids_for_deletion)}"
            ])
            
            return "\n".join(response_parts)
            
        except Exception as e:
            raise ToolExecutionError(
                f"Ошибка при работе с событиями календаря: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ScheduleGroupMeetingInput(BaseModel):
    """Input schema for schedule_group_meeting tool."""
    
    title: str = Field(description="Meeting title/summary")
    attendees: List[str] = Field(description="List of attendee email addresses")
    duration: str = Field(default="50m", description="Meeting duration (e.g., '50m', '1h')")
    buffer: str = Field(default="10m", description="Buffer time after meeting (e.g., '10m', '15m')")
    description: Optional[str] = Field(default=None, description="Meeting description")
    location: Optional[str] = Field(default=None, description="Meeting location or video link")
    search_days: int = Field(default=7, description="Number of days to search for available slot")
    working_hours_start: int = Field(default=9, description="Start of working hours (0-23)")
    working_hours_end: int = Field(default=18, description="End of working hours (0-23)")


class ScheduleGroupMeetingTool(BaseTool):
    """
    Tool for scheduling meetings with multiple participants.
    
    Finds the first available time slot when ALL participants are free,
    respecting buffer time between meetings.
    """
    
    name: str = "schedule_group_meeting"
    description: str = """
    Schedule a meeting with multiple participants by finding the first available time slot.
    
    Features:
    - Finds first slot when ALL participants are free
    - Respects buffer time between meetings (default 10 min)
    - Works within working hours (default 9:00-18:00)
    
    Input:
    - title: Meeting title (required)
    - attendees: List of attendee emails (required)
    - duration: Meeting duration (default '50m')
    - buffer: Buffer after meeting (default '10m')
    - description: Optional meeting description
    - location: Optional location or video link
    - search_days: Days to search (default 7)
    - working_hours_start: Start hour (default 9)
    - working_hours_end: End hour (default 18)
    
    Example:
    - title="Командная встреча", attendees=["alice@example.com", "bob@example.com"]
    - Will find first slot where both Alice and Bob are available
    """
    args_schema: type = ScheduleGroupMeetingInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        title: str,
        attendees: List[str],
        duration: str = "50m",
        buffer: str = "10m",
        description: Optional[str] = None,
        location: Optional[str] = None,
        search_days: int = 7,
        working_hours_start: int = 9,
        working_hours_end: int = 18
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            from src.core.meeting_scheduler import MeetingScheduler
            from src.utils.validators import validate_duration, validate_attendee_list
            
            # Validate inputs
            attendee_emails = validate_attendee_list(attendees)
            duration_minutes = validate_duration(duration)
            buffer_minutes = validate_duration(buffer)
            
            timezone = get_config().timezone
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # Get organizer's email (primary calendar) and include in participants
            mcp_manager = get_mcp_manager()
            try:
                calendars_result = await mcp_manager.call_tool("list_calendars", {}, server_name="calendar")
                # Parse result to find primary calendar email
                if calendars_result:
                    import json as _json
                    if hasattr(calendars_result[0], 'text'):
                        calendars_data = _json.loads(calendars_result[0].text)
                    else:
                        calendars_data = calendars_result[0]
                    
                    for cal in calendars_data.get("calendars", []):
                        if cal.get("primary"):
                            organizer_email = cal.get("id")
                            if organizer_email and organizer_email not in attendee_emails:
                                attendee_emails = [organizer_email] + attendee_emails
                                logger.info(f"[ScheduleGroupMeetingTool] Added organizer {organizer_email} to participants")
                            break
            except Exception as e:
                logger.warning(f"[ScheduleGroupMeetingTool] Could not get organizer email: {e}")
            
            # Calculate search range
            search_start = now
            search_end = now + timedelta(days=search_days)
            
            # Create scheduler with MCP integration
            scheduler = MeetingScheduler(use_mcp=True)
            
            # Find available slot (includes organizer + attendees)
            slot = await scheduler.find_available_slot(
                participants=attendee_emails,
                duration_minutes=duration_minutes,
                buffer_minutes=buffer_minutes,
                search_start=search_start,
                search_end=search_end,
                working_hours=(working_hours_start, working_hours_end)
            )
            
            if not slot:
                return (
                    f"Не удалось найти свободное время для встречи '{title}' "
                    f"с участниками {', '.join(attendee_emails)} в ближайшие {search_days} дней. "
                    f"Попробуйте увеличить период поиска или изменить рабочие часы."
                )
            
            # Format slot times
            slot_start = slot["start"]
            slot_end = slot["end"]
            
            # Localize if needed
            if slot_start.tzinfo is None:
                slot_start = tz.localize(slot_start)
            if slot_end.tzinfo is None:
                slot_end = tz.localize(slot_end)
            
            # Create the event using MCP
            mcp_manager = get_mcp_manager()
            
            event_args = {
                "summary": title,
                "start": {
                    "dateTime": slot_start.isoformat(),
                    "timeZone": timezone
                },
                "end": {
                    "dateTime": slot_end.isoformat(),
                    "timeZone": timezone
                },
                "attendees": [{"email": email} for email in attendee_emails]
            }
            
            if description:
                event_args["description"] = description
            
            if location:
                event_args["location"] = location
            
            result = await mcp_manager.call_tool("create_event", event_args, server_name="calendar")
            
            # Format response
            formatted_start = slot_start.strftime("%Y-%m-%d %H:%M")
            formatted_end = slot_end.strftime("%H:%M")
            
            return (
                f"✅ Встреча '{title}' запланирована!\n"
                f"📅 Время: {formatted_start} - {formatted_end}\n"
                f"👥 Участники: {', '.join(attendee_emails)}\n"
                f"⏱ Длительность: {duration_minutes} мин (+ {buffer_minutes} мин буфер)"
            )
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Ошибка валидации: {e.message}",
                tool_name=self.name,
                tool_args={"title": title, "attendees": attendees}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Не удалось запланировать встречу: {e}",
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
        ScheduleGroupMeetingTool(),
        DeleteCalendarEventsTool(),
    ]

