"""
Gmail MCP Server.
Provides MCP tools for Gmail operations via OAuth2.
Supports reading, searching, sending, and managing emails without Composio.
"""

import asyncio
import json
import sys
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
import re
import html

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailMCPServer:
    """MCP Server for Gmail operations."""
    
    def __init__(self, token_path: Path):
        """
        Initialize Gmail MCP Server.
        
        Args:
            token_path: Path to OAuth token file
        """
        self.token_path = Path(token_path)
        self._gmail_service = None
        self.server = Server("gmail-mcp")
        self._setup_tools()
    
    def _get_gmail_service(self):
        """Get or create Gmail API service."""
        if self._gmail_service is None:
            if not self.token_path.exists():
                raise ValueError(
                    f"OAuth token not found at {self.token_path}. "
                    "Please complete OAuth flow first."
                )
            
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                GMAIL_SCOPES
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
                            "Please re-authenticate via /api/integrations/gmail/enable"
                        )
                else:
                    # Token expired and no refresh_token - user needs to re-authenticate
                    raise ValueError(
                        "Token expired and no refresh token available. "
                        "Please re-authenticate via /api/integrations/gmail/enable. "
                        "Make sure to use 'prompt=consent' during OAuth to get a refresh token."
                    )
            
            self._gmail_service = build('gmail', 'v1', credentials=creds)
        
        return self._gmail_service
    
    def _decode_email_body(self, payload: Dict) -> str:
        """Decode email body from base64url encoding."""
        body = ""
        
        if 'body' in payload and payload['body'].get('data'):
            # Simple message with body directly
            data = payload['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        elif 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    if part['body'].get('data'):
                        data = part['body']['data']
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        break
                elif mime_type == 'text/html':
                    if part['body'].get('data') and not body:
                        data = part['body']['data']
                        html_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        # Simple HTML to text conversion
                        body = re.sub('<[^<]+?>', '', html_body)
                        body = html.unescape(body)
                elif 'parts' in part:
                    # Nested multipart
                    body = self._decode_email_body(part)
                    if body:
                        break
        
        return body.strip()
    
    def _get_header_value(self, headers: List[Dict], name: str) -> str:
        """Get header value by name."""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return ""
    
    def _format_email_summary(self, message: Dict) -> Dict:
        """Format email message for summary display."""
        headers = message.get('payload', {}).get('headers', [])
        
        return {
            "id": message['id'],
            "threadId": message.get('threadId'),
            "snippet": message.get('snippet', ''),
            "from": self._get_header_value(headers, 'From'),
            "to": self._get_header_value(headers, 'To'),
            "subject": self._get_header_value(headers, 'Subject'),
            "date": self._get_header_value(headers, 'Date'),
            "labels": message.get('labelIds', []),
            "isUnread": 'UNREAD' in message.get('labelIds', []),
            "isStarred": 'STARRED' in message.get('labelIds', []),
            "isImportant": 'IMPORTANT' in message.get('labelIds', []),
        }
    
    def _create_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html_body: bool = False,
        reply_to: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None
    ) -> Dict:
        """Create email message for sending."""
        if html_body:
            message = MIMEMultipart('alternative')
            text_part = MIMEText(re.sub('<[^<]+?>', '', body), 'plain')
            html_part = MIMEText(body, 'html')
            message.attach(text_part)
            message.attach(html_part)
        else:
            message = MIMEText(body)
        
        message['to'] = to
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
        if reply_to:
            message['Reply-To'] = reply_to
        if in_reply_to:
            message['In-Reply-To'] = in_reply_to
        if references:
            message['References'] = references
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw}
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available Gmail tools."""
            return [
                # ========== READ OPERATIONS ==========
                Tool(
                    name="gmail_list_messages",
                    description="List emails from inbox or specific label. Returns recent emails with summary info.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of emails to return (default: 10, max: 100)",
                                "default": 10
                            },
                            "labelIds": {
                                "type": "array",
                                "description": "Filter by label IDs (e.g., ['INBOX'], ['UNREAD'], ['STARRED'])",
                                "items": {"type": "string"},
                                "default": ["INBOX"]
                            },
                            "includeSpamTrash": {
                                "type": "boolean",
                                "description": "Include spam and trash messages",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="gmail_get_message",
                    description="Get full details of a specific email by message ID, including body content.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "The ID of the message to retrieve"
                            },
                            "format": {
                                "type": "string",
                                "description": "Message format: 'full', 'minimal', 'metadata'",
                                "enum": ["full", "minimal", "metadata"],
                                "default": "full"
                            }
                        },
                        "required": ["messageId"]
                    }
                ),
                Tool(
                    name="gmail_search",
                    description="Search emails using Gmail search syntax. Supports from:, to:, subject:, is:, has:, newer_than:, older_than:, etc.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Gmail search query (e.g., 'from:sender@email.com', 'subject:meeting', 'is:unread newer_than:3d')"
                            },
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 10)",
                                "default": 10
                            },
                            "labelIds": {
                                "type": "array",
                                "description": "Filter by label IDs",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="gmail_get_thread",
                    description="Get an email thread (conversation) with all messages in it.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "threadId": {
                                "type": "string",
                                "description": "The ID of the thread to retrieve"
                            }
                        },
                        "required": ["threadId"]
                    }
                ),
                Tool(
                    name="gmail_list_labels",
                    description="List all labels (folders) in the mailbox.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="gmail_get_unread_count",
                    description="Get count of unread messages in inbox or specific label.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "labelId": {
                                "type": "string",
                                "description": "Label ID to check (default: INBOX)",
                                "default": "INBOX"
                            }
                        }
                    }
                ),
                
                # ========== SEND OPERATIONS ==========
                Tool(
                    name="gmail_send_email",
                    description="Send a new email message.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "to": {
                                "type": "string",
                                "description": "Recipient email address (comma-separated for multiple)"
                            },
                            "subject": {
                                "type": "string",
                                "description": "Email subject"
                            },
                            "body": {
                                "type": "string",
                                "description": "Email body content (plain text or HTML)"
                            },
                            "cc": {
                                "type": "string",
                                "description": "CC recipients (comma-separated)"
                            },
                            "bcc": {
                                "type": "string",
                                "description": "BCC recipients (comma-separated)"
                            },
                            "isHtml": {
                                "type": "boolean",
                                "description": "Whether body is HTML formatted",
                                "default": False
                            }
                        },
                        "required": ["to", "subject", "body"]
                    }
                ),
                Tool(
                    name="gmail_reply",
                    description="Reply to an existing email message.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "ID of the message to reply to"
                            },
                            "body": {
                                "type": "string",
                                "description": "Reply body content"
                            },
                            "replyAll": {
                                "type": "boolean",
                                "description": "Reply to all recipients",
                                "default": False
                            },
                            "isHtml": {
                                "type": "boolean",
                                "description": "Whether body is HTML formatted",
                                "default": False
                            }
                        },
                        "required": ["messageId", "body"]
                    }
                ),
                Tool(
                    name="gmail_forward",
                    description="Forward an email to another recipient.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "ID of the message to forward"
                            },
                            "to": {
                                "type": "string",
                                "description": "Recipient email address"
                            },
                            "additionalMessage": {
                                "type": "string",
                                "description": "Optional message to add before forwarded content"
                            }
                        },
                        "required": ["messageId", "to"]
                    }
                ),
                Tool(
                    name="gmail_create_draft",
                    description="Create an email draft without sending.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "to": {
                                "type": "string",
                                "description": "Recipient email address"
                            },
                            "subject": {
                                "type": "string",
                                "description": "Email subject"
                            },
                            "body": {
                                "type": "string",
                                "description": "Email body content"
                            },
                            "cc": {
                                "type": "string",
                                "description": "CC recipients"
                            },
                            "isHtml": {
                                "type": "boolean",
                                "description": "Whether body is HTML formatted",
                                "default": False
                            }
                        },
                        "required": ["to", "subject", "body"]
                    }
                ),
                
                # ========== MANAGE OPERATIONS ==========
                Tool(
                    name="gmail_mark_read",
                    description="Mark one or more emails as read.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageIds": {
                                "type": "array",
                                "description": "Array of message IDs to mark as read",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["messageIds"]
                    }
                ),
                Tool(
                    name="gmail_mark_unread",
                    description="Mark one or more emails as unread.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageIds": {
                                "type": "array",
                                "description": "Array of message IDs to mark as unread",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["messageIds"]
                    }
                ),
                Tool(
                    name="gmail_star_message",
                    description="Add or remove star from a message.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "Message ID"
                            },
                            "starred": {
                                "type": "boolean",
                                "description": "True to add star, False to remove",
                                "default": True
                            }
                        },
                        "required": ["messageId"]
                    }
                ),
                Tool(
                    name="gmail_archive_message",
                    description="Archive a message (remove from inbox but keep in All Mail).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "Message ID to archive"
                            }
                        },
                        "required": ["messageId"]
                    }
                ),
                Tool(
                    name="gmail_trash_message",
                    description="Move a message to trash.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "Message ID to trash"
                            }
                        },
                        "required": ["messageId"]
                    }
                ),
                Tool(
                    name="gmail_add_label",
                    description="Add a label to a message.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "Message ID"
                            },
                            "labelId": {
                                "type": "string",
                                "description": "Label ID to add"
                            }
                        },
                        "required": ["messageId", "labelId"]
                    }
                ),
                Tool(
                    name="gmail_remove_label",
                    description="Remove a label from a message.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "messageId": {
                                "type": "string",
                                "description": "Message ID"
                            },
                            "labelId": {
                                "type": "string",
                                "description": "Label ID to remove"
                            }
                        },
                        "required": ["messageId", "labelId"]
                    }
                ),
                Tool(
                    name="gmail_get_important_emails",
                    description="Get important or high-priority emails that might need attention. Returns starred, unread, or marked important messages.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "maxResults": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10
                            },
                            "includeStarred": {
                                "type": "boolean",
                                "description": "Include starred messages",
                                "default": True
                            },
                            "includeUnread": {
                                "type": "boolean",
                                "description": "Include unread messages",
                                "default": True
                            },
                            "daysBack": {
                                "type": "integer",
                                "description": "Only include messages from last N days",
                                "default": 7
                            }
                        }
                    }
                ),
                Tool(
                    name="gmail_get_profile",
                    description="Get user's Gmail profile information (email address, total messages, threads).",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                service = self._get_gmail_service()
                
                # ========== READ OPERATIONS ==========
                if name == "gmail_list_messages":
                    max_results = min(arguments.get("maxResults", 10), 100)
                    label_ids = arguments.get("labelIds", ["INBOX"])
                    include_spam_trash = arguments.get("includeSpamTrash", False)
                    
                    results = service.users().messages().list(
                        userId="me",
                        maxResults=max_results,
                        labelIds=label_ids,
                        includeSpamTrash=include_spam_trash
                    ).execute()
                    
                    messages = results.get('messages', [])
                    
                    # Get details for each message
                    detailed_messages = []
                    for msg in messages:
                        msg_detail = service.users().messages().get(
                            userId="me",
                            id=msg['id'],
                            format="metadata",
                            metadataHeaders=["From", "To", "Subject", "Date"]
                        ).execute()
                        detailed_messages.append(self._format_email_summary(msg_detail))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "count": len(detailed_messages),
                            "messages": detailed_messages
                        }, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_get_message":
                    message_id = arguments.get("messageId")
                    format_type = arguments.get("format", "full")
                    
                    message = service.users().messages().get(
                        userId="me",
                        id=message_id,
                        format=format_type
                    ).execute()
                    
                    result = self._format_email_summary(message)
                    
                    if format_type == "full":
                        result["body"] = self._decode_email_body(message.get('payload', {}))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps(result, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_search":
                    query = arguments.get("query")
                    max_results = min(arguments.get("maxResults", 10), 100)
                    label_ids = arguments.get("labelIds")
                    
                    params = {
                        "userId": "me",
                        "q": query,
                        "maxResults": max_results
                    }
                    if label_ids:
                        params["labelIds"] = label_ids
                    
                    results = service.users().messages().list(**params).execute()
                    
                    messages = results.get('messages', [])
                    
                    # Get details for each message
                    detailed_messages = []
                    for msg in messages:
                        msg_detail = service.users().messages().get(
                            userId="me",
                            id=msg['id'],
                            format="metadata",
                            metadataHeaders=["From", "To", "Subject", "Date"]
                        ).execute()
                        detailed_messages.append(self._format_email_summary(msg_detail))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "query": query,
                            "count": len(detailed_messages),
                            "messages": detailed_messages
                        }, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_get_thread":
                    thread_id = arguments.get("threadId")
                    
                    thread = service.users().threads().get(
                        userId="me",
                        id=thread_id
                    ).execute()
                    
                    messages = []
                    for msg in thread.get('messages', []):
                        msg_summary = self._format_email_summary(msg)
                        msg_summary["body"] = self._decode_email_body(msg.get('payload', {}))
                        messages.append(msg_summary)
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "threadId": thread_id,
                            "messageCount": len(messages),
                            "messages": messages
                        }, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_list_labels":
                    results = service.users().labels().list(userId="me").execute()
                    labels = results.get('labels', [])
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "labels": [
                                {
                                    "id": label['id'],
                                    "name": label['name'],
                                    "type": label.get('type', 'user')
                                }
                                for label in labels
                            ]
                        }, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_get_unread_count":
                    label_id = arguments.get("labelId", "INBOX")
                    
                    label = service.users().labels().get(
                        userId="me",
                        id=label_id
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "labelId": label_id,
                            "name": label.get('name'),
                            "unreadCount": label.get('messagesUnread', 0),
                            "totalCount": label.get('messagesTotal', 0)
                        }, indent=2)
                    )]
                
                # ========== SEND OPERATIONS ==========
                elif name == "gmail_send_email":
                    to = arguments.get("to")
                    subject = arguments.get("subject")
                    body = arguments.get("body")
                    cc = arguments.get("cc")
                    bcc = arguments.get("bcc")
                    is_html = arguments.get("isHtml", False)
                    
                    message = self._create_message(
                        to=to,
                        subject=subject,
                        body=body,
                        cc=cc,
                        bcc=bcc,
                        html_body=is_html
                    )
                    
                    sent = service.users().messages().send(
                        userId="me",
                        body=message
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "sent",
                            "messageId": sent['id'],
                            "threadId": sent.get('threadId'),
                            "to": to,
                            "subject": subject
                        }, indent=2)
                    )]
                
                elif name == "gmail_reply":
                    message_id = arguments.get("messageId")
                    body = arguments.get("body")
                    reply_all = arguments.get("replyAll", False)
                    is_html = arguments.get("isHtml", False)
                    
                    # Get original message
                    original = service.users().messages().get(
                        userId="me",
                        id=message_id,
                        format="metadata",
                        metadataHeaders=["From", "To", "Cc", "Subject", "Message-ID", "References"]
                    ).execute()
                    
                    headers = original.get('payload', {}).get('headers', [])
                    original_from = self._get_header_value(headers, 'From')
                    original_to = self._get_header_value(headers, 'To')
                    original_cc = self._get_header_value(headers, 'Cc')
                    original_subject = self._get_header_value(headers, 'Subject')
                    message_id_header = self._get_header_value(headers, 'Message-ID')
                    references = self._get_header_value(headers, 'References')
                    
                    # Determine recipients
                    to = original_from
                    cc = None
                    if reply_all:
                        # Include original To and Cc (excluding self)
                        cc_list = []
                        if original_to:
                            cc_list.append(original_to)
                        if original_cc:
                            cc_list.append(original_cc)
                        if cc_list:
                            cc = ", ".join(cc_list)
                    
                    # Prepare subject
                    if not original_subject.lower().startswith("re:"):
                        subject = f"Re: {original_subject}"
                    else:
                        subject = original_subject
                    
                    # Prepare references
                    new_references = message_id_header
                    if references:
                        new_references = f"{references} {message_id_header}"
                    
                    message = self._create_message(
                        to=to,
                        subject=subject,
                        body=body,
                        cc=cc,
                        html_body=is_html,
                        in_reply_to=message_id_header,
                        references=new_references
                    )
                    
                    # Add thread ID to keep in same thread
                    message['threadId'] = original.get('threadId')
                    
                    sent = service.users().messages().send(
                        userId="me",
                        body=message
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "replied",
                            "messageId": sent['id'],
                            "threadId": sent.get('threadId'),
                            "to": to,
                            "subject": subject
                        }, indent=2)
                    )]
                
                elif name == "gmail_forward":
                    message_id = arguments.get("messageId")
                    to = arguments.get("to")
                    additional_message = arguments.get("additionalMessage", "")
                    
                    # Get original message
                    original = service.users().messages().get(
                        userId="me",
                        id=message_id,
                        format="full"
                    ).execute()
                    
                    headers = original.get('payload', {}).get('headers', [])
                    original_from = self._get_header_value(headers, 'From')
                    original_to = self._get_header_value(headers, 'To')
                    original_date = self._get_header_value(headers, 'Date')
                    original_subject = self._get_header_value(headers, 'Subject')
                    original_body = self._decode_email_body(original.get('payload', {}))
                    
                    # Build forwarded message
                    forward_header = f"\n\n---------- Forwarded message ---------\nFrom: {original_from}\nDate: {original_date}\nSubject: {original_subject}\nTo: {original_to}\n\n"
                    
                    body = additional_message + forward_header + original_body
                    
                    # Prepare subject
                    if not original_subject.lower().startswith("fwd:"):
                        subject = f"Fwd: {original_subject}"
                    else:
                        subject = original_subject
                    
                    message = self._create_message(
                        to=to,
                        subject=subject,
                        body=body
                    )
                    
                    sent = service.users().messages().send(
                        userId="me",
                        body=message
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "forwarded",
                            "messageId": sent['id'],
                            "to": to,
                            "subject": subject
                        }, indent=2)
                    )]
                
                elif name == "gmail_create_draft":
                    to = arguments.get("to")
                    subject = arguments.get("subject")
                    body = arguments.get("body")
                    cc = arguments.get("cc")
                    is_html = arguments.get("isHtml", False)
                    
                    message = self._create_message(
                        to=to,
                        subject=subject,
                        body=body,
                        cc=cc,
                        html_body=is_html
                    )
                    
                    draft = service.users().drafts().create(
                        userId="me",
                        body={"message": message}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "draft_created",
                            "draftId": draft['id'],
                            "messageId": draft['message']['id'],
                            "to": to,
                            "subject": subject
                        }, indent=2)
                    )]
                
                # ========== MANAGE OPERATIONS ==========
                elif name == "gmail_mark_read":
                    message_ids = arguments.get("messageIds", [])
                    
                    for msg_id in message_ids:
                        service.users().messages().modify(
                            userId="me",
                            id=msg_id,
                            body={"removeLabelIds": ["UNREAD"]}
                        ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "marked_read",
                            "count": len(message_ids),
                            "messageIds": message_ids
                        }, indent=2)
                    )]
                
                elif name == "gmail_mark_unread":
                    message_ids = arguments.get("messageIds", [])
                    
                    for msg_id in message_ids:
                        service.users().messages().modify(
                            userId="me",
                            id=msg_id,
                            body={"addLabelIds": ["UNREAD"]}
                        ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "marked_unread",
                            "count": len(message_ids),
                            "messageIds": message_ids
                        }, indent=2)
                    )]
                
                elif name == "gmail_star_message":
                    message_id = arguments.get("messageId")
                    starred = arguments.get("starred", True)
                    
                    if starred:
                        body = {"addLabelIds": ["STARRED"]}
                    else:
                        body = {"removeLabelIds": ["STARRED"]}
                    
                    service.users().messages().modify(
                        userId="me",
                        id=message_id,
                        body=body
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "starred" if starred else "unstarred",
                            "messageId": message_id
                        }, indent=2)
                    )]
                
                elif name == "gmail_archive_message":
                    message_id = arguments.get("messageId")
                    
                    service.users().messages().modify(
                        userId="me",
                        id=message_id,
                        body={"removeLabelIds": ["INBOX"]}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "archived",
                            "messageId": message_id
                        }, indent=2)
                    )]
                
                elif name == "gmail_trash_message":
                    message_id = arguments.get("messageId")
                    
                    service.users().messages().trash(
                        userId="me",
                        id=message_id
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "trashed",
                            "messageId": message_id
                        }, indent=2)
                    )]
                
                elif name == "gmail_add_label":
                    message_id = arguments.get("messageId")
                    label_id = arguments.get("labelId")
                    
                    service.users().messages().modify(
                        userId="me",
                        id=message_id,
                        body={"addLabelIds": [label_id]}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "label_added",
                            "messageId": message_id,
                            "labelId": label_id
                        }, indent=2)
                    )]
                
                elif name == "gmail_remove_label":
                    message_id = arguments.get("messageId")
                    label_id = arguments.get("labelId")
                    
                    service.users().messages().modify(
                        userId="me",
                        id=message_id,
                        body={"removeLabelIds": [label_id]}
                    ).execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "label_removed",
                            "messageId": message_id,
                            "labelId": label_id
                        }, indent=2)
                    )]
                
                elif name == "gmail_get_important_emails":
                    max_results = min(arguments.get("maxResults", 10), 50)
                    include_starred = arguments.get("includeStarred", True)
                    include_unread = arguments.get("includeUnread", True)
                    days_back = arguments.get("daysBack", 7)
                    
                    # Build query
                    query_parts = []
                    if include_starred:
                        query_parts.append("is:starred")
                    if include_unread:
                        query_parts.append("is:unread")
                    
                    query_parts.append("is:important")
                    query_parts.append(f"newer_than:{days_back}d")
                    
                    # Use OR for starred/unread/important
                    query = f"({' OR '.join(query_parts[:3])}) {query_parts[3]}"
                    
                    results = service.users().messages().list(
                        userId="me",
                        q=query,
                        maxResults=max_results
                    ).execute()
                    
                    messages = results.get('messages', [])
                    
                    detailed_messages = []
                    for msg in messages:
                        msg_detail = service.users().messages().get(
                            userId="me",
                            id=msg['id'],
                            format="metadata",
                            metadataHeaders=["From", "To", "Subject", "Date"]
                        ).execute()
                        detailed_messages.append(self._format_email_summary(msg_detail))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "count": len(detailed_messages),
                            "criteria": {
                                "includeStarred": include_starred,
                                "includeUnread": include_unread,
                                "daysBack": days_back
                            },
                            "messages": detailed_messages
                        }, indent=2, ensure_ascii=False)
                    )]
                
                elif name == "gmail_get_profile":
                    profile = service.users().getProfile(userId="me").execute()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "emailAddress": profile.get('emailAddress'),
                            "messagesTotal": profile.get('messagesTotal'),
                            "threadsTotal": profile.get('threadsTotal'),
                            "historyId": profile.get('historyId')
                        }, indent=2)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            
            except HttpError as e:
                error_content = e.content.decode() if e.content else str(e)
                error_msg = f"Gmail API error: {error_content}"
                logger.error(error_msg)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg, "status": e.resp.status}, indent=2)
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
    
    parser = argparse.ArgumentParser(description="Gmail MCP Server")
    parser.add_argument(
        "--token-path",
        type=str,
        default="config/gmail_token.json",
        help="Path to OAuth token file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = GmailMCPServer(Path(args.token_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())


