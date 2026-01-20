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
from src.core.guardrails import GuardrailsLoader
from src.utils.config_loader import get_config
from src.utils.exceptions import AgentError


def get_minimal_main_agent_prompt() -> str:
    """
    Минимальный base prompt для MainAgent.
    Вся domain-specific логика в skills.
    """
    return """Ты универсальный AI-ассистент.

## Язык
- Думай и отвечай на русском
- Reasoning на русском

## Принцип работы
1. Следуй <guardrails> (КРИТИЧНЫЙ приоритет)
2. Следуй <skill_instructions> для domain-specific задач
3. Используй релевантные инструменты из <available_tools>
4. Структурируй ответы понятно

## Если нет активного skill
- Анализируй запрос пользователя
- Выбирай подходящие инструменты
- При сомнениях — уточняй у пользователя

Будь полезным, профессиональным и эффективным."""


def _get_default_main_agent_prompt() -> str:
    """
    DEPRECATED: Используй get_minimal_main_agent_prompt() + GuardrailsLoader.
    Оставлено для обратной совместимости.
    """
    return get_minimal_main_agent_prompt()


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
        self.planner = Planner()
        self.model_name = model_name
        
        # Load guardrails
        self._guardrails_loader = GuardrailsLoader()
        
        # Load all tools directly from MCP tools (no sub-agents)
        from src.mcp_tools.calendar_tools import get_calendar_tools
        from src.mcp_tools.gmail_tools import get_gmail_tools
        from src.mcp_tools.sheets_tools import get_sheets_tools
        from src.mcp_tools.workspace_tools import get_workspace_tools
        from src.mcp_tools.onec_tools import get_onec_tools
        from src.mcp_tools.projectlad_tools import get_projectlad_tools
        from src.mcp_tools.code_execution_tools import get_code_execution_tools
        
        all_tools_list = (
            get_calendar_tools() +
            get_gmail_tools() +
            get_sheets_tools() +
            get_workspace_tools() +
            get_onec_tools() +
            get_projectlad_tools() +
            get_code_execution_tools()
        )
        
        # Remove duplicates by tool name (keep first occurrence)
        seen_names = set()
        all_tools = []
        for tool in all_tools_list:
            if tool.name not in seen_names:
                seen_names.add(tool.name)
                all_tools.append(tool)
        
        # Combine guardrails + minimal prompt
        guardrails = self._guardrails_loader.load_guardrails()
        minimal_prompt = get_minimal_main_agent_prompt()
        full_system_prompt = f"{guardrails}\n\n{minimal_prompt}"
        
        super().__init__(
            name="MainAgent",
            system_prompt=full_system_prompt,
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
            
            # All execution goes through main agent (no sub-agents)
            result = await self.execute(step["description"], context)
            
            results.append(result)
        
        return {
            "type": "execution_result",
            "plan_id": plan["id"],
            "results": results,
            "status": "completed"
        }
    
    # delegate_to_sub_agent removed - no sub-agents in new architecture

