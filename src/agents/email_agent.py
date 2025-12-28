"""
Email Agent specialized in Gmail operations.
Handles email composition, sending, searching, and management.
"""

from typing import List, Optional
from langchain_core.tools import BaseTool

from src.agents.base_agent import BaseAgent
from src.mcp_tools.gmail_tools import get_gmail_tools


EMAIL_AGENT_SYSTEM_PROMPT = """You are an expert email assistant specialized in email operations.

## Language Requirements
- All your reasoning (thinking process) must be in Russian
- All your responses to users must be in Russian
- Use Russian for all internal reasoning and decision-making

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
5. When searching, use available email search syntax effectively:
   - Use appropriate search operators for filtering emails (by sender, subject, date, etc.)
   - For relative dates like "last 3 days", use appropriate date filter syntax
   - For absolute dates, use appropriate date format

6. For sensitive operations, confirm details before executing
7. Provide clear summaries of search results
8. Handle errors gracefully and suggest alternatives
9. When user asks for emails from last N days, use appropriate date filter in the search query

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

