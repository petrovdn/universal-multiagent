"""
Unified ReAct Engine - parameterized ReAct core that works with any ActionProvider.
Supports different modes (query, agent, plan) through configuration.
"""

from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass
import asyncio
import json
import re

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.context_manager import ConversationContext
from src.core.react_state import ReActState, ActionRecord, Observation
from src.core.result_analyzer import ResultAnalyzer, Analysis
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ReActConfig:
    """Configuration for UnifiedReActEngine execution mode."""
    mode: Literal["query", "agent", "plan"]
    allowed_categories: List[CapabilityCategory]
    max_iterations: int = 10
    show_plan_to_user: bool = False
    require_plan_approval: bool = False
    enable_alternatives: bool = True


class UnifiedReActEngine:
    """
    Unified ReAct engine that works with CapabilityRegistry.
    Supports different modes through configuration.
    
    This engine is provider-agnostic - it doesn't know about MCP vs A2A,
    it just works with capabilities from the registry.
    """
    
    def __init__(
        self,
        config: ReActConfig,
        capability_registry: CapabilityRegistry,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize UnifiedReActEngine.
        
        Args:
            config: ReAct configuration
            capability_registry: Capability registry with all providers
            ws_manager: WebSocket manager for events
            session_id: Session identifier
            model_name: Model name for LLM (optional)
        """
        self.config = config
        self.registry = capability_registry
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
        
        # Get allowed capabilities based on config
        self.capabilities = self.registry.get_capabilities(
            categories=config.allowed_categories
        )
        
        # Build LLM tools from capabilities for planning
        self.tools = self._build_tools_from_capabilities()
        
        # Create LLM with thinking support
        self.llm = self._create_llm_with_thinking()
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Result analyzer
        self.result_analyzer = ResultAnalyzer(model_name=model_name)
        
        # Stop flag
        self._stop_requested: bool = False
        
        logger.info(
            f"[UnifiedReActEngine] Initialized for session {session_id} "
            f"with mode={config.mode}, {len(self.capabilities)} capabilities"
        )
    
    def stop(self):
        """Request stop of execution."""
        self._stop_requested = True
        logger.info(f"[UnifiedReActEngine] Stop requested for session {self.session_id}")
    
    def _build_tools_from_capabilities(self) -> List[BaseTool]:
        """
        Build LangChain tools from capabilities for LLM planning.
        
        Returns:
            List of BaseTool objects for LLM
        """
        # For now, we need to get actual BaseTool instances from MCP provider
        # This is a temporary bridge - in future, we might not need this
        tools = []
        
        # Get MCP provider if available
        for provider in self.registry.providers:
            if provider.provider_type.value == "mcp_tool":
                # MCP provider has direct access to BaseTool instances
                if hasattr(provider, 'tools'):
                    tools.extend(provider.tools.values())
                break
        
        logger.info(f"[UnifiedReActEngine] Built {len(tools)} tools for LLM planning")
        return tools
    
    def _create_llm_with_thinking(self, budget_tokens: int = 5000) -> BaseChatModel:
        """Create LLM instance with extended thinking support."""
        from src.utils.config_loader import get_config
        from langchain_anthropic import ChatAnthropic
        
        config_model_name = self.model_name or "claude-sonnet-4-5"
        config = get_config()
        
        try:
            from src.agents.model_factory import get_available_models
            available_models = get_available_models()
            
            if config_model_name in available_models:
                model_config = available_models[config_model_name]
                provider = model_config.get("provider")
                
                if provider == "anthropic" and model_config.get("supports_reasoning"):
                    reasoning_type = model_config.get("reasoning_type")
                    if reasoning_type == "extended_thinking":
                        return ChatAnthropic(
                            model=model_config["model_id"],
                            api_key=config.anthropic_api_key,
                            streaming=True,
                            temperature=1,
                            thinking={
                                "type": "enabled",
                                "budget_tokens": budget_tokens
                            }
                        )
            
            # Fallback
            return create_llm(config_model_name)
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Failed to create LLM: {e}")
            return create_llm(config.default_model)
    
    async def execute(
        self,
        goal: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None,
        phase: Optional[str] = None  # For Plan Mode: "research", "plan", "execute"
    ) -> Dict[str, Any]:
        """
        Execute ReAct cycle for goal.
        
        Args:
            goal: User's goal
            context: Conversation context
            file_ids: Optional list of file IDs
            phase: Optional phase identifier (for Plan Mode)
            
        Returns:
            Execution result
        """
        file_ids = file_ids or []
        
        # Initialize state
        state = ReActState(goal=goal)
        state.context = {
            "file_ids": file_ids,
            "session_id": self.session_id,
            "phase": phase
        }
        self._stop_requested = False
        
        # Send start event
        await self.ws_manager.send_event(
            self.session_id,
            "react_start",
            {"goal": goal, "mode": self.config.mode}
        )
        
        try:
            # Main ReAct loop
            while state.iteration < state.max_iterations:
                if self._stop_requested:
                    logger.info(f"[UnifiedReActEngine] Stop requested at iteration {state.iteration}")
                    break
                
                state.iteration += 1
                logger.info(f"[UnifiedReActEngine] Starting iteration {state.iteration}")
                
                # 1. THINK - Analyze current situation
                state.status = "thinking"
                thought = await self._think(state, context, file_ids)
                state.current_thought = thought
                state.add_reasoning_step("think", thought)
                await self._stream_reasoning("react_thinking", {
                    "thought": thought,
                    "iteration": state.iteration
                })
                
                if self._stop_requested:
                    break
                
                # 2. PLAN - Choose next action
                state.status = "acting"
                action_plan = await self._plan_action(state, thought, context, file_ids)
                
                # Check for special "FINISH" marker
                tool_name = action_plan.get("tool_name", "")
                if tool_name.upper() == "FINISH" or tool_name == "finish":
                    logger.info(f"[UnifiedReActEngine] LLM indicated task completion")
                    state.add_reasoning_step("plan", action_plan.get("reasoning", "Задача выполнена"), {
                        "tool": "FINISH",
                        "marker": True
                    })
                    await self._stream_reasoning("react_action", {
                        "action": action_plan.get("description", "Задача выполнена"),
                        "tool": "FINISH",
                        "params": {},
                        "iteration": state.iteration
                    })
                    return await self._finalize_success(
                        state,
                        action_plan.get("description", "Задача успешно выполнена"),
                        context
                    )
                
                state.add_reasoning_step("plan", action_plan.get("reasoning", ""), {
                    "tool": action_plan.get("tool_name"),
                    "arguments": action_plan.get("arguments", {})
                })
                await self._stream_reasoning("react_action", {
                    "action": action_plan.get("description", ""),
                    "tool": action_plan.get("tool_name"),
                    "params": action_plan.get("arguments", {}),
                    "iteration": state.iteration
                })
                
                if self._stop_requested:
                    break
                
                # 3. ACT - Execute action through registry
                action_record = state.add_action(
                    action_plan.get("tool_name", "unknown"),
                    action_plan.get("arguments", {})
                )
                
                try:
                    result = await self._execute_action(action_plan, context)
                except Exception as e:
                    logger.error(f"[UnifiedReActEngine] Action execution failed: {e}")
                    result = f"Error: {str(e)}"
                
                # 4. OBSERVE - Analyze result
                state.status = "observing"
                observation = state.add_observation(
                    action_record,
                    result,
                    success=True  # Will be updated by analyzer
                )
                
                await self._stream_reasoning("react_observation", {
                    "result": str(result)[:500],
                    "iteration": state.iteration
                })
                
                # Analyze result
                analysis = await self.result_analyzer.analyze(
                    action_record,
                    result,
                    state.goal,
                    state.observations[:-1]
                )
                
                # Update observation with analysis
                observation.success = analysis.is_success
                observation.error_message = analysis.error_message
                observation.extracted_data = analysis.extracted_data
                
                state.add_reasoning_step("observe", f"Analysis: {analysis.progress_toward_goal:.0%} progress", {
                    "success": analysis.is_success,
                    "progress": analysis.progress_toward_goal,
                    "error": analysis.error_message
                })
                
                # 5. ADAPT - Make decision
                state.status = "adapting"
                
                if analysis.is_goal_achieved:
                    logger.info(f"[UnifiedReActEngine] Goal achieved at iteration {state.iteration}")
                    return await self._finalize_success(state, result, context)
                
                elif analysis.is_error:
                    if self.config.enable_alternatives:
                        alternative = await self._find_alternative(state, analysis, context, file_ids)
                        if alternative:
                            logger.info(f"[UnifiedReActEngine] Trying alternative: {alternative.get('description', '')}")
                            state.alternatives_tried.append(alternative.get("description", ""))
                            state.add_reasoning_step("adapt", f"Trying alternative: {alternative.get('description', '')}", {
                                "alternative": alternative
                            })
                            await self._stream_reasoning("react_adapting", {
                                "reason": analysis.error_message or "Action failed",
                                "new_strategy": alternative.get("description", ""),
                                "iteration": state.iteration
                            })
                            # Continue loop with alternative
                        else:
                            logger.warning(f"[UnifiedReActEngine] No alternatives found, failing gracefully")
                            return await self._finalize_failure(state, analysis, context)
                    else:
                        return await self._finalize_failure(state, analysis, context)
                else:
                    # Progress made, continue
                    state.add_reasoning_step("adapt", "Continuing with progress", {
                        "progress": analysis.progress_toward_goal
                    })
                    logger.info(f"[UnifiedReActEngine] Progress: {analysis.progress_toward_goal:.0%}")
            
            # Max iterations reached
            logger.warning(f"[UnifiedReActEngine] Max iterations reached")
            return await self._finalize_timeout(state, context)
            
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in execute: {e}", exc_info=True)
            await self.ws_manager.send_event(
                self.session_id,
                "react_failed",
                {
                    "reason": str(e),
                    "tried": [alt for alt in state.alternatives_tried]
                }
            )
            raise
    
    async def _think(
        self,
        state: ReActState,
        context: ConversationContext,
        file_ids: List[str]
    ) -> str:
        """Generate thought about current situation."""
        context_str = f"Цель: {state.goal}\n\n"
        
        if state.action_history:
            context_str += "Выполненные действия:\n"
            for i, action in enumerate(state.action_history[-5:], 1):
                obs = next((o for o in state.observations if o.action == action), None)
                status = "✓" if obs and obs.success else "✗"
                context_str += f"{i}. {status} {action.tool_name}\n"
        
        if state.observations:
            context_str += "\nПоследние результаты:\n"
            for obs in state.observations[-3:]:
                result_preview = str(obs.raw_result)[:200]
                context_str += f"- {obs.action.tool_name}: {result_preview}...\n"
        
        prompt = f"""Ты выполняешь задачу пошагово, используя доступные инструменты.

{context_str}

Проанализируй текущую ситуацию:
1. Что уже сделано?
2. Что осталось сделать для достижения цели?
3. Какое следующее действие будет наиболее эффективным?

Дай краткий анализ (2-3 предложения) на русском языке."""

        try:
            messages = [
                SystemMessage(content="Ты эксперт по анализу задач и планированию действий. Отвечай кратко и по делу на русском языке."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Handle different response formats
            if isinstance(response.content, list):
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                    elif isinstance(block, str):
                        text_parts.append(block)
                thought = " ".join(text_parts).strip()
            elif isinstance(response.content, str):
                thought = response.content.strip()
            else:
                thought = str(response.content).strip()
            
            return thought
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in _think: {e}")
            return f"Анализирую ситуацию... (итерация {state.iteration})"
    
    async def _plan_action(
        self,
        state: ReActState,
        thought: str,
        context: ConversationContext,
        file_ids: List[str]
    ) -> Dict[str, Any]:
        """Plan next action based on thought."""
        # Get capability descriptions (filtered by allowed categories)
        capability_descriptions = []
        for cap in self.capabilities[:50]:  # Limit to first 50
            capability_descriptions.append(f"- {cap.name}: {cap.description}")
        
        tools_str = "\n".join(capability_descriptions)
        
        # Build context
        context_str = f"Цель: {state.goal}\n\n"
        context_str += f"Текущий анализ: {thought}\n\n"
        
        if state.action_history:
            context_str += "Уже выполнено:\n"
            for action in state.action_history[-3:]:
                context_str += f"- {action.tool_name}\n"
        
        # Add open files context
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            context_str += "\nОткрытые файлы:\n"
            for file in open_files:
                if file.get('type') == 'sheets':
                    context_str += f"- Таблица: {file.get('title')} (ID: {file.get('spreadsheet_id')})\n"
                elif file.get('type') == 'docs':
                    context_str += f"- Документ: {file.get('title')} (ID: {file.get('document_id')})\n"
        
        prompt = f"""Ты планируешь следующее действие для достижения цели.

{context_str}

Доступные инструменты:
{tools_str}

Выбери ОДИН инструмент и укажи параметры для его вызова. Ответь в формате JSON:
{{
    "tool_name": "имя_инструмента",
    "arguments": {{"param1": "value1", "param2": "value2"}},
    "description": "краткое описание действия",
    "reasoning": "почему выбрано это действие"
}}

Если цель полностью достигнута и больше не требуется действий, используй специальный маркер:
{{
    "tool_name": "FINISH",
    "arguments": {{}},
    "description": "краткое описание выполненной задачи",
    "reasoning": "почему задача считается выполненной"
}}

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""

        try:
            messages = [
                SystemMessage(content="Ты эксперт по планированию действий. Отвечай только валидным JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Handle different response formats
            if isinstance(response.content, list):
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                    elif isinstance(block, str):
                        text_parts.append(block)
                response_text = " ".join(text_parts).strip()
            elif isinstance(response.content, str):
                response_text = response.content.strip()
            else:
                response_text = str(response.content).strip()
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                action_plan = json.loads(json_str)
            else:
                action_plan = json.loads(response_text)
            
            # Validate
            if "tool_name" not in action_plan:
                raise ValueError("tool_name missing in action plan")
            
            return action_plan
            
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in _plan_action: {e}")
            # Fallback
            if self.capabilities:
                fallback_cap = self.capabilities[0]
                return {
                    "tool_name": fallback_cap.name,
                    "arguments": {},
                    "description": f"Fallback: использование {fallback_cap.name}",
                    "reasoning": f"Ошибка планирования: {str(e)}. Используется fallback инструмент."
                }
            else:
                return {
                    "tool_name": "error",
                    "arguments": {},
                    "description": "Ошибка планирования: нет доступных инструментов",
                    "reasoning": str(e)
                }
    
    async def _execute_action(
        self,
        action_plan: Dict[str, Any],
        context: ConversationContext
    ) -> Any:
        """Execute action through CapabilityRegistry (provider-agnostic)."""
        capability_name = action_plan.get("tool_name")
        arguments = action_plan.get("arguments", {})
        
        # Registry routes to appropriate provider (MCP or A2A)
        return await self.registry.execute(capability_name, arguments)
    
    async def _find_alternative(
        self,
        state: ReActState,
        analysis: Analysis,
        context: ConversationContext,
        file_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Find alternative action when current one failed."""
        context_str = f"Цель: {state.goal}\n\n"
        context_str += f"Ошибка: {analysis.error_message}\n\n"
        context_str += "Неудачные попытки:\n"
        for action in state.action_history[-3:]:
            context_str += f"- {action.tool_name}\n"
        
        context_str += f"\nИспробованные альтернативы: {', '.join(state.alternatives_tried) if state.alternatives_tried else 'нет'}\n"
        
        # Get capability descriptions
        capability_descriptions = []
        for cap in self.capabilities[:50]:
            capability_descriptions.append(f"- {cap.name}: {cap.description}")
        
        tools_str = "\n".join(capability_descriptions)
        
        prompt = f"""Предыдущее действие не удалось. Найди альтернативный способ достижения цели.

{context_str}

Доступные инструменты:
{tools_str}

Предложи альтернативное действие в формате JSON:
{{
    "tool_name": "имя_инструмента",
    "arguments": {{"param1": "value1"}},
    "description": "описание альтернативного действия",
    "reasoning": "почему это должно сработать"
}}

Если альтернативы нет, верни {{"alternative": false}}.

Отвечай ТОЛЬКО валидным JSON."""

        try:
            messages = [
                SystemMessage(content="Ты эксперт по поиску альтернативных решений. Отвечай только валидным JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Handle different response formats
            if isinstance(response.content, list):
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                    elif isinstance(block, str):
                        text_parts.append(block)
                response_text = " ".join(text_parts).strip()
            elif isinstance(response.content, str):
                response_text = response.content.strip()
            else:
                response_text = str(response.content).strip()
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                alternative = json.loads(json_str)
            else:
                alternative = json.loads(response_text)
            
            # Check if alternative exists
            if alternative.get("alternative") is False:
                return None
            
            if "tool_name" not in alternative:
                return None
            
            return alternative
            
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in _find_alternative: {e}")
            return None
    
    async def _finalize_success(
        self,
        state: ReActState,
        final_result: Any,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Finalize successful execution."""
        state.status = "done"
        
        result_summary = {
            "status": "completed",
            "goal": state.goal,
            "iterations": state.iteration,
            "actions_taken": len(state.action_history),
            "final_result": str(final_result),
            "reasoning_trail": [
                {
                    "iteration": step.iteration,
                    "type": step.step_type,
                    "content": step.content,
                    "metadata": step.metadata
                }
                for step in state.reasoning_trail
            ]
        }
        
        await self.ws_manager.send_event(
            self.session_id,
            "react_complete",
            {
                "result": str(final_result)[:1000],
                "trail": result_summary["reasoning_trail"][-10:]
            }
        )
        
        if hasattr(context, 'add_message'):
            context.add_message("assistant", f"Задача выполнена: {state.goal}")
        
        logger.info(f"[UnifiedReActEngine] Successfully completed in {state.iteration} iterations")
        return result_summary
    
    async def _finalize_failure(
        self,
        state: ReActState,
        analysis: Analysis,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Finalize failed execution with report."""
        state.status = "failed"
        
        failure_report = {
            "status": "failed",
            "goal": state.goal,
            "iterations": state.iteration,
            "actions_taken": len(state.action_history),
            "error": analysis.error_message or "Не удалось достичь цели",
            "alternatives_tried": state.alternatives_tried,
            "reasoning_trail": [
                {
                    "iteration": step.iteration,
                    "type": step.step_type,
                    "content": step.content,
                    "metadata": step.metadata
                }
                for step in state.reasoning_trail
            ]
        }
        
        await self.ws_manager.send_event(
            self.session_id,
            "react_failed",
            {
                "reason": failure_report["error"],
                "tried": state.alternatives_tried
            }
        )
        
        logger.warning(f"[UnifiedReActEngine] Failed after {state.iteration} iterations: {failure_report['error']}")
        return failure_report
    
    async def _finalize_timeout(
        self,
        state: ReActState,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Finalize execution that reached max iterations."""
        state.status = "failed"
        
        timeout_report = {
            "status": "timeout",
            "goal": state.goal,
            "iterations": state.iteration,
            "actions_taken": len(state.action_history),
            "message": f"Достигнут лимит итераций ({state.max_iterations})",
            "reasoning_trail": [
                {
                    "iteration": step.iteration,
                    "type": step.step_type,
                    "content": step.content,
                    "metadata": step.metadata
                }
                for step in state.reasoning_trail
            ]
        }
        
        await self.ws_manager.send_event(
            self.session_id,
            "react_failed",
            {
                "reason": timeout_report["message"],
                "tried": state.alternatives_tried
            }
        )
        
        logger.warning(f"[UnifiedReActEngine] Timeout after {state.iteration} iterations")
        return timeout_report
    
    async def _stream_reasoning(self, event_type: str, data: Dict[str, Any]):
        """Stream reasoning event to WebSocket."""
        try:
            connection_count = self.ws_manager.get_connection_count(self.session_id)
            if connection_count > 0:
                await self.ws_manager.send_event(
                    self.session_id,
                    event_type,
                    data
                )
            else:
                logger.debug(f"[UnifiedReActEngine] Skipping event {event_type} - no WebSocket connection")
        except Exception as e:
            logger.debug(f"[UnifiedReActEngine] Failed to send event {event_type}: {e}")

