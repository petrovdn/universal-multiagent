"""
MCP servers for Google Workspace integrations.

Available servers:
- gmail_server: Gmail operations via OAuth2
- google_calendar_server: Google Calendar operations via OAuth2
"""

from .gmail_server import GmailMCPServer
from .google_calendar_server import GoogleCalendarMCPServer

__all__ = [
    "GmailMCPServer",
    "GoogleCalendarMCPServer",
]
