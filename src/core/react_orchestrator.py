"""
ReAct Orchestrator for adaptive multi-step execution.
Implements ReAct pattern: Think -> Act -> Observe -> Adapt cycle.

DEPRECATED: This module is deprecated in favor of UnifiedReActEngine.
Use UnifiedReActEngine with AgentModeAdapter instead.
This module is kept for backward compatibility and will be removed in a future version.
"""

from typing import Dict, Any, List, Optional
import asyncio
import json
import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.context_manager import ConversationContext
from src.core.react_state import ReActState, ActionRecord, Observation
from src.core.result_analyzer import ResultAnalyzer, Analysis
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm
from src.utils.logging_config import get_logger
from src.utils.capabilities import get_available_capabilities, build_step_executor_prompt
from src.mcp_tools.workspace_tools import get_workspace_tools
from src.mcp_tools.sheets_tools import get_sheets_tools
from src.mcp_tools.gmail_tools import get_gmail_tools
from src.mcp_tools.calendar_tools import get_calendar_tools
from src.mcp_tools.slides_tools import get_slides_tools
from src.mcp_tools.docs_tools import get_docs_tools

logger = get_logger(__name__)


def _escape_braces_for_fstring(text: str) -> str:
    """Escape curly braces in text to safely use in f-strings."""
    return text.replace("{", "{{").replace("}", "}}")


class ReActOrchestrator:
    """
    ReAct-based orchestrator for adaptive task execution.
    
    Implements iterative cycle:
    1. THINK - Analyze current situation
    2. PLAN - Choose next action dynamically
    3. ACT - Execute action via MCP tools
    4. OBSERVE - Analyze result
    5. ADAPT - Adjust strategy based on result
    """
    
    def __init__(
        self,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize ReActOrchestrator.
        
        Args:
            ws_manager: WebSocket manager for sending events
            session_id: Session identifier
            model_name: Model name for LLM (optional)
        """
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
        
        # Load tools
        self.tools = self._load_tools()
        
        # Create LLM with thinking support
        self.llm = self._create_llm_with_thinking()
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Result analyzer
        self.result_analyzer = ResultAnalyzer(model_name=model_name)
        
        # Stop flag
        self._stop_requested: bool = False
        self._streaming_task: Optional[asyncio.Task] = None
        
        logger.warning(
            f"[ReActOrchestrator] DEPRECATED: ReActOrchestrator is deprecated. "
            f"Use UnifiedReActEngine with AgentModeAdapter instead."
        )
        logger.info(f"[ReActOrchestrator] Initialized for session {session_id} with model {model_name or 'default'}")
    
    def stop(self):
        """Request stop of execution."""
        self._stop_requested = True
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
        logger.info(f"[ReActOrchestrator] Stop requested for session {self.session_id}")
    
    def _load_tools(self) -> List[BaseTool]:
        """Load all available tools."""
        tools = []
        try:
            tools.extend(get_workspace_tools())
            tools.extend(get_sheets_tools())
            tools.extend(get_gmail_tools())
            tools.extend(get_calendar_tools())
            tools.extend(get_slides_tools())
            tools.extend(get_docs_tools())
            
            # Load 1C tools
            from src.mcp_tools.onec_tools import get_onec_tools
            tools.extend(get_onec_tools())
            
            # Load Project Lad tools
            from src.mcp_tools.projectlad_tools import get_projectlad_tools
            tools.extend(get_projectlad_tools())
            
            # Remove duplicates
            seen_names = set()
            unique_tools = []
            for tool in tools:
                if tool.name not in seen_names:
                    seen_names.add(tool.name)
                    unique_tools.append(tool)
            
            logger.info(f"[ReActOrchestrator] Loaded {len(unique_tools)} tools")
            return unique_tools
        except Exception as e:
            logger.error(f"[ReActOrchestrator] Failed to load tools: {e}")
            return []
    
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
            logger.error(f"[ReActOrchestrator] Failed to create LLM: {e}")
            return create_llm(config.default_model)
    
    async def execute(
        self,
        user_request: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute ReAct cycle for user request.
        
        Args:
            user_request: User's request
            context: Conversation context
            file_ids: Optional list of file IDs
            
        Returns:
            Execution result
        """
        file_ids = file_ids or []
        
        # Initialize state
        state = ReActState(goal=user_request)
        state.context = {
            "file_ids": file_ids,
            "session_id": self.session_id
        }
        self._stop_requested = False # Reset stop flag for new execution
        
        
        # Send start event
        await self.ws_manager.send_event(
            self.session_id,
            "react_start",
            {"goal": user_request}
        )
        
        try:
            # Main ReAct loop
            while state.iteration < state.max_iterations:
                if self._stop_requested:
                    logger.info(f"[ReActOrchestrator] Stop requested at iteration {state.iteration}")
                    break
                
                state.iteration += 1
                logger.info(f"[ReActOrchestrator] Starting iteration {state.iteration}")
                
                
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
                    # LLM indicates task is complete
                    logger.info(f"[ReActOrchestrator] LLM indicated task completion with FINISH marker")
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
                    # Treat as successful completion
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
                
                # 3. ACT - Execute action
                action_record = state.add_action(
                    action_plan.get("tool_name", "unknown"),
                    action_plan.get("arguments", {})
                )
                
                try:
                    result = await self._execute_action(action_plan, context)
                except Exception as e:
                    logger.error(f"[ReActOrchestrator] Action execution failed: {e}")
                    result = f"Error: {str(e)}"
                
                # 4. OBSERVE - Analyze result
                state.status = "observing"
                observation = state.add_observation(
                    action_record,
                    result,
                    success=True  # Will be updated by analyzer
                )
                
                await self._stream_reasoning("react_observation", {
                    "result": str(result)[:500],  # Truncate for display
                    "iteration": state.iteration
                })
                
                # Analyze result
                analysis = await self.result_analyzer.analyze(
                    action_record,
                    result,
                    state.goal,
                    state.observations[:-1]  # Previous observations
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
                    # Goal achieved!
                    logger.info(f"[ReActOrchestrator] Goal achieved at iteration {state.iteration}")
                    return await self._finalize_success(state, result, context)
                
                elif analysis.is_error:
                    # Error occurred - try alternative
                    alternative = await self._find_alternative(state, analysis, context, file_ids)
                    if alternative:
                        logger.info(f"[ReActOrchestrator] Trying alternative: {alternative.get('description', '')}")
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
                        # No alternatives - fail gracefully
                        logger.warning(f"[ReActOrchestrator] No alternatives found, failing gracefully")
                        return await self._finalize_failure(state, analysis, context)
                else:
                    # Progress made, continue
                    state.add_reasoning_step("adapt", "Continuing with progress", {
                        "progress": analysis.progress_toward_goal
                    })
                    logger.info(f"[ReActOrchestrator] Progress: {analysis.progress_toward_goal:.0%}")
            
            # Max iterations reached
            logger.warning(f"[ReActOrchestrator] Max iterations reached")
            return await self._finalize_timeout(state, context)
            
        except Exception as e:
            logger.error(f"[ReActOrchestrator] Error in execute: {e}", exc_info=True)
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
        """
        Generate thought about current situation.
        
        Args:
            state: Current ReAct state
            context: Conversation context
            file_ids: File IDs
            
        Returns:
            Thought text
        """
        # Build context for thinking
        context_str = f"Цель: {state.goal}\n\n"
        
        # Add file context (uploaded files have PRIORITY #1)
        if file_ids:
            uploaded_files_found = []
            for file_id in file_ids:
                file_data = context.get_file(file_id)
                if file_data:
                    uploaded_files_found.append(file_data)
            if uploaded_files_found:
                context_str += "📎 Прикрепленные файлы (содержимое уже в сообщении):\n"
                for file_data in uploaded_files_found:
                    context_str += f"- {file_data.get('filename', 'unknown')}\n"
        
        # Add open files context (PRIORITY #2)
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            context_str += "📂 Открытые файлы в рабочей области:\n"
            for file in open_files:
                title = file.get('title', 'Без названия')
                context_str += f"- {title}\n"
        
        if state.action_history:
            context_str += "\nВыполненные действия:\n"
            for i, action in enumerate(state.action_history[-5:], 1):  # Last 5 actions
                obs = next((o for o in state.observations if o.action == action), None)
                status = "✓" if obs and obs.success else "✗"
                context_str += f"{i}. {status} {action.tool_name}\n"
        
        if state.observations:
            context_str += "\nПоследние результаты:\n"
            for obs in state.observations[-3:]:  # Last 3 observations
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
            
            # Handle different response formats (string or list for Claude extended thinking)
            if isinstance(response.content, list):
                # Extract text from content blocks
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
            logger.error(f"[ReActOrchestrator] Error in _think: {e}")
            return f"Анализирую ситуацию... (итерация {state.iteration})"
    
    async def _plan_action(
        self,
        state: ReActState,
        thought: str,
        context: ConversationContext,
        file_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Plan next action based on thought.
        
        Args:
            state: Current ReAct state
            thought: Current thought
            context: Conversation context
            file_ids: File IDs
            
        Returns:
            Action plan with tool_name, arguments, description
        """
        # Build system prompt with available tools
        try:
            capabilities = await get_available_capabilities()
        except:
            capabilities = {"enabled_servers": [], "tools_by_category": {}}
        
        # Get tool descriptions
        tool_descriptions = []
        for tool in self.tools[:50]:  # Limit to first 50 tools
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        tools_str = "\n".join(tool_descriptions)
        
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
                context_str += "\n📎 ПРИКРЕПЛЕННЫЕ ФАЙЛЫ (ПРИОРИТЕТ #1 - используй их ПЕРВЫМ!):\n"
                for file_data in uploaded_files_found:
                    filename = file_data.get('filename', 'unknown')
                    file_type = file_data.get('type', '')
                    if file_type.startswith('image/'):
                        context_str += f"- Изображение: {filename} (содержимое уже в сообщении)\n"
                    elif file_type == 'application/pdf' and 'text' in file_data:
                        context_str += f"- PDF: {filename} (текст уже включен в сообщение)\n"
                    else:
                        context_str += f"- {filename} ({file_type})\n"
                context_str += "⚠️ НЕ ищи эти файлы в Google Drive - их содержимое УЖЕ в сообщении!\n"
        
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
                # Extract text from content blocks
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
            logger.error(f"[ReActOrchestrator] Error in _plan_action: {e}")
            # Fallback: return a valid action (use first available tool)
            fallback_tool = self.tools[0] if self.tools else None
            if fallback_tool:
                return {
                    "tool_name": fallback_tool.name,
                    "arguments": {},
                    "description": f"Fallback: использование {fallback_tool.name}",
                    "reasoning": f"Ошибка планирования: {str(e)}. Используется fallback инструмент."
                }
            else:
                # No tools available - return error action
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
        """
        Execute planned action.
        
        Args:
            action_plan: Action plan with tool_name and arguments
            context: Conversation context
            
        Returns:
            Action result
        """
        tool_name = action_plan.get("tool_name")
        arguments = action_plan.get("arguments", {})
        
        # Find tool
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Execute tool
        try:
            result = await tool.ainvoke(arguments)
            return result
        except Exception as e:
            logger.error(f"[ReActOrchestrator] Tool execution failed: {e}")
            raise
    
    async def _find_alternative(
        self,
        state: ReActState,
        analysis: Analysis,
        context: ConversationContext,
        file_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Find alternative action when current one failed.
        
        Args:
            state: Current ReAct state
            analysis: Analysis of failed action
            context: Conversation context
            file_ids: File IDs
            
        Returns:
            Alternative action plan or None
        """
        # Build context
        context_str = f"Цель: {state.goal}\n\n"
        context_str += f"Ошибка: {analysis.error_message}\n\n"
        context_str += "Неудачные попытки:\n"
        for action in state.action_history[-3:]:
            context_str += f"- {action.tool_name}\n"
        
        context_str += f"\nИспробованные альтернативы: {', '.join(state.alternatives_tried) if state.alternatives_tried else 'нет'}\n"
        
        # Get tool descriptions
        tool_descriptions = []
        for tool in self.tools[:50]:
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        tools_str = "\n".join(tool_descriptions)
        
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
                # Extract text from content blocks
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
            logger.error(f"[ReActOrchestrator] Error in _find_alternative: {e}")
            return None
    
    async def _finalize_success(
        self,
        state: ReActState,
        final_result: Any,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Finalize successful execution."""
        state.status = "done"
        
        # Build result summary
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
        
        # Send completion event
        await self.ws_manager.send_event(
            self.session_id,
            "react_complete",
            {
                "result": str(final_result)[:1000],  # Truncate
                "trail": result_summary["reasoning_trail"][-10:]  # Last 10 steps
            }
        )
        
        # Add to context
        if hasattr(context, 'add_message'):
            context.add_message("assistant", f"Задача выполнена: {state.goal}")
        
        logger.info(f"[ReActOrchestrator] Successfully completed in {state.iteration} iterations")
        return result_summary
    
    async def _finalize_failure(
        self,
        state: ReActState,
        analysis: Analysis,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Finalize failed execution with report."""
        state.status = "failed"
        
        # Build failure report
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
        
        # Send failure event
        await self.ws_manager.send_event(
            self.session_id,
            "react_failed",
            {
                "reason": failure_report["error"],
                "tried": state.alternatives_tried
            }
        )
        
        logger.warning(f"[ReActOrchestrator] Failed after {state.iteration} iterations: {failure_report['error']}")
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
        
        logger.warning(f"[ReActOrchestrator] Timeout after {state.iteration} iterations")
        return timeout_report
    
    async def _stream_reasoning(self, event_type: str, data: Dict[str, Any]):
        """Stream reasoning event to WebSocket."""
        # Only send if WebSocket is connected (for testing without frontend, this is optional)
        try:
            connection_count = self.ws_manager.get_connection_count(self.session_id)
            if connection_count > 0:
                await self.ws_manager.send_event(
                    self.session_id,
                    event_type,
                    data
                )
            else:
                # Log for debugging when no connection (normal for test scripts)
                logger.debug(f"[ReActOrchestrator] Skipping event {event_type} - no WebSocket connection")
        except Exception as e:
            # Don't fail if WebSocket fails (for testing)
            logger.debug(f"[ReActOrchestrator] Failed to send event {event_type}: {e}")

