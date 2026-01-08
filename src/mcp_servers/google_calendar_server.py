"""
Google Calendar MCP Server.
Provides MCP tools for Google Calendar operations via OAuth2.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Calendar API scopes
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]


class GoogleCalendarMCPServer:
    """MCP Server for Google Calendar operations."""
    
    def __init__(self, token_path: Path):
        """
        Initialize Google Calendar MCP Server.
        
        Args:
            token_path: Path to OAuth token file
        """
        self.token_path = Path(token_path)
        self._calendar_service = None
        self.server = Server("google-calendar-mcp")
        self._setup_tools()
    
    def _get_calendar_service(self):
        """Get or create Google Calendar API service."""
        if self._calendar_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                CALENDAR_SCOPES
            )
            
            # Refresh token if expired
            if creds.expired:
                if creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Save refreshed token
                        with open(self.token_path, 'w') as token:
                            token.write(creds.to_json())
                    except Exception as e:
                        logger.error(f"Failed to refresh token: {e}")
                        raise ValueError(
                            f"Token expired and refresh failed: {e}. "
                            "Please re-authenticate via /api/integrations/google-calendar/enable"
                        )
                else:
                    # Token expired and no refresh_token - user needs to re-authenticate
                    raise ValueError(
                        "Token expired and no refresh token available. "
                        "Please re-authenticate via /api/integrations/google-calendar/enable. "
                        "Make sure to use 'prompt=consent' during OAuth to get a refresh token."
                    )
            
            self._calendar_service = build('calendar', 'v3', credentials=creds)
        
        return self._calendar_service
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="list_calendars",
                    description="List all available calendars",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="list_events",
                    description="List calendar events for a time range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "timeMin": {
                                "type": "string",
                                "description": "Start time (ISO 8601 format)"
                            },
                            "timeMax": {
                                "type": "string",
                                "description": "End time (ISO 8601 format)"
                            },
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10
                            }
                        }
                    }
                ),
                Tool(
                    name="get_event",
                    description="Get details of a specific event",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "eventId": {
                                "type": "string",
                                "description": "Event ID"
                            }
                        },
                        "required": ["eventId"]
                    }
                ),
                Tool(
                    name="create_event",
                    description="Create a new calendar event",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Event title/summary"
                            },
                            "description": {
                                "type": "string",
                                "description": "Event description"
                            },
                            "location": {
                                "type": "string",
                                "description": "Event location"
                            },
                            "start": {
                                "type": "object",
                                "description": "Start time",
                                "properties": {
                                    "dateTime": {"type": "string"},
                                    "timeZone": {"type": "string"}
                                }
                            },
                            "end": {
                                "type": "object",
                                "description": "End time",
                                "properties": {
                                    "dateTime": {"type": "string"},
                                    "timeZone": {"type": "string"}
                                }
                            },
                            "attendees": {
                                "type": "array",
                                "description": "List of attendee emails",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"}
                                    }
                                }
                            }
                        },
                        "required": ["summary", "start", "end"]
                    }
                ),
                Tool(
                    name="update_event",
                    description="Update an existing calendar event",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "eventId": {
                                "type": "string",
                                "description": "Event ID"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Event title/summary"
                            },
                            "description": {
                                "type": "string",
                                "description": "Event description"
                            },
                            "location": {
                                "type": "string",
                                "description": "Event location"
                            },
                            "start": {
                                "type": "object",
                                "description": "Start time",
                                "properties": {
                                    "dateTime": {"type": "string"},
                                    "timeZone": {"type": "string"}
                                }
                            },
                            "end": {
                                "type": "object",
                                "description": "End time",
                                "properties": {
                                    "dateTime": {"type": "string"},
                                    "timeZone": {"type": "string"}
                                }
                            },
                            "attendees": {
                                "type": "array",
                                "description": "List of attendee emails",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"}
                                    }
                                }
                            }
                        },
                        "required": ["eventId"]
                    }
                ),
                Tool(
                    name="delete_event",
                    description="Delete a calendar event",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "eventId": {
                                "type": "string",
                                "description": "Event ID"
                            }
                        },
                        "required": ["eventId"]
                    }
                ),
                Tool(
                    name="quick_add_event",
                    description="Quick add event using natural language (e.g., 'Meeting tomorrow at 2pm')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "calendarId": {
                                "type": "string",
                                "description": "Calendar ID (default: 'primary')",
                                "default": "primary"
                            },
                            "text": {
                                "type": "string",
                                "description": "Event description in natural language"
                            }
                        },
                        "required": ["text"]
                    }
                ),
                Tool(
                    name="freebusy_query",
                    description="Check free/busy information for multiple users. Returns busy time slots for each user.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "timeMin": {
                                "type": "string",
                                "description": "Start of time range (ISO 8601 format)"
                            },
                            "timeMax": {
                                "type": "string",
                                "description": "End of time range (ISO 8601 format)"
                            },
                            "items": {
                                "type": "array",
                                "description": "List of calendars/users to check",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "Calendar ID or email address"
                                        }
                                    }
                                }
                            },
                            "timeZone": {
                                "type": "string",
                                "description": "Timezone (default: UTC)",
                                "default": "UTC"
                            }
                        },
                        "required": ["timeMin", "timeMax", "items"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                service = self._get_calendar_service()
                
                if name == "list_calendars":
                    result = service.calendarList().list().execute()
                    calendars = result.get('items', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "calendars": [
                                {
                                    "id": cal.get('id'),
                                    "summary": cal.get('summary'),
                                    "description": cal.get('description'),
                                    "primary": cal.get('primary', False)
                                }
                                for cal in calendars
                            ]
                        }, indent=2)
                    )]
                
                elif name == "list_events":
                    calendar_id = arguments.get("calendarId", "primary")
                    time_min = arguments.get("timeMin")
                    time_max = arguments.get("timeMax")
                    max_results = arguments.get("maxResults", 10)
                    
                    events_result = service.events().list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    
                    events = events_result.get('items', [])
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "items": events,
                            "count": len(events)
                        }, indent=2, default=str)
                    )]
                
                elif name == "get_event":
                    calendar_id = arguments.get("calendarId", "primary")
                    event_id = arguments.get("eventId")
                    
                    event = service.events().get(
                        calendarId=calendar_id,
                        eventId=event_id
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps(event, indent=2, default=str)
                    )]
                
                elif name == "create_event":
                    calendar_id = arguments.get("calendarId", "primary")
                    event_body = {
                        "summary": arguments.get("summary"),
                        "description": arguments.get("description"),
                        "location": arguments.get("location"),
                        "start": arguments.get("start"),
                        "end": arguments.get("end"),
                    }
                    
                    if arguments.get("attendees"):
                        event_body["attendees"] = arguments.get("attendees")
                    
                    # Remove None values
                    event_body = {k: v for k, v in event_body.items() if v is not None}
                    
                    event = service.events().insert(
                        calendarId=calendar_id,
                        body=event_body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "id": event.get('id'),
                            "summary": event.get('summary'),
                            "start": event.get('start'),
                            "end": event.get('end'),
                            "status": "created"
                        }, indent=2, default=str)
                    )]
                
                elif name == "update_event":
                    calendar_id = arguments.get("calendarId", "primary")
                    event_id = arguments.get("eventId")
                    
                    # Get existing event
                    event = service.events().get(
                        calendarId=calendar_id,
                        eventId=event_id
                    ).execute()
                    
                    # Update fields
                    if "summary" in arguments:
                        event["summary"] = arguments["summary"]
                    if "description" in arguments:
                        event["description"] = arguments["description"]
                    if "location" in arguments:
                        event["location"] = arguments["location"]
                    if "start" in arguments:
                        event["start"] = arguments["start"]
                    if "end" in arguments:
                        event["end"] = arguments["end"]
                    if "attendees" in arguments:
                        event["attendees"] = arguments["attendees"]
                    
                    updated_event = service.events().update(
                        calendarId=calendar_id,
                        eventId=event_id,
                        body=event
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "id": updated_event.get('id'),
                            "summary": updated_event.get('summary'),
                            "status": "updated"
                        }, indent=2, default=str)
                    )]
                
                elif name == "delete_event":
                    calendar_id = arguments.get("calendarId", "primary")
                    event_id = arguments.get("eventId")
                    
                    service.events().delete(
                        calendarId=calendar_id,
                        eventId=event_id
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "deleted",
                            "eventId": event_id
                        }, indent=2)
                    )]
                
                elif name == "quick_add_event":
                    calendar_id = arguments.get("calendarId", "primary")
                    text = arguments.get("text")
                    
                    event = service.events().quickAdd(
                        calendarId=calendar_id,
                        text=text
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "id": event.get('id'),
                            "summary": event.get('summary'),
                            "start": event.get('start'),
                            "end": event.get('end'),
                            "status": "created"
                        }, indent=2, default=str)
                    )]
                
                elif name == "freebusy_query":
                    time_min = arguments.get("timeMin")
                    time_max = arguments.get("timeMax")
                    items = arguments.get("items", [])
                    time_zone = arguments.get("timeZone", "UTC")
                    
                    # Build freebusy request body
                    body = {
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "timeZone": time_zone,
                        "items": items
                    }
                    
                    # Query freebusy information
                    freebusy_result = service.freebusy().query(body=body).execute()
                    
                    # Extract calendars data
                    calendars = freebusy_result.get('calendars', {})
                    
                    # Format response
                    result = {
                        "timeMin": freebusy_result.get('timeMin'),
                        "timeMax": freebusy_result.get('timeMax'),
                        "calendars": {}
                    }
                    
                    for calendar_id, calendar_data in calendars.items():
                        busy_slots = calendar_data.get('busy', [])
                        errors = calendar_data.get('errors', [])
                        
                        result["calendars"][calendar_id] = {
                            "busy": busy_slots,
                            "errors": errors
                        }
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps(result, indent=2, default=str)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            
            except HttpError as e:
                error_msg = f"Google Calendar API error: {e.content.decode() if e.content else str(e)}"
                logger.error(error_msg)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2)
                )]
            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2)
                )]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Google Calendar MCP Server")
    parser.add_argument(
        "--token-path",
        type=str,
        default="config/google_calendar_token.json",
        help="Path to OAuth token file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = GoogleCalendarMCPServer(Path(args.token_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())



