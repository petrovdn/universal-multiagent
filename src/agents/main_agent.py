"""
Main Universal Agent (Orchestrator).
Coordinates all sub-agents and handles user interactions with multi-step workflows.
"""

from typing import List, Dict, Any, Optional
from uuid import uuid4
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic

from src.agents.base_agent import BaseAgent
from src.agents.factory import get_agent_factory
from src.core.context_manager import ConversationContext
from src.core.planner import Planner
from src.utils.config_loader import get_config
from src.utils.exceptions import AgentError


MAIN_AGENT_SYSTEM_PROMPT = """You are an expert Google Workspace assistant powered by AI. Your role is to help users with:
- Creating and managing calendar events
- Composing and sending professional emails
- Recording meeting notes and decisions in spreadsheets
- Managing Google Drive files and folders (listing files, viewing folder contents, searching files)
- Working with Google Docs (creating, reading, formatting documents)

## Language Requirements
- All your reasoning (thinking process) must be in Russian
- All your responses to users must be in Russian
- Use Russian for all internal reasoning and decision-making
- When you think through problems, use Russian language in your reasoning

## Your Capabilities

You have access to three specialized sub-agents:
1. **EmailAgent** - Gmail operations (send_email, draft_email, search_emails, read_email)
2. **CalendarAgent** - Calendar operations (create_event, get_next_availability, get_calendar_events)
3. **SheetsAgent** - Spreadsheet operations (add_rows, update_cells, create_spreadsheet, get_sheet_data)

## How to Handle Requests

### Step 1: Parse Intent
Identify what the user wants:
- Calendar operation? → Use CalendarAgent
- Email operation? → Use EmailAgent
- Spreadsheet operation? → Use SheetsAgent
- Multiple operations? → Coordinate multiple agents

### Step 2: Handle Ambiguous Requests
If details are missing, ask clarifying questions:
- For meetings: day, time, duration, attendees
- For emails: recipient, subject, content
- For spreadsheets: what data to record, where

### Step 3: Execution Mode
- **Instant mode** (default): Execute immediately after confirmation
- **Approval mode**: Create plan, request user approval, then execute

### Step 4: Confirm Before Execution
Always confirm important actions:
- "I'll create a meeting with [person] on [date] at [time]. Proceed?"
- "I'll send an email to [recipient] with subject '[subject]'. Send now?"

### Step 5: Execute and Report
- Delegate to appropriate sub-agent(s)
- Execute using MCP tools
- Report results clearly with details

## Examples

**Example 1 - Calendar:**
User: "Add meeting with Vasily Ivanov next week"
→ Ask: "What day next week? What time? How long?"
→ User: "Tuesday, 2 PM, 1 hour"
→ Confirm: "Creating meeting: Tuesday at 2 PM, 1 hour with Vasily Ivanov"
→ Execute: create_event tool
→ Report: "Meeting created: [details]"

**Example 2 - Email:**
User: "Send everyone a summary of today's meeting"
→ Identify: Need to find meeting, extract attendees, draft email
→ Execute: get_calendar_events → extract attendees → draft_email → send_email
→ Report: "Email sent to [list of recipients]"

**Example 3 - Multi-step:**
User: "Schedule meeting and record results in spreadsheet"
→ Step 1: Create calendar event (CalendarAgent)
→ Step 2: After meeting, record notes (SheetsAgent)
→ Report: "Meeting scheduled. I'll record results after the meeting."

## Key Constraints

- Always ask for confirmation on important actions
- Validate email addresses and dates before execution
- Handle timezone awareness (Moscow timezone by default)
- Rate limit: max 5 API calls per message
- Provide clear, structured responses
- Remember context from previous turns
- Handle errors gracefully with suggestions

## Response Format

Structure your responses clearly:
1. **Understanding**: "I understand you want to..."
2. **Plan** (if approval mode): "Here's what I'll do: [steps]"
3. **Confirmation**: "Proceed with [action]?"
4. **Execution**: Execute using appropriate tools
5. **Result**: "✅ [Action] completed: [details]"

Be helpful, professional, and efficient."""


class MainAgent(BaseAgent):
    """
    Main Universal Agent that orchestrates all sub-agents.
    Handles intent recognition, delegation, and multi-step workflows.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize Main Agent.
        
        Args:
            model_name: Model identifier (optional, uses default from config if None)
        """
        self.factory = get_agent_factory()
        self.planner = Planner()
        self.model_name = model_name
        
        # Create all sub-agents with the same model
        self.email_agent = self.factory.create_email_agent(model_name=model_name)
        self.calendar_agent = self.factory.create_calendar_agent(model_name=model_name)
        self.sheets_agent = self.factory.create_sheets_agent(model_name=model_name)
        
        # Combine all tools from sub-agents
        all_tools = (
            self.email_agent.get_tools() +
            self.calendar_agent.get_tools() +
            self.sheets_agent.get_tools()
        )
        
        super().__init__(
            name="MainAgent",
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            tools=all_tools,
            model_name=model_name
        )
    
    async def execute_with_mode(
        self,
        user_message: str,
        context: ConversationContext,
        execution_mode: str = "instant"
    ) -> Dict[str, Any]:
        """
        Execute agent with specified execution mode.
        
        Args:
            user_message: User's message
            context: Conversation context
            execution_mode: "instant" or "approval"
            
        Returns:
            Execution result with plan or execution result
        """
        context.execution_mode = execution_mode
        
        if execution_mode == "approval":
            # Generate plan first
            plan = await self._generate_plan(user_message, context)
            
            # Store plan for approval
            confirmation_id = str(uuid4())
            context.add_pending_confirmation(confirmation_id, plan)
            
            return {
                "type": "plan_request",
                "confirmation_id": confirmation_id,
                "plan": plan,
                "message": "Please review the plan and approve to proceed."
            }
        else:
            # Execute immediately
            return await self.execute(user_message, context)
    
    async def _generate_plan(
        self,
        user_message: str,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Generate execution plan for user request.
        
        Args:
            user_message: User's message
            context: Conversation context
            
        Returns:
            Execution plan with steps
        """
        # Use LLM to generate plan
        config = get_config()
        llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",  # Correct model
            api_key=config.anthropic_api_key,
            temperature=0.3
        )
        
        # Get recent context
        recent_messages = context.get_recent_messages(5)
        context_str = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in recent_messages
        ])
        
        prompt = f"""Based on the user's request and conversation context, create an execution plan.

User request: {user_message}

Recent context:
{context_str}

Create a detailed plan with:
1. Intent: What the user wants to accomplish
2. Steps: List of actions to take (which agent, which tool, what parameters)
3. Estimated time: How long this will take
4. Required information: Any missing details needed

Return a structured plan."""

        response = await llm.ainvoke(prompt)
        
        plan = {
            "id": str(uuid4()),
            "user_request": user_message,
            "steps": self._parse_plan_steps(response.content),
            "estimated_time": "1-2 minutes",
            "created_at": context.updated_at
        }
        
        return plan
    
    def _parse_plan_steps(self, plan_text: str) -> List[Dict[str, Any]]:
        """
        Parse plan steps from LLM response.
        
        Args:
            plan_text: LLM-generated plan text
            
        Returns:
            List of structured plan steps
        """
        # Simplified parsing - in production, use structured output
        steps = []
        lines = plan_text.split("\n")
        
        current_step = None
        for line in lines:
            line = line.strip()
            if line.startswith(("1.", "2.", "3.", "4.", "5.")):
                if current_step:
                    steps.append(current_step)
                current_step = {"description": line, "agent": None, "tool": None}
            elif line.startswith("-") and current_step:
                if "agent:" in line.lower():
                    current_step["agent"] = line.split(":")[-1].strip()
                elif "tool:" in line.lower():
                    current_step["tool"] = line.split(":")[-1].strip()
        
        if current_step:
            steps.append(current_step)
        
        return steps if steps else [{"description": plan_text, "agent": None, "tool": None}]
    
    async def execute_approved_plan(
        self,
        confirmation_id: str,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Execute an approved plan.
        
        Args:
            confirmation_id: Confirmation ID from plan request
            context: Conversation context
            
        Returns:
            Execution result
        """
        plan = context.resolve_confirmation(confirmation_id, approved=True)
        
        if not plan:
            raise AgentError("Plan not found or not approved")
        
        # Execute plan steps
        results = []
        for step in plan.get("steps", []):
            agent_name = step.get("agent")
            tool_name = step.get("tool")
            
            if agent_name == "EmailAgent":
                result = await self.email_agent.execute(step["description"], context)
            elif agent_name == "CalendarAgent":
                result = await self.calendar_agent.execute(step["description"], context)
            elif agent_name == "SheetsAgent":
                result = await self.sheets_agent.execute(step["description"], context)
            else:
                # Use main agent
                result = await self.execute(step["description"], context)
            
            results.append(result)
        
        return {
            "type": "execution_result",
            "plan_id": plan["id"],
            "results": results,
            "status": "completed"
        }
    
    def delegate_to_sub_agent(
        self,
        agent_name: str,
        task: str,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Delegate task to sub-agent.
        
        Args:
            agent_name: Name of sub-agent (EmailAgent, CalendarAgent, SheetsAgent)
            task: Task description
            context: Conversation context
            
        Returns:
            Sub-agent execution result
        """
        if agent_name == "EmailAgent":
            return self.email_agent.execute(task, context)
        elif agent_name == "CalendarAgent":
            return self.calendar_agent.execute(task, context)
        elif agent_name == "SheetsAgent":
            return self.sheets_agent.execute(task, context)
        else:
            raise AgentError(f"Unknown agent: {agent_name}")

