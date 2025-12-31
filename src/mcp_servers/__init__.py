"""
MCP servers for Google Workspace integrations and 1C:Бухгалтерия.

Available servers:
- gmail_server: Gmail operations via OAuth2
- google_calendar_server: Google Calendar operations via OAuth2
- onec_server: 1C:Бухгалтерия OData operations
"""

from .gmail_server import GmailMCPServer
from .google_calendar_server import GoogleCalendarMCPServer
from .onec_server import OneCMCPServer

__all__ = [
    "GmailMCPServer",
    "GoogleCalendarMCPServer",
    "OneCMCPServer",
]
