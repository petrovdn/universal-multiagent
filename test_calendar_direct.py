"""
Direct test of Google Calendar MCP server using the server directly.
Tests calendar operations without MCP manager.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.server.stdio import stdio_server
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from src.mcp_servers.google_calendar_server import GoogleCalendarMCPServer


async def test_calendar_direct():
    """Test Calendar MCP server directly."""
    print("=" * 80)
    print("Google Calendar MCP Direct Test")
    print("=" * 80)
    print()
    
    # Check token exists
    token_path = Path("config/google_calendar_token.json")
    if not token_path.exists():
        print(f"ERROR: Token not found at {token_path}")
        print("Please enable Google Calendar integration first.")
        return
    
    print(f"Token found at: {token_path}")
    print()
    
    # Create server instance
    server = GoogleCalendarMCPServer(token_path)
    
    # Test 1: Get calendar service (this will test token and API connection)
    print("1. Testing Calendar API connection...")
    try:
        service = server._get_calendar_service()
        print("   ✓ Calendar service initialized successfully")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Test 2: List calendars
    print("2. Listing available calendars...")
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        print(f"   Found {len(calendars)} calendars:")
        for cal in calendars:
            cal_id = cal.get('id', 'Unknown')
            summary = cal.get('summary', 'No name')
            primary = " (primary)" if cal.get('primary', False) else ""
            print(f"   - {summary} [{cal_id}]{primary}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 3: Get events from yesterday
    print("3. Getting events from YESTERDAY...")
    try:
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=yesterday_start.isoformat() + 'Z',
            timeMax=yesterday_end.isoformat() + 'Z',
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        print(f"   Found {len(events)} events yesterday:")
        if not events:
            print("   (No events found)")
        else:
            for event in events:
                event_id = event.get('id', 'Unknown')
                summary = event.get('summary', 'No title')
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                print(f"   - {summary} (starts: {start}) [ID: {event_id[:30]}...]")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 4: Get events from today
    print("4. Getting events from TODAY...")
    try:
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat() + 'Z',
            timeMax=today_end.isoformat() + 'Z',
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        print(f"   Found {len(events)} events today:")
        if not events:
            print("   (No events found)")
        else:
            for event in events:
                event_id = event.get('id', 'Unknown')
                summary = event.get('summary', 'No title')
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                location = event.get('location', '')
                description = event.get('description', '')
                if location:
                    print(f"   - {summary} (starts: {start}, location: {location}) [ID: {event_id[:30]}...]")
                else:
                    print(f"   - {summary} (starts: {start}) [ID: {event_id[:30]}...]")
                if description:
                    desc_short = description[:50] + "..." if len(description) > 50 else description
                    print(f"     Description: {desc_short}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 5: Create a test event
    print("5. Creating a test event (tomorrow at 3 PM UTC)...")
    try:
        tomorrow = datetime.now() + timedelta(days=1)
        event_start = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
        event_end = event_start + timedelta(hours=1)
        
        event_body = {
            'summary': 'Test Event from MCP',
            'description': 'This is a test event created via Calendar MCP server',
            'location': 'Test Location',
            'start': {
                'dateTime': event_start.isoformat() + 'Z',
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': event_end.isoformat() + 'Z',
                'timeZone': 'UTC'
            }
        }
        
        created_event = service.events().insert(
            calendarId='primary',
            body=event_body
        ).execute()
        
        event_id = created_event.get('id')
        summary = created_event.get('summary')
        start = created_event.get('start', {}).get('dateTime', 'Unknown')
        print(f"   ✓ Event created successfully!")
        print(f"   Event ID: {event_id}")
        print(f"   Summary: {summary}")
        print(f"   Start time: {start}")
        print(f"   Full event URL: {created_event.get('htmlLink', 'N/A')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_calendar_direct())

