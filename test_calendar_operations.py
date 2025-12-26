"""
Comprehensive test of Google Calendar MCP server.
Tests calendar operations: listing calendars, getting events (yesterday and today), creating events.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.mcp_loader import get_mcp_manager


async def test_calendar_operations():
    """Test Google Calendar MCP operations."""
    print("=" * 80)
    print("Google Calendar MCP Operations Test")
    print("=" * 80)
    print()
    
    # Get MCP manager
    mcp_manager = get_mcp_manager()
    
    # Test 1: Connect to Calendar MCP
    print("1. Testing MCP connection...")
    try:
        results = await mcp_manager.connect_all()
        calendar_connected = results.get("calendar", False)
        print(f"   Calendar connection: {'✓ Connected' if calendar_connected else '✗ Failed'}")
        if not calendar_connected:
            print("   ERROR: Cannot connect to Calendar MCP server")
            return
    except Exception as e:
        print(f"   ERROR: Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Test 2: List available tools
    print("2. Listing available Calendar tools...")
    try:
        connection = mcp_manager.connections.get("calendar")
        if connection:
            tools = connection.get_tools()
            print(f"   Found {len(tools)} tools:")
            for tool_name in sorted(tools.keys()):
                tool_desc = tools[tool_name].get('description', '')[:60]
                print(f"   - {tool_name}: {tool_desc}...")
        else:
            print("   ERROR: Calendar connection not found")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 3: List calendars
    print("3. Listing available calendars...")
    try:
        result = await mcp_manager.call_tool(
            "list_calendars",
            {},
            server_name="calendar"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            calendars = data.get('calendars', [])
            print(f"   Found {len(calendars)} calendars:")
            for cal in calendars:
                cal_id = cal.get('id', 'Unknown')
                summary = cal.get('summary', 'No name')
                primary = " (primary)" if cal.get('primary', False) else ""
                print(f"   - {summary} [{cal_id}]{primary}")
        else:
            print(f"   Result: {data}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 4: Get events from yesterday
    print("4. Getting events from YESTERDAY...")
    try:
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        result = await mcp_manager.call_tool(
            "list_events",
            {
                "calendarId": "primary",
                "timeMin": yesterday_start.isoformat() + "Z",
                "timeMax": yesterday_end.isoformat() + "Z",
                "maxResults": 50
            },
            server_name="calendar"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            events = data.get('items', [])
            count = data.get('count', len(events))
            print(f"   Found {count} events yesterday:")
            for event in events:
                event_id = event.get('id', 'Unknown')
                summary = event.get('summary', 'No title')
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                print(f"   - {summary} (starts: {start}) [ID: {event_id[:20]}...]")
        else:
            print(f"   Result: {data}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 5: Get events from today
    print("5. Getting events from TODAY...")
    try:
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        result = await mcp_manager.call_tool(
            "list_events",
            {
                "calendarId": "primary",
                "timeMin": today_start.isoformat() + "Z",
                "timeMax": today_end.isoformat() + "Z",
                "maxResults": 50
            },
            server_name="calendar"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            events = data.get('items', [])
            count = data.get('count', len(events))
            print(f"   Found {count} events today:")
            for event in events:
                event_id = event.get('id', 'Unknown')
                summary = event.get('summary', 'No title')
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                location = event.get('location', '')
                if location:
                    print(f"   - {summary} (starts: {start}, location: {location}) [ID: {event_id[:20]}...]")
                else:
                    print(f"   - {summary} (starts: {start}) [ID: {event_id[:20]}...]")
        else:
            print(f"   Result: {data}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 6: Create a test event
    print("6. Creating a test event (tomorrow at 3 PM)...")
    try:
        tomorrow = datetime.now() + timedelta(days=1)
        event_start = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
        event_end = event_start + timedelta(hours=1)
        
        # Get timezone (using UTC for simplicity)
        result = await mcp_manager.call_tool(
            "create_event",
            {
                "calendarId": "primary",
                "summary": "Test Event from MCP",
                "description": "This is a test event created via MCP server",
                "location": "Test Location",
                "start": {
                    "dateTime": event_start.isoformat() + "Z",
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": event_end.isoformat() + "Z",
                    "timeZone": "UTC"
                }
            },
            server_name="calendar"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            event_id = data.get('id', 'Unknown')
            summary = data.get('summary', 'No title')
            status = data.get('status', 'Unknown')
            print(f"   ✓ Event created successfully!")
            print(f"   Event ID: {event_id}")
            print(f"   Summary: {summary}")
            print(f"   Status: {status}")
            print(f"   Start time: {event_start.isoformat()}")
        else:
            print(f"   Result: {data}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_calendar_operations())

