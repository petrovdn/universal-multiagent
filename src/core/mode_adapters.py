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
        self._active_engine: Optional[UnifiedReActEngine] = None
    
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
        
        # Save reference for stop() method
        self._active_engine = engine
        
        try:
            result = await engine.execute(goal, context, file_ids)
            # Format result for query mode - emphasize data and insights
            return self._format_query_response(result)
        finally:
            # Clear reference after execution
            self._active_engine = None
    
    def _format_query_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format result for query mode presentation."""
        return {
            **result,
            "mode": "query",
            "read_only": True
        }
    
    def stop(self):
        """Stop active engine execution."""
        if self._active_engine:
            self._active_engine.stop()
            logger.info(f"[QueryModeAdapter] Stop requested for session {self.session_id}")


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
        self._active_engine: Optional[UnifiedReActEngine] = None
    
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
        
        # Save reference for stop() method
        self._active_engine = engine
        
        try:
            result = await engine.execute(goal, context, file_ids)
            return {
                **result,
                "mode": "agent"
            }
        finally:
            # Clear reference after execution
            self._active_engine = None
    
    def stop(self):
        """Stop active engine execution."""
        if self._active_engine:
            self._active_engine.stop()
            logger.info(f"[AgentModeAdapter] Stop requested for session {self.session_id}")


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
        self._active_engine: Optional[UnifiedReActEngine] = None
        
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
        logger.info(f"[PlanModeAdapter] execute() called for goal: {goal[:100]}")
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:plan_execute_start",
                    "message": "PlanModeAdapter.execute() called",
                    "data": {
                        "session_id": self.session_id,
                        "goal_length": len(goal) if goal else 0,
                        "goal_preview": goal[:100] if goal else ""
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H3"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        # Phase 1: Research (read-only)
        logger.info(f"[PlanModeAdapter] Starting research phase")
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:before_research_phase",
                    "message": "Before _research_phase()",
                    "data": {
                        "session_id": self.session_id
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H4"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        research_result = await self._research_phase(goal, context, file_ids)
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:after_research_phase",
                    "message": "After _research_phase()",
                    "data": {
                        "session_id": self.session_id,
                        "has_result": bool(research_result.get('final_result')) if research_result else False
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H4"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        logger.info(f"[PlanModeAdapter] Research phase completed: has_result={bool(research_result.get('final_result'))}")
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:before_plan_generation",
                    "message": "Before plan generation",
                    "data": {
                        "session_id": self.session_id,
                        "has_research_result": bool(research_result),
                        "research_result_keys": list(research_result.keys()) if research_result else []
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H8"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")
        # #endregion
        
        # Phase 2: Generate Plan
        logger.info(f"[PlanModeAdapter] Starting plan generation")
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:before_generate_plan_call",
                    "message": "Before _generate_plan() call",
                    "data": {
                        "session_id": self.session_id
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H8"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")
        # #endregion
        
        try:
            plan = await self._generate_plan(goal, research_result, context)
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:after_generate_plan_call",
                        "message": "After _generate_plan() call",
                        "data": {
                            "session_id": self.session_id,
                            "has_plan": bool(plan),
                            "plan_keys": list(plan.keys()) if plan else [],
                            "plan_length": len(plan.get('plan', '')) if plan else 0
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H8"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                logger.error(f"Failed to write debug log: {e}")
            # #endregion
        except Exception as e:
            logger.error(f"[PlanModeAdapter] Error in _generate_plan: {e}", exc_info=True)
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:generate_plan_error",
                        "message": "Error in _generate_plan()",
                        "data": {
                            "session_id": self.session_id,
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H8"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            raise
        logger.info(f"[PlanModeAdapter] Plan generated: has_plan={bool(plan.get('plan'))}, plan_length={len(plan.get('plan', ''))}, steps_count={len(plan.get('steps', []))}")
        
        # Phase 3: User Review (wait for approval/edit)
        logger.info(f"[PlanModeAdapter] Starting wait_for_approval phase")
        approved_plan = await self._wait_for_approval(plan, context)
        logger.info(f"[PlanModeAdapter] Approval phase completed: approved={bool(approved_plan)}")
        
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
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:_research_phase_start",
                    "message": "_research_phase() called",
                    "data": {
                        "session_id": self.session_id,
                        "goal": goal[:100] if goal else ""
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H4"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
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
        
        # Save reference for stop() method
        self._active_engine = engine
        
        try:
            research_goal = f"Исследуй существующий код и данные для задачи: {goal}"
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:before_engine_execute_research",
                        "message": "Before engine.execute() with phase='research'",
                        "data": {
                            "session_id": self.session_id,
                            "research_goal": research_goal[:100]
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H5"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            
            result = await engine.execute(research_goal, context, file_ids, phase="research")
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:after_engine_execute_research",
                        "message": "After engine.execute() with phase='research'",
                        "data": {
                            "session_id": self.session_id,
                            "has_result": bool(result) if result else False
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H5"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            
            logger.info(f"[PlanModeAdapter] Research phase completed")
            return result
        finally:
            # Clear reference after research phase
            self._active_engine = None
    
    async def _generate_plan(
        self,
        goal: str,
        research_result: Dict[str, Any],
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Phase 2: Generate markdown plan based on research."""
        logger.info(f"[PlanModeAdapter] Generating plan for: {goal}")
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:_generate_plan_start",
                    "message": "_generate_plan() called",
                    "data": {
                        "session_id": self.session_id,
                        "goal": goal[:100] if goal else ""
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H8"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")
        # #endregion
        
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.agents.model_factory import create_llm
        
        # Use LLM to generate plan
        llm = create_llm(self.model_name or "claude-sonnet-4-5")
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:_generate_plan_llm_created",
                    "message": "LLM created, preparing messages",
                    "data": {
                        "session_id": self.session_id,
                        "model_name": self.model_name or "claude-sonnet-4-5"
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H8"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        research_summary = research_result.get("final_result", "")
        if len(research_summary) > 2000:
            research_summary = research_summary[:2000] + "..."
        
        system_prompt = """Ты эксперт по созданию детальных планов выполнения задач.
Создай структурированный план в формате Markdown.

План должен включать:
1. Обзор задачи (краткое описание)
2. Пошаговые этапы выполнения (одноуровневый нумерованный список задач)
3. Необходимые ресурсы
4. Потенциальные риски

ВАЖНО: 
- Используй заголовки (##, ###) для разделов
- Для списка задач используй ОДНОУРОВНЕВЫЙ нумерованный список (1., 2., 3., ...) без вложенности
- Каждая задача должна быть на отдельной строке с номером
- Используй форматирование Markdown для читаемости (жирный текст, списки, код)"""
        
        user_prompt = f"""Задача: {goal}

Результаты исследования:
{research_summary}

Создай детальный план выполнения в формате Markdown."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                log_entry = {
                    "location": "mode_adapters.py:_generate_plan_before_llm_invoke",
                    "message": "Before llm.ainvoke()",
                    "data": {
                        "session_id": self.session_id,
                        "messages_count": len(messages),
                        "user_prompt_length": len(user_prompt)
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "hypothesisId": "H8"
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        try:
            response = await llm.ainvoke(messages)
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:_generate_plan_after_llm_invoke",
                        "message": "After llm.ainvoke()",
                        "data": {
                            "session_id": self.session_id,
                            "has_response": bool(response),
                            "response_content_type": type(response.content).__name__ if response and hasattr(response, 'content') else None,
                            "response_content_length": len(response.content) if response and hasattr(response, 'content') else 0
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H8"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            
            # Handle both string and list content (Claude can return list of content blocks)
            content = response.content
            if isinstance(content, list):
                # Extract text from content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, str):
                        text_parts.append(block)
                plan_text = " ".join(text_parts).strip() if text_parts else str(content).strip()
            else:
                plan_text = str(content).strip()
            
            # Extract steps from plan (simple heuristic - can be improved)
            steps = self._extract_steps_from_plan(plan_text)
            
            plan = {
                "plan": plan_text,
                "steps": steps
            }
            
            self._plan_text = plan_text
            self._plan_steps = steps
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:_generate_plan_complete",
                        "message": "_generate_plan() completed",
                        "data": {
                            "session_id": self.session_id,
                            "plan_length": len(plan_text),
                            "steps_count": len(steps)
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H8"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            
            logger.info(f"[PlanModeAdapter] Generated plan with {len(steps)} steps")
            return plan
        except Exception as e:
            logger.error(f"[PlanModeAdapter] Error generating plan: {e}", exc_info=True)
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    log_entry = {
                        "location": "mode_adapters.py:_generate_plan_error",
                        "message": "Error in _generate_plan()",
                        "data": {
                            "session_id": self.session_id,
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "hypothesisId": "H8"
                    }
                    f.write(json.dumps(log_entry) + '\n')
            except Exception:
                pass
            # #endregion
            raise
    
    def _extract_steps_from_plan(self, plan_text: str) -> List[str]:
        """
        Extract step titles from markdown plan.
        Only extracts top-level numbered list items (one-level list).
        """
        import re
        steps = []
        
        # Only match top-level numbered lists (no leading spaces/tabs)
        # Pattern: "1. Step title" at the start of line
        step_pattern = r'^\d+\.\s+(.+)$'
        
        for line in plan_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Match only top-level numbered lists
            match = re.match(step_pattern, line)
            if match:
                step_title = match.group(1).strip()
                # Only add if it's a reasonable length and not empty
                if step_title and len(step_title) < 200:
                    steps.append(step_title)
        
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
        
        logger.info(f"[PlanModeAdapter] _wait_for_approval called, plan keys: {plan.keys()}, plan length: {len(plan.get('plan', ''))}")
        
        self._confirmation_id = str(uuid.uuid4())
        self._confirmation_event = asyncio.Event()
        
        plan_text = plan.get("plan", "")
        plan_steps = plan.get("steps", [])
        
        logger.info(f"[PlanModeAdapter] Sending plan_generated event: session_id={self.session_id}, plan_length={len(plan_text)}, steps_count={len(plan_steps)}, confirmation_id={self._confirmation_id}")
        
        # Send plan to frontend
        await self.ws_manager.send_event(
            self.session_id,
            "plan_generated",
            {
                "plan": plan_text,
                "steps": plan_steps,
                "confirmation_id": self._confirmation_id
            }
        )
        
        logger.info(f"[PlanModeAdapter] plan_generated event sent successfully")
        
        await self.ws_manager.send_event(
            self.session_id,
            "awaiting_confirmation",
            {}
        )
        
        logger.info(f"[PlanModeAdapter] awaiting_confirmation event sent")
        
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
        """
        Confirm plan (called from AgentWrapper).
        If edited_plan is provided, updates plan text and re-extracts steps from it.
        """
        if edited_plan:
            # Update plan text
            self._plan_text = edited_plan.get("plan", self._plan_text)
            # Re-extract steps from plan text (plan might have been edited)
            # This ensures steps always match the current plan content
            self._plan_steps = self._extract_steps_from_plan(self._plan_text)
            logger.info(f"[PlanModeAdapter] Plan confirmed with {len(self._plan_steps)} steps extracted from plan")
        
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
        
        # Save reference for stop() method
        self._active_engine = engine
        
        try:
            # Execute with plan context
            goal = f"Выполни план:\n{plan['plan']}"
            result = await engine.execute(goal, context, file_ids, phase="execute")
            
            return {
                **result,
                "mode": "plan",
                "plan": plan["plan"],
                "steps": plan["steps"]
            }
        finally:
            # Clear reference after execution
            self._active_engine = None
    
    def stop(self):
        """Stop active engine execution."""
        if self._active_engine:
            self._active_engine.stop()
            logger.info(f"[PlanModeAdapter] Stop requested for session {self.session_id}")

