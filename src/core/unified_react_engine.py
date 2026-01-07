"""
Unified ReAct Engine - parameterized ReAct core that works with any ActionProvider.
Supports different modes (query, agent, plan) through configuration.
"""

from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass
import asyncio
import json
import re
import time

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.context_manager import ConversationContext
from src.core.react_state import ReActState, ActionRecord, Observation
from src.core.result_analyzer import ResultAnalyzer, Analysis
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm, supports_vision
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
        self._current_thinking_id: Optional[str] = None  # Current thinking block ID
        self._thinking_start_time: Optional[float] = None  # Start time for elapsed calculation
        self._current_intent_id: Optional[str] = None  # Current intent block ID (Cursor-style)
        
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
        
        # Check if query needs tools or can be answered directly (like Cursor does)
        needs_tools = await self._needs_tools(goal, context)
        
        if not needs_tools:
            # Simple query - answer directly without tools
            logger.info(f"[UnifiedReActEngine] Simple query detected, answering directly without tools")
            try:
                return await self._answer_directly(goal, context, state)
            except Exception as e:
                logger.warning(f"[UnifiedReActEngine] Direct answer failed, falling back to ReAct: {e}")
                # Continue with normal ReAct loop if direct answer fails
        
        # Send start event (legacy)
        await self.ws_manager.send_event(
            self.session_id,
            "react_start",
            {"goal": goal, "mode": self.config.mode}
        )
        
        # Send thinking_started event (new Cursor-style)
        self._current_thinking_id = f"thinking-{int(time.time() * 1000)}"
        self._thinking_start_time = time.time()  # Сохраняем время старта
        await self.ws_manager.send_event(
            self.session_id,
            "thinking_started",
            {"thinking_id": self._current_thinking_id, "started_at": int(time.time() * 1000)}
        )
        
        try:
            # Main ReAct loop
            while state.iteration < state.max_iterations:
                if self._stop_requested:
                    logger.info(f"[UnifiedReActEngine] Stop requested at iteration {state.iteration}")
                    break
                
                state.iteration += 1
                logger.info(f"[UnifiedReActEngine] Starting iteration {state.iteration}")
                
                # === EARLY INTENT: Start of iteration ===
                iteration_intent_id = f"intent-iter-{state.iteration}-{int(time.time() * 1000)}"
                files_info = ""
                if file_ids:
                    file_count = len(file_ids)
                    image_count = sum(1 for fid in file_ids if context.get_file(fid) and context.get_file(fid).get('type', '').startswith('image/'))
                    pdf_count = sum(1 for fid in file_ids if context.get_file(fid) and context.get_file(fid).get('type', '') == 'application/pdf')
                    doc_count = sum(1 for fid in file_ids if context.get_file(fid) and context.get_file(fid).get('type', '') in ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'))
                    parts = []
                    if pdf_count: parts.append(f"{pdf_count} PDF")
                    if doc_count: parts.append(f"{doc_count} документ")
                    if image_count: parts.append(f"{image_count} изображение")
                    if parts:
                        files_info = f" ({', '.join(parts)})"
                
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_start",
                    {
                        "intent_id": iteration_intent_id,
                        "text": f"Итерация {state.iteration}: Анализирую запрос{files_info}..."
                    }
                )
                
                # 1. THINK - Analyze current situation
                state.status = "thinking"
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_detail",
                    {"intent_id": iteration_intent_id, "type": "think", "description": "Формирую понимание задачи..."}
                )
                
                # Start progress updates while LLM thinks
                think_progress_messages = [
                    "Изучаю контекст запроса...",
                    "Анализирую структуру задачи...",
                    "Извлекаю ключевую информацию...",
                    "Определяю требуемые действия...",
                ]
                think_progress_task = asyncio.create_task(
                    self._send_progress_updates(iteration_intent_id, think_progress_messages, interval=4.0)
                )
                
                try:
                    thought = await self._think(state, context, file_ids)
                finally:
                    think_progress_task.cancel()
                    try:
                        await think_progress_task
                    except asyncio.CancelledError:
                        pass
                
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
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_detail",
                    {"intent_id": iteration_intent_id, "type": "plan", "description": "Выбираю следующее действие..."}
                )
                
                # Start progress updates while LLM plans
                plan_progress_messages = [
                    "Оцениваю возможные подходы...",
                    "Выбираю оптимальную стратегию...",
                    "Подготавливаю параметры действия...",
                ]
                plan_progress_task = asyncio.create_task(
                    self._send_progress_updates(iteration_intent_id, plan_progress_messages, interval=4.0)
                )
                
                try:
                    action_plan = await self._plan_action(state, thought, context, file_ids)
                finally:
                    plan_progress_task.cancel()
                    try:
                        await plan_progress_task
                    except asyncio.CancelledError:
                        pass
                
                # Complete iteration intent
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_complete",
                    {"intent_id": iteration_intent_id, "summary": f"Итерация {state.iteration} завершена"}
                )
                
                # Check for special "FINISH" marker
                tool_name = action_plan.get("tool_name", "")
                if tool_name.upper() == "FINISH" or tool_name == "finish":
                    logger.info(f"[UnifiedReActEngine] LLM indicated task completion")
                    finish_reasoning = action_plan.get("reasoning", "Задача выполнена")
                    finish_description = action_plan.get("description", "Задача выполнена")
                    state.add_reasoning_step("plan", finish_reasoning, {
                        "tool": "FINISH",
                        "marker": True
                    })
                    await self._stream_reasoning("react_action", {
                        "action": finish_description,
                        "tool": "FINISH",
                        "params": {},
                        "iteration": state.iteration
                    })
                    # Add a synthetic observation with the reasoning for final answer generation
                    finish_action = state.add_action("FINISH", {})
                    state.add_observation(
                        action=finish_action,
                        raw_result=finish_reasoning,
                        success=True
                    )
                    return await self._finalize_success(
                        state,
                        finish_description,
                        context,
                        file_ids
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
                    "result": str(result),  # Full result - no truncation
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
                    return await self._finalize_success(state, result, context, file_ids)
                
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
    
    async def _needs_tools(self, goal: str, context: ConversationContext) -> bool:
        """
        Determine if the query needs tools or can be answered directly.
        
        Simple queries (greetings, simple questions) don't need tools.
        Complex queries (data retrieval, file operations) need tools.
        """
        goal_lower = goal.lower().strip()
        
        # Simple greetings and basic questions - no tools needed
        simple_patterns = [
            r'^(привет|hello|hi|здравствуй|здравствуйте|добрый\s+(день|вечер|утро))',
            r'^(спасибо|thanks|thank\s+you|благодарю)',
            r'^(как\s+дела|how\s+are\s+you|что\s+ты|who\s+are\s+you|что\s+умеешь)',
            r'^(пока|bye|goodbye|до\s+свидания)',
        ]
        
        for pattern in simple_patterns:
            if re.match(pattern, goal_lower):
                return False
        
        # Check if query mentions specific actions that require tools
        tool_keywords = [
            'найди', 'find', 'получи', 'get', 'выведи', 'show', 'открой', 'open',
            'создай', 'create', 'отправь', 'send', 'сохрани', 'save',
            'календарь', 'calendar', 'встречи', 'events', 'meetings',
            'письма', 'emails', 'почта', 'mail',
            'таблица', 'table', 'sheets', 'документ', 'document',
            'файл', 'file', 'данные', 'data'
        ]
        
        for keyword in tool_keywords:
            if keyword in goal_lower:
                return True
        
        # Use LLM to determine if tools are needed (for edge cases)
        try:
            prompt = f"""Определи, нужны ли инструменты (календарь, почта, файлы) для ответа на этот запрос:

Запрос: "{goal}"

Ответь только одним словом: ДА или НЕТ.

ДА - если нужны инструменты (например, "найди встречи", "покажи письма", "открой файл")
НЕТ - если это простой вопрос или приветствие, не требующее инструментов"""
            
            messages = [
                SystemMessage(content="Ты эксперт по определению необходимости использования инструментов. Отвечай только ДА или НЕТ."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = str(response.content).strip().upper()
            
            return "ДА" in response_text or "YES" in response_text
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error checking if tools needed: {e}")
            # Default to using tools if check fails
            return True
    
    async def _answer_directly(
        self,
        goal: str,
        context: ConversationContext,
        state: ReActState
    ) -> Dict[str, Any]:
        """
        Answer simple queries directly without using tools.
        This mimics Cursor's behavior for simple queries.
        """
        try:
            # Build context from conversation history
            context_str = ""
            if hasattr(context, 'messages') and context.messages:
                recent_messages = context.messages[-6:]  # Last 6 messages
                context_str = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    for msg in recent_messages
                    if isinstance(msg, dict)
                ])
            
            prompt = f"""Ты полезный AI-ассистент. Ответь на запрос пользователя естественно и дружелюбно.

{context_str if context_str else ''}

Запрос пользователя: {goal}

Ответь кратко и по делу на русском языке."""
            
            messages = [
                SystemMessage(content="Ты дружелюбный и полезный AI-ассистент. Отвечай естественно и кратко на русском языке."),
                HumanMessage(content=prompt)
            ]
            
            # Send thinking_started event
            self._current_thinking_id = f"thinking-{int(time.time() * 1000)}"
            self._thinking_start_time = time.time()
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_started",
                {"thinking_id": self._current_thinking_id, "started_at": int(time.time() * 1000)}
            )
            
            response = await self.llm.ainvoke(messages)
            
            # Extract response text
            if isinstance(response.content, list):
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                    elif isinstance(block, str):
                        text_parts.append(block)
                answer = " ".join(text_parts).strip()
            elif isinstance(response.content, str):
                answer = response.content.strip()
            else:
                answer = str(response.content).strip()
            
            # Send thinking_completed
            if self._current_thinking_id:
                elapsed_seconds = time.time() - self._thinking_start_time
                await self.ws_manager.send_event(
                    self.session_id,
                    "thinking_completed",
                    {
                        "thinking_id": self._current_thinking_id,
                        "full_content": answer,
                        "elapsed_seconds": elapsed_seconds,
                        "auto_collapse": True
                    }
                )
                self._current_thinking_id = None
                self._thinking_start_time = None
            
            # Send final result or message_complete based on mode
            if self.config.mode == "query":
                await self.ws_manager.send_event(
                    self.session_id,
                    "final_result",
                    {"content": answer}
                )
            else:
                message_id = f"react_{self.session_id}_{int(time.time() * 1000)}"
                await self.ws_manager.send_event(
                    self.session_id,
                    "message_complete",
                    {
                        "role": "assistant",
                        "message_id": message_id,
                        "content": answer
                    }
                )
            
            return {
                "status": "completed",
                "goal": goal,
                "iterations": 1,
                "actions_taken": 0,
                "final_result": answer,
                "reasoning_trail": [
                    {
                        "iteration": 1,
                        "type": "direct_answer",
                        "content": answer,
                        "metadata": {"simple_query": True}
                    }
                ]
            }
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in _answer_directly: {e}")
            # If direct answer fails, raise exception to fall back to normal ReAct loop
            raise
    
    async def _send_progress_updates(
        self,
        intent_id: str,
        messages: List[str],
        interval: float = 4.0
    ) -> None:
        """
        Send progress updates every interval seconds until cancelled.
        
        This runs as a background task to show user that work is happening
        during long LLM operations.
        """
        try:
            for msg in messages:
                await asyncio.sleep(interval)
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_detail",
                    {"intent_id": intent_id, "type": "analyze", "description": msg}
                )
        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass
    
    async def _think(
        self,
        state: ReActState,
        context: ConversationContext,
        file_ids: List[str]
    ) -> str:
        """Generate thought about current situation."""
        context_str = f"Цель: {state.goal}\n\n"
        
        # Add file context (uploaded files have PRIORITY #1)
        if file_ids:
            uploaded_files_found = []
            for file_id in file_ids:
                file_data = context.get_file(file_id)
                if file_data:
                    uploaded_files_found.append(file_data)
            if uploaded_files_found:
                context_str += "📎 Прикрепленные файлы:\n"
                for file_data in uploaded_files_found:
                    filename = file_data.get('filename', 'unknown')
                    file_type = file_data.get('type', '')
                    if file_type == 'application/pdf' and 'text' in file_data:
                        pdf_text = file_data.get('text', '')
                        max_len = 8000  # Increased for better analysis
                        if len(pdf_text) > max_len:
                            pdf_text = pdf_text[:max_len] + "\n... (обрезано, полный текст " + str(len(file_data.get('text', ''))) + " символов)"
                        context_str += f"- PDF: {filename}\n{pdf_text}\n"
                    elif file_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                      "application/msword") and 'text' in file_data:
                        docx_text = file_data.get('text', '')
                        max_len = 8000  # Increased for better analysis
                        if len(docx_text) > max_len:
                            docx_text = docx_text[:max_len] + "\n... (обрезано, полный текст " + str(len(file_data.get('text', ''))) + " символов)"
                        context_str += f"- Word документ: {filename}\n{docx_text}\n"
                    else:
                        context_str += f"- {filename}\n"
        
        # Add open files context (PRIORITY #2)
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            context_str += "📂 Открытые файлы в рабочей области:\n"
            for file in open_files:
                title = file.get('title', 'Без названия')
                context_str += f"- {title}\n"
        
        if state.action_history:
            context_str += "\nВыполненные действия:\n"
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
            
            # Stream thinking process
            thought = ""
            thinking_id = f"thinking_{self.session_id}_{int(time.time() * 1000)}"
            
            # Send thinking start
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_started",
                {"thinking_id": thinking_id}
            )
            
            async for chunk in self.llm.astream(messages):
                chunk_text = ""
                if hasattr(chunk, 'content') and chunk.content:
                    if isinstance(chunk.content, list):
                        for block in chunk.content:
                            if hasattr(block, "text"):
                                chunk_text += block.text
                            elif isinstance(block, dict) and "text" in block:
                                chunk_text += block["text"]
                            elif isinstance(block, str):
                                chunk_text += block
                    elif isinstance(chunk.content, str):
                        chunk_text = chunk.content
                elif isinstance(chunk, str):
                    chunk_text = chunk
                
                if chunk_text:
                    thought += chunk_text
                    await self.ws_manager.send_event(
                        self.session_id,
                        "thinking_chunk",
                        {
                            "thinking_id": thinking_id,
                            "chunk": chunk_text  # Frontend expects "chunk" not "content"
                        }
                    )
            
            # Complete thinking
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_completed",
                {"thinking_id": thinking_id}
            )
            
            return thought.strip()
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
        
        # Add uploaded files context (PRIORITY #1) - must come FIRST
        if file_ids:
            uploaded_files_found = []
            for file_id in file_ids:
                file_data = context.get_file(file_id)
                if file_data:
                    uploaded_files_found.append(file_data)
            
            if uploaded_files_found:
                # Проверяем поддержку vision у модели
                model_supports_vision = supports_vision(self.model_name) if self.model_name else False
                
                context_str += "\n📎 ПРИКРЕПЛЕННЫЕ ФАЙЛЫ (ПРИОРИТЕТ #1 - используй их ПЕРВЫМ!):\n"
                has_images = False
                for file_data in uploaded_files_found:
                    filename = file_data.get('filename', 'unknown')
                    file_type = file_data.get('type', '')
                    if file_type.startswith('image/'):
                        has_images = True
                        if model_supports_vision:
                            context_str += f"- Изображение: {filename} (УЖЕ ПЕРЕДАНО В ЭТОМ СООБЩЕНИИ через Vision API - видишь его прямо сейчас!)\n"
                        else:
                            context_str += f"- Изображение: {filename} (модель не поддерживает vision, пропущено)\n"
                            logger.warning(f"Model {self.model_name} doesn't support vision, skipping image {filename}")
                    elif file_type == 'application/pdf' and 'text' in file_data:
                        pdf_text = file_data.get('text', '')
                        # Truncate if too long - increased limit for better analysis
                        max_len = 10000
                        if len(pdf_text) > max_len:
                            pdf_text = pdf_text[:max_len] + "\n... (текст обрезан, полный размер " + str(len(file_data.get('text', ''))) + " символов)"
                        context_str += f"- PDF: {filename}\n--- СОДЕРЖИМОЕ PDF ---\n{pdf_text}\n--- КОНЕЦ PDF ---\n"
                    elif file_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                      "application/msword") and 'text' in file_data:
                        docx_text = file_data.get('text', '')
                        # Truncate if too long - increased limit for better analysis
                        max_len = 10000
                        if len(docx_text) > max_len:
                            docx_text = docx_text[:max_len] + "\n... (текст обрезан, полный размер " + str(len(file_data.get('text', ''))) + " символов)"
                        context_str += f"- Word документ: {filename}\n--- СОДЕРЖИМОЕ DOCX ---\n{docx_text}\n--- КОНЕЦ DOCX ---\n"
                    else:
                        context_str += f"- {filename} ({file_type})\n"
                
                if has_images and model_supports_vision:
                    context_str += "\n⚠️ КРИТИЧНО: Изображения УЖЕ ПЕРЕДАНЫ в этом сообщении через Vision API! Ты видишь их прямо сейчас! НЕ используй инструменты для их анализа - просто опиши что видишь на изображениях!\n"
                else:
                    context_str += "⚠️ НЕ ищи эти файлы в Google Drive - их содержимое УЖЕ ВЫШЕ!\n"
        
        # Add open files context (PRIORITY #2)
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            context_str += "\n📂 Открытые файлы в рабочей области (ПРИОРИТЕТ #2):\n"
            for file in open_files:
                if file.get('type') == 'sheets':
                    context_str += f"- Таблица: {file.get('title')} (ID: {file.get('spreadsheet_id')})\n"
                elif file.get('type') == 'docs':
                    context_str += f"- Документ: {file.get('title')} (ID: {file.get('document_id')})\n"
            context_str += "⚠️ Используй document_id/spreadsheet_id напрямую, НЕ ищи через search!\n"
        
        prompt = f"""Ты планируешь следующее действие для достижения цели.

{context_str}

Доступные инструменты:
{tools_str}

ВАЖНО:
- Если получен результат с количеством событий/данных, но БЕЗ деталей (например, "Found 10 events" без списка), 
  это означает, что нужно получить ДЕТАЛИ этих данных
- НЕ завершай задачу, пока не получены все необходимые детали для ответа пользователю
- Для календаря: если получено только количество событий, нужно получить детали каждого события
- Для файлов: если получен список файлов, но нужно содержимое - получи содержимое
- Для писем: если получен список писем, но нужно содержимое - получи содержимое

КРИТИЧНО ДЛЯ ПРИКРЕПЛЕННЫХ ФАЙЛОВ:
- Если в прикрепленных файлах есть ИЗОБРАЖЕНИЯ - они УЖЕ ПЕРЕДАНЫ в этом сообщении через Vision API! 
  Ты видишь их прямо сейчас! НЕ используй инструменты типа "vision-api" или "analyze_image" - просто опиши что видишь!
- Если в прикрепленных файлах есть PDF или DOCX - их ТЕКСТ УЖЕ ПРЕДСТАВЛЕН ВЫШЕ в контексте!
- Если пользователь спрашивает "что в файле" или "что в файлах" и содержимое файлов УЖЕ ВИДНО (текст PDF/DOCX в контексте выше, изображение через Vision API), 
  то задача УЖЕ ВЫПОЛНЕНА - используй FINISH и опиши содержимое файлов в ответе!
- НЕ ищи файлы в Google Drive или рабочей области, если они уже прикреплены и их содержимое уже видно!

Выбери ОДИН инструмент и укажи параметры для его вызова. Ответь в формате JSON:
{{
    "tool_name": "имя_инструмента",
    "arguments": {{"param1": "value1", "param2": "value2"}},
    "description": "краткое описание действия",
    "reasoning": "почему выбрано это действие"
}}

Если цель полностью достигнута и получены ВСЕ необходимые детали для полного ответа пользователю, используй специальный маркер:
{{
    "tool_name": "FINISH",
    "arguments": {{}},
    "description": "краткое описание выполненной задачи",
    "reasoning": "почему задача считается выполненной (укажи, какие данные получены)"
}}

ОСОБЕННО: Если пользователь спрашивает о содержимом прикрепленных файлов, и содержимое УЖЕ ВИДНО (текст PDF/DOCX в контексте выше, изображение через Vision API), 
используй FINISH немедленно - не ищи файлы в других местах!

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""

        try:
            # Проверяем поддержку vision и собираем изображения
            model_supports_vision = supports_vision(self.model_name) if self.model_name else False
            image_contents = []
            
            if file_ids and model_supports_vision:
                for file_id in file_ids:
                    file_data = context.get_file(file_id)
                    if file_data:
                        file_type = file_data.get('type', '')
                        if file_type.startswith('image/'):
                            media_type = file_data.get('media_type', file_type)
                            base64_data = file_data.get('data', '')
                            if base64_data:
                                image_contents.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{base64_data}"
                                    }
                                })
            
            # Формируем сообщение
            if image_contents:
                # Multimodal сообщение с изображениями
                message_content = [{"type": "text", "text": prompt}] + image_contents
                messages = [
                    SystemMessage(content="Ты эксперт по планированию действий. Отвечай только валидным JSON."),
                    HumanMessage(content=message_content)
                ]
            else:
                # Обычное текстовое сообщение
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
    
    async def _generate_final_answer(self, state: ReActState, context: Optional[ConversationContext] = None, file_ids: Optional[List[str]] = None) -> str:
        """Generate a human-friendly final answer based on all collected results with streaming."""
        try:
            # Collect all observations/results
            observations_text = ""
            for obs in state.observations:
                if obs.raw_result:
                    observations_text += f"- {obs.action.tool_name}: {str(obs.raw_result)[:1500]}\n"
            
            # If no observations but we have FINISH reasoning, use it
            if not observations_text:
                # Check for FINISH marker in reasoning trail
                for step in reversed(state.reasoning_trail):
                    if step.metadata and step.metadata.get("tool") == "FINISH":
                        # Use the reasoning from FINISH step
                        observations_text = step.content
                        break
            
            if not observations_text:
                observations_text = "Нет результатов от инструментов."
            
            # Build file contents for FINISH cases
            file_contents_text = ""
            if file_ids and context:
                for file_id in file_ids:
                    file_data = context.get_file(file_id)
                    if file_data:
                        filename = file_data.get('filename', 'unknown')
                        file_type = file_data.get('type', '')
                        full_text = file_data.get('text', '')
                        # Use larger limit for final answer - user wants detailed description
                        max_len = 15000
                        if file_type == 'application/pdf' and 'text' in file_data:
                            pdf_text = full_text[:max_len] if len(full_text) > max_len else full_text
                            truncation_note = f"\n... (показано {max_len} из {len(full_text)} символов)" if len(full_text) > max_len else ""
                            file_contents_text += f"\n📄 PDF '{filename}':\n{pdf_text}{truncation_note}\n"
                        elif file_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                          "application/msword") and 'text' in file_data:
                            docx_text = full_text[:max_len] if len(full_text) > max_len else full_text
                            truncation_note = f"\n... (показано {max_len} из {len(full_text)} символов)" if len(full_text) > max_len else ""
                            file_contents_text += f"\n📄 Word '{filename}':\n{docx_text}{truncation_note}\n"
                        elif file_type.startswith('image/'):
                            file_contents_text += f"\n🖼️ Изображение '{filename}': (передано через Vision API - опиши что видишь)\n"
            
            # Check if user asked for a table
            goal_lower = state.goal.lower()
            wants_table = any(word in goal_lower for word in ['табличк', 'таблиц', 'table'])
            
            if wants_table:
                table_instruction = """
ФОРМАТ ОТВЕТА:
Выведи данные в виде MARKDOWN ТАБЛИЦЫ. Пример:
| Название | Дата | Время |
|----------|------|-------|
| Встреча 1 | 2025-12-25 | 10:00 |

После таблицы добавь примечание:
"💡 Если нужно создать Google таблицу с этими данными, переключитесь в режим **Агент**."
"""
            else:
                table_instruction = ""
            
            # Check if this is a FINISH case (reasoning contains file analysis)
            is_finish_case = any(
                step.metadata and step.metadata.get("tool") == "FINISH"
                for step in state.reasoning_trail
            )
            
            if is_finish_case and file_contents_text:
                # For FINISH with file content, include actual file contents in prompt
                prompt = f"""Пользователь спросил: "{state.goal}"

Вот содержимое прикрепленных файлов:
{file_contents_text}

{table_instruction}
ВАЖНО: Опиши КОНКРЕТНО что находится в файлах. Например:
- Для PDF: "В файле находится чек на оплату налогов на сумму X руб. от даты Y..."
- Для изображения: "На изображении показан человек, играющий в теннис..."
НЕ говори абстрактно "файл содержит текстовую информацию". Будь КОНКРЕТНЫМ!

Ответ:"""
            elif is_finish_case:
                # FINISH case without file contents - use reasoning
                prompt = f"""Пользователь спросил: "{state.goal}"

Анализ:
{observations_text}

{table_instruction}
Сформулируй понятный ответ на русском языке, описывая что находится в файле/файлах. Будь конкретным и информативным.

Ответ:"""
            else:
                prompt = f"""Вопрос пользователя: "{state.goal}"

Результаты поиска:
{observations_text}

ВАЖНО: Внимательно проанализируй результаты выше. Если там есть данные (events, messages, files и т.д.) - значит они НАЙДЕНЫ.
{table_instruction}
Сформулируй ответ на русском языке:
- Если найдены данные - перечисли их кратко и понятно
- Если данные пустые (пустой массив [], "Found 0") - скажи что ничего не найдено
- НЕ говори что данных нет, если в результатах есть записи!

Ответ:"""

            # Build multimodal message with images if available
            image_contents = []
            model_supports_vision = supports_vision(self.model_name) if self.model_name else False
            
            if file_ids and context and model_supports_vision:
                for file_id in file_ids:
                    file_data = context.get_file(file_id)
                    if file_data:
                        file_type = file_data.get('type', '')
                        if file_type.startswith('image/'):
                            media_type = file_data.get('media_type', file_type)
                            base64_data = file_data.get('data', '')
                            if base64_data:
                                image_contents.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{base64_data}"
                                    }
                                })
            
            # Create message (multimodal if images present)
            if image_contents:
                message_content = [{"type": "text", "text": prompt}] + image_contents
                messages = [HumanMessage(content=message_content)]
            else:
                messages = [HumanMessage(content=prompt)]

            # Stream the response
            full_answer = ""
            
            # Send intent event to show user what's happening
            intent_message = "Анализирую содержимое файлов" if file_contents_text else "Формирую ответ"
            if len(image_contents) > 0:
                intent_message += f" (включая {len(image_contents)} изображение(я))..."
            else:
                intent_message += "..."
            
            intent_id = f"intent-final-{int(time.time() * 1000)}"
            await self.ws_manager.send_event(
                self.session_id,
                "intent_start",
                {"intent_id": intent_id, "text": intent_message}  # Fixed: use 'text' not 'intent'
            )
            
            # Send details about each file being analyzed
            if file_ids and context:
                for i, file_id in enumerate(file_ids):
                    file_data = context.get_file(file_id)
                    if file_data:
                        filename = file_data.get('filename', 'unknown')
                        file_type = file_data.get('type', '')
                        detail_type = 'read'
                        if file_type.startswith('image/'):
                            detail_desc = f"Анализирую изображение: {filename}"
                        elif 'pdf' in file_type:
                            detail_desc = f"Читаю PDF: {filename}"
                        elif 'word' in file_type or 'document' in file_type:
                            detail_desc = f"Читаю документ: {filename}"
                        else:
                            detail_desc = f"Обрабатываю файл: {filename}"
                        
                        await self.ws_manager.send_event(
                            self.session_id,
                            "intent_detail",
                            {
                                "intent_id": intent_id,
                                "type": detail_type,
                                "description": detail_desc
                            }
                        )
            
            # Send start event
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_start",
                {}
            )
            
            # Stream chunks
            async for chunk in self.llm.astream(messages):
                chunk_text = ""
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                    # Handle multimodal response where content is a list
                    if isinstance(content, list):
                        for block in content:
                            if hasattr(block, 'text'):
                                chunk_text += block.text
                            elif isinstance(block, dict) and 'text' in block:
                                chunk_text += block['text']
                            elif isinstance(block, str):
                                chunk_text += block
                    elif isinstance(content, str):
                        chunk_text = content
                elif isinstance(chunk, str):
                    chunk_text = chunk
                
                if chunk_text:
                    full_answer += chunk_text
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_chunk",
                        {"content": full_answer}  # Send accumulated content
                    )
            
            # Send intent completion
            await self.ws_manager.send_event(
                self.session_id,
                "intent_complete",
                {"intent_id": intent_id, "summary": "Анализ завершён"}
            )
            
            # Send completion event
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_complete",
                {"content": full_answer.strip()}
            )
            
            return full_answer.strip()
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error generating final answer: {e}")
            # Fallback to last result
            if state.observations:
                last_result = str(state.observations[-1].raw_result)
                return self._format_result_summary(last_result, state.observations[-1].action.tool_name)
            return "Задача выполнена."

    async def _finalize_success(
        self,
        state: ReActState,
        final_result: Any,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Finalize successful execution."""
        state.status = "done"
        
        # Generate human-friendly final answer instead of raw result
        human_answer = await self._generate_final_answer(state, context, file_ids)
        
        result_summary = {
            "status": "completed",
            "goal": state.goal,
            "iterations": state.iteration,
            "actions_taken": len(state.action_history),
            "final_result": human_answer,
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
        
        # Send thinking_completed event FIRST (before final_result to stop animations)
        if self._current_thinking_id and self._thinking_start_time:
            elapsed_seconds = time.time() - self._thinking_start_time
            # Собираем весь контент из reasoning trail
            full_content = "\n".join([step.content for step in state.reasoning_trail])
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_completed",
                {
                    "thinking_id": self._current_thinking_id,
                    "full_content": full_content,
                    "elapsed_seconds": elapsed_seconds,
                    "auto_collapse": True
                }
            )
            self._current_thinking_id = None
            self._thinking_start_time = None
        
        # Send react_complete event
        await self.ws_manager.send_event(
            self.session_id,
            "react_complete",
            {
                "result": human_answer[:1000],
                "trail": result_summary["reasoning_trail"][-10:]
            }
        )
        
        # Send final_result or message_complete event based on mode
        # NOTE: final_result_start, final_result_chunk, final_result_complete are already sent by _generate_final_answer
        # So we only send final_result here as a final confirmation (or skip if already sent)
        if self.config.mode == "query":
            # For query mode, send workflow_stopped to indicate completion (stops animations)
            await self.ws_manager.send_event(
                self.session_id,
                "workflow_stopped",
                {
                    "reason": "Задача выполнена"
                }
            )
        else:
            # For agent and plan modes, send message_complete to ensure response is displayed
            message_id = f"react_{self.session_id}_{int(time.time() * 1000)}"
            await self.ws_manager.send_event(
                self.session_id,
                "message_complete",
                {
                    "role": "assistant",
                    "message_id": message_id,
                    "content": human_answer
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
        
        # Send message_complete with error message for agent/plan modes
        if self.config.mode != "query":
            error_message = f"❌ Не удалось выполнить задачу: {failure_report['error']}"
            message_id = f"react_{self.session_id}_{int(time.time() * 1000)}"
            await self.ws_manager.send_event(
                self.session_id,
                "message_complete",
                {
                    "role": "assistant",
                    "message_id": message_id,
                    "content": error_message
                }
            )
        
        # Send thinking_completed event (with error, не сворачиваем)
        if self._current_thinking_id and self._thinking_start_time:
            elapsed_seconds = time.time() - self._thinking_start_time
            full_content = "\n".join([step.content for step in state.reasoning_trail])
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_completed",
                {
                    "thinking_id": self._current_thinking_id,
                    "full_content": full_content,
                    "elapsed_seconds": elapsed_seconds,
                    "auto_collapse": False  # Не сворачиваем при ошибке
                }
            )
            self._current_thinking_id = None
            self._thinking_start_time = None
        
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
        
        # Send timeout message based on mode
        timeout_message = f"⏱️ {timeout_report['message']}. Попробуйте уточнить запрос или разбить задачу на более мелкие шаги."
        
        if self.config.mode == "query":
            # For Query mode, send final_result event
            await self.ws_manager.send_event(
                self.session_id,
                "final_result",
                {
                    "content": timeout_message
                }
            )
        else:
            # For agent and plan modes, send message_complete
            message_id = f"react_{self.session_id}_{int(time.time() * 1000)}"
            await self.ws_manager.send_event(
                self.session_id,
                "message_complete",
                {
                    "role": "assistant",
                    "message_id": message_id,
                    "content": timeout_message
                }
            )
        
        # Send thinking_completed event (timeout)
        if self._current_thinking_id and self._thinking_start_time:
            elapsed_seconds = time.time() - self._thinking_start_time
            full_content = "\n".join([step.content for step in state.reasoning_trail])
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_completed",
                {
                    "thinking_id": self._current_thinking_id,
                    "full_content": full_content,
                    "elapsed_seconds": elapsed_seconds,
                    "auto_collapse": False
                }
            )
            self._current_thinking_id = None
            self._thinking_start_time = None
        
        logger.warning(f"[UnifiedReActEngine] Timeout after {state.iteration} iterations")
        return timeout_report
    
    def _transform_to_human_readable(self, action: str, tool_name: str) -> str:
        """Transform technical messages to human-readable format."""
        action_lower = action.lower()
        tool_lower = tool_name.lower()
        
        # Если уже human-readable, возвращаем как есть
        if not action_lower.startswith(('fallback:', 'error:', 'использование')):
            return action
        
        # Маппинг tool names на human-readable описания
        if 'calendar' in tool_lower or 'event' in tool_lower:
            return "📅 Получаю события календаря..."
        elif 'email' in tool_lower or 'gmail' in tool_lower or 'mail' in tool_lower:
            return "📧 Ищу в почте..."
        elif 'file' in tool_lower or 'workspace' in tool_lower or 'drive' in tool_lower:
            return "📁 Ищу файлы..."
        elif 'search' in tool_lower:
            return "🔍 Ищу информацию..."
        elif 'create' in tool_lower or 'write' in tool_lower:
            return "✏️ Создаю документ..."
        elif 'read' in tool_lower or 'get' in tool_lower:
            return "📖 Читаю информацию..."
        else:
            return "🔧 Выполняю действие..."
    
    def _get_detail_type(self, tool_name: str) -> str:
        """Map tool name to intent detail type."""
        tool_lower = tool_name.lower()
        if 'search' in tool_lower or 'find' in tool_lower:
            return 'search'
        elif 'read' in tool_lower or 'get' in tool_lower or 'list' in tool_lower or 'fetch' in tool_lower:
            return 'read'
        elif 'create' in tool_lower or 'write' in tool_lower or 'send' in tool_lower or 'update' in tool_lower:
            return 'write'
        else:
            return 'execute'
    
    def _extract_result_details(self, result: str) -> List[str]:
        """Extract meaningful details from result for display in intent block."""
        details = []
        try:
            import json
            import re
            logger.debug(f"[_extract_result_details] Parsing result: {result[:200]}...")
            
            # Try to parse as JSON
            data = None
            if result.strip().startswith('{') or result.strip().startswith('['):
                try:
                    data = json.loads(result)
                except json.JSONDecodeError:
                    pass
            
            if isinstance(data, list):
                # List of items (events, messages, files)
                logger.debug(f"[_extract_result_details] Found list with {len(data)} items")
                for item in data[:10]:  # Max 10 items
                    if isinstance(item, dict):
                        name = item.get('summary') or item.get('title') or item.get('subject') or item.get('name') or item.get('filename')
                        start = item.get('start', {})
                        time_str = ""
                        if isinstance(start, dict):
                            time_str = start.get('dateTime', start.get('date', ''))[:16].replace('T', ' ')
                        elif isinstance(start, str):
                            time_str = start[:16].replace('T', ' ')
                        if name:
                            if time_str:
                                details.append(f"📅 {name} - {time_str}")
                            else:
                                details.append(f"• {name}")
            elif isinstance(data, dict):
                logger.debug(f"[_extract_result_details] Found dict with keys: {list(data.keys())[:10]}")
                if 'events' in data:
                    for event in data['events'][:10]:
                        name = event.get('summary') or event.get('title')
                        start = event.get('start', {})
                        time_str = ""
                        if isinstance(start, dict):
                            time_str = start.get('dateTime', start.get('date', ''))[:16].replace('T', ' ')
                        if name:
                            details.append(f"📅 {name} - {time_str}" if time_str else f"📅 {name}")
                elif 'messages' in data:
                    for msg in data['messages'][:10]:
                        subject = msg.get('subject') or msg.get('snippet', '')[:50]
                        if subject:
                            details.append(f"📧 {subject}")
                elif 'files' in data:
                    for f in data['files'][:10]:
                        name = f.get('name') or f.get('title')
                        if name:
                            details.append(f"📄 {name}")
                else:
                    name = data.get('summary') or data.get('title') or data.get('subject')
                    if name:
                        details.append(f"• {name}")
            
            # If no structured data found, check for "Found N event(s)" pattern - parse calendar format
            if not details and 'Found' in result and 'event' in result.lower():
                lines = result.split('\n')
                current_event_name = None
                current_event_time = None
                
                for line in lines:
                    line = line.strip()
                    # Match event number and name: "1. проверка 1"
                    event_match = re.match(r'^(\d+)\.\s*(.+)$', line)
                    if event_match:
                        # Save previous event if exists
                        if current_event_name:
                            if current_event_time:
                                details.append(f"📅 {current_event_name} - {current_event_time}")
                            else:
                                details.append(f"📅 {current_event_name}")
                        current_event_name = event_match.group(2).strip()
                        current_event_time = None
                    # Match time line: "Время: 2025-12-25 05:00 - 2025-12-25 06:00"
                    elif line.startswith('Время:') or line.startswith('Time:'):
                        time_part = line.split(':', 1)[1].strip()
                        # Extract just date and start time
                        time_match = re.match(r'(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})?', time_part)
                        if time_match:
                            current_event_time = f"{time_match.group(1)} {time_match.group(2) or ''}".strip()
                    
                    if len(details) >= 10:
                        break
                
                # Don't forget the last event
                if current_event_name and len(details) < 10:
                    if current_event_time:
                        details.append(f"📅 {current_event_name} - {current_event_time}")
                    else:
                        details.append(f"📅 {current_event_name}")
                        
        except Exception as e:
            logger.error(f"[_extract_result_details] Error: {e}")
            lines = result.split('\n')
            for line in lines[:5]:
                line = line.strip()
                if line and len(line) > 3 and not line.startswith('{'):
                    details.append(f"• {line[:100]}")
        
        logger.debug(f"[_extract_result_details] Extracted {len(details)} details: {details}")
        return details

    def _format_result_summary(self, result: str, tool: str) -> str:
        """Format raw tool result into human-readable Russian summary."""
        import re
        result_lower = result.lower()
        tool_lower = tool.lower() if tool else ""
        
        # Extract count from common patterns like "Found 5 events", "Found 0 messages"
        count_match = re.search(r'found\s+(\d+)\s+(\w+)', result_lower)
        if count_match:
            count = int(count_match.group(1))
            item_type = count_match.group(2)
            
            # Map item types to Russian with proper pluralization
            def pluralize_ru(n: int, one: str, few: str, many: str) -> str:
                mod10 = n % 10
                mod100 = n % 100
                if mod100 >= 11 and mod100 <= 14:
                    return many
                if mod10 == 1:
                    return one
                if mod10 >= 2 and mod10 <= 4:
                    return few
                return many
            
            if 'event' in item_type or 'calendar' in item_type or 'встреч' in tool_lower:
                word = pluralize_ru(count, 'встреча', 'встречи', 'встреч')
                return f"Найдено {count} {word}" if count > 0 else "Встреч не найдено"
            elif 'message' in item_type or 'mail' in item_type or 'email' in item_type or 'письм' in tool_lower:
                word = pluralize_ru(count, 'письмо', 'письма', 'писем')
                return f"Найдено {count} {word}" if count > 0 else "Писем не найдено"
            elif 'file' in item_type or 'document' in item_type or 'doc' in item_type or 'файл' in tool_lower:
                word = pluralize_ru(count, 'файл', 'файла', 'файлов')
                return f"Найдено {count} {word}" if count > 0 else "Файлов не найдено"
            elif 'contact' in item_type or 'контакт' in tool_lower:
                word = pluralize_ru(count, 'контакт', 'контакта', 'контактов')
                return f"Найдено {count} {word}" if count > 0 else "Контактов не найдено"
            elif 'task' in item_type or 'задач' in tool_lower:
                word = pluralize_ru(count, 'задача', 'задачи', 'задач')
                return f"Найдено {count} {word}" if count > 0 else "Задач не найдено"
            else:
                word = pluralize_ru(count, 'результат', 'результата', 'результатов')
                return f"Найдено {count} {word}" if count > 0 else "Ничего не найдено"
        
        # Handle success/error patterns
        if 'success' in result_lower or 'successfully' in result_lower:
            return "✓ Выполнено успешно"
        if 'error' in result_lower or 'failed' in result_lower:
            return "✗ Ошибка выполнения"
        if 'created' in result_lower:
            return "✓ Создано"
        if 'sent' in result_lower:
            return "✓ Отправлено"
        if 'updated' in result_lower:
            return "✓ Обновлено"
        if 'deleted' in result_lower:
            return "✓ Удалено"
        
        # Default: truncate result
        if len(result) > 50:
            return result[:47] + "..."
        return result if result else "Выполнено"

    async def _stream_reasoning(self, event_type: str, data: Dict[str, Any]):
        """Stream reasoning event to WebSocket - Cursor-style intent blocks only."""
        try:
            connection_count = self.ws_manager.get_connection_count(self.session_id)
            if connection_count > 0:
                # Only send intent events (Cursor-style) - no legacy events
                if event_type == "react_thinking":
                    # Don't start intent on thinking - wait for action
                    pass
                
                elif event_type == "react_action":
                    # Start NEW intent with action description
                    tool = data.get("tool", "unknown")
                    action = data.get("action", "")
                    
                    # Save tool for later use in observation
                    self._last_tool = tool
                    
                    # Create human-readable description for the intent
                    description = self._transform_to_human_readable(action, tool)
                    
                    # Start new intent for this action
                    self._current_intent_id = f"intent-{int(time.time() * 1000)}"
                    await self.ws_manager.send_event(
                        self.session_id,
                        "intent_start",
                        {
                            "intent_id": self._current_intent_id,
                            "text": description
                        }
                    )
                
                elif event_type == "react_observation":
                    # Add result details and complete the intent
                    if hasattr(self, '_current_intent_id') and self._current_intent_id:
                        result = str(data.get("result", ""))
                        tool = getattr(self, '_last_tool', 'unknown')
                        
                        # Format result into human-readable Russian summary
                        summary = self._format_result_summary(result, tool)
                        
                        # Extract and send result details (e.g., meeting names, file names)
                        details = self._extract_result_details(result)
                        for detail in details:
                            await self.ws_manager.send_event(
                                self.session_id,
                                "intent_detail",
                                {
                                    "intent_id": self._current_intent_id,
                                    "type": "analyze",
                                    "description": detail
                                }
                            )
                        
                        # Complete intent with summary (for collapsed header)
                        await self.ws_manager.send_event(
                            self.session_id,
                            "intent_complete",
                            {
                                "intent_id": self._current_intent_id,
                                "summary": summary,
                                "auto_collapse": True
                            }
                        )
                        self._current_intent_id = None
                
            else:
                logger.debug(f"[UnifiedReActEngine] Skipping event {event_type} - no WebSocket connection")
        except Exception as e:
            logger.debug(f"[UnifiedReActEngine] Failed to send event {event_type}: {e}")

