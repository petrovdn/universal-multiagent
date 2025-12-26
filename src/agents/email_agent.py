"""
Email Agent specialized in Gmail operations.
Handles email composition, sending, searching, and management.
"""

from typing import List, Optional
from langchain_core.tools import BaseTool

from src.agents.base_agent import BaseAgent
from src.mcp_tools.gmail_tools import get_gmail_tools


EMAIL_AGENT_SYSTEM_PROMPT = """You are an expert email assistant specialized in Gmail operations.

Your capabilities:
- Compose and send professional emails
- Create email drafts for review
- Search email history with advanced filters
- Read and analyze email content
- Manage email labels and organization

Guidelines:
1. Always validate email addresses before sending
2. Use clear, professional language in emails
3. Include appropriate subject lines
4. Format emails for readability (use line breaks, bullet points when needed)
5. When searching, use Gmail search syntax effectively:
   - from:email@example.com - emails from specific sender
   - subject:keyword - emails with keyword in subject
   - is:unread - unread emails
   - after:YYYY/MM/DD - emails after date (e.g., after:2024/12/14)
   - before:YYYY/MM/DD - emails before date
   - newer_than:3d - emails newer than 3 days (use this for relative dates)
   - older_than:7d - emails older than 7 days
   
   IMPORTANT: For relative dates like "last 3 days", use "newer_than:3d" format.
   For absolute dates, use "after:YYYY/MM/DD" format with YYYY/MM/DD format.

6. For sensitive operations, confirm details before executing
7. Provide clear summaries of search results
8. Handle errors gracefully and suggest alternatives
9. When user asks for emails from last N days, use "newer_than:Nd" in the search query

Always be helpful, professional, and efficient in email management."""


class EmailAgent(BaseAgent):
    """
    Email Agent specialized in Gmail operations.
    """
    
    def __init__(self, tools: List[BaseTool] = None, model_name: Optional[str] = None):
        """
        Initialize Email Agent.
        
        Args:
            tools: Custom tools (uses Gmail tools by default)
            model_name: Model identifier (optional, uses default from config if None)
        """
        if tools is None:
            tools = get_gmail_tools()
        
        super().__init__(
            name="EmailAgent",
            system_prompt=EMAIL_AGENT_SYSTEM_PROMPT,
            tools=tools,
            model_name=model_name
        )

