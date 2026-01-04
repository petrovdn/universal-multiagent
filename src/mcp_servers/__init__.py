"""
MCP servers for Google Workspace integrations, 1C:Бухгалтерия, and Project Lad.

Available servers:
- gmail_server: Gmail operations via OAuth2
- google_calendar_server: Google Calendar operations via OAuth2
- onec_server: 1C:Бухгалтерия OData operations
- projectlad_server: Project Lad operations
"""

from .gmail_server import GmailMCPServer
from .google_calendar_server import GoogleCalendarMCPServer
from .onec_server import OneCMCPServer
from .projectlad_server import ProjectLadMCPServer

__all__ = [
    "GmailMCPServer",
    "GoogleCalendarMCPServer",
    "OneCMCPServer",
    "ProjectLadMCPServer",
]
