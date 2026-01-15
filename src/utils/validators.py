"""
Input validation utilities for the multi-agent system.
Validates emails, dates, timezones, and other inputs before processing.
"""

import re
import json
import pytz
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timedelta
from calendar import monthrange
from email.utils import parseaddr

from src.utils.exceptions import ValidationError


# Email validation regex (RFC 5322 compliant)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_email(email: str) -> str:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Normalized email address
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError("Email address is required", field="email")
    
    email = email.strip().lower()
    
    # Basic format check
    if not EMAIL_REGEX.match(email):
        raise ValidationError(
            f"Invalid email format: {email}",
            field="email",
            value=email
        )
    
    # Additional check using email.utils
    name, addr = parseaddr(email)
    if not addr or addr != email:
        raise ValidationError(
            f"Invalid email address: {email}",
            field="email",
            value=email
        )
    
    return email


def validate_email_list(emails: List[str]) -> List[str]:
    """
    Validate a list of email addresses.
    
    Args:
        emails: List of email addresses
        
    Returns:
        List of normalized email addresses
        
    Raises:
        ValidationError: If any email is invalid
    """
    if not emails:
        return []
    
    validated = []
    for email in emails:
        validated.append(validate_email(email))
    
    return validated


def validate_timezone(timezone: str) -> str:
    """
    Validate timezone string.
    
    Args:
        timezone: Timezone identifier (e.g., 'Europe/Moscow')
        
    Returns:
        Validated timezone string
        
    Raises:
        ValidationError: If timezone is invalid
    """
    if not timezone:
        raise ValidationError("Timezone is required", field="timezone")
    
    try:
        pytz.timezone(timezone)
        return timezone
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValidationError(
            f"Unknown timezone: {timezone}",
            field="timezone",
            value=timezone
        )


def parse_datetime(
    date_str: str,
    timezone: str = "Europe/Moscow"
) -> datetime:
    """
    Parse datetime string with timezone support.
    
    Supports formats:
    - ISO 8601: "2024-01-15T14:30:00+03:00"
    - Simple: "2024-01-15 14:30"
    - Natural language: "next Monday at 2 PM"
    
    Args:
        date_str: Date/time string to parse
        timezone: Default timezone if not specified
        
    Returns:
        Datetime object with timezone
        
    Raises:
        ValidationError: If date cannot be parsed
    """
    if not date_str:
        raise ValidationError("Date/time is required", field="datetime")
    
    # Validate timezone
    tz = pytz.timezone(validate_timezone(timezone))
    
    # Try ISO 8601 format first
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt
    except ValueError:
        pass
    
    # Try simple format: "YYYY-MM-DD HH:MM"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return tz.localize(dt)
    except ValueError:
        pass
    
    # Try natural language parsing (extended support)
    # Handle common Russian and English expressions
    date_str_lower = date_str.lower().strip()
    now = datetime.now(tz)
    
    # Helper function to extract time from string
    def extract_time(text: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract hour and minute from text."""
        # Russian patterns: "в 10", "в 10:00", "в 10 часов", "в 10:30"
        ru_pattern = r'в\s+(\d{1,2})(?::(\d{2}))?(?:\s+час)?'
        ru_match = re.search(ru_pattern, text)
        if ru_match:
            hour = int(ru_match.group(1))
            minute = int(ru_match.group(2)) if ru_match.group(2) else 0
            return hour, minute
        
        # English patterns: "at 10", "at 10:00", "at 10 AM", "at 2 PM"
        en_pattern = r'at\s+(\d{1,2})(?::(\d{2}))?(?:\s*(?:am|pm))?'
        en_match = re.search(en_pattern, text)
        if en_match:
            hour = int(en_match.group(1))
            minute = int(en_match.group(2)) if en_match.group(2) else 0
            # Handle AM/PM
            if 'pm' in text and hour < 12:
                hour += 12
            elif 'am' in text and hour == 12:
                hour = 0
            return hour, minute
        
        return None, None
    
    # Russian: "сегодня" / "today"
    if date_str_lower.startswith("сегодня") or date_str_lower.startswith("today"):
        hour, minute = extract_time(date_str_lower)
        if hour is not None:
            dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If time is in the past, assume next day
            if dt < now:
                dt = dt + timedelta(days=1)
        else:
            # Default to current time or 10:00 if current time is late
            if now.hour >= 18:
                dt = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
            else:
                dt = now.replace(second=0, microsecond=0)
        return dt
    
    # Russian: "завтра" / "tomorrow"
    if date_str_lower.startswith("завтра") or date_str_lower.startswith("tomorrow"):
        hour, minute = extract_time(date_str_lower)
        tomorrow = now + timedelta(days=1)
        if hour is not None:
            dt = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Default to 10:00 if no time specified
            dt = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        return dt
    
    # Russian: "послезавтра" / "day after tomorrow"
    if date_str_lower.startswith("послезавтра") or "day after tomorrow" in date_str_lower:
        hour, minute = extract_time(date_str_lower)
        day_after_tomorrow = now + timedelta(days=2)
        if hour is not None:
            dt = day_after_tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = day_after_tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        return dt
    
    # Russian: "за прошлые две недели" / "за последние две недели" / "past two weeks"
    if "за прошлые две недели" in date_str_lower or "за последние две недели" in date_str_lower or "past two weeks" in date_str_lower or "last two weeks" in date_str_lower:
        # Calculate start of two weeks ago
        two_weeks_ago = now - timedelta(days=14)
        two_weeks_ago = two_weeks_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Return start time (end will be calculated by caller)
        hour, minute = extract_time(date_str_lower)
        if hour is not None:
            dt = two_weeks_ago.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = two_weeks_ago
        return dt
    
    # Russian: "за прошлую неделю" / "на прошлой неделе" / "past week" / "last week" - previous calendar week (Mon-Sun)
    if "за прошлую неделю" in date_str_lower or "за последнюю неделю" in date_str_lower or "на прошлой неделе" in date_str_lower or "past week" in date_str_lower or "last week" in date_str_lower:
        # Calculate previous calendar week (Monday to Sunday)
        days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
        current_week_monday = now - timedelta(days=days_since_monday)
        last_week_monday = current_week_monday - timedelta(days=7)
        last_week_monday = last_week_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Return start of last week (Monday)
        hour, minute = extract_time(date_str_lower)
        if hour is not None:
            dt = last_week_monday.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = last_week_monday
        return dt
    
    # Russian: "на неделе" / "this week" / "на этой неделе"
    if "на неделе" in date_str_lower or "на этой неделе" in date_str_lower or "this week" in date_str_lower:
        # Calculate start of current week (Monday)
        days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
        week_start = now - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate end of current week (Sunday 23:59:59)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # If only start_time is needed, return start of week
        # If only end_time is needed, return end of week
        # For simplicity, return start of week if no specific time mentioned
        hour, minute = extract_time(date_str_lower)
        if hour is not None:
            dt = week_start.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = week_start
        return dt
    
    # Russian: "через неделю" / "next week" / "in a week"
    if "через неделю" in date_str_lower or "next week" in date_str_lower or "in a week" in date_str_lower:
        hour, minute = extract_time(date_str_lower)
        next_week = now + timedelta(days=7)
        if hour is not None:
            dt = next_week.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = next_week.replace(hour=10, minute=0, second=0, microsecond=0)
        return dt
    
    # Russian: "через месяц" / "next month" / "in a month"
    if "через месяц" in date_str_lower or "next month" in date_str_lower or "in a month" in date_str_lower:
        hour, minute = extract_time(date_str_lower)
        # Approximate: add 30 days
        next_month = now + timedelta(days=30)
        if hour is not None:
            dt = next_month.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = next_month.replace(hour=10, minute=0, second=0, microsecond=0)
        return dt
    
    # Russian: "через N дней" / "in N days"
    days_match = re.search(r'через\s+(\d+)\s+дн', date_str_lower)
    if not days_match:
        days_match = re.search(r'in\s+(\d+)\s+days?', date_str_lower)
    if days_match:
        days = int(days_match.group(1))
        hour, minute = extract_time(date_str_lower)
        future_date = now + timedelta(days=days)
        if hour is not None:
            dt = future_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            dt = future_date.replace(hour=10, minute=0, second=0, microsecond=0)
        return dt
    
    # If all parsing attempts fail, raise error
    raise ValidationError(
        f"Unable to parse date/time: {date_str}. "
        f"Supported formats: ISO 8601, 'YYYY-MM-DD HH:MM', or natural language "
        f"(сегодня, завтра, послезавтра, за прошлую неделю, за прошлые две недели, через неделю, через месяц, через N дней, "
        f"today, tomorrow, past week, last week, past two weeks, next week, next month, in N days)",
        field="datetime",
        value=date_str
    )


def parse_date_range(
    date_str: str,
    timezone: str = "Europe/Moscow"
) -> Tuple[datetime, datetime]:
    """
    Parse date range expressions like "в январе", "в первом квартале", "в 2026".
    
    Supports formats:
    - "в текущем месяце", "в этом месяце" → весь текущий месяц
    - "в прошлом месяце" → весь предыдущий месяц
    - "в следующем месяце" → весь следующий месяц
    - "в январе", "в феврале", ... → весь указанный месяц текущего года
    - "в январе 2026" → весь указанный месяц указанного года
    - "в первом квартале", "во втором квартале", ... → весь квартал текущего года
    - "в первом квартале 2026" → весь квартал указанного года
    - "в 2026", "в 2025" → весь указанный год
    
    Args:
        date_str: Date range string to parse
        timezone: Default timezone if not specified
        
    Returns:
        Tuple of (start_datetime, end_datetime) for the range
        
    Raises:
        ValidationError: If date range cannot be parsed
    """
    if not date_str:
        raise ValidationError("Date range is required", field="date_range")
    
    # Validate timezone
    tz = pytz.timezone(validate_timezone(timezone))
    now = datetime.now(tz)
    date_str_lower = date_str.lower().strip()
    
    # Russian month names (genitive case: "в январе", "в феврале")
    month_names = {
        "январе": 1, "феврале": 2, "марте": 3, "апреле": 4,
        "мае": 5, "июне": 6, "июле": 7, "августе": 8,
        "сентябре": 9, "октябре": 10, "ноябре": 11, "декабре": 12
    }
    
    # Current month: "в текущем месяце", "в этом месяце"
    if "в текущем месяце" in date_str_lower or "в этом месяце" in date_str_lower:
        year = now.year
        month = now.month
        days = monthrange(year, month)[1]
        start = tz.localize(datetime(year, month, 1, 0, 0, 0))
        end = tz.localize(datetime(year, month, days, 23, 59, 59))
        return start, end
    
    # Last month: "в прошлом месяце"
    if "в прошлом месяце" in date_str_lower:
        if now.month == 1:
            year = now.year - 1
            month = 12
        else:
            year = now.year
            month = now.month - 1
        days = monthrange(year, month)[1]
        start = tz.localize(datetime(year, month, 1, 0, 0, 0))
        end = tz.localize(datetime(year, month, days, 23, 59, 59))
        return start, end
    
    # Next month: "в следующем месяце"
    if "в следующем месяце" in date_str_lower:
        if now.month == 12:
            year = now.year + 1
            month = 1
        else:
            year = now.year
            month = now.month + 1
        days = monthrange(year, month)[1]
        start = tz.localize(datetime(year, month, 1, 0, 0, 0))
        end = tz.localize(datetime(year, month, days, 23, 59, 59))
        return start, end
    
    # Quarters with optional year: "в первом квартале", "в первом квартале 2026"
    # Check quarters before months to avoid conflicts
    quarter_patterns = [
        (r"в\s+первом\s+квартале\s+(\d{4})", 1, 3),
        (r"в\s+втором\s+квартале\s+(\d{4})", 4, 6),
        (r"в\s+третьем\s+квартале\s+(\d{4})", 7, 9),
        (r"в\s+четвертом\s+квартале\s+(\d{4})", 10, 12),
        (r"во\s+втором\s+квартале\s+(\d{4})", 4, 6),
        (r"в\s+первом\s+квартале", 1, 3),
        (r"во\s+втором\s+квартале", 4, 6),
        (r"в\s+третьем\s+квартале", 7, 9),
        (r"в\s+четвертом\s+квартале", 10, 12),
    ]
    
    for pattern, start_month, end_month in quarter_patterns:
        match = re.search(pattern, date_str_lower)
        if match:
            if match.groups() and match.group(1):
                year = int(match.group(1))
            else:
                year = now.year
            
            start_day = 1
            end_day = monthrange(year, end_month)[1]
            start = tz.localize(datetime(year, start_month, start_day, 0, 0, 0))
            end = tz.localize(datetime(year, end_month, end_day, 23, 59, 59))
            return start, end
    
    # Named month with optional year: "в январе 2026", "в январе"
    # Check months with year first, then without year
    for month_name, month_num in month_names.items():
        # With year: "в январе 2026"
        pattern_with_year = rf"в\s+{month_name}\s+(\d{{4}})"
        match = re.search(pattern_with_year, date_str_lower)
        if match:
            year = int(match.group(1))
            days = monthrange(year, month_num)[1]
            start = tz.localize(datetime(year, month_num, 1, 0, 0, 0))
            end = tz.localize(datetime(year, month_num, days, 23, 59, 59))
            return start, end
    
    # Without year (current year): "в январе"
    for month_name, month_num in month_names.items():
        pattern_without_year = rf"в\s+{month_name}\b"
        match = re.search(pattern_without_year, date_str_lower)
        if match:
            year = now.year
            days = monthrange(year, month_num)[1]
            start = tz.localize(datetime(year, month_num, 1, 0, 0, 0))
            end = tz.localize(datetime(year, month_num, days, 23, 59, 59))
            return start, end
    
    # Year: "в 2026", "в 2025"
    # Check year last to avoid conflicts with months and quarters
    year_match = re.search(r"^в\s+(\d{4})$", date_str_lower.strip())
    if year_match:
        year = int(year_match.group(1))
        start = tz.localize(datetime(year, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(year, 12, 31, 23, 59, 59))
        return start, end
    
    # If all parsing attempts fail, raise error
    raise ValidationError(
        f"Unable to parse date range: {date_str}. "
        f"Supported formats: 'в текущем месяце', 'в прошлом месяце', 'в следующем месяце', "
        f"'в январе', 'в январе 2026', 'в первом квартале', 'в первом квартале 2026', 'в 2026'",
        field="date_range",
        value=date_str
    )


def parse_attendee_filter(
    filter_str: str
) -> Dict[str, Any]:
    """
    Parse attendee filter from natural language.
    
    Supports formats:
    - "Марат и Аня" → {"operator": "AND", "patterns": ["марат", "аня"]}
    - "Марат или Аня" → {"operator": "OR", "patterns": ["марат", "аня"]}
    - "marat@" → {"operator": "OR", "patterns": ["marat@"]}
    - "@lad24.ru" → {"operator": "OR", "patterns": ["@lad24.ru"]}
    - "Марат и anna@lad24.ru" → {"operator": "AND", "patterns": ["марат", "anna@lad24.ru"]}
    
    Args:
        filter_str: Filter string to parse
        
    Returns:
        Dict with "operator" ("AND"|"OR") and "patterns" (list of strings).
        
    Raises:
        ValidationError: If filter string cannot be parsed
    """
    if not filter_str or not filter_str.strip():
        raise ValidationError("Attendee filter is required", field="attendee_filter")
    
    filter_str = filter_str.strip()
    filter_lower = filter_str.lower()
    
    # Determine operator: "и" / "and" → AND, "или" / "or" → OR
    # Default to OR if no explicit operator
    has_and = " и " in filter_str or " and " in filter_lower
    has_or = " или " in filter_str or " or " in filter_lower
    
    if has_and and has_or:
        # Mixed operators - use AND as default (more restrictive)
        operator = "AND"
    elif has_and:
        operator = "AND"
    elif has_or:
        operator = "OR"
    else:
        # No explicit operator - default to OR
        operator = "OR"
    
    # Split by operator
    if has_and:
        # Split by " и " or " and "
        parts = re.split(r'\s+и\s+|\s+and\s+', filter_str, flags=re.IGNORECASE)
    elif has_or:
        # Split by " или " or " or "
        parts = re.split(r'\s+или\s+|\s+or\s+', filter_str, flags=re.IGNORECASE)
    else:
        # Single pattern
        parts = [filter_str]
    
    # Extract patterns
    patterns = []
    email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')  # Full email
    partial_email_pattern = re.compile(r'[\w\.-]+@|@[\w\.-]+\.\w+')  # Partial email
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        part_lower = part.lower()
        
        # Check if it's a full email
        if email_pattern.match(part):
            patterns.append(part)
        # Check if it's a partial email (starts or ends with @)
        elif partial_email_pattern.search(part):
            patterns.append(part)
        else:
            # It's a name - normalize to lowercase
            patterns.append(part_lower)
    
    if not patterns:
        raise ValidationError(
            f"Unable to parse attendee filter: {filter_str}. "
            f"Supported formats: 'Марат и Аня', 'Марат или Аня', 'marat@', '@lad24.ru'",
            field="attendee_filter",
            value=filter_str
        )
    
    return {
        "operator": operator,
        "patterns": patterns
    }


def validate_date_not_past(date: datetime, field_name: str = "date") -> datetime:
    """
    Validate that date is not in the past.
    
    Args:
        date: Datetime to validate
        field_name: Name of field for error message
        
    Returns:
        Validated datetime
        
    Raises:
        ValidationError: If date is in the past
    """
    now = datetime.now(date.tzinfo)
    if date < now:
        raise ValidationError(
            f"{field_name} cannot be in the past",
            field=field_name,
            value=date.isoformat()
        )
    return date


def validate_spreadsheet_range(range_str: str) -> str:
    """
    Validate Google Sheets range notation (A1 notation).
    
    Examples:
    - "A1" - Single cell
    - "A1:B10" - Cell range
    - "Sheet1!A1:B10" - Range with sheet name
    
    Args:
        range_str: Range string to validate
        
    Returns:
        Validated range string
        
    Raises:
        ValidationError: If range format is invalid
    """
    if not range_str:
        raise ValidationError("Spreadsheet range is required", field="range")
    
    # Basic A1 notation pattern
    # Matches: A1, A1:B10, Sheet1!A1:B10, Лист1!A1:B10
    # Sheet name can contain any characters except '!'
    range_pattern = re.compile(
        r'^([^!]+!)?([A-Z]+[0-9]+)(:([A-Z]+[0-9]+))?$'
    )
    
    if not range_pattern.match(range_str):
        raise ValidationError(
            f"Invalid spreadsheet range format: {range_str}. "
            f"Expected A1 notation (e.g., 'A1', 'A1:B10', 'Sheet1!A1:B10')",
            field="range",
            value=range_str
        )
    
    return range_str


def validate_attendee_list(attendees: List[str]) -> List[str]:
    """
    Validate list of attendee emails.
    
    Args:
        attendees: List of attendee identifiers (emails or names)
        
    Returns:
        List of validated email addresses
        
    Raises:
        ValidationError: If any attendee is invalid
    """
    if not attendees:
        return []
    
    validated = []
    for attendee in attendees:
        # Try to extract email if it's in "Name <email>" format
        name, email = parseaddr(attendee)
        if email:
            validated.append(validate_email(email))
        else:
            # Assume it's just an email
            validated.append(validate_email(attendee))
    
    return validated


def validate_duration(duration_str: str) -> int:
    """
    Validate and parse duration string to minutes.
    
    Supports formats:
    - "30m" or "30 min" - 30 minutes
    - "1h" or "1 hour" - 60 minutes
    - "2h 30m" - 150 minutes
    
    Args:
        duration_str: Duration string to parse
        
    Returns:
        Duration in minutes
        
    Raises:
        ValidationError: If duration cannot be parsed
    """
    if not duration_str:
        raise ValidationError("Duration is required", field="duration")
    
    duration_str = duration_str.strip().lower()
    
    # Pattern: number followed by h/m/hour/min
    pattern = re.compile(r'(\d+)\s*(h|hour|hours|m|min|mins|minute|minutes)')
    matches = pattern.findall(duration_str)
    
    if not matches:
        raise ValidationError(
            f"Invalid duration format: {duration_str}. "
            f"Expected format: '30m', '1h', '2h 30m'",
            field="duration",
            value=duration_str
        )
    
    total_minutes = 0
    for value, unit in matches:
        value = int(value)
        if unit.startswith('h'):
            total_minutes += value * 60
        else:
            total_minutes += value
    
    if total_minutes <= 0:
        raise ValidationError(
            "Duration must be greater than 0",
            field="duration",
            value=duration_str
        )
    
    return total_minutes



