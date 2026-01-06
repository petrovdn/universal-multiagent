"""
Mode Adapters for different execution modes (Query, Agent, Plan).
Each adapter configures UnifiedReActEngine for its specific use case.
"""

import asyncio
from typing import Dict, Any, List, Optional
from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.core.context_manager import ConversationContext
from src.api.websocket_manager import WebSocketManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class QueryModeAdapter:
    """
    Query Mode Adapter - read-only mode for data gathering and analysis.
    
    Uses only READ capabilities. Perfect for:
    - Reading files, emails, calendar events
    - Searching data
    - Generating reports from existing data
    - No modifications allowed
    """
    
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize Query Mode Adapter.
        
        Args:
            capability_registry: Capability registry
            ws_manager: WebSocket manager
            session_id: Session identifier
            model_name: Model name for LLM
        """
        self.registry = capability_registry
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
    
    def get_config(self) -> ReActConfig:
        """Get ReAct configuration for Query mode."""
        return ReActConfig(
            mode="query",
            allowed_categories=[CapabilityCategory.READ],
            max_iterations=10,
            show_plan_to_user=False,
            require_plan_approval=False,
            enable_alternatives=True
        )
    
    async def execute(
        self,
        goal: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute query mode - read-only data gathering.
        
        Args:
            goal: User's query/goal
            context: Conversation context
            file_ids: Optional file IDs
            
        Returns:
            Execution result with formatted response
        """
        config = self.get_config()
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=self.registry,
            ws_manager=self.ws_manager,
            session_id=self.session_id,
            model_name=self.model_name
        )
        
        result = await engine.execute(goal, context, file_ids)
        
        # Format result for query mode - emphasize data and insights
        return self._format_query_response(result)
    
    def _format_query_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format result for query mode presentation."""
        return {
            **result,
            "mode": "query",
            "read_only": True
        }


class AgentModeAdapter:
    """
    Agent Mode Adapter - autonomous execution with all capabilities.
    
    Uses both READ and WRITE capabilities. Perfect for:
    - Immediate task execution
    - Creating, updating, deleting resources
    - Multi-step workflows
    - Adaptive problem solving
    """
    
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize Agent Mode Adapter.
        
        Args:
            capability_registry: Capability registry
            ws_manager: WebSocket manager
            session_id: Session identifier
            model_name: Model name for LLM
        """
        self.registry = capability_registry
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
    
    def get_config(self) -> ReActConfig:
        """Get ReAct configuration for Agent mode."""
        return ReActConfig(
            mode="agent",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=15,
            show_plan_to_user=False,
            require_plan_approval=False,
            enable_alternatives=True
        )
    
    async def execute(
        self,
        goal: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute agent mode - autonomous execution with all capabilities.
        
        Args:
            goal: User's goal
            context: Conversation context
            file_ids: Optional file IDs
            
        Returns:
            Execution result
        """
        config = self.get_config()
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=self.registry,
            ws_manager=self.ws_manager,
            session_id=self.session_id,
            model_name=self.model_name
        )
        
        result = await engine.execute(goal, context, file_ids)
        
        return {
            **result,
            "mode": "agent"
        }


class PlanModeAdapter:
    """
    Plan Mode Adapter - phased execution with planning and user approval.
    
    Phase 1 (Research): Read-only exploration
    Phase 2 (Planning): Generate markdown plan
    Phase 3 (User Review): Wait for approval/edit
    Phase 4 (Execution): Execute plan with all capabilities
    
    Perfect for:
    - Complex multi-step tasks
    - Tasks requiring user review
    - Integration projects
    - Code generation with review
    """
    
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize Plan Mode Adapter.
        
        Args:
            capability_registry: Capability registry
            ws_manager: WebSocket manager
            session_id: Session identifier
            model_name: Model name for LLM
        """
        self.registry = capability_registry
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
        
        # State for plan approval
        self._plan_text: Optional[str] = None
        self._plan_steps: List[str] = []
        self._confirmation_id: Optional[str] = None
        self._confirmation_event: Optional[Any] = None
        self._confirmation_result: Optional[bool] = None
    
    async def execute(
        self,
        goal: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute plan mode - phased execution with planning.
        
        Args:
            goal: User's goal
            context: Conversation context
            file_ids: Optional file IDs
            
        Returns:
            Execution result
        """
        # Phase 1: Research (read-only)
        research_result = await self._research_phase(goal, context, file_ids)
        
        # Phase 2: Generate Plan
        plan = await self._generate_plan(goal, research_result, context)
        
        # Phase 3: User Review (wait for approval/edit)
        approved_plan = await self._wait_for_approval(plan, context)
        
        if not approved_plan:
            return {
                "status": "rejected",
                "message": "Plan rejected by user"
            }
        
        # Phase 4: Execute (full ReAct with all tools)
        return await self._execute_phase(approved_plan, context, file_ids)
    
    async def _research_phase(
        self,
        goal: str,
        context: ConversationContext,
        file_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Phase 1: Research existing code/data (read-only)."""
        logger.info(f"[PlanModeAdapter] Starting research phase for: {goal}")
        
        config = ReActConfig(
            mode="plan",
            allowed_categories=[CapabilityCategory.READ],
            max_iterations=5,
            show_plan_to_user=False,
            require_plan_approval=False,
            enable_alternatives=True
        )
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=self.registry,
            ws_manager=self.ws_manager,
            session_id=self.session_id,
            model_name=self.model_name
        )
        
        research_goal = f"Исследуй существующий код и данные для задачи: {goal}"
        result = await engine.execute(research_goal, context, file_ids, phase="research")
        
        logger.info(f"[PlanModeAdapter] Research phase completed")
        return result
    
    async def _generate_plan(
        self,
        goal: str,
        research_result: Dict[str, Any],
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Phase 2: Generate markdown plan based on research."""
        logger.info(f"[PlanModeAdapter] Generating plan for: {goal}")
        
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.agents.model_factory import create_llm
        
        # Use LLM to generate plan
        llm = create_llm(self.model_name or "claude-sonnet-4-5")
        
        research_summary = research_result.get("final_result", "")
        if len(research_summary) > 2000:
            research_summary = research_summary[:2000] + "..."
        
        system_prompt = """Ты эксперт по созданию детальных планов выполнения задач.
Создай структурированный план в формате Markdown.

План должен включать:
1. Обзор задачи
2. Пошаговые этапы выполнения
3. Необходимые ресурсы
4. Потенциальные риски

Используй заголовки, списки и форматирование Markdown для читаемости."""
        
        user_prompt = f"""Задача: {goal}

Результаты исследования:
{research_summary}

Создай детальный план выполнения в формате Markdown."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        plan_text = response.content.strip()
        
        # Extract steps from plan (simple heuristic - can be improved)
        steps = self._extract_steps_from_plan(plan_text)
        
        plan = {
            "plan": plan_text,
            "steps": steps
        }
        
        self._plan_text = plan_text
        self._plan_steps = steps
        
        logger.info(f"[PlanModeAdapter] Generated plan with {len(steps)} steps")
        return plan
    
    def _extract_steps_from_plan(self, plan_text: str) -> List[str]:
        """Extract step titles from markdown plan."""
        import re
        steps = []
        
        # Look for numbered lists or ## headings
        # Pattern: "1. Step title" or "## Step title"
        step_patterns = [
            r'^\d+\.\s+(.+)$',  # Numbered list
            r'^##\s+(.+)$',  # H2 headings
            r'^###\s+(.+)$',  # H3 headings
        ]
        
        for line in plan_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            for pattern in step_patterns:
                match = re.match(pattern, line)
                if match:
                    step_title = match.group(1).strip()
                    if step_title and len(step_title) < 200:  # Reasonable length
                        steps.append(step_title)
                        break
        
        # If no steps found, create default
        if not steps:
            steps = ["Выполнить задачу"]
        
        return steps
    
    async def _wait_for_approval(
        self,
        plan: Dict[str, Any],
        context: ConversationContext
    ) -> Optional[Dict[str, Any]]:
        """Phase 3: Wait for user approval/edit of plan."""
        import uuid
        
        self._confirmation_id = str(uuid.uuid4())
        self._confirmation_event = asyncio.Event()
        
        # Send plan to frontend
        await self.ws_manager.send_event(
            self.session_id,
            "plan_generated",
            {
                "plan": plan["plan"],
                "steps": plan["steps"],
                "confirmation_id": self._confirmation_id
            }
        )
        
        await self.ws_manager.send_event(
            self.session_id,
            "awaiting_confirmation",
            {}
        )
        
        # Store in context
        if hasattr(context, 'add_pending_confirmation'):
            context.add_pending_confirmation(self._confirmation_id, plan)
        
        # Wait for confirmation (will be set by confirm_plan() or reject_plan())
        try:
            await asyncio.wait_for(self._confirmation_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            logger.warning(f"[PlanModeAdapter] Confirmation timeout")
            return None
        
        if not self._confirmation_result:
            return None
        
        # Return approved plan (may have been edited)
        return {
            "plan": self._plan_text,
            "steps": self._plan_steps
        }
    
    def confirm_plan(self, edited_plan: Optional[Dict[str, Any]] = None):
        """Confirm plan (called from AgentWrapper)."""
        if edited_plan:
            self._plan_text = edited_plan.get("plan", self._plan_text)
            self._plan_steps = edited_plan.get("steps", self._plan_steps)
        
        self._confirmation_result = True
        if self._confirmation_event:
            self._confirmation_event.set()
    
    def reject_plan(self):
        """Reject plan (called from AgentWrapper)."""
        self._confirmation_result = False
        if self._confirmation_event:
            self._confirmation_event.set()
    
    def get_confirmation_id(self) -> Optional[str]:
        """Get confirmation ID."""
        return self._confirmation_id
    
    async def _execute_phase(
        self,
        plan: Dict[str, Any],
        context: ConversationContext,
        file_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Phase 4: Execute plan with all capabilities."""
        logger.info(f"[PlanModeAdapter] Starting execution phase")
        
        config = ReActConfig(
            mode="plan",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=20,
            show_plan_to_user=True,
            require_plan_approval=False,
            enable_alternatives=True
        )
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=self.registry,
            ws_manager=self.ws_manager,
            session_id=self.session_id,
            model_name=self.model_name
        )
        
        # Execute with plan context
        goal = f"Выполни план:\n{plan['plan']}"
        result = await engine.execute(goal, context, file_ids, phase="execute")
        
        return {
            **result,
            "mode": "plan",
            "plan": plan["plan"],
            "steps": plan["steps"]
        }

