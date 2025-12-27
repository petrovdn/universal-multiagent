"""
Test Calendar MCP server via stdio protocol.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters


async def test_calendar_mcp_stdio():
    """Test Calendar MCP server via stdio."""
    print("=" * 80)
    print("Google Calendar MCP Stdio Test")
    print("=" * 80)
    print()
    
    # Check token exists
    token_path = Path("config/google_calendar_token.json")
    if not token_path.exists():
        print(f"ERROR: Token not found at {token_path}")
        return
    
    # Server parameters
    server_params = StdioServerParameters(
        command="python3",
        args=[
            str(Path(__file__).parent / "src" / "mcp_servers" / "google_calendar_server.py"),
            "--token-path",
            str(token_path.absolute())
        ],
        env=None
    )
    
    print("Connecting to Calendar MCP server via stdio...")
    print()
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # Test 1: List tools
            print("1. Listing available tools...")
            try:
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"   Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description[:60]}...")
            except Exception as e:
                print(f"   ERROR: {e}")
                import traceback
                traceback.print_exc()
                return
            
            print()
            
            # Test 2: List calendars
            print("2. Listing calendars...")
            try:
                result = await session.call_tool("list_calendars", {})
                if result.content:
                    text_content = result.content[0].text
                    data = json.loads(text_content)
                    calendars = data.get('calendars', [])
                    print(f"   Found {len(calendars)} calendars:")
                    for cal in calendars:
                        print(f"   - {cal.get('summary')} [{cal.get('id')}]")
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
                
                result = await session.call_tool("list_events", {
                    "calendarId": "primary",
                    "timeMin": yesterday_start.isoformat() + "Z",
                    "timeMax": yesterday_end.isoformat() + "Z",
                    "maxResults": 50
                })
                
                if result.content:
                    text_content = result.content[0].text
                    data = json.loads(text_content)
                    events = data.get('items', [])
                    print(f"   Found {len(events)} events:")
                    for event in events:
                        summary = event.get('summary', 'No title')
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                        print(f"   - {summary} (starts: {start})")
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
                
                result = await session.call_tool("list_events", {
                    "calendarId": "primary",
                    "timeMin": today_start.isoformat() + "Z",
                    "timeMax": today_end.isoformat() + "Z",
                    "maxResults": 50
                })
                
                if result.content:
                    text_content = result.content[0].text
                    data = json.loads(text_content)
                    events = data.get('items', [])
                    print(f"   Found {len(events)} events:")
                    for event in events:
                        summary = event.get('summary', 'No title')
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                        location = event.get('location', '')
                        if location:
                            print(f"   - {summary} (starts: {start}, location: {location})")
                        else:
                            print(f"   - {summary} (starts: {start})")
            except Exception as e:
                print(f"   ERROR: {e}")
                import traceback
                traceback.print_exc()
            
            print()
            
            # Test 5: Create event
            print("5. Creating a test event...")
            try:
                tomorrow = datetime.now() + timedelta(days=1)
                event_start = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
                event_end = event_start + timedelta(hours=1)
                
                result = await session.call_tool("create_event", {
                    "calendarId": "primary",
                    "summary": "Test Event from MCP Stdio",
                    "description": "Created via MCP stdio protocol",
                    "start": {
                        "dateTime": event_start.isoformat() + "Z",
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": event_end.isoformat() + "Z",
                        "timeZone": "UTC"
                    }
                })
                
                if result.content:
                    text_content = result.content[0].text
                    data = json.loads(text_content)
                    print(f"   ✓ Event created!")
                    print(f"   Event ID: {data.get('id')}")
                    print(f"   Summary: {data.get('summary')}")
            except Exception as e:
                print(f"   ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    from mcp import ClientSession
    asyncio.run(test_calendar_mcp_stdio())

