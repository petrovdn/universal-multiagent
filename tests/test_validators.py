"""
Tests for validation utilities.
"""

import pytest
from datetime import datetime, timedelta

from src.utils.validators import (
    validate_email,
    validate_email_list,
    validate_timezone,
    parse_datetime,
    validate_date_not_past,
    validate_spreadsheet_range,
    validate_attendee_list,
    validate_duration,
    ValidationError
)


def test_validate_email_valid():
    """Test valid email validation."""
    assert validate_email("test@example.com") == "test@example.com"
    assert validate_email("user.name+tag@domain.co.uk") == "user.name+tag@domain.co.uk"


def test_validate_email_invalid():
    """Test invalid email validation."""
    with pytest.raises(ValidationError):
        validate_email("invalid-email")
    
    with pytest.raises(ValidationError):
        validate_email("")
    
    with pytest.raises(ValidationError):
        validate_email("@example.com")


def test_validate_email_list():
    """Test email list validation."""
    emails = ["user1@example.com", "user2@example.com"]
    result = validate_email_list(emails)
    assert len(result) == 2
    assert result[0] == "user1@example.com"


def test_validate_timezone():
    """Test timezone validation."""
    assert validate_timezone("Europe/Moscow") == "Europe/Moscow"
    assert validate_timezone("America/New_York") == "America/New_York"
    
    with pytest.raises(ValidationError):
        validate_timezone("Invalid/Timezone")


def test_parse_datetime():
    """Test datetime parsing."""
    dt = parse_datetime("2024-01-15 14:30", "Europe/Moscow")
    assert isinstance(dt, datetime)
    assert dt.hour == 14
    assert dt.minute == 30


def test_validate_date_not_past():
    """Test date not past validation."""
    future_date = datetime.now() + timedelta(days=1)
    assert validate_date_not_past(future_date) == future_date
    
    past_date = datetime.now() - timedelta(days=1)
    with pytest.raises(ValidationError):
        validate_date_not_past(past_date)


def test_validate_spreadsheet_range():
    """Test spreadsheet range validation."""
    assert validate_spreadsheet_range("A1") == "A1"
    assert validate_spreadsheet_range("A1:B10") == "A1:B10"
    assert validate_spreadsheet_range("Sheet1!A1:B10") == "Sheet1!A1:B10"
    
    with pytest.raises(ValidationError):
        validate_spreadsheet_range("invalid")
    
    with pytest.raises(ValidationError):
        validate_spreadsheet_range("")


def test_validate_attendee_list():
    """Test attendee list validation."""
    attendees = ["user@example.com", "John Doe <john@example.com>"]
    result = validate_attendee_list(attendees)
    assert len(result) == 2


def test_validate_duration():
    """Test duration validation."""
    assert validate_duration("30m") == 30
    assert validate_duration("1h") == 60
    assert validate_duration("2h 30m") == 150
    
    with pytest.raises(ValidationError):
        validate_duration("invalid")
    
    with pytest.raises(ValidationError):
        validate_duration("")



