"""
Gmail MCP tool wrappers for LangChain.
Provides validated, user-friendly interfaces to Gmail operations.
Uses the custom Gmail MCP server with gmail_* prefixed tool names.
"""

import json
from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.validators import validate_email, validate_email_list
from src.utils.exceptions import ToolExecutionError, ValidationError
from src.utils.retry import retry_on_mcp_error


class SendEmailInput(BaseModel):
    """Input schema for send_email tool."""
    
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (plain text or HTML)")
    cc: Optional[str] = Field(default=None, description="CC email address")
    bcc: Optional[str] = Field(default=None, description="BCC email address")
    html: bool = Field(default=False, description="Whether body is HTML")


class SendEmailTool(BaseTool):
    """Tool for sending emails via Gmail."""
    
    name: str = "send_email"
    description: str = """
    Send an email through Gmail.
    
    Input should be a JSON object with:
    - to: Recipient email address (required)
    - subject: Email subject (required)
    - body: Email body text (required)
    - cc: CC recipient (optional)
    - bcc: BCC recipient (optional)
    - html: Whether body is HTML (default: false)
    """
    args_schema: type = SendEmailInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # Validate email addresses
            to_email = validate_email(to)
            cc_email = validate_email(cc) if cc else None
            bcc_email = validate_email(bcc) if bcc else None
            
            # Prepare arguments for gmail_send_email
            args = {
                "to": to_email,
                "subject": subject,
                "body": body,
                "isHtml": html
            }
            if cc_email:
                args["cc"] = cc_email
            if bcc_email:
                args["bcc"] = bcc_email
            
            # Call MCP tool - using gmail_send_email
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("gmail_send_email", args, server_name="gmail")
            
            # Parse result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                msg_id = result.get('messageId', 'unknown')
                return f"Email sent successfully to {to_email}. Message ID: {msg_id}"
            
            return f"Email sent successfully to {to_email}."
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Email validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"to": to, "subject": subject}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to send email: {e}",
                tool_name=self.name,
                tool_args={"to": to, "subject": subject}
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous execution (not supported)."""
        raise NotImplementedError("Use async execution")


class DraftEmailInput(BaseModel):
    """Input schema for draft_email tool."""
    
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body")
    cc: Optional[str] = Field(default=None, description="CC email address")


class DraftEmailTool(BaseTool):
    """Tool for creating email drafts."""
    
    name: str = "draft_email"
    description: str = "Create an email draft in Gmail without sending it."
    args_schema: type = DraftEmailInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            to_email = validate_email(to)
            cc_email = validate_email(cc) if cc else None
            
            args = {
                "to": to_email,
                "subject": subject,
                "body": body
            }
            if cc_email:
                args["cc"] = cc_email
            
            mcp_manager = get_mcp_manager()
            # Using gmail_create_draft
            result = await mcp_manager.call_tool("gmail_create_draft", args, server_name="gmail")
            
            # Parse result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                draft_id = result.get('draftId', 'unknown')
                return f"Email draft created. Draft ID: {draft_id}"
            
            return f"Email draft created successfully."
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to create draft: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class SearchEmailsInput(BaseModel):
    """Input schema for search_emails tool."""
    
    query: str = Field(description="Gmail search query (e.g., 'from:example@gmail.com subject:meeting')")
    max_results: int = Field(default=10, description="Maximum number of results")


class SearchEmailsTool(BaseTool):
    """Tool for searching emails in Gmail."""
    
    name: str = "search_emails"
    description: str = """
    Search emails in Gmail using Gmail search syntax.
    
    Examples:
    - 'from:example@gmail.com' - Emails from specific sender
    - 'subject:meeting' - Emails with 'meeting' in subject
    - 'is:unread' - Unread emails
    - 'after:2024/12/14' - Emails after date (format: YYYY/MM/DD)
    - 'newer_than:3d' - Emails newer than 3 days (use for relative dates)
    - 'newer_than:7d' - Emails newer than 7 days
    
    IMPORTANT: For "last N days" queries, use "newer_than:Nd" format.
    For example, "emails from last 3 days" should use query: "newer_than:3d"
    """
    args_schema: type = SearchEmailsInput
    
    @retry_on_mcp_error()
    async def _arun(self, query: str, max_results: int = 10) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "query": query,
                "maxResults": max_results
            }
            
            mcp_manager = get_mcp_manager()
            # Using gmail_search
            result = await mcp_manager.call_tool("gmail_search", args, server_name="gmail")
            
            # Parse result - handle TextContent list
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            # Parse result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            # Extract messages from result
            messages = []
            if isinstance(result, dict):
                messages = result.get("messages", [])
                count = result.get("count", len(messages))
            elif isinstance(result, list):
                messages = result
                count = len(messages)
            else:
                count = 0
            
            if count == 0:
                return f"No emails found matching query: {query}"
            
            # Format response with email summaries
            response_lines = [f"Found {count} emails matching query: {query}\n"]
            for i, msg in enumerate(messages[:5], 1):  # Show first 5
                if isinstance(msg, dict):
                    subj = msg.get('subject', 'No subject')
                    from_addr = msg.get('from', 'Unknown')
                    msg_id = msg.get('id', 'unknown')
                    date = msg.get('date', '')
                    is_unread = '📩' if msg.get('isUnread') else '📧'
                    response_lines.append(f"{i}. {is_unread} {subj[:50]}")
                    response_lines.append(f"   От: {from_addr[:40]}")
                    if date:
                        response_lines.append(f"   Дата: {date}")
                    response_lines.append(f"   ID: {msg_id}")
                    response_lines.append("")
            
            if count > 5:
                response_lines.append(f"... и ещё {count - 5} писем")
            
            return "\n".join(response_lines)
            
        except ToolExecutionError:
            raise
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            raise ToolExecutionError(
                f"Failed to search emails: {error_msg}",
                tool_name=self.name,
                tool_args={"query": query, "max_results": max_results}
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ReadEmailInput(BaseModel):
    """Input schema for read_email tool."""
    
    message_id: str = Field(description="Gmail message ID")


class ReadEmailTool(BaseTool):
    """Tool for reading a specific email."""
    
    name: str = "read_email"
    description: str = "Read the content of a specific email by message ID."
    args_schema: type = ReadEmailInput
    
    @retry_on_mcp_error()
    async def _arun(self, message_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {"messageId": message_id}
            
            mcp_manager = get_mcp_manager()
            # Using gmail_get_message
            result = await mcp_manager.call_tool("gmail_get_message", args, server_name="gmail")
            
            # Parse result - handle TextContent list
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            # Parse result - MCP returns string JSON
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # If can't parse as JSON, maybe it's an error message
                    if "error" in result.lower() or "404" in result:
                        raise ToolExecutionError(
                            f"Failed to read email: {result}",
                            tool_name=self.name
                        )
                    pass
            
            # Check if result contains error
            if isinstance(result, dict):
                # Check for error field first
                if "error" in result:
                    error_msg = result.get("error", "Unknown error")
                    raise ToolExecutionError(
                        f"Gmail API error: {error_msg}",
                        tool_name=self.name,
                        tool_args=args
                    )
                
                # Extract email data
                subject = result.get("subject", "No subject")
                from_addr = result.get("from", "Unknown")
                to_addr = result.get("to", "")
                date = result.get("date", "")
                body = result.get("body", "")
                
                # Truncate body for display
                if len(body) > 1000:
                    body = body[:1000] + "..."
                
                response = f"📧 Email Details:\n\n"
                response += f"От: {from_addr}\n"
                if to_addr:
                    response += f"Кому: {to_addr}\n"
                response += f"Тема: {subject}\n"
                if date:
                    response += f"Дата: {date}\n"
                response += f"\n--- Содержание ---\n\n{body}"
                
                return response
            
            # If result is not a dict, return as string
            result_str = str(result)
            if "error" in result_str.lower() or "404" in result_str:
                raise ToolExecutionError(
                    f"Failed to read email: {result_str}",
                    tool_name=self.name
                )
            
            return f"Email content: {result_str}"
            
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to read email: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class ListEmailsInput(BaseModel):
    """Input schema for list_emails tool."""
    
    max_results: int = Field(default=10, description="Maximum number of results")
    label: str = Field(default="INBOX", description="Label to list emails from (INBOX, SENT, etc)")


class ListEmailsTool(BaseTool):
    """Tool for listing recent emails."""
    
    name: str = "list_emails"
    description: str = """
    List recent emails from Gmail inbox or specific label.
    Use this to see recent emails without a specific search query.
    """
    args_schema: type = ListEmailsInput
    
    @retry_on_mcp_error()
    async def _arun(self, max_results: int = 10, label: str = "INBOX") -> str:
        """Execute the tool asynchronously."""
        try:
            args = {
                "maxResults": max_results,
                "labelIds": [label]
            }
            
            mcp_manager = get_mcp_manager()
            # Using gmail_list_messages
            result = await mcp_manager.call_tool("gmail_list_messages", args, server_name="gmail")
            
            # Parse result - handle different return types from MCP
            # MCP can return: string JSON, dict, or list of TextContent objects
            if isinstance(result, list) and len(result) > 0:
                # Extract text from TextContent objects
                # TextContent typically has .text or dict with 'text' key
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result = first_item['text']
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass
            
            # Extract messages
            messages = []
            if isinstance(result, dict):
                messages = result.get("messages", [])
                count = result.get("count", len(messages))
            elif isinstance(result, list):
                messages = result
                count = len(messages)
            else:
                count = 0
            
            if count == 0:
                return f"No emails found in {label}"
            
            # Format response
            response_lines = [f"📬 {count} emails in {label}:\n"]
            for i, msg in enumerate(messages[:max_results], 1):
                if isinstance(msg, dict):
                    subj = msg.get('subject', 'No subject')
                    from_addr = msg.get('from', 'Unknown')
                    msg_id = msg.get('id', 'unknown')
                    is_unread = '📩' if msg.get('isUnread') else '📧'
                    is_starred = '⭐' if msg.get('isStarred') else ''
                    response_lines.append(f"{i}. {is_unread}{is_starred} {subj[:50]}")
                    response_lines.append(f"   От: {from_addr[:40]}")
                    response_lines.append(f"   ID: {msg_id}")
                    response_lines.append("")
            
            return "\n".join(response_lines)
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to list emails: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_gmail_tools() -> List[BaseTool]:
    """
    Get all Gmail tools.
    
    Returns:
        List of Gmail tool instances
    """
    return [
        SendEmailTool(),
        DraftEmailTool(),
        SearchEmailsTool(),
        ReadEmailTool(),
        ListEmailsTool(),
    ]
