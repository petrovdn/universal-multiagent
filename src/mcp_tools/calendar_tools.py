"""
Google Calendar MCP tool wrappers for LangChain.
Provides validated interfaces to calendar operations with timezone handling.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime as dt, timedelta
import pytz
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
            result = await mcp_manager.call_tool("get_next_availability", args, server_name="calendar")
            
            available_time = result.get("start", "unknown")
            return f"Next available time slot: {available_time} for {len(attendee_emails)} attendees"
            
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
        description="Start of time range. Use relative dates like 'вчера', 'сегодня', 'завтра' or ISO format. DO NOT use old dates from past years."
    )
    end_time: Optional[str] = Field(
        default=None, 
        description="End of time range. Use relative dates like 'вчера', 'сегодня', 'завтра' or ISO format. DO NOT use old dates from past years."
    )
    max_results: int = Field(default=10, description="Maximum number of events")


class GetCalendarEventsTool(BaseTool):
    """Tool for retrieving calendar events."""
    
    name: str = "get_calendar_events"
    description: str = """Get calendar events for a time range.
    
IMPORTANT: When user asks about "вчера" (yesterday) or "сегодня" (today), 
pass these words directly as start_time/end_time parameters. 
DO NOT convert them to specific dates - the tool will handle parsing.
Example: start_time="вчера", end_time="вчера" for yesterday's events.
Example: start_time="сегодня", end_time="сегодня" for today's events."""
    args_schema: type = GetCalendarEventsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Execute the tool asynchronously."""
        # #region agent log
        import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:220","message":"get_calendar_events ENTRY","data":{"start_time":start_time,"end_time":end_time,"max_results":max_results},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A,B"})+'\n')
        # #endregion
        try:
            timezone = get_config().timezone
            tz = pytz.timezone(timezone)
            now = dt.now(tz)
            
            args = {"maxResults": max_results}
            
            if start_time:
                # Check if date is suspiciously old (more than 1 year ago)
                try:
                    # Try to parse as ISO date first
                    if 'T' in start_time or len(start_time) == 10:
                        parsed_test = dt.fromisoformat(start_time.replace('Z', '+00:00'))
                        if parsed_test.year < now.year - 1:
                            # Date is too old, treat as relative date
                            # #region agent log
                            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:232","message":"Detected old date, converting to relative","data":{"input":start_time,"parsed_year":parsed_test.year,"current_year":now.year},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"B"})+'\n')
                            # #endregion
                            # If it's a date from 2023 and we're in 2025, user probably meant "вчера" or "сегодня"
                            # But we can't guess, so we'll parse it anyway and let Google Calendar return empty
                            pass
                except Exception:
                    pass  # Not an ISO date, will be parsed as relative
                
                start_dt = parse_datetime(start_time, timezone)
                # If it's a relative date without time, set to start of day
                is_relative_date = start_time.lower() in ("вчера", "сегодня", "завтра", "yesterday", "today", "tomorrow")
                if is_relative_date:
                    # Always set to start of day for relative dates
                    start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                args["timeMin"] = start_dt.isoformat()
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:250","message":"Parsed start_time","data":{"input":start_time,"parsed":start_dt.isoformat(),"timezone":timezone,"year":start_dt.year},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"B,C"})+'\n')
                # #endregion
            
            if end_time:
                # Similar check for end_time
                try:
                    if 'T' in end_time or len(end_time) == 10:
                        parsed_test = dt.fromisoformat(end_time.replace('Z', '+00:00'))
                        if parsed_test.year < now.year - 1:
                            # #region agent log
                            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:260","message":"Detected old end_date","data":{"input":end_time,"parsed_year":parsed_test.year},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"B"})+'\n')
                            # #endregion
                            pass
                except Exception:
                    pass
                
                end_dt = parse_datetime(end_time, timezone)
                # If it's a relative date without time, set to end of day
                is_relative_date = end_time.lower() in ("вчера", "сегодня", "завтра", "yesterday", "today", "tomorrow")
                if is_relative_date:
                    # Always set to end of day for relative dates
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                args["timeMax"] = end_dt.isoformat()
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:275","message":"Parsed end_time","data":{"input":end_time,"parsed":end_dt.isoformat(),"timezone":timezone,"year":end_dt.year},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"B,C"})+'\n')
                # #endregion
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("list_events", args, server_name="calendar")
            # #region agent log
            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:241","message":"Raw MCP result","data":{"result_type":str(type(result)),"result_repr":repr(result)[:500],"is_list":isinstance(result,list),"len":len(result) if isinstance(result,list) else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
            # #endregion
            
            # MCP server may return TextContent objects that need to be parsed
            # Handle different result formats from MCP server
            events = []
            
            if isinstance(result, list):
                # Could be a list of events or list of TextContent objects
                if result and hasattr(result[0], 'text'):
                    # List of TextContent objects - parse the JSON inside
                    try:
                        import json as json_lib
                        for item in result:
                            if hasattr(item, 'text'):
                                parsed = json_lib.loads(item.text)
                                if isinstance(parsed, dict) and 'items' in parsed:
                                    events.extend(parsed['items'])
                                elif isinstance(parsed, list):
                                    events.extend(parsed)
                    except Exception as parse_error:
                        # #region agent log
                        import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:260","message":"Failed to parse TextContent","data":{"error":str(parse_error)},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                        # #endregion
                        events = result  # Fallback to raw list
                else:
                    # Regular list of event dicts
                    events = result
            elif isinstance(result, dict):
                events = result.get("items", [])
            elif hasattr(result, 'text'):
                # Single TextContent object
                try:
                    import json as json_lib
                    parsed = json_lib.loads(result.text)
                    if isinstance(parsed, dict) and 'items' in parsed:
                        events = parsed['items']
                    elif isinstance(parsed, list):
                        events = parsed
                except Exception:
                    events = []
            
            # #region agent log
            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:278","message":"Parsed events","data":{"events_count":len(events),"first_event":events[0] if events else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
            # #endregion
            
            # Format events into readable text - compact format
            if not events:
                return_value = "No events found for the specified time range."
            else:
                event_details = []
                for event in events:
                    if isinstance(event, dict):
                        summary = event.get('summary', 'No title')
                        start = event.get('start', {})
                        
                        # Parse and format start time nicely
                        start_time_str = start.get('dateTime') or start.get('date', '')
                        if start_time_str:
                            try:
                                # Use datetime class from imported module
                                if 'T' in start_time_str:
                                    # datetime format
                                    event_dt = dt.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                    # Format as "HH:MM" or "DD.MM HH:MM" if not today
                                    time_str = event_dt.strftime("%H:%M")
                                    event_details.append(f"- {summary} в {time_str}")
                                else:
                                    # date only format
                                    event_dt = dt.fromisoformat(start_time_str)
                                    date_str = event_dt.strftime("%d.%m")
                                    event_details.append(f"- {summary} ({date_str})")
                            except Exception:
                                event_details.append(f"- {summary}")
                        else:
                            event_details.append(f"- {summary}")
                    else:
                        event_details.append(f"- {str(event)}")
                
                return_value = f"Найдено {len(events)} событий:\n" + "\n".join(event_details)
            
            return return_value
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get events: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetEventInput(BaseModel):
    """Input schema for get_event tool."""
    
    event_id: str = Field(description="Event ID from calendar")
    calendar_id: Optional[str] = Field(default="primary", description="Calendar ID (default: primary)")


class GetEventTool(BaseTool):
    """Tool for getting detailed information about a specific calendar event."""
    
    name: str = "get_event"
    description: str = """Get detailed information about a specific calendar event.
    
    Required:
    - event_id: The ID of the event (can be obtained from list_events)
    
    Optional:
    - calendar_id: Calendar ID (default: 'primary')
    
    Returns detailed event information including:
    - Summary/title
    - Start and end times
    - Description
    - Location
    - Attendees
    - Status
    - Other event details"""
    args_schema: type = GetEventInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        event_id: str,
        calendar_id: str = "primary"
    ) -> str:
        """Execute the tool asynchronously."""
        # #region agent log
        import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:435","message":"get_event ENTRY","data":{"event_id":event_id,"calendar_id":calendar_id,"len":len(event_id),"has_space":' ' in event_id,"has_unicode":any(ord(c) > 127 for c in event_id if c.isalpha())},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
        # #endregion
        try:
            # Check if event_id looks like a title/name instead of an actual ID
            # Event IDs are typically long alphanumeric strings (20+ chars), not readable text
            actual_event_id = event_id
            is_title = len(event_id) < 20 or ' ' in event_id or any(ord(c) > 127 for c in event_id if c.isalpha())
            # #region agent log
            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:442","message":"Checking if event_id is title","data":{"event_id":event_id,"is_title":is_title},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
            # #endregion
            if is_title:
                # This looks like a title, not an ID - need to search for the event
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:404","message":"Event ID looks like title, searching","data":{"input":event_id},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                # #endregion
                
                # Search for events with matching title
                mcp_manager = get_mcp_manager()
                timezone = get_config().timezone
                tz = pytz.timezone(timezone)
                now = dt.now(tz)
                
                # Search in today, yesterday, and tomorrow
                search_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                search_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
                
                search_args = {
                    "timeMin": search_start.isoformat(),
                    "timeMax": search_end.isoformat(),
                    "maxResults": 50
                }
                
                search_result = await mcp_manager.call_tool("list_events", search_args, server_name="calendar")
                
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:465","message":"Search result for title lookup","data":{"result_type":str(type(search_result)),"is_list":isinstance(search_result,list),"len":len(search_result) if isinstance(search_result,list) else None,"has_text":hasattr(search_result[0],'text') if isinstance(search_result,list) and search_result else False},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                # #endregion
                
                # Parse search results
                found_events = []
                if isinstance(search_result, list) and search_result:
                    if hasattr(search_result[0], 'text'):
                        try:
                            import json as json_lib
                            parsed = json_lib.loads(search_result[0].text)
                            if isinstance(parsed, dict) and 'items' in parsed:
                                found_events = parsed['items']
                            elif isinstance(parsed, list):
                                found_events = parsed
                        except Exception as e:
                            # #region agent log
                            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:477","message":"Failed to parse search result","data":{"error":str(e)},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                            # #endregion
                            pass
                    elif isinstance(search_result[0], dict):
                        found_events = search_result
                
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:485","message":"Parsed found_events","data":{"count":len(found_events),"first_summary":found_events[0].get('summary') if found_events and isinstance(found_events[0],dict) else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                # #endregion
                
                # Find matching event by title (case-insensitive partial match)
                matching_event = None
                event_id_lower = event_id.lower()
                for event in found_events:
                    if isinstance(event, dict):
                        event_summary = event.get('summary', '').lower()
                        if event_id_lower in event_summary or event_summary in event_id_lower:
                            matching_event = event
                            break
                
                if matching_event:
                    actual_event_id = matching_event.get('id')
                    # #region agent log
                    import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:497","message":"Found event by title","data":{"title":event_id,"found_id":actual_event_id,"found_summary":matching_event.get('summary')},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                    # #endregion
                else:
                    # #region agent log
                    import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:501","message":"Event not found by title","data":{"title":event_id,"searched_events":len(found_events)},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                    # #endregion
                    raise ToolExecutionError(
                        f"Event with title '{event_id}' not found. Please use the exact event ID from the list.",
                        tool_name=self.name
                    )
            
            args = {
                "eventId": actual_event_id,
                "calendarId": calendar_id
            }
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("get_event", args, server_name="calendar")
            # #region agent log
            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:510","message":"get_event MCP result","data":{"result_type":str(type(result)),"is_list":isinstance(result,list),"len":len(result) if isinstance(result,list) else None,"first_item_type":str(type(result[0])) if isinstance(result,list) and result else None,"has_text":hasattr(result[0],'text') if isinstance(result,list) and result else False,"first_item_repr":str(result[0])[:500] if isinstance(result,list) and result else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A,B,C"})+'\n')
            # #endregion
            
            # Handle different result formats from MCP server
            event_data = None
            
            # Case 1: List of TextContent objects
            if isinstance(result, list) and result:
                if hasattr(result[0], 'text'):
                    # TextContent object - parse JSON
                    # #region agent log
                    import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:518","message":"Processing TextContent","data":{"text_preview":result[0].text[:500]},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                    # #endregion
                    try:
                        import json as json_lib
                        event_data = json_lib.loads(result[0].text)
                    except Exception as e:
                        # #region agent log
                        import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:525","message":"Failed to parse TextContent in get_event","data":{"error":str(e),"text_preview":result[0].text[:500] if hasattr(result[0],'text') else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                        # #endregion
                        event_data = {"raw": str(result)}
                elif isinstance(result[0], dict):
                    # Direct dict in list
                    # #region agent log
                    import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:530","message":"Processing dict in list","data":{"keys":list(result[0].keys()) if isinstance(result[0],dict) else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                    # #endregion
                    event_data = result[0]
                else:
                    # Try to parse as JSON string
                    # #region agent log
                    import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:535","message":"Processing non-dict, non-TextContent","data":{"type":str(type(result[0])),"repr":str(result[0])[:500]},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                    # #endregion
                    try:
                        import json as json_lib
                        event_data = json_lib.loads(str(result[0]))
                    except Exception as e:
                        # #region agent log
                        import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:540","message":"Failed to parse as JSON string","data":{"error":str(e)},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
                        # #endregion
                        event_data = {"raw": str(result)}
            # Case 2: Single TextContent object
            elif hasattr(result, 'text'):
                try:
                    import json as json_lib
                    event_data = json_lib.loads(result.text)
                except Exception:
                    event_data = {"raw": str(result)}
            # Case 3: Direct dict
            elif isinstance(result, dict):
                event_data = result
            else:
                event_data = {"raw": str(result)}
            
            # #region agent log
            import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:580","message":"Parsed event_data","data":{"is_dict":isinstance(event_data,dict),"keys":list(event_data.keys()) if isinstance(event_data,dict) else None,"has_description":"description" in event_data if isinstance(event_data,dict) else False,"has_attendees":"attendees" in event_data if isinstance(event_data,dict) else False,"description_preview":event_data.get("description","")[:100] if isinstance(event_data,dict) else None,"attendees_count":len(event_data.get("attendees",[])) if isinstance(event_data,dict) else None,"error":event_data.get("error") if isinstance(event_data,dict) else None,"full_error":str(event_data) if isinstance(event_data,dict) and "error" in event_data else None},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A,B,C"})+'\n')
            # #endregion
            
            # Check for errors from MCP server
            if isinstance(event_data, dict) and "error" in event_data:
                error_msg = event_data.get("error", "Unknown error")
                # #region agent log
                import json,asyncio;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:584","message":"MCP server returned error","data":{"error":error_msg,"event_id":actual_event_id},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"B"})+'\n')
                # #endregion
                raise ToolExecutionError(
                    f"Failed to get event details: {error_msg}",
                    tool_name=self.name
                )
            
            # Format event details in a readable way
            if isinstance(event_data, dict):
                summary = event_data.get('summary', 'No title')
                start = event_data.get('start', {})
                end = event_data.get('end', {})
                description = event_data.get('description', '')
                location = event_data.get('location', '')
                status = event_data.get('status', '')
                attendees = event_data.get('attendees', [])
                
                # Format start/end times
                start_time = start.get('dateTime') or start.get('date', 'No time')
                end_time = end.get('dateTime') or end.get('date', 'No time')
                
                # Parse and format times nicely
                try:
                    if 'T' in start_time:
                        start_dt = dt.fromisoformat(start_time.replace('Z', '+00:00'))
                        start_formatted = start_dt.strftime("%d.%m.%Y %H:%M")
                    else:
                        start_formatted = start_time
                    
                    if 'T' in end_time:
                        end_dt = dt.fromisoformat(end_time.replace('Z', '+00:00'))
                        end_formatted = end_dt.strftime("%d.%m.%Y %H:%M")
                    else:
                        end_formatted = end_time
                except Exception:
                    start_formatted = start_time
                    end_formatted = end_time
                
                # Build response
                details = [f"📅 {summary}"]
                details.append(f"⏰ Начало: {start_formatted}")
                details.append(f"⏰ Конец: {end_formatted}")
                
                if location:
                    details.append(f"📍 Место: {location}")
                
                if description:
                    # Truncate long descriptions
                    desc = description[:200] + "..." if len(description) > 200 else description
                    details.append(f"📝 Описание: {desc}")
                
                if attendees:
                    attendee_names = [att.get('email', att.get('displayName', 'Unknown')) for att in attendees]
                    details.append(f"👥 Участники: {', '.join(attendee_names[:5])}")
                    if len(attendees) > 5:
                        details.append(f"   ... и еще {len(attendees) - 5}")
                
                if status:
                    status_ru = {"confirmed": "Подтверждено", "tentative": "Предварительно", "cancelled": "Отменено"}.get(status, status)
                    details.append(f"✅ Статус: {status_ru}")
                
                return "\n".join(details)
            else:
                return f"Информация о событии:\n{str(event_data)}"
            
        except Exception as e:
            # #region agent log
            import json,asyncio,traceback;open('/Users/Dima/universal-multiagent/.cursor/debug.log','a').write(json.dumps({"location":"calendar_tools.py:470","message":"get_event EXCEPTION","data":{"error_type":type(e).__name__,"error_msg":str(e),"traceback":traceback.format_exc()},"timestamp":asyncio.get_event_loop().time(),"sessionId":"debug-session","hypothesisId":"A"})+'\n')
            # #endregion
            raise ToolExecutionError(
                f"Failed to get event details: {e}",
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
        GetEventTool(),
    ]

