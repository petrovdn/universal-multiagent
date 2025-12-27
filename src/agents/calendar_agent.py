"""
Calendar Agent specialized in Google Calendar operations.
Handles event creation, scheduling, availability checking, and calendar management.
"""

from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
import pytz
from langchain_core.tools import BaseTool

from src.agents.base_agent import BaseAgent
from src.mcp_tools.calendar_tools import get_calendar_tools
from src.utils.config_loader import get_config
from src.core.context_manager import ConversationContext


def get_calendar_system_prompt() -> str:
    """
    Generate calendar system prompt with current date/time information.
    
    Returns:
        System prompt string with current date/time
    """
    config = get_config()
    timezone = pytz.timezone(config.timezone)
    now = datetime.now(timezone)
    
    # Format current date/time in a readable format
    current_date_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")
    current_datetime_str = now.strftime("%Y-%m-%d %H:%M")
    current_weekday = now.strftime("%A")  # Monday, Tuesday, etc.
    
    # Russian weekday names
    weekdays_ru = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }
    weekday_ru = weekdays_ru.get(current_weekday, current_weekday)
    
    base_prompt = """You are an expert calendar assistant specialized in Google Calendar operations.

Your capabilities:
- Create and manage calendar events
- Find available time slots for meetings
- Check calendar availability for multiple attendees
- Handle timezone conversions (default: Europe/Moscow)
- Detect and resolve scheduling conflicts
- Manage recurring events
- Add/remove attendees from events

IMPORTANT - CURRENT DATE AND TIME:
The current date and time is: {current_datetime} ({weekday_ru})
Current date: {current_date}
Current time: {current_time}
Timezone: {timezone}

When interpreting relative dates, use this information:
- "вчера" / "yesterday" → {yesterday_date} (one day before {current_date})
- "сегодня" / "today" → {current_date}
- "завтра" / "tomorrow" → {tomorrow_date}
- "послезавтра" / "day after tomorrow" → {day_after_tomorrow}
- "через неделю" / "next week" → calculate 7 days from {current_date}
- "через месяц" / "next month" → calculate approximately 30 days from {current_date}
- "в понедельник" / "on Monday" → find the next Monday from {current_date}
- "в следующую пятницу" / "next Friday" → find the next Friday from {current_date}

IMPORTANT for get_calendar_events tool:
- When user asks about "вчера" / "yesterday", pass start_time="вчера" (not a specific date)
- When user asks about "сегодня" / "today", pass start_time="сегодня" (not a specific date)
- The tool will automatically parse these relative dates correctly
- For date ranges, use natural language: start_time="вчера", end_time="сегодня"

Guidelines:
1. Always validate dates and times before creating events
2. Check for conflicts before scheduling
3. Use timezone-aware datetime handling
4. When finding availability:
   - Consider all attendees' calendars
   - Suggest multiple time options when possible
   - Respect working hours (9 AM - 6 PM by default)
   
5. For event creation:
   - Include clear, descriptive titles
   - Add location when provided
   - Include meeting description/agenda when available
   - Set appropriate duration (default: 1 hour if not specified)
   
6. Handle natural language time expressions:
   - "next Monday" → calculate actual date based on current date
   - "2 PM" → use today ({current_date}) or specified date
   - "tomorrow at 3" → calculate tomorrow's date ({tomorrow_date}) at 3 PM
   - "через неделю" → calculate date 7 days from now
   - "через месяц" → calculate date approximately 30 days from now
   
7. For ambiguous requests, ask clarifying questions:
   - Which day of the week?
   - What time?
   - How long should the meeting be?
   - Who should be invited?
   
8. Provide clear confirmations with:
   - Event title
   - Date and time (with timezone)
   - Attendees
   - Duration
   - Location (if provided)

Always be helpful, proactive, and ensure scheduling accuracy."""
    
    # Calculate yesterday, tomorrow and day after tomorrow
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)
    day_after_tomorrow = now + timedelta(days=2)
    
    return base_prompt.format(
        current_datetime=current_datetime_str,
        weekday_ru=weekday_ru,
        current_date=current_date_str,
        current_time=current_time_str,
        timezone=config.timezone,
        yesterday_date=yesterday.strftime("%Y-%m-%d"),
        tomorrow_date=tomorrow.strftime("%Y-%m-%d"),
        day_after_tomorrow=day_after_tomorrow.strftime("%Y-%m-%d")
    )


# REMOVED: CALENDAR_AGENT_SYSTEM_PROMPT = get_calendar_system_prompt()
# This was causing get_config() to be called during module import, which fails
# if environment variables are not set. The prompt is now generated lazily
# in CalendarAgent.__init__() when actually needed.


class CalendarAgent(BaseAgent):
    """
    Calendar Agent specialized in scheduling and calendar management.
    """
    
    def __init__(self, tools: List[BaseTool] = None, model_name: Optional[str] = None):
        """
        Initialize Calendar Agent.
        
        Args:
            tools: Custom tools (uses Calendar tools by default)
            model_name: Model identifier (optional, uses default from config if None)
        """
        if tools is None:
            tools = get_calendar_tools()
        
        # Get fresh system prompt with current date/time
        system_prompt = get_calendar_system_prompt()
        
        super().__init__(
            name="CalendarAgent",
            system_prompt=system_prompt,
            tools=tools,
            model_name=model_name
        )
        
        # Track last date to avoid unnecessary graph rebuilds
        config = get_config()
        timezone = pytz.timezone(config.timezone)
        self._last_prompt_date = datetime.now(timezone).date()
    
    def _update_system_prompt(self):
        """
        Update system prompt with current date/time.
        This ensures the agent always knows the current date.
        Only rebuilds graph if date has changed (not just time).
        """
        config = get_config()
        timezone = pytz.timezone(config.timezone)
        current_date = datetime.now(timezone).date()
        
        new_prompt = get_calendar_system_prompt()
        self.system_prompt = new_prompt
        
        # Only rebuild graph if date has changed (not just time)
        if current_date != self._last_prompt_date:
            self.graph = self._build_graph()
            self._last_prompt_date = current_date
    
    async def execute(
        self,
        user_message: str,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Execute agent with user message, updating system prompt with current date first.
        
        Args:
            user_message: User's message
            context: Conversation context
            
        Returns:
            Agent execution result
        """
        # Update system prompt with current date/time before execution
        self._update_system_prompt()
        return await super().execute(user_message, context)
    
    async def execute_with_streaming(
        self,
        user_message: str,
        context: ConversationContext,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute agent with streaming, updating system prompt with current date first.
        
        Args:
            user_message: User's message
            context: Conversation context
            event_callback: Async callback for streaming events
            
        Returns:
            Agent execution result
        """
        # Update system prompt with current date/time before execution
        self._update_system_prompt()
        return await super().execute_with_streaming(user_message, context, event_callback)

