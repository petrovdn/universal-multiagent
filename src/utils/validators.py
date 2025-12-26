"""
Input validation utilities for the multi-agent system.
Validates emails, dates, timezones, and other inputs before processing.
"""

import re
import pytz
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
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
        f"(сегодня, завтра, послезавтра, через неделю, через месяц, через N дней, "
        f"today, tomorrow, next week, next month, in N days)",
        field="datetime",
        value=date_str
    )


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
    # Matches: A1, A1:B10, Sheet1!A1:B10
    range_pattern = re.compile(
        r'^([A-Za-z0-9_]+!)?([A-Z]+[0-9]+)(:([A-Z]+[0-9]+))?$'
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



