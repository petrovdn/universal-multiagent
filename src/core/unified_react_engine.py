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
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.context_manager import ConversationContext
from src.core.react_state import ReActState, ActionRecord, Observation
from src.core.result_analyzer import ResultAnalyzer, Analysis
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.core.file_context_resolver import FileContextResolver
from src.core.action_filter import ActionFilter
from src.core.file_reference_resolver import (
    get_relevant_file_ids,
    find_source_for_reference,
    extract_entities_from_response,
)
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
        
        # File context resolver and action filter for smart file handling
        self.file_context_resolver = FileContextResolver()
        self.action_filter = ActionFilter()
        
        # Fast LLM for simple checks (no extended thinking)
        self.fast_llm = self._create_fast_llm()
        
        # SmartProgress and TaskComplexity
        from src.core.smart_progress import SmartProgressGenerator
        from src.core.task_complexity import TaskComplexityAnalyzer
        
        self.smart_progress = SmartProgressGenerator(ws_manager, session_id)
        self.complexity_analyzer = TaskComplexityAnalyzer()
        
        # Stop flag
        self._stop_requested: bool = False
        self._current_thinking_id: Optional[str] = None  # Current thinking block ID
        self._thinking_start_time: Optional[float] = None  # Start time for elapsed calculation
        self._current_intent_id: Optional[str] = None  # Current intent block ID (Cursor-style)
        self._current_iteration: int = 0  # Current ReAct iteration number
        
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
    
    def _create_fast_llm(self) -> BaseChatModel:
        """Create fast LLM for simple checks (no extended thinking)."""
        from src.utils.config_loader import get_config
        from src.agents.model_factory import create_llm
        
        config = get_config()
        # Use haiku or default model without thinking for fast responses
        try:
            return create_llm("claude-3-haiku")
        except Exception:
            return create_llm(config.default_model)
    
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
        
        # === Check for pending confirmation ===
        goal_lower = goal.lower().strip()
        confirmation_keywords = ["да", "давай", "создай", "подтверждаю", "ок", "ok", "yes", "согласен"]
        is_confirmation = any(kw in goal_lower for kw in confirmation_keywords) and len(goal_lower) < 20
        
        if is_confirmation and context.pending_confirmations.get("meeting"):
            pending = context.pending_confirmations["meeting"]
            logger.info(f"[UnifiedReActEngine] Confirmation detected - creating meeting with pending data")
            
            # Clear pending confirmation
            context.pending_confirmations.pop("meeting", None)
            
            # Build a new goal for ReAct that includes all meeting details
            args = pending["arguments"]
            attendees_str = ", ".join(args.get("attendees", []))
            slot_start = args.get("slot_start", "")
            
            # Extract description first
            description = args.get("description")
            if not description and args.get("original_goal"):
                # Extract description from original goal if available
                import re
                original_goal = args["original_goal"]
                
                # Try multiple patterns - more flexible
                patterns = [
                    r'в содержании[^\w]*(?:напиши|напиши|добавь)[^\w]*(.+?)(?:\.|$)',
                    r'в содержании[^\w]+(.+?)(?:\.|$)',
                    r'описание[^\w]+(.+?)(?:\.|$)',
                    r'тост[^\w]+(.+?)(?:\.|$)',
                    r'(?:в содержании|описание|тост)[\s:]+(.+?)(?:\.|$)',
                ]
                for pattern in patterns:
                    desc_match = re.search(pattern, original_goal, re.IGNORECASE | re.DOTALL)
                    if desc_match:
                        description = desc_match.group(1).strip()
                        # Clean up - remove quotes if present
                        description = description.strip('"\'')
                        if description:
                            break
                
                # If still not found, try to extract everything after "в содержании" to end
                if not description:
                    desc_match = re.search(r'в содержании[^\w]+(.+)', original_goal, re.IGNORECASE | re.DOTALL)
                    if desc_match:
                        description = desc_match.group(1).strip()
                        # Remove trailing punctuation
                        description = description.rstrip('.,;!?')
                        description = description.strip('"\'')
            
            # Check if description is an instruction to generate content (e.g., "напиши тост про...")
            # If so, generate it using LLM before passing to goal
            if description:
                description_lower = description.lower()
                generation_keywords = ["напиши", "создай", "составь", "придумай", "сгенерируй"]
                is_generation_request = any(kw in description_lower for kw in generation_keywords)
                
                # Also check original_goal for generation instructions (e.g., "в содержании напиши тост про...")
                # Even if extracted description doesn't contain "напиши", if original goal had it, we need to generate
                if not is_generation_request and args.get("original_goal"):
                    original_goal_lower = args["original_goal"].lower()
                    # Check if original goal contains generation instruction before description
                    if any(kw in original_goal_lower for kw in generation_keywords):
                        # Check if description is a topic/theme (not a ready text)
                        # Patterns that indicate generation needed: "тост про", "про ИИ", "про [topic]"
                        generation_patterns = [
                            r'тост\s+про',
                            r'про\s+[а-яё]+',  # "про ИИ", "про резиновую лодку"
                            r'на\s+тему',
                            r'о\s+[а-яё]+'  # "о ИИ", "о творчестве"
                        ]
                        import re
                        for pattern in generation_patterns:
                            if re.search(pattern, description_lower):
                                is_generation_request = True
                                logger.info(f"[UnifiedReActEngine] Detected generation pattern in description: {pattern}")
                                break
                
                if is_generation_request:
                    logger.info(f"[UnifiedReActEngine] Description is a generation request, generating content: {description[:100]}")
                    try:
                        # Use LLM to generate the content
                        from langchain_anthropic import ChatAnthropic
                        from langchain_core.messages import HumanMessage
                        from src.utils.config_loader import get_config
                        config = get_config()
                        llm = ChatAnthropic(
                            model="claude-sonnet-4-5-20250929",
                            api_key=config.anthropic_api_key,
                            temperature=0.7
                        )
                        
                        prompt = f"Пользователь просит: {description}\n\nСоздай/напиши это содержание. Будь креативным и следуй инструкции пользователя."
                        response = await llm.ainvoke([HumanMessage(content=prompt)])
                        generated_description = response.content.strip()
                        
                        logger.info(f"[UnifiedReActEngine] Generated description: {generated_description[:100]}")
                        description = generated_description
                    except Exception as e:
                        logger.error(f"[UnifiedReActEngine] Failed to generate description: {e}")
                        # Fallback: use original description as-is
                        pass
            
            # Build goal that explicitly uses schedule_group_meeting with confirmed=True
            # IMPORTANT: Use schedule_group_meeting, NOT create_event directly
            # DO NOT use create_event - it is blocked. Use schedule_group_meeting instead.
            new_goal = f"Вызови schedule_group_meeting для создания встречи '{args.get('title', 'Встреча')}' с участниками {attendees_str} на время {slot_start}, длительность {args.get('duration', '1h')}. Параметры вызова: confirmed=True, slot_start='{slot_start}'"
            
            if description:
                new_goal += f", description='{description}'"
                new_goal += f". ВАЖНО: обязательно передай description='{description}' в schedule_group_meeting!"
            
            if args.get("location"):
                new_goal += f", location='{args['location']}'"
            
            new_goal += ". НЕ используй create_event - он заблокирован."
            
            logger.info(f"[UnifiedReActEngine] Created ReAct goal from confirmation: {new_goal[:200]}")
            logger.info(f"[UnifiedReActEngine] Description extracted: {description[:100] if description else 'None'}")
            
            # Continue with ReAct execution (will call schedule_group_meeting with confirmed=True)
            # Modify goal to trigger ReAct
            goal = new_goal
        
        # === Smart file resolution for follow-up questions ===
        # Priority: 1) Conversation history, 2) Entity memory keywords, 3) General patterns
        if not file_ids and context and hasattr(context, 'uploaded_files') and context.uploaded_files:
            
            # NEW: Check if query has multiple parts (conjunction) - likely asking about multiple files
            goal_lower = goal.lower()
            multi_part_indicators = [' и ', ' а также ', ' ещё ', ' еще ', ' плюс ', ' потом ']
            is_multi_part_query = any(ind in goal_lower for ind in multi_part_indicators)
            
            # If multi-part query AND multiple files in context - use ALL files
            # This handles cases like "расскажи о годовом цикле И опиши спортивную форму"
            # where different parts refer to different files
            if is_multi_part_query and len(context.uploaded_files) > 1:
                file_ids = list(context.uploaded_files.keys())
                logger.info(f"[execute] Multi-part query detected, using ALL {len(file_ids)} files: {file_ids}")
                print(f"[execute] Multi-part query - using all files: {file_ids}", flush=True)
            elif not file_ids:
                # Only do smart resolution if multi-part didn't apply
                # 1. First, search conversation history for references
                # "расскажи про человека" → find where "человек" was mentioned → get source file
                history_source_files = find_source_for_reference(goal, context)
                
                if history_source_files:
                    # Found source files from conversation history
                    # If multiple files, try to narrow down by keyword matching
                    if len(history_source_files) > 1:
                        keyword_matches = get_relevant_file_ids(goal, context)
                        if keyword_matches:
                            # Use intersection: files that are both in history AND match keywords
                            relevant = [f for f in keyword_matches if f in history_source_files]
                            if relevant:
                                file_ids = relevant
                                logger.info(f"[execute] Narrowed from {len(history_source_files)} to {len(file_ids)} files by keyword: {file_ids}")
                                print(f"[execute] Narrowed to relevant files: {file_ids}", flush=True)
                            else:
                                # No intersection, use keyword matches directly
                                file_ids = keyword_matches
                                logger.info(f"[execute] Using keyword matches instead: {file_ids}")
                                print(f"[execute] Using keyword matches: {file_ids}", flush=True)
                        else:
                            # No keyword matches, use all from history
                            file_ids = history_source_files
                            logger.info(f"[execute] Using all {len(file_ids)} source files from history: {file_ids}")
                            print(f"[execute] Using all files from history: {file_ids}", flush=True)
                    else:
                        # Single file from history
                        file_ids = history_source_files
                        logger.info(f"[execute] Found source file from history: {file_ids}")
                        print(f"[execute] Found source from history: {file_ids}", flush=True)
                else:
                    # 2. Try keyword-based resolution from entity_memory
                    relevant_ids = get_relevant_file_ids(goal, context)
                    
                    if relevant_ids:
                        # Found specific relevant files by keywords
                        file_ids = relevant_ids
                        logger.info(f"[execute] Found {len(file_ids)} relevant files by keywords: {file_ids}")
                        print(f"[execute] Found relevant files by keywords: {file_ids}", flush=True)
                    else:
                        # 3. Check if query seems to be about files in general
                        general_file_patterns = ['что видишь', 'что в файл', 'опиши файл', 'опиши все', 
                                                'про все файлы', 'во всех файлах', 'в файлах']
                        if any(p in goal_lower for p in general_file_patterns):
                            # General query about all files
                            file_ids = list(context.uploaded_files.keys())
                            logger.info(f"[execute] Using ALL {len(file_ids)} files for general query")
                            print(f"[execute] Using all files for general query: {file_ids}", flush=True)
                        else:
                            logger.info(f"[execute] No relevant files found for query: {goal[:50]}")
                            print(f"[execute] No relevant files found for query", flush=True)
        
        logger.info(f"[execute] Starting execution - goal: {goal[:100]}, file_ids: {file_ids}, file_ids count: {len(file_ids)}")
        print(f"[execute] Starting execution - goal: {goal[:100]}, file_ids: {file_ids}", flush=True)
        if hasattr(context, 'uploaded_files'):
            total_files = len(context.uploaded_files)
            logger.info(f"[execute] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}")
            print(f"[execute] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}", flush=True)
        _exec_start = time.time()
        _calendar_caps = [c.name for c in self.capabilities if 'calendar' in c.name.lower() or 'event' in c.name.lower()]
        # Initialize state
        state = ReActState(goal=goal)
        state.context = {
            "file_ids": file_ids,
            "session_id": self.session_id,
            "phase": phase
        }
        self._stop_requested = False
        
        # === OPTIMIZATION: Send intent_start IMMEDIATELY for instant feedback ===
        # Analyze task phases (fast - regex only, no LLM)
        task_phases = self._analyze_task_phases(goal)
        self._is_multi_phase = len(task_phases) >= 2
        self._task_phases = task_phases
        self._current_phase_category = None
        self._phase_intent_ids = {}  # category -> intent_id mapping
        # Create intent_start IMMEDIATELY (before any LLM calls)
        if self._is_multi_phase:
            logger.info(f"[UnifiedReActEngine] Multi-phase task detected: {len(task_phases)} phases")
            # Create the FIRST phase intent
            first_phase = task_phases[0]
            task_intent_id = f"phase-{int(time.time() * 1000)}"
            self._current_intent_id = task_intent_id
            self._current_phase_category = first_phase['category']
            self._phase_intent_ids[first_phase['category']] = task_intent_id
            await self.ws_manager.send_event(
                self.session_id,
                "intent_start",
                {"intent_id": task_intent_id, "text": first_phase['description']}
            )
        else:
            # Single-phase task: Create ONE task-level intent for the entire goal
            task_intent_id = f"task-{int(time.time() * 1000)}"
            self._current_intent_id = task_intent_id
            
            # Generate meaningful task description from goal
            task_description = self._generate_task_description(goal, file_ids)
            await self.ws_manager.send_event(
                self.session_id,
                "intent_start",
                {"intent_id": task_intent_id, "text": task_description}
            )
        
        self._task_intent_id = self._current_intent_id  # Store for the entire execution
        _needs_tools_start = time.time()
        # NOW check if query needs tools (may take 500-2000ms with LLM)
        # Check if query needs tools or can be answered directly (like Cursor does)
        # Pass file_ids to detect questions about attached files (e.g., "что видишь?")
        needs_tools = await self._needs_tools(goal, context, file_ids)
        _needs_tools_end = time.time()
        # Анализируем сложность задачи и выбираем модель/budget
        complexity = self.complexity_analyzer.analyze(goal)
        
        # Выбираем модель и budget на основе сложности
        if complexity.use_fast_model:
            # Используем быструю модель без thinking
            self.llm = self.fast_llm
        else:
            # Используем основную модель с адаптивным budget
            self.llm = self._create_llm_with_thinking(complexity.budget_tokens)
        
        # Запускаем SmartProgress с оценочным временем (только если нужны инструменты)
        if needs_tools:
            await self.smart_progress.start(goal, complexity.estimated_duration_sec)
        
        if not needs_tools:
            # Simple query - answer directly without tools
            logger.info(f"[UnifiedReActEngine] Simple query detected, answering directly without tools")
            # Complete the intent since we're finishing early
            if self._current_intent_id:
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_complete",
                    {
                        "intent_id": self._current_intent_id,
                        "summary": "Завершено"
                    }
                )
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
                self._current_iteration = state.iteration  # Store for use in _execute_action
                logger.info(f"[UnifiedReActEngine] Starting iteration {state.iteration}")
                
                # === Send iteration_start event for UI ===
                await self.ws_manager.send_event(
                    self.session_id,
                    "iteration_start",
                    {
                        "intent_id": self._current_intent_id,
                        "iteration_number": state.iteration
                    }
                )
                
                # 1. THINK - Analyze current situation
                state.status = "thinking"
                # Real progress: no fake messages, just actual work
                _think_plan_start = time.time()
                # Объединённый вызов: анализ + планирование
                thought, action_plan = await self._think_and_plan(state, context, file_ids)
                _think_plan_end = time.time()
                state.current_thought = thought
                state.add_reasoning_step("think", thought)
                await self._stream_reasoning("react_thinking", {
                    "thought": thought,
                    "iteration": state.iteration
                })
                
                # === Send iteration_thinking_complete event ===
                think_duration = _think_plan_end - _think_plan_start
                await self.ws_manager.send_event(
                    self.session_id,
                    "iteration_thinking_complete",
                    {
                        "intent_id": self._current_intent_id,
                        "iteration_number": state.iteration,
                        "duration_sec": think_duration
                    }
                )
                
                if self._stop_requested:
                    break
                
                # 2. PLAN - Action plan уже получен из _think_and_plan
                state.status = "acting"
                planned_tool = action_plan.get("tool_name", "")
                
                # #region agent log - H7: Planned tool for this iteration
                try:
                    with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                        import json as _json
                        f.write(_json.dumps({
                            "location": "unified_react_engine.py:575",
                            "message": "H7: Planned tool before ANTI-LOOP",
                            "data": {
                                "iteration": state.iteration,
                                "planned_tool": planned_tool,
                                "description": action_plan.get("description", ""),
                                "observations_count": len(state.observations),
                                "observations_tools": [obs.action.tool_name for obs in state.observations]
                            },
                            "timestamp": __import__("time").time() * 1000,
                            "sessionId": self.session_id,
                            "hypothesisId": "H7"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                
                # === Send iteration_plan event ===
                await self.ws_manager.send_event(
                    self.session_id,
                    "iteration_plan",
                    {
                        "iteration": state.iteration,
                        "thought": thought[:200] if thought else "",
                        "planned_action": planned_tool,
                        "description": action_plan.get("description", ""),
                        "reasoning": action_plan.get("reasoning", "")
                    }
                )
                
                # === Send iteration_summary event for UI ===
                action_description = action_plan.get("description", "") or f"выполню {planned_tool}"
                
                # Преобразуем "Чтение..." → "Прочитаю...", "Форматирование..." → "Отформатирую..."
                def to_first_person(text: str) -> str:
                    replacements = [
                        ("Чтение", "Прочитаю"),
                        ("чтение", "прочитаю"),
                        ("Запись", "Запишу"),
                        ("запись", "запишу"),
                        ("Форматирование", "Отформатирую"),
                        ("форматирование", "отформатирую"),
                        ("Добавление", "Добавлю"),
                        ("добавление", "добавлю"),
                        ("Создание", "Создам"),
                        ("создание", "создам"),
                        ("Получение", "Получу"),
                        ("получение", "получу"),
                        ("Поиск", "Найду"),
                        ("поиск", "найду"),
                        ("Обновление", "Обновлю"),
                        ("обновление", "обновлю"),
                    ]
                    result = text
                    for old, new in replacements:
                        if result.startswith(old):
                            result = new + result[len(old):]
                            break
                    return result
                
                action_first_person = to_first_person(action_description)
                
                if state.iteration == 1:
                    # Первая итерация - "Прочитаю X для Y"
                    summary_text = f"→ {action_first_person}"
                    
                    # Обновляем заголовок шага на основе первого действия
                    short_title = self._get_short_action_title(planned_tool, action_plan.get("arguments", {}))
                    if short_title and self._current_intent_id:
                        await self.ws_manager.send_event(
                            self.session_id,
                            "intent_title_update",
                            {
                                "intent_id": self._current_intent_id,
                                "title": short_title
                            }
                        )
                else:
                    # Последующие итерации - оценка предыдущего + план
                    prev_result = ""
                    if state.observations:
                        last_obs = state.observations[-1]
                        if last_obs.success:
                            prev_tool = last_obs.action.tool_name
                            if "read" in prev_tool.lower():
                                prev_result = "Прочитал, понял контекст. "
                            elif "append" in prev_tool.lower() or "insert" in prev_tool.lower():
                                prev_result = "Текст добавлен, отлично! "
                            elif "format" in prev_tool.lower():
                                prev_result = "Отформатировал. "
                            elif "create" in prev_tool.lower():
                                prev_result = "Создал. "
                            else:
                                prev_result = "Готово. "
                        else:
                            prev_result = "Попробую по-другому. "
                    # Для последующих итераций делаем первую букву строчной
                    action_lower = action_first_person[0].lower() + action_first_person[1:] if action_first_person else ""
                    summary_text = f"→ {prev_result}Теперь {action_lower}"
                
                await self.ws_manager.send_event(
                    self.session_id,
                    "iteration_summary",
                    {
                        "intent_id": self._current_intent_id,
                        "iteration_number": state.iteration,
                        "summary": summary_text
                    }
                )
                
                # === ANTI-LOOP: Block repeated read_document calls ===
                # If document was already read successfully, redirect to format_document_text
                if planned_tool == "read_document" and len(state.observations) > 0:
                    planned_doc_id = action_plan.get("arguments", {}).get("document_id", "")
                    for obs in state.observations:
                        if obs.action.tool_name == "read_document" and obs.success:
                            prev_doc_id = obs.action.arguments.get("document_id", "")
                            if prev_doc_id == planned_doc_id:
                                # Document already read - check if this is a compound task
                                goal_lower = state.goal.lower()
                                
                                # Проверяем составную задачу (допиши + форматируй)
                                modify_keywords = ["допиши", "добавь", "напиши", "вставь"]
                                format_keywords = ["форматир", "красиво", "красив", "оформи", "format"]
                                needs_modification = any(kw in goal_lower for kw in modify_keywords)
                                needs_formatting = any(kw in goal_lower for kw in format_keywords)
                                
                                # Проверяем, была ли выполнена модификация (хокку добавлено?)
                                modify_done = any(
                                    obs.action.tool_name in ["append_to_document", "insert_into_document", "update_document"] and obs.success
                                    for obs in state.observations
                                )
                                
                                # Проверяем какое форматирование уже сделано
                                bold_count = sum(
                                    1 for obs in state.observations
                                    if obs.action.tool_name == "format_document_text" and obs.success
                                )
                                paragraph_done = any(
                                    obs.action.tool_name == "format_document_paragraph" and obs.success
                                    for obs in state.observations
                                )
                                doc_length = self._get_document_length_from_observations(state)
                                
                                # #region agent log - H6: ANTI-LOOP read_document redirect
                                try:
                                    with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                                        import json as _json
                                        f.write(_json.dumps({
                                            "location": "unified_react_engine.py:ANTI-LOOP",
                                            "message": "H6: read_document ANTI-LOOP check",
                                            "data": {
                                                "needs_modification": needs_modification,
                                                "modify_done": modify_done,
                                                "needs_formatting": needs_formatting,
                                                "bold_count": bold_count,
                                                "paragraph_done": paragraph_done,
                                                "iteration": state.iteration
                                            },
                                            "timestamp": __import__("time").time() * 1000,
                                            "sessionId": self.session_id,
                                            "hypothesisId": "H6"
                                        }) + "\n")
                                except Exception:
                                    pass
                                # #endregion
                                
                                # КРИТИЧЕСКАЯ ЛОГИКА: Если нужна модификация (хокку) И она НЕ сделана
                                # → НЕ перенаправляем на форматирование! Пусть LLM добавит хокку.
                                if needs_modification and not modify_done:
                                    # Блокируем повторное чтение, но НЕ перенаправляем на форматирование
                                    logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Document read, but modification (haiku) not done yet - blocking read, let LLM add content")
                                    action_plan = {
                                        "tool_name": "append_to_document",
                                        "arguments": {
                                            "document_id": planned_doc_id,
                                            "content": ""  # LLM должен сгенерировать
                                        },
                                        "description": "Добавление основной мысли (хокку)",
                                        "reasoning": "Документ уже прочитан, теперь нужно добавить хокку"
                                    }
                                    # НЕ меняем planned_tool - позволяем LLM сгенерировать контент
                                    # Вместо этого просто прерываем цикл ANTI-LOOP
                                    break
                                
                                # Форматирование только если модификация УЖЕ сделана или не нужна
                                if needs_formatting and (modify_done or not needs_modification) and bold_count == 0:
                                    # Первый раз: выделяем заголовок жирным
                                    logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Document already read, formatting title bold")
                                    doc_text = self._get_document_text_from_observations(state)
                                    first_range = {"start": 1, "end": min(doc_length, 100), "reason": "заголовок"}
                                    
                                    if doc_text:
                                        try:
                                            ranges = await self._get_smart_formatting_ranges(doc_text, doc_length)
                                            if ranges:
                                                first_range = ranges[0]
                                        except Exception:
                                            pass  # Use fallback
                                    
                                    action_plan = {
                                        "tool_name": "format_document_text",
                                        "arguments": {
                                            "document_id": planned_doc_id,
                                            "start_index": first_range["start"],
                                            "end_index": first_range["end"],
                                            "bold": True
                                        },
                                        "description": f"Выделение жирным: {first_range.get('reason', 'заголовок')}",
                                        "reasoning": "Умное определение заголовка"
                                    }
                                    planned_tool = "format_document_text"
                                elif needs_formatting and (modify_done or not needs_modification) and bold_count == 1:
                                    # Второй раз: выделяем основную мысль (хокку в конце) жирным
                                    logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Title done, formatting conclusion bold")
                                    # Выделяем последние ~150 символов (хокку/основная мысль)
                                    conclusion_start = max(1, doc_length - 150)
                                    action_plan = {
                                        "tool_name": "format_document_text",
                                        "arguments": {
                                            "document_id": planned_doc_id,
                                            "start_index": conclusion_start,
                                            "end_index": doc_length,
                                            "bold": True
                                        },
                                        "description": "Выделение жирным: основная мысль/хокку",
                                        "reasoning": "Заголовок выделен, теперь выделяем хокку в конце"
                                    }
                                    planned_tool = "format_document_text"
                                elif needs_formatting and (modify_done or not needs_modification) and bold_count >= 2 and not paragraph_done:
                                    # Потом выравнивание абзацев
                                    logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Bold done, redirecting to format_document_paragraph")
                                    action_plan = {
                                        "tool_name": "format_document_paragraph",
                                        "arguments": {
                                            "document_id": planned_doc_id,
                                            "start_index": 1,
                                            "end_index": doc_length,
                                            "alignment": "JUSTIFIED",
                                            "first_line_indent_pt": 36
                                        },
                                        "description": "Выравнивание текста по ширине с красной строкой",
                                        "reasoning": "Жирный заголовок сделан, теперь выравнивание"
                                    }
                                    planned_tool = "format_document_paragraph"
                                else:
                                    # Всё сделано - FINISH
                                    logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: All formatting done, forcing FINISH")
                                    action_plan = {
                                        "tool_name": "FINISH",
                                        "arguments": {},
                                        "description": "Документ обработан",
                                        "reasoning": "Документ уже прочитан и отформатирован"
                                    }
                                    planned_tool = "FINISH"
                                break
                
                # === CRITICAL: Block update_document for formatting tasks ===
                # "Красиво оформить" should use format_document_text, NOT update_document
                # update_document REWRITES the entire document, destroying original text
                text_modifying_tools = ["update_document", "insert_into_document", "append_to_document"]
                if planned_tool in text_modifying_tools:
                    goal_lower = state.goal.lower()
                    format_keywords = ["форматир", "красиво", "красив", "оформи", "оформить", "format", "выдели", "жирн"]
                    is_formatting_task = any(kw in goal_lower for kw in format_keywords)
                    
                    # Проверяем, является ли задача составной
                    is_compound, phases = self._is_compound_task(state.goal)
                    
                    # #region agent log - H1: compound task detection
                    try:
                        with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                            import json as _json
                            f.write(_json.dumps({
                                "location": "unified_react_engine.py:730",
                                "message": "H1: Compound task detection",
                                "data": {
                                    "is_compound": is_compound,
                                    "phases": phases,
                                    "planned_tool": planned_tool,
                                    "is_formatting_task": is_formatting_task,
                                    "iteration": state.iteration,
                                    "observations_count": len(state.observations)
                                },
                                "timestamp": __import__("time").time() * 1000,
                                "sessionId": self.session_id,
                                "hypothesisId": "H1"
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    
                    if is_compound and "modify" in phases:
                        # Составная задача - проверяем, выполнена ли фаза модификации
                        modify_done = any(
                            obs.action.tool_name in text_modifying_tools and obs.success
                            for obs in state.observations
                        )
                        # #region agent log - H3: modify phase check
                        try:
                            with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                                import json as _json
                                f.write(_json.dumps({
                                    "location": "unified_react_engine.py:755",
                                    "message": "H3: Modify phase check",
                                    "data": {
                                        "modify_done": modify_done,
                                        "planned_tool": planned_tool,
                                        "will_redirect_to_format": modify_done
                                    },
                                    "timestamp": __import__("time").time() * 1000,
                                    "sessionId": self.session_id,
                                    "hypothesisId": "H3"
                                }) + "\n")
                        except Exception:
                            pass
                        # #endregion
                        
                        if not modify_done:
                            # Разрешаем модификацию - это первая фаза составной задачи
                            logger.info(f"[UnifiedReActEngine] Compound task detected: allowing {planned_tool} for modify phase")
                            pass  # Не блокируем
                        else:
                            # Модификация выполнена - теперь проверяем какое форматирование уже сделано
                            doc_id = action_plan.get("arguments", {}).get("document_id", "")
                            
                            # Считаем сколько раз уже применяли format_document_text
                            bold_count = sum(
                                1 for obs in state.observations
                                if obs.action.tool_name == "format_document_text" and obs.success
                            )
                            # Проверяем, было ли уже выполнено форматирование абзацев
                            paragraph_done = any(
                                obs.action.tool_name == "format_document_paragraph" and obs.success
                                for obs in state.observations
                            )
                            
                            doc_length = self._get_document_length_from_observations(state)
                            
                            if bold_count == 0:
                                # Первый раз: выделяем заголовок жирным
                                logger.warning(f"[UnifiedReActEngine] BLOCK: {planned_tool} blocked - formatting title bold")
                                doc_text = self._get_document_text_from_observations(state)
                                if doc_text:
                                    ranges = await self._get_smart_formatting_ranges(doc_text, doc_length)
                                    first_range = ranges[0] if ranges else {"start": 1, "end": min(doc_length, 100)}
                                else:
                                    first_range = {"start": 1, "end": min(doc_length, 100)}
                                
                                action_plan = {
                                    "tool_name": "format_document_text",
                                    "arguments": {
                                        "document_id": doc_id,
                                        "start_index": first_range["start"],
                                        "end_index": first_range["end"],
                                        "bold": True
                                    },
                                    "description": f"Выделение жирным: {first_range.get('reason', 'заголовок')}",
                                    "reasoning": f"Модификация выполнена, форматирование заголовка"
                                }
                                planned_tool = "format_document_text"
                            elif bold_count == 1:
                                # Второй раз: выделяем основную мысль (хокку в конце)
                                logger.warning(f"[UnifiedReActEngine] BLOCK: {planned_tool} blocked - formatting conclusion bold")
                                conclusion_start = max(1, doc_length - 150)
                                action_plan = {
                                    "tool_name": "format_document_text",
                                    "arguments": {
                                        "document_id": doc_id,
                                        "start_index": conclusion_start,
                                        "end_index": doc_length,
                                        "bold": True
                                    },
                                    "description": "Выделение жирным: основная мысль/хокку",
                                    "reasoning": "Заголовок выделен, теперь выделяем хокку"
                                }
                                planned_tool = "format_document_text"
                            elif bold_count >= 2 and not paragraph_done:
                                # Потом делаем выравнивание абзацев
                                logger.warning(f"[UnifiedReActEngine] BLOCK: {planned_tool} blocked - redirecting to format_document_paragraph (alignment)")
                                action_plan = {
                                    "tool_name": "format_document_paragraph",
                                    "arguments": {
                                        "document_id": doc_id,
                                        "start_index": 1,
                                        "end_index": doc_length,
                                        "alignment": "JUSTIFIED",
                                        "first_line_indent_pt": 36  # Красная строка ~12.7mm
                                    },
                                    "description": "Выравнивание текста по ширине с красной строкой",
                                    "reasoning": "Жирный заголовок сделан, теперь выравнивание абзацев"
                                }
                                planned_tool = "format_document_paragraph"
                            else:
                                # Всё форматирование сделано - завершаем
                                logger.info(f"[UnifiedReActEngine] All formatting done, forcing FINISH")
                                action_plan = {
                                    "tool_name": "FINISH",
                                    "arguments": {},
                                    "description": "Текст добавлен и отформатирован",
                                    "reasoning": "Модификация и форматирование завершены"
                                }
                                planned_tool = "FINISH"
                    elif is_formatting_task:
                        # Get document_id from the planned arguments
                        doc_id = action_plan.get("arguments", {}).get("document_id", "")
                        logger.warning(f"[UnifiedReActEngine] BLOCK: {planned_tool} blocked for formatting task, using smart formatting")
                        
                        # Умное определение что выделить жирным
                        doc_length = self._get_document_length_from_observations(state)
                        doc_text = self._get_document_text_from_observations(state)
                        if doc_text:
                            ranges = await self._get_smart_formatting_ranges(doc_text, doc_length)
                            first_range = ranges[0] if ranges else {"start": 1, "end": min(doc_length, 100)}
                        else:
                            first_range = {"start": 1, "end": min(doc_length, 100)}
                        
                        action_plan = {
                            "tool_name": "format_document_text",
                            "arguments": {
                                "document_id": doc_id,
                                "start_index": first_range["start"],
                                "end_index": first_range["end"],
                                "bold": True
                            },
                            "description": f"Выделение жирным: {first_range.get('reason', 'заголовок')}",
                            "reasoning": f"Задача форматирования: умное определение вместо {planned_tool}"
                        }
                        planned_tool = "format_document_text"
                
                # === ANTI-LOOP: Block premature FINISH for formatting tasks ===
                # If LLM wants FINISH but format_document_paragraph not done yet
                if planned_tool == "FINISH":
                    goal_lower = state.goal.lower()
                    format_keywords = ["форматир", "красиво", "красив", "оформи", "format"]
                    is_formatting_task = any(kw in goal_lower for kw in format_keywords)
                    
                    if is_formatting_task:
                        paragraph_done = any(
                            obs.action.tool_name == "format_document_paragraph" and obs.success
                            for obs in state.observations
                        )
                        # #region agent log - H9: Premature FINISH check
                        try:
                            with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                                import json as _json
                                f.write(_json.dumps({
                                    "location": "unified_react_engine.py:FINISH-CHECK",
                                    "message": "H9: Premature FINISH check",
                                    "data": {
                                        "is_formatting_task": is_formatting_task,
                                        "paragraph_done": paragraph_done,
                                        "will_redirect": not paragraph_done,
                                        "iteration": state.iteration
                                    },
                                    "timestamp": __import__("time").time() * 1000,
                                    "sessionId": self.session_id,
                                    "hypothesisId": "H9"
                                }) + "\n")
                        except Exception:
                            pass
                        # #endregion
                        
                        if not paragraph_done:
                            # FINISH преждевременный - нужно ещё отформатировать абзацы
                            logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Premature FINISH, need format_document_paragraph")
                            
                            # Получаем document_id из предыдущих операций
                            doc_id = ""
                            doc_length = 100
                            for obs in state.observations:
                                if obs.action.tool_name in ["read_document", "append_to_document", "insert_into_document", "format_document_text"]:
                                    doc_id = obs.action.arguments.get("document_id", "") or obs.action.arguments.get("documentId", "")
                                    if doc_id:
                                        break
                            
                            if doc_id:
                                doc_length = self._get_document_length_from_observations(state)
                                action_plan = {
                                    "tool_name": "format_document_paragraph",
                                    "arguments": {
                                        "document_id": doc_id,
                                        "start_index": 1,
                                        "end_index": doc_length,
                                        "alignment": "JUSTIFIED",
                                        "first_line_indent_pt": 36
                                    },
                                    "description": "Выравнивание текста по ширине с красной строкой",
                                    "reasoning": "FINISH преждевременный, нужно ещё выровнять абзацы"
                                }
                                planned_tool = "format_document_paragraph"
                
                # === ANTI-LOOP: Detect repeated get_calendar_events calls ===
                # FIXED: Do NOT automatically create events! Just FINISH with explanation.
                if planned_tool == "get_calendar_events" and len(state.action_history) > 0:
                    # Check if last action was also get_calendar_events
                    last_action = state.action_history[-1]
                    if last_action.tool_name == "get_calendar_events":
                        # Check if it failed
                        last_obs = state.observations[-1] if state.observations else None
                        if last_obs and not last_obs.success:
                            logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: get_calendar_events failed, finishing with explanation")
                            # Return FINISH with explanation instead of creating event!
                            action_plan = {
                                "tool_name": "FINISH",
                                "arguments": {},
                                "description": "Не удалось получить события календаря",
                                "reasoning": f"Ошибка при получении событий: {last_obs.error_message or last_obs.raw_result}"
                            }
                            planned_tool = "FINISH"
                        else:
                            logger.warning(f"[UnifiedReActEngine] ANTI-LOOP: Repeated get_calendar_events, finishing")
                            action_plan = {
                                "tool_name": "FINISH",
                                "arguments": {},
                                "description": "Календарные события уже получены",
                                "reasoning": "Повторный вызов get_calendar_events, завершаем задачу"
                            }
                            planned_tool = "FINISH"
                
                # === UNIVERSAL ANTI-LOOP: Detect repeated failed tool calls ===
                # If same tool failed 2+ times (not necessarily consecutive), block it
                if planned_tool.upper() != "FINISH" and len(state.observations) >= 2:
                    # Count ALL failures of the same tool (not just consecutive)
                    failed_same_tool_count = sum(
                        1 for obs in state.observations 
                        if obs.action.tool_name == planned_tool and not obs.success
                    )
                    
                    if failed_same_tool_count >= 2:
                        # Tool failed 2+ times, we need to try something different
                        logger.warning(f"[UnifiedReActEngine] UNIVERSAL ANTI-LOOP: Tool {planned_tool} failed {failed_same_tool_count} times in a row!")
                        
                        # Map blocked tool to alternative
                        tool_alternatives = {
                            "find_and_open_file": "read_document",  # Google Docs
                            "open_file": "read_document",
                            "search_files": "list_workspace_files",
                        }
                        
                        alternative = tool_alternatives.get(planned_tool)
                        if alternative:
                            logger.info(f"[UnifiedReActEngine] Switching from {planned_tool} to {alternative}")
                            
                            # Get document ID from previous attempts if available
                            doc_id = None
                            for obs in state.observations:
                                if "Сказка" in str(obs.raw_result) or "сказка" in str(obs.raw_result):
                                    # Try to extract document ID
                                    import re
                                    id_match = re.search(r'ID[:\s]+([a-zA-Z0-9_-]{20,})', str(obs.raw_result))
                                    if id_match:
                                        doc_id = id_match.group(1)
                                        break
                            
                            # Override action_plan
                            action_plan = {
                                "tool_name": alternative,
                                "arguments": {"query": "сказка"} if not doc_id else {"document_id": doc_id},
                                "description": f"Автоматическое переключение с {planned_tool} на {alternative}",
                                "reasoning": f"Инструмент {planned_tool} не работает, пробуем {alternative}"
                            }
                            planned_tool = alternative
                        else:
                            # No known alternative, force FINISH with explanation
                            logger.warning(f"[UnifiedReActEngine] No alternative for {planned_tool}, forcing FINISH")
                            _last_obs = state.observations[-1] if state.observations else None
                            _error_msg = "неизвестная"
                            if _last_obs:
                                if _last_obs.error_message:
                                    _error_msg = _last_obs.error_message[:200]
                                elif _last_obs.raw_result:
                                    _error_msg = str(_last_obs.raw_result)[:200]
                            action_plan = {
                                "tool_name": "FINISH",
                                "arguments": {},
                                "final_answer": f"Не удалось выполнить задачу: инструмент {planned_tool} недоступен или не работает корректно. Ошибка: {_error_msg}"
                            }
                            planned_tool = "FINISH"
                
                # === MULTI-PHASE: Check for phase transition ===
                # IMPORTANT: Check transitions even if task wasn't initially detected as multi-phase
                # This allows dynamic detection when different tool categories are used
                if planned_tool.upper() != "FINISH":
                    new_category = self._get_tool_category(planned_tool)
                    # Check if we're transitioning to a new phase
                    # Allow transition if:
                    # 1. Task was detected as multi-phase initially, OR
                    # 2. We're using a different category than current (dynamic detection)
                    # BUT: Skip transitions involving docs_format to prevent UI flickering during document formatting
                    is_formatting_transition = (
                        new_category == 'docs_format' or 
                        self._current_phase_category == 'docs_format' or
                        (self._current_phase_category == 'files' and new_category == 'docs_format')
                    )
                    should_transition = (
                        new_category != self._current_phase_category and 
                        new_category != 'general' and
                        (self._is_multi_phase or self._current_phase_category is not None) and
                        not is_formatting_transition  # Prevent UI flickering for formatting tasks
                    )
                    
                    if should_transition:
                        # Complete current intent before starting new one
                        if self._current_intent_id:
                            await self.ws_manager.send_event(
                                self.session_id,
                                "intent_complete",
                                {
                                    "intent_id": self._current_intent_id,
                                    "summary": "Завершено"
                                }
                            )
                        
                        # Find or create intent for new phase
                        if new_category in self._phase_intent_ids:
                            # Reusing existing phase intent
                            self._current_intent_id = self._phase_intent_ids[new_category]
                        else:
                            # Create new phase intent
                            new_intent_id = f"phase-{int(time.time() * 1000)}"
                            self._phase_intent_ids[new_category] = new_intent_id
                            self._current_intent_id = new_intent_id
                            
                            phase_description = self._get_phase_description_for_category(new_category)
                            await self.ws_manager.send_event(
                                self.session_id,
                                "intent_start",
                                {"intent_id": new_intent_id, "text": phase_description}
                            )
                            logger.info(f"[UnifiedReActEngine] Phase transition: {self._current_phase_category} -> {new_category}")
                        self._current_phase_category = new_category
                        self._task_intent_id = self._current_intent_id
                    elif self._current_phase_category is None:
                        # First tool usage - set initial category
                        self._current_phase_category = new_category
                
                # === Add intent_detail for planned action (skip for tools with operations) ===
                if planned_tool.upper() != "FINISH":
                    # Check if this tool supports operations - if yes, skip intent_detail (will send operation_start instead)
                    tools_with_operations = {
                        'get_calendar_events',
                        'get_sheet_data',
                        'add_rows',
                        'update_cells',
                        'list_emails',
                        'search_emails',
                        'read_document',
                        'update_document',
                        'get_presentation',
                        'format_document_text',
                        'format_document_paragraph',
                    }
                    if planned_tool not in tools_with_operations:
                        # Add detail about what we're going to do (only for tools without operations)
                        action_description = action_plan.get("description", "")[:80]
                        await self.ws_manager.send_event(
                            self.session_id,
                            "intent_detail",
                            {
                            "intent_id": self._current_intent_id,
                            "type": "execute",
                            "description": f"🎯 {action_description}" if action_description else f"🔧 {self._get_tool_display_name(planned_tool, action_plan.get('arguments', {}))}"
                            }
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
                    
                    # FIX: Break the loop and finalize when FINISH marker is detected
                    # Previously, code continued to execute FINISH as a tool, causing errors and infinite loop
                    return await self._finalize_success(state, finish_reasoning, context, file_ids)
                
                # Check for "ASK_CLARIFICATION" marker
                elif tool_name.upper() == "ASK_CLARIFICATION" or tool_name == "ask_clarification":
                    logger.info(f"[UnifiedReActEngine] LLM requested clarification for incomplete request")
                    questions = action_plan.get("arguments", {}).get("questions", [])
                    clarification_reasoning = action_plan.get("reasoning", "Нужны уточнения для выполнения задачи")
                    
                    # Формируем ответ с уточняющими вопросами
                    if questions:
                        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
                        clarification_response = f"Для выполнения вашего запроса мне нужны дополнительные уточнения:\n\n{questions_text}\n\nПожалуйста, предоставьте эту информацию, и я смогу выполнить задачу."
                    else:
                        clarification_response = f"Для выполнения вашего запроса '{state.goal}' мне нужны дополнительные уточнения. Пожалуйста, уточните детали."
                    
                    # Отправляем уточняющие вопросы через WebSocket
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result",
                        {
                            "content": clarification_response,
                            "metadata": {
                                "type": "clarification",
                                "questions": questions,
                                "reasoning": clarification_reasoning
                            }
                        }
                    )
                    
                    # Завершаем выполнение, так как нужны уточнения от пользователя
                    state.add_reasoning_step("plan", clarification_reasoning, {
                        "tool": "ASK_CLARIFICATION",
                        "questions": questions
                    })
                    clarification_action = state.add_action("ASK_CLARIFICATION", {"questions": questions})
                    state.add_observation(clarification_action, clarification_response, success=True)
                    
                    # Прерываем цикл - ждём ответа пользователя
                    break
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
                # Validate action through ActionFilter (blocks redundant file searches)
                validation_result = self.action_filter.validate(action_plan, context, file_ids)
                if not validation_result.allowed:
                    # Action blocked - use alternative or skip
                    logger.info(f"[UnifiedReActEngine] Action blocked: {validation_result.reason}")
                    
                    if validation_result.alternative:
                        alt = validation_result.alternative
                        
                        # If alternative is "use_attached_content", we have the content already
                        if alt.get("action") == "use_attached_content":
                            # Skip the tool call, use content directly
                            action_record = state.add_action(
                                "use_attached_content",
                                {"filename": alt.get("filename", ""), "content_available": True}
                            )
                            result = alt.get("content", "")
                            
                            # Add observation and continue
                            observation = state.add_observation(action_record, result, success=True)
                            await self._stream_reasoning("react_observation", {
                                "result": f"Используется содержимое прикреплённого файла: {alt.get('filename', '')}",
                                "iteration": state.iteration
                            })
                            continue
                        else:
                            # Use alternative tool
                            action_plan = {
                                "tool_name": alt.get("tool_name", action_plan.get("tool_name")),
                                "arguments": alt.get("arguments", action_plan.get("arguments", {})),
                                "description": f"Заменено: {validation_result.reason}",
                                "reasoning": validation_result.reason
                            }
                            logger.info(f"[UnifiedReActEngine] Using alternative: {action_plan['tool_name']}")
                
                action_record = state.add_action(
                    action_plan.get("tool_name", "unknown"),
                    action_plan.get("arguments", {})
                )
                planned_tool = action_plan.get("tool_name", "unknown")
                
                # === Send iteration_action_start event for UI ===
                action_title = self._get_tool_display_name(planned_tool, action_plan.get("arguments", {}))
                await self.ws_manager.send_event(
                    self.session_id,
                    "iteration_action_start",
                    {
                        "intent_id": self._current_intent_id,
                        "iteration_number": state.iteration,
                        "title": action_title
                    }
                )
                
                _exec_action_start = time.time()
                try:
                    result = await self._execute_action(action_plan, context)
                    _exec_action_end = time.time()
                    
                    # === Send iteration_action_complete event for UI ===
                    result_summary = "Выполнено"
                    await self.ws_manager.send_event(
                        self.session_id,
                        "iteration_action_complete",
                        {
                            "intent_id": self._current_intent_id,
                            "iteration_number": state.iteration,
                            "result": result_summary
                        }
                    )
                except Exception as e:
                    _exec_action_end = time.time()
                    error_msg = str(e)
                    logger.error(f"[UnifiedReActEngine] Action execution failed: {error_msg}")
                    
                    # === Send iteration_action_complete event for UI (error case) ===
                    await self.ws_manager.send_event(
                        self.session_id,
                        "iteration_action_complete",
                        {
                            "intent_id": self._current_intent_id,
                            "iteration_number": state.iteration,
                            "result": f"Ошибка: {error_msg[:50]}..."
                        }
                    )
                    
                    # Проверяем, не пытается ли инструмент открыть уже загруженный файл
                    if planned_tool in ["open_file", "find_and_open_file", "workspace_open_file", "workspace_find_and_open_file"]:
                        # Проверяем, есть ли загруженные файлы
                        if file_ids and hasattr(context, 'uploaded_files') and context.uploaded_files:
                            attached_files = {fid: context.get_file(fid) for fid in file_ids if context.get_file(fid)}
                            if attached_files:
                                logger.warning(f"[UnifiedReActEngine] Tool {planned_tool} failed, but files are already attached: {list(attached_files.keys())}")
                                print(f"[UnifiedReActEngine] Tool {planned_tool} failed, but files are attached: {list(attached_files.keys())}", flush=True)
                                result = f"Ошибка: Файл уже прикреплён к запросу. Используй содержимое файла из секции 'ПРИКРЕПЛЕННЫЕ ФАЙЛЫ' выше. Не нужно открывать файл через инструменты - его текст уже доступен в контексте."
                            else:
                                result = f"Error: {error_msg}"
                        else:
                            result = f"Error: {error_msg}"
                    else:
                        result = f"Error: {error_msg}"
                
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
                
                # #region agent log - H5: analysis result check
                try:
                    with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                        import json as _json
                        f.write(_json.dumps({
                            "location": "unified_react_engine.py:1251",
                            "message": "H5: Analysis result for adapt decision",
                            "data": {
                                "is_goal_achieved": analysis.is_goal_achieved,
                                "is_success": analysis.is_success,
                                "is_error": analysis.is_error,
                                "progress": analysis.progress_toward_goal,
                                "next_action_suggestion": analysis.next_action_suggestion,
                                "iteration": state.iteration,
                                "tool_name": action_record.tool_name
                            },
                            "timestamp": __import__("time").time() * 1000,
                            "sessionId": self.session_id,
                            "hypothesisId": "H5"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                
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
                    import json as _json
                    state.add_reasoning_step("adapt", "Continuing with progress", {
                        "progress": analysis.progress_toward_goal
                    })
                    logger.info(f"[UnifiedReActEngine] Progress: {analysis.progress_toward_goal:.0%}")
            
            # Check if we exited due to ASK_CLARIFICATION (should return successfully with clarification response)
            if state.action_history and state.action_history[-1].tool_name == "ASK_CLARIFICATION":
                logger.info(f"[UnifiedReActEngine] Exiting after ASK_CLARIFICATION - awaiting user response")
                state.status = "awaiting_clarification"
                
                # Return successfully with clarification info
                return {
                    "status": "awaiting_clarification",
                    "goal": state.goal,
                    "iterations": state.iteration,
                    "actions_taken": len(state.action_history),
                    "clarification_requested": True,
                    "reasoning_trail": [
                        {
                            "iteration": step.iteration,
                            "type": step.step_type,
                            "content": step.content[:200] if step.content else ""
                        }
                        for step in state.reasoning_trail[-5:]
                    ]
                }
            
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
        finally:
            # Останавливаем SmartProgress в любом случае
            self.smart_progress.stop()
    
    async def _needs_tools(self, goal: str, context: ConversationContext, file_ids: Optional[List[str]] = None) -> bool:
        """
        Determine if the query needs tools or can be answered directly.
        
        Simple queries (greetings, simple questions) don't need tools.
        Complex queries (data retrieval, file operations) need tools.
        Also checks conversation context for follow-up queries.
        
        If files are attached and user asks about their content, we need to
        process them through _generate_final_answer which supports Vision API.
        """
        goal_lower = goal.lower().strip()
        
        # === Check if user is asking about attached files ===
        # Patterns like "что видишь?", "что на картинке?", "опиши файл", "что в файлах?"
        if file_ids and len(file_ids) > 0:
            content_question_patterns = [
                'видишь', 'видно', 'видиш', 'что это', 'что здесь', 'что там',
                'опиши', 'расскажи', 'объясни', 'проанализируй', 'анализируй',
                'что на', 'что в', 'о чём', 'о чем', 'содержимое', 'содержание',
                'картинк', 'изображени', 'фото', 'фотограф', 'снимк',
                'написано', 'прочитай', 'прочти', 'скажи что',
                'покажи что', 'расскажи что', 'describe', 'what is', 'what do you see'
            ]
            if any(pattern in goal_lower for pattern in content_question_patterns):
                logger.info(f"[UnifiedReActEngine] Files attached + content question detected - needs file analysis")
                return True
        
        # IMPORTANT: Check tool keywords FIRST before simple patterns
        # This prevents false matches like "пока" matching "покажи"
        # First, check if query contains tool keywords - if yes, it needs tools
        tool_keywords_early = [
            'найди', 'find', 'получи', 'get', 'выведи', 'show', 'покажи', 'открой', 'open',
            'возьми', 'take', 'прочитай', 'read', 'читай', 'посмотри', 'look',
            'создай', 'create', 'отправь', 'send', 'сохрани', 'save', 'запиши', 'write',
            'календар', 'calendar',  # Use stem 'календар' to match all Russian cases: календарь, календаря, календаре, etc.
            # Russian word forms for "встреча" (meeting) - all cases
            'встреч',  # Stem covers all forms: встреча, встречи, встречу, встречей, встречам, встречами, встречах
            'событи',  # Stem covers: события, событий, событие, etc.
            'events', 'meetings', 'event', 'meeting',
            'письма', 'emails', 'почта', 'mail',
            'таблица', 'table', 'sheets', 'документ', 'document', 'файл', 'file',
            'данные', 'data', 'текст', 'text',  # "текст" in context of files/documents needs tools
            'список', 'list', 'действий', 'actions', 'персонаж', 'character', 'персонажей', 'characters',
            # 1C / Accounting keywords
            'проводк', '1с', '1c', 'бухгалтер', 'выручк', 'остатк', 'склад',
            # Project Lad keywords
            'проект', 'портфел', 'гант', 'вех', 'работ', 'project lad', 'projectlad',
            # NEW - расширенные ключевые слова для покрытия 80% запросов
            'статистик', 'отчет', 'отчёт', 'report', 'статистика',
            'сравни', 'compare', 'сравнение', 'comparison',
            'проанализируй', 'analyze', 'анализ', 'analysis',
            'подготовь', 'prepare', 'составь', 'составить',
            'выгрузи', 'export', 'импортируй', 'import', 'импорт',
            'обнови', 'update', 'измени', 'change', 'изменение',
            'удали', 'delete', 'очисти', 'clear', 'удаление',
            'скопируй', 'copy', 'перенеси', 'move', 'перемести',
            # Document formatting keywords - CRITICAL for formatting tasks
            'отформатируй', 'форматируй', 'format', 'оформи', 'оформить',
            'красиво', 'красив',  # "красиво оформить", "сделай красиво"
            'отредактируй', 'редактируй', 'edit', 'выдели', 'highlight',
            'жирн', 'bold', 'курсив', 'italic', 'подчеркн', 'underline',
        ]
        
        for keyword in tool_keywords_early:
            if keyword in goal_lower:
                return True
        
        # Simple greetings and basic questions - no tools needed
        # Check AFTER tool keywords to avoid false matches (e.g., "пока" in "покажи")
        simple_patterns = [
            r'^(привет|hello|hi|здравствуй|здравствуйте|добрый\s+(день|вечер|утро))',
            r'^(спасибо|thanks|thank\s+you|благодарю)',
            r'^(как\s+дела|how\s+are\s+you|что\s+ты|who\s+are\s+you|что\s+умеешь)',
            r'^(пока|bye|goodbye|до\s+свидания)$',  # Use $ to match end of string, not just start
        ]
        
        for pattern in simple_patterns:
            if re.match(pattern, goal_lower):
                log_data = {
                    "location": "unified_react_engine.py:535",
                    "message": "_needs_tools: simple pattern matched - returning False",
                    "data": {"pattern": pattern, "goal": goal},
                    "timestamp": time.time() * 1000,
                    "sessionId": self.session_id,
                    "runId": "run1",
                    "hypothesisId": "H_NEEDS_TOOLS"
                }
                try:
                        f.write(json.dumps(log_data, default=str) + "\n")
                except Exception:
                    pass
                return False
        
        # Check for simple generative patterns (poems, jokes, greetings, etc.) - no tools needed
        # IMPORTANT: Only match if these are CREATIVE tasks WITHOUT external data requirements
        # Patterns that mention files, documents, tables should NOT match here
        simple_generative_patterns = [
            # Only match standalone creative requests WITHOUT file/table context
            r"(напиши|составь|сочини|придумай)\s+(мне\s+)?(краткое\s+)?(поздравление|стих|стихотворение|шутку|анекдот|письмо|хокку|хайку|haiku|рассказ|историю|песню)(?!.*(файл|документ|таблиц|текст\s+файл|текст\s+документ|из\s+файл|из\s+документ|в\s+таблиц|возьми|прочитай|открой|найди))",
            r"(напиши|составь|сочини|придумай)\s+\w*\s*(хокку|хайку|haiku)(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ|возьми|прочитай))",
            r"write\s+(me\s+)?(a\s+)?(greeting|poem|joke|message|story|haiku)(?!.*(file|document|table|from\s+file|from\s+document|in\s+table|read|open|find|take))",
            # Direct creative requests (standalone, no context)
            r"^(хокку|хайку|haiku|стих|анекдот|шутка)$",
            # Only match very short creative requests like "напиши хокку" without any file/table context
            r"^(напиши|составь|сочини|придумай)\s+(хокку|хайку|haiku|стих|анекдот|шутку|рассказ|историю|песню)$",
            # NEW - творческие задачи без инструментов
            r"^(объясни|explain)\s+(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ))",
            r"^(переведи|translate)\s+(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ))",
            r"^(перефразируй|rephrase)\s+(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ))",
            r"^(суммируй|summarize)\s+(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ))",
            r"^(ответь|answer)\s+на\s+вопрос(?!.*(файл|документ|таблиц|из\s+файл|из\s+документ))",
        ]
        
        for pattern in simple_generative_patterns:
            match = re.search(pattern, goal_lower)
            if match:
                log_data = {
                    "location": "unified_react_engine.py:588",
                    "message": "_needs_tools: generative pattern matched - returning False",
                    "data": {"pattern": pattern, "goal": goal, "matched_text": match.group(0)},
                    "timestamp": time.time() * 1000,
                    "sessionId": self.session_id,
                    "runId": "run1",
                    "hypothesisId": "H_NEEDS_TOOLS"
                }
                try:
                        f.write(json.dumps(log_data, default=str) + "\n")
                except Exception:
                    pass
                return False
        
        # Check for specific calendar-related patterns
        calendar_patterns = [
            r'список\s+встреч',  # "список встреч" (list of meetings)
            r'встреч[аи]?\s+на\s+(этой|следующей|прошлой)\s+неделе',  # "встречи на этой неделе"
            r'встреч[аи]?\s+(на\s+)?(сегодня|завтра|послезавтра)',  # "встречи сегодня", "встречи на завтра"
            r'расписание\s+(на|на\s+этой)',  # "расписание на этой неделе"
            r'покажи\s+встреч',  # "покажи встречи"
            r'(в|на)\s+календар',  # "в календаре", "на календаре" - all cases
            r'(что|какие|сколько).*(на\s+)?(этой|следующей|прошлой)\s+неделе.*(в\s+)?календар',  # "что на этой неделе в календаре"
            r'событи.*(на\s+)?(этой|следующей|прошлой)\s+неделе',  # "события на этой неделе"
        ]
        
        for pattern in calendar_patterns:
            if re.search(pattern, goal_lower):
                log_data = {
                    "location": "unified_react_engine.py:578",
                    "message": "_needs_tools: calendar pattern matched - returning True",
                    "data": {"pattern": pattern, "goal": goal},
                    "timestamp": time.time() * 1000,
                    "sessionId": self.session_id,
                    "runId": "run1",
                    "hypothesisId": "H_NEEDS_TOOLS"
                }
                try:
                        f.write(json.dumps(log_data, default=str) + "\n")
                except Exception:
                    pass
                return True
        
        # === NEW: Check for follow-up/clarification queries that reference previous context ===
        # These patterns indicate user is asking for more info about a previous topic
        followup_patterns = [
            r'^а\s+(на|в|за|что|как|где|когда|сколько)',  # "а на следующей неделе?", "а в понедельник?"
            r'^(а|и|еще|ещё|также|тоже)\s',  # "а ...", "еще покажи", "также ..."
            r'^(на|в|за)\s+(следующ|прошл|эт)',  # "на следующей неделе", "в прошлый раз"
            r'(следующ|прошл|предыдущ)\s*(недел|месяц|день|год)',  # "следующей неделе", "прошлом месяце"
            r'^(что|какие|сколько)\s+(там|еще|ещё)',  # "что там еще?"
            r'^(покажи|выведи|дай)\s+(еще|ещё|больше|другие)',  # "покажи еще", "дай больше"
        ]
        
        is_followup = any(re.search(pattern, goal_lower) for pattern in followup_patterns)
        
        # If it looks like a follow-up, check previous context for tool-related topics
        if is_followup and hasattr(context, 'messages') and context.messages:
            recent_messages = context.get_recent_messages(6)  # Last 3 exchanges
            
            # Context keyword groups for different tool categories
            context_keyword_groups = {
                'calendar': ['встреч', 'календар', 'событи', 'расписани', 'meeting', 'event', 'calendar', 'schedule'],
                'email': ['письм', 'почт', 'email', 'mail', 'сообщени'],
                'files': ['файл', 'документ', 'file', 'document'],
                'sheets': ['таблиц', 'sheet', 'spreadsheet', 'ячейк', 'столбц', 'строк'],
                'accounting': ['проводк', '1с', '1c', 'бухгалтер', 'выручк', 'остатк', 'склад', 'учет', 'учёт', 'odata'],
                'projectlad': ['проект', 'портфел', 'гант', 'вех', 'работ', 'project lad', 'projectlad', 'pl', 'пл', 'диаграмм']
            }
            
            # Check recent messages for context
            for msg in recent_messages:
                msg_content = msg.get('content', '').lower()
                
                for category, keywords in context_keyword_groups.items():
                    if any(kw in msg_content for kw in keywords):
                        logger.info(f"[UnifiedReActEngine] Follow-up detected with {category} context")
                        return True
        
        # Use LLM to determine if tools are needed (for edge cases)
        # NOW with context!
        try:
            # Build context string from recent messages
            context_str = ""
            if hasattr(context, 'messages') and context.messages:
                recent = context.get_recent_messages(4)
                if recent:
                    context_str = "\n\nКонтекст предыдущих сообщений:\n"
                    for msg in recent:
                        role = "Пользователь" if msg.get('role') == 'user' else "Ассистент"
                        content = msg.get('content', '')[:200]  # Truncate
                        context_str += f"{role}: {content}\n"
            
            prompt = f"""Определи, нужны ли ВНЕШНИЕ инструменты для ответа на этот запрос:

Запрос: "{goal}"
{context_str}

Ответь только одним словом: ДА или НЕТ.

НЕТ - если это:
- Простой вопрос, приветствие, благодарность
- ТВОРЧЕСКАЯ просьба: написать стих, хокку, рассказ, шутку, историю, сочинить текст
- Любая генеративная задача, которую можно выполнить БЕЗ внешних данных

ДА - если нужны ВНЕШНИЕ данные из:
- Календарь: "найди встречи", "покажи события на неделе"
- Почта: "покажи письма", "непрочитанные сообщения"  
- Файлы: "открой файл", "найди документ"
- Таблицы: "данные из таблицы", "значения в ячейках"
- 1С/Бухгалтерия: "проводки", "остатки на складах", "выручка"
- Project Lad: "проекты", "портфель", "диаграмма ганта", "вехи"

ВАЖНО: 
- Если это УТОЧНЯЮЩИЙ вопрос (например "а на следующей неделе?", "а за прошлый месяц?", "еще покажи") 
  и в КОНТЕКСТЕ обсуждались встречи/письма/файлы/таблицы/проводки/проекты - это ДА, нужны те же инструменты.
- Короткие уточнения типа "а вчера?", "а там?" относятся к предыдущей теме разговора."""
            
            messages = [
                SystemMessage(content="Ты эксперт по определению необходимости использования инструментов. Учитывай контекст разговора. Отвечай только ДА или НЕТ."),
                HumanMessage(content=prompt)
            ]
            
            # Use fast LLM (no extended thinking) for quick classification
            response = await self.fast_llm.ainvoke(messages)
            response_text = str(response.content).strip().upper()
            
            llm_result = "ДА" in response_text or "YES" in response_text
            
            log_data = {
                "location": "unified_react_engine.py:669",
                "message": "_needs_tools: LLM decision",
                "data": {
                    "goal": goal,
                    "llm_response": response_text,
                    "llm_result": llm_result
                },
                "timestamp": time.time() * 1000,
                "sessionId": self.session_id,
                "runId": "run1",
                "hypothesisId": "H_NEEDS_TOOLS"
            }
            try:
                    f.write(json.dumps(log_data, default=str) + "\n")
            except Exception:
                pass
            return llm_result
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error checking if tools needed: {e}")
            log_data = {
                "location": "unified_react_engine.py:673",
                "message": "_needs_tools: error occurred, defaulting to True",
                "data": {"goal": goal, "error": str(e)},
                "timestamp": time.time() * 1000,
                "sessionId": self.session_id,
                "runId": "run1",
                "hypothesisId": "H_NEEDS_TOOLS"
            }
            try:
                    f.write(json.dumps(log_data, default=str) + "\n")
            except Exception:
                pass
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
        Properly passes conversation history for reference resolution.
        """
        try:
            # Check if model uses extended thinking
            uses_extended_thinking = False
            try:
                from src.agents.model_factory import get_available_models
                available_models = get_available_models()
                if self.model_name and self.model_name in available_models:
                    model_config = available_models[self.model_name]
                    if model_config.get("reasoning_type") == "extended_thinking":
                        uses_extended_thinking = True
            except:
                pass
            
            # Build messages list with proper conversation history
            messages = [
                SystemMessage(content="""Ты дружелюбный и полезный AI-ассистент. 
Отвечай естественно и кратко на русском языке.
Учитывай контекст предыдущих сообщений в разговоре.
Если пользователь ссылается на что-то из предыдущих сообщений (например "переделай его", "сделай еще"), используй информацию из истории разговора.""")
            ]
            
            # Add conversation history as proper messages (for reference resolution)
            if hasattr(context, 'messages') and context.messages:
                recent_messages = context.messages[-6:]  # Last 6 messages (3 exchanges)
                for msg in recent_messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if not content:
                        continue
                    
                    if role == 'user':
                        messages.append(HumanMessage(content=content))
                    elif role == 'assistant':
                        # For extended thinking models, wrap as HumanMessage to avoid API errors
                        if uses_extended_thinking:
                            messages.append(HumanMessage(
                                content=f"[Предыдущий ответ ассистента]:\n{content}"
                            ))
                        else:
                            messages.append(AIMessage(content=content))
            
            # Add current user request
            messages.append(HumanMessage(content=goal))
            
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
            # Agent mode uses final_result like query mode (UI expects workflow.finalResult)
            if self.config.mode in ("query", "agent"):
                await self.ws_manager.send_event(
                    self.session_id,
                    "final_result",
                    {"content": answer}
                )
            else:
                # Plan mode uses message_complete
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
            
            # Save response to context for follow-up reference resolution
            if hasattr(context, 'add_message'):
                extracted_entities = extract_entities_from_response(answer)
                context.add_message(
                    "assistant",
                    answer,
                    metadata={
                        "source_files": [],  # No files used in direct answer
                        "extracted_entities": extracted_entities,
                        "goal": goal
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
        interval: float = 5.0
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
    
    def _get_task_intents(self, goal: str) -> List[str]:
        """
        Generate context-dependent intent messages based on task type.
        
        Instead of generic fake messages like "Изучаю контекст запроса...",
        returns relevant intents for the specific task.
        
        Args:
            goal: User's request/goal
            
        Returns:
            List of relevant intent descriptions
        """
        goal_lower = goal.lower()
        
        # Calendar / Meetings
        if any(w in goal_lower for w in ['встреч', 'событ', 'календар', 'meeting', 'schedule', 'запланир']):
            if any(w in goal_lower for w in ['создай', 'запланир', 'сделай', 'назначь', 'добавь']):
                return ["Определяю участников", "Проверяю календарь", "Создаю встречу"]
            return ["Получаю события из календаря"]
        
        # Email / Gmail
        elif any(w in goal_lower for w in ['письм', 'почт', 'email', 'gmail', 'mail']):
            if any(w in goal_lower for w in ['отправ', 'напиш', 'написать']):
                return ["Составляю письмо", "Отправляю"]
            return ["Ищу письма"]
        
        # Sheets / Data
        elif any(w in goal_lower for w in ['таблиц', 'sheet', 'excel', 'данны']):
            if any(w in goal_lower for w in ['запиш', 'добав', 'измен', 'обнов']):
                return ["Подготавливаю данные", "Записываю в таблицу"]
            return ["Запрашиваю данные из таблицы"]
        
        # Files / Documents
        elif any(w in goal_lower for w in ['файл', 'документ', 'открой', 'найди файл']):
            return ["Ищу файлы"]
        
        # 1C / Accounting
        elif any(w in goal_lower for w in ['1с', '1c', 'проводк', 'остатк', 'бухгалтер', 'склад']):
            return ["Запрашиваю данные из 1С"]
        
        # Project management
        elif any(w in goal_lower for w in ['проект', 'задач', 'project', 'task']):
            return ["Получаю информацию о проекте"]
        
        # Default - simple intent without fake progress
        return ["Обрабатываю запрос"]
    
    def _generate_task_description(self, goal: str, file_ids: Optional[List[str]] = None) -> str:
        """
        Generate a high-level task description for the task-level intent.
        
        This is shown as the main intent header (Cursor-style).
        Unlike per-iteration intents, this describes the entire task goal.
        
        Args:
            goal: User's request/goal
            file_ids: Optional list of attached file IDs
            
        Returns:
            Human-readable task description
        """
        goal_lower = goal.lower()
        
        # Questions about attached files - show meaningful description
        content_patterns = [
            'видишь', 'видно', 'видиш', 'что это', 'что здесь', 'что там',
            'опиши', 'расскажи', 'объясни', 'проанализируй',
            'что на', 'что в', 'о чём', 'о чем', 'содержимое',
            'картинк', 'изображени', 'фото', 'написано', 'прочитай'
        ]
        if file_ids and len(file_ids) > 0 and any(p in goal_lower for p in content_patterns):
            return "Анализирую содержимое файлов"
        
        # Calendar / Meetings - use goal directly if it's specific
        if any(w in goal_lower for w in ['встреч', 'событ', 'календар', 'meeting']):
            if any(w in goal_lower for w in ['создай', 'запланир', 'назначь']):
                # Extract email if present
                import re
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', goal)
                if email_match:
                    return f"Создание встречи с {email_match.group()}"
                return "Создание встречи"
            return "Получение событий календаря"
        
        # Email
        elif any(w in goal_lower for w in ['письм', 'почт', 'email', 'gmail']):
            if any(w in goal_lower for w in ['отправ', 'напиш']):
                return "Отправка письма"
            return "Поиск писем"
        
        # Data / Sheets
        elif any(w in goal_lower for w in ['таблиц', 'sheet', 'данны']):
            return "Работа с таблицей"
        
        # Files
        elif any(w in goal_lower for w in ['файл', 'документ']):
            return "Поиск файлов"
        
        # 1C
        elif any(w in goal_lower for w in ['1с', '1c']):
            return "Запрос к 1С"
        
        # Default - truncate goal if too long
        if len(goal) > 60:
            return goal[:57] + "..."
        return goal
    
    def _analyze_task_phases(self, goal: str) -> List[Dict[str, Any]]:
        """
        Analyze goal to identify multiple logical phases.
        
        Returns list of phases if task is multi-step, or empty list for single-step.
        Each phase has: {name, description, keywords, category}
        
        Args:
            goal: User's request/goal
            
        Returns:
            List of phases or empty list if single-step task
        """
        goal_lower = goal.lower()
        phases = []
        
        # Define phase categories with their detection keywords
        # IMPORTANT: Order matters - more specific patterns should come first
        phase_definitions = [
            {
                'name': 'data_1c',
                # REMOVED 'зарплат' and 'сотрудник' - too ambiguous, can appear in table names
                # Only detect 1C when explicitly mentioned or with accounting context
                'keywords': ['1с', '1c', 'бухгалтер', 'odata'],
                'description': '📊 Получение данных из 1С',
                'category': 'accounting',
                'context_exclude': ['запиш', 'запиши', 'создай', 'таблиц', 'в таблиц']  # If these words present, NOT 1C read
            },
            {
                'name': 'email_read',
                'keywords': ['письм', 'почт', 'email', 'gmail', 'inbox', 'найди письм'],
                'description': '📧 Поиск и чтение писем',
                'category': 'email_read'
            },
            {
                'name': 'email_send',
                'keywords': ['отправ', 'напиш', 'send', 'подтвержд'],
                'description': '📧 Отправка письма',
                'category': 'email_send'
            },
            {
                'name': 'calendar_read',
                'keywords': ['покажи встреч', 'событ', 'свободн', 'занят', 'calendar'],
                'description': '📅 Проверка календаря',
                'category': 'calendar_read'
            },
            {
                'name': 'calendar_create',
                'keywords': ['создай встреч', 'запланир', 'назначь', 'забронир', 'создай задач'],
                'description': '📅 Создание события',
                'category': 'calendar_create'
            },
            {
                'name': 'sheets_write',
                'keywords': ['запиш', 'запиши', 'записать', 'запиш', 'запись в', 'в таблиц', 'записать в таблиц'],
                'description': '📋 Запись в таблицу',
                'category': 'sheets_write'
            },
            {
                'name': 'sheets_create',
                'keywords': ['создай таблиц', 'новую таблиц', 'create sheet'],
                'description': '📋 Создание таблицы',
                'category': 'sheets_create'
            },
            {
                'name': 'sheets_read',
                'keywords': ['таблиц', 'sheet', 'получи данны', 'читай таблиц', 'читай sheet'],
                'description': '📋 Чтение таблицы',
                'category': 'sheets_read'
            },
            {
                'name': 'code_execute',
                'keywords': ['код', 'python', 'питон', 'script', 'расчет', 'вычисл', 'скрипт'],
                'description': '🐍 Выполнение кода',
                'category': 'code'
            },
            {
                'name': 'chart_create',
                'keywords': ['диаграмм', 'график', 'chart', 'graph', 'визуализ', 'постро'],
                'description': '📈 Создание графика',
                'category': 'visualization'
            },
            {
                'name': 'file_search',
                'keywords': ['файл', 'документ', 'найди', 'открой', 'текст', 'сказк', 'возьми текст', 'читай документ', 'read_document'],
                'description': '📁 Поиск и чтение файлов',
                'category': 'files'
            },
        ]
        
        # Detect which phases are present in the goal
        matched_keywords = {}
        for phase_def in phase_definitions:
            matched_kw = [kw for kw in phase_def['keywords'] if kw in goal_lower]
            if matched_kw:
                # Context exclusion check: if phase has context_exclude and any of those words present, skip
                if 'context_exclude' in phase_def:
                    if any(exclude_kw in goal_lower for exclude_kw in phase_def['context_exclude']):
                        # Skip this phase - context indicates it's not applicable
                        continue
                
                phases.append({
                    'name': phase_def['name'],
                    'description': phase_def['description'],
                    'category': phase_def['category'],
                    'keywords': phase_def['keywords']
                })
                matched_keywords[phase_def['name']] = matched_kw
        # Check for explicit multi-step patterns
        explicit_multi_step = any(pattern in goal_lower for pattern in [
            'по очереди', 'потом', 'затем', 'далее', 'после этого',
            'шаг 1', 'шаг 2', '1.', '2.', '1)', '2)',
            'сначала', 'в первую очередь', 'во-первых',
        ])
        
        # Only return phases if:
        # 1. Multiple different categories detected, OR
        # 2. Explicit multi-step pattern found
        unique_categories = set(p['category'] for p in phases)
        if len(unique_categories) >= 2 or (explicit_multi_step and len(phases) >= 1):
            # Remove duplicates within same category, keep first
            seen_categories = set()
            unique_phases = []
            for phase in phases:
                if phase['category'] not in seen_categories:
                    seen_categories.add(phase['category'])
                    unique_phases.append(phase)
            
            # Sort phases by order of appearance in goal (earliest keyword first)
            def get_first_keyword_position(phase):
                positions = []
                for kw in phase['keywords']:
                    pos = goal_lower.find(kw)
                    if pos >= 0:
                        positions.append(pos)
                return min(positions) if positions else 9999
            
            unique_phases.sort(key=get_first_keyword_position)
            
            return unique_phases
        
        return []  # Single-step task
    
    def _get_tool_category(self, tool_name: str) -> str:
        """
        Get category of a tool for phase tracking.
        
        Args:
            tool_name: Internal tool name
            
        Returns:
            Category string (e.g., 'email', 'calendar', 'sheets', 'accounting', 'code')
        """
        tool_categories = {
            # 1C / Accounting
            'onec_get_data': 'accounting',
            'onec_execute_query': 'accounting',
            'onec_list_catalogs': 'accounting',
            
            # Email
            'gmail_search': 'email_read',
            'gmail_get_message': 'email_read',
            'gmail_list_messages': 'email_read',
            'gmail_send_email': 'email_send',
            
            # Calendar
            'calendar_list_events': 'calendar_read',
            'calendar_get_event': 'calendar_read',
            'calendar_create_event': 'calendar_create',
            'calendar_update_event': 'calendar_create',
            'calendar_delete_event': 'calendar_create',
            
            # Sheets - MCP tool names
            'sheets_create': 'sheets_create',
            'sheets_read_range': 'sheets_read',
            'sheets_write_range': 'sheets_write',
            'sheets_batch_update': 'sheets_write',
            # Sheets - LangChain tool names (actual names used by LLM)
            'get_sheet_data': 'sheets_read',
            'add_rows': 'sheets_write',
            'update_cells': 'sheets_write',
            'create_spreadsheet': 'sheets_create',
            'get_spreadsheet_info': 'sheets_read',
            'format_cells': 'sheets_write',
            'auto_resize_columns': 'sheets_write',
            'merge_cells': 'sheets_write',
            
            # Code execution
            'code_execute': 'code',
            'python_execute': 'code',
            'execute_python': 'code',
            
            # Files / Documents
            'workspace_search_files': 'files',
            'drive_search': 'files',
            'drive_get_file': 'files',
            'find_and_open_file': 'files',
            'file_search': 'files',
            'read_document': 'files',  # Google Docs reading
            'docs_read': 'files',
            
            # Document operations (Google Docs)
            'update_document': 'docs_write',
            'insert_into_document': 'docs_write',
            'append_to_document': 'docs_write',
            'format_document_text': 'docs_format',
            'format_document_paragraph': 'docs_format',
            
            # Charts / Visualization
            'create_chart': 'visualization',
            'slides_create': 'visualization',
        }
        
        # Normalize tool name and check
        tool_lower = tool_name.lower()
        
        # Direct match
        if tool_lower in tool_categories:
            return tool_categories[tool_lower]
        
        # Prefix match
        for key, category in tool_categories.items():
            if tool_lower.startswith(key.split('_')[0]):
                return category
        
        return 'general'
    
    def _get_phase_description_for_category(self, category: str) -> str:
        """Get human-readable phase description for a tool category."""
        category_descriptions = {
            'accounting': '📊 Получение данных из 1С',
            'email_read': '📧 Поиск и чтение писем',
            'email_send': '📧 Отправка письма',
            'calendar_read': '📅 Проверка календаря',
            'calendar_create': '📅 Создание события',
            'sheets_create': '📋 Создание таблицы',
            'sheets_read': '📋 Чтение таблицы',
            'sheets_write': '📋 Запись в таблицу',
            'files': '📁 Поиск и чтение файлов',
            'docs_write': '📄 Обновление документа',
            'docs_format': '📄 Форматирование документа',
            'code': '🐍 Выполнение кода',
            'visualization': '📈 Создание графика',
            'files': '📁 Поиск файлов',
        }
        return category_descriptions.get(category, '⚙️ Выполнение действия')
    
    def _is_compound_task(self, goal: str) -> tuple[bool, list[str]]:
        """
        Определяет, является ли задача составной (несколько операций).
        Возвращает (is_compound, phases) где phases = ['modify', 'format'] и т.д.
        
        Args:
            goal: Текст цели задачи
            
        Returns:
            Tuple[bool, list[str]]: (is_compound, phases)
        """
        goal_lower = goal.lower()
        
        # Паттерны модификации контента
        modify_keywords = ["допиши", "добавь", "напиши", "вставь", "создай", "append", "insert", "add"]
        has_modify = any(kw in goal_lower for kw in modify_keywords)
        
        # Паттерны форматирования
        format_keywords = ["форматир", "красиво", "оформи", "format"]
        has_format = any(kw in goal_lower for kw in format_keywords)
        
        phases = []
        if has_modify:
            phases.append("modify")
        if has_format:
            phases.append("format")
        
        return (len(phases) > 1, phases)
    
    def _get_document_length_from_observations(self, state: ReActState) -> int:
        """
        Получает длину документа из предыдущих наблюдений read_document.
        
        Args:
            state: Текущее состояние ReAct
            
        Returns:
            Длина документа в символах, или 100 по умолчанию
        """
        import re
        for obs in state.observations:
            if obs.action.tool_name == "read_document" and obs.success:
                # Парсим TEXT_LENGTH из результата
                result_str = str(obs.raw_result)
                match = re.search(r'TEXT_LENGTH:\s*(\d+)', result_str)
                if match:
                    return int(match.group(1))
                # Альтернативный паттерн: ищем в формате "[TEXT_LENGTH: X characters]"
                match = re.search(r'\[TEXT_LENGTH:\s*(\d+)', result_str)
                if match:
                    return int(match.group(1))
        return 100  # fallback
    
    def _get_document_text_from_observations(self, state: ReActState) -> Optional[str]:
        """
        Получает текст документа из предыдущих наблюдений read_document.
        
        Returns:
            Текст документа или None
        """
        for obs in state.observations:
            if obs.action.tool_name == "read_document" and obs.success:
                result_str = str(obs.raw_result)
                # Убираем метаданные и оставляем только текст
                # Формат: "Document content:\n\n{text}\n\n[TEXT_LENGTH: N characters]"
                if "Document content:" in result_str:
                    text = result_str.split("Document content:", 1)[1]
                    # Убираем [TEXT_LENGTH: ...] в конце
                    import re
                    text = re.sub(r'\[TEXT_LENGTH:\s*\d+\s*characters?\]', '', text)
                    return text.strip()
                return result_str
        return None
    
    async def _get_smart_formatting_ranges(self, document_text: str, doc_length: int) -> list:
        """
        Использует fast_llm для определения какие части текста выделить жирным.
        
        Args:
            document_text: Текст документа
            doc_length: Длина документа
            
        Returns:
            Список диапазонов для выделения жирным: [{"start": N, "end": M, "reason": "..."}]
        """
        # Ограничиваем текст для анализа
        text_for_analysis = document_text[:2000] if len(document_text) > 2000 else document_text
        
        prompt = f"""Проанализируй текст и определи какие части нужно выделить жирным шрифтом.

Текст:
{text_for_analysis}

Выдели жирным:
1. Заголовок (первая строка если это заголовок)
2. Ключевые мысли или выводы
3. Важные термины или понятия

Ответь ТОЛЬКО JSON массивом (без markdown):
[{{"start": 1, "end": N, "reason": "заголовок"}}]

Где start и end - позиции символов (начиная с 1).
Максимум 3-4 диапазона. Если заголовок очевиден - достаточно только его."""

        try:
            from langchain_core.messages import HumanMessage
            response = await self.fast_llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Парсим JSON
            import json
            import re
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                ranges = json.loads(json_match.group(0))
                # Валидация
                valid_ranges = []
                for r in ranges:
                    if isinstance(r, dict) and "start" in r and "end" in r:
                        start = max(1, int(r["start"]))
                        end = min(doc_length, int(r["end"]))
                        if end > start:
                            valid_ranges.append({"start": start, "end": end, "reason": r.get("reason", "")})
                return valid_ranges if valid_ranges else [{"start": 1, "end": min(doc_length, 100), "reason": "fallback"}]
            
        except Exception as e:
            logger.warning(f"[UnifiedReActEngine] Smart formatting failed: {e}")
        
        # Fallback: первая строка как заголовок
        first_newline = document_text.find('\n')
        if first_newline > 0 and first_newline < 200:
            return [{"start": 1, "end": first_newline, "reason": "first_line"}]
        return [{"start": 1, "end": min(doc_length, 100), "reason": "fallback"}]
    
    def _get_short_action_title(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        """
        Get short title for step header based on first action.
        
        Args:
            tool_name: Tool name
            args: Tool arguments
            
        Returns:
            Short title like "📄 Чтение документа" or None
        """
        title_map = {
            'read_document': '📄 Чтение документа',
            'append_to_document': '📝 Добавление текста',
            'insert_into_document': '📝 Вставка текста',
            'update_document': '📄 Обновление документа',
            'format_document_text': '✨ Форматирование документа',
            'format_document_paragraph': '✨ Форматирование абзаца',
            'get_calendar_events': '📅 Получение событий',
            'create_calendar_event': '📅 Создание встречи',
            'list_emails': '📧 Чтение писем',
            'search_emails': '📧 Поиск писем',
            'get_sheet_data': '📊 Чтение таблицы',
            'add_rows': '📊 Запись в таблицу',
            'workspace_search_files': '📁 Поиск файлов',
        }
        return title_map.get(tool_name)
    
    def _get_tool_display_name(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Get human-readable display name for tool execution.
        
        Converts internal tool names to user-friendly descriptions.
        
        Args:
            tool_name: Internal tool name (e.g., "calendar_list_events")
            args: Tool arguments
            
        Returns:
            Human-readable description (e.g., "📅 Получаю события из календаря")
        """
        tool_map = {
            # Calendar
            'calendar_list_events': '📅 Получаю события из календаря',
            'calendar_create_event': '📅 Создаю встречу',
            'calendar_update_event': '📅 Обновляю событие',
            'calendar_delete_event': '📅 Удаляю событие',
            'calendar_get_event': '📅 Получаю информацию о событии',
            
            # Gmail
            'gmail_search': '📧 Ищу письма',
            'gmail_send_email': '📧 Отправляю письмо',
            'gmail_get_message': '📧 Читаю письмо',
            'gmail_list_messages': '📧 Получаю список писем',
            
            # Sheets
            'sheets_read_range': '📊 Читаю данные из таблицы',
            'sheets_write_range': '📊 Записываю данные в таблицу',
            'sheets_append_rows': '📊 Добавляю строки в таблицу',
            'sheets_get_spreadsheet': '📊 Получаю информацию о таблице',
            
            # Docs
            'docs_read': '📄 Читаю документ',
            'docs_create': '📄 Создаю документ',
            'docs_update': '📄 Обновляю документ',
            
            # Files / Workspace
            'workspace_search_files': '📁 Ищу файлы',
            'workspace_find_and_open_file': '📁 Открываю файл',
            'workspace_get_file_info': '📁 Получаю информацию о файле',
            
            # Slides
            'slides_create': '🎨 Создаю презентацию',
            'slides_create_slide': '🎨 Добавляю слайд',
            
            # 1C
            'onec_get_data': '🏢 Запрашиваю данные из 1С',
            'onec_query': '🏢 Выполняю запрос к 1С',
        }
        
        # Get base action name
        base_name = tool_map.get(tool_name)
        
        if not base_name:
            # Fallback: convert snake_case to readable format
            readable = tool_name.replace('_', ' ').title()
            base_name = f"🔧 {readable}"
        
        # Add context from arguments if available
        if 'query' in args:
            query = str(args['query'])
            if len(query) < 40:
                return f"{base_name} «{query}»"
        elif 'summary' in args:
            summary = str(args['summary'])
            if len(summary) < 40:
                return f"{base_name} «{summary}»"
        elif 'title' in args:
            title = str(args['title'])
            if len(title) < 40:
                return f"{base_name} «{title}»"
        elif 'attendees' in args:
            attendees = args['attendees']
            if isinstance(attendees, list) and attendees:
                first_attendee = str(attendees[0])
                if '@' in first_attendee:
                    return f"{base_name} с {first_attendee}"
        
        return base_name
    
    def _get_result_summary(self, tool_name: str, result: Any) -> Optional[str]:
        """
        Generate human-readable summary of tool execution result.
        
        Args:
            tool_name: Name of the executed tool
            result: Result from tool execution
            
        Returns:
            Summary string or None if no meaningful summary
        """
        if result is None:
            return None
            
        result_str = str(result)
        
        # Check for error indicators
        if any(err in result_str.lower() for err in ['error', 'ошибка', 'не удалось', 'failed', 'не найден']):
            # Extract first line of error
            first_line = result_str.split('\n')[0][:80]
            return f"❌ {first_line}"
        
        # Check for success indicators
        if any(ok in result_str.lower() for ok in ['создан', 'created', 'успешно', 'success', 'найден', 'found']):
            first_line = result_str.split('\n')[0][:80]
            return f"✅ {first_line}"
        
        # Tool-specific summaries
        if 'calendar' in tool_name:
            if 'events' in result_str.lower() or 'событий' in result_str.lower():
                return f"✅ Получены данные календаря"
            if 'slot' in result_str.lower() or 'слот' in result_str.lower():
                return f"✅ Найден свободный слот"
        
        if 'gmail' in tool_name or 'email' in tool_name:
            if 'отправлено' in result_str.lower() or 'sent' in result_str.lower():
                return f"✅ Письмо отправлено"
            return f"✅ Получены данные почты"
        
        if 'sheets' in tool_name:
            return f"✅ Данные таблицы получены"
        
        # Generic success for non-empty result
        if len(result_str) > 10:
            return f"✅ Выполнено"
        
        return None
    
    class StreamingThoughtParser:
        """Парсит thought из стрима и отправляет по WebSocket.
        
        Также отправляет intent_detail события если передан intent_id,
        что позволяет показывать thinking в UI как часть intent блока.
        
        Стримит iteration_thinking_chunk для IterationBlock UI.
        """
        
        def __init__(self, ws_manager: WebSocketManager, session_id: str, intent_id: Optional[str] = None, iteration_number: int = 1):
            self.ws_manager = ws_manager
            self.session_id = session_id
            self.intent_id = intent_id  # Для отправки intent_thinking_append
            self.iteration_number = iteration_number  # Для iteration_thinking_chunk
            self.buffer = ""
            self.thought_started = False
            self.thought_complete = False
            self.thought_content = ""
            self.thinking_id = f"thinking_{session_id}_{int(time.time() * 1000)}"
        
        async def process_chunk(self, chunk: str) -> None:
            """Обрабатывает chunk, извлекает thought и стримит.
            
            Отправляет:
            - thinking_chunk: legacy событие для ThinkingMessage
            - intent_detail: новое событие для IntentMessage (если есть intent_id)
            """
            self.buffer += chunk
            
            # Проверяем начало thought
            if "<thought>" in self.buffer and not self.thought_started:
                self.thought_started = True
                await self.ws_manager.send_event(
                    self.session_id,
                    "thinking_started",
                    {"thinking_id": self.thinking_id}
                )
                # Удаляем открывающий тег из буфера
                self.buffer = self.buffer.replace("<thought>", "", 1)
            
            # Если thought начался, извлекаем контент
            if self.thought_started and not self.thought_complete:
                # Ищем закрывающий тег
                if "</thought>" in self.buffer:
                    # Извлекаем контент до закрывающего тега
                    parts = self.buffer.split("</thought>", 1)
                    full_thought = parts[0]
                    
                    # FIX: Вычисляем только НОВУЮ часть (то, что ещё не было в thought_content)
                    # Это исправляет баг дублирования!
                    final_new_part = full_thought[len(self.thought_content):] if self.thought_content else full_thought
                    
                    # Стримим только новую часть (если есть)
                    if final_new_part.strip():
                        await self.ws_manager.send_event(
                            self.session_id,
                            "thinking_chunk",
                            {
                                "thinking_id": self.thinking_id,
                                "chunk": final_new_part
                            }
                        )
                        # Отправляем как intent_detail для UI
                        await self._send_intent_detail(final_new_part.strip(), force_flush=True)
                    else:
                        # Даже если chunk пустой, flush буфер
                        await self._send_intent_detail("", force_flush=True)
                    
                    # FIX: Присваиваем, а не добавляем (было: self.thought_content += thought_chunk)
                    self.thought_content = full_thought
                    
                    self.thought_complete = True
                    await self.ws_manager.send_event(
                        self.session_id,
                        "thinking_completed",
                        {"thinking_id": self.thinking_id}
                    )
                    
                    # Оставляем остаток буфера (action часть)
                    self.buffer = parts[1] if len(parts) > 1 else ""
                else:
                    # Ещё нет закрывающего тега, стримим весь буфер
                    # Но нужно стримить только новые части
                    if len(self.buffer) > len(self.thought_content):
                        new_chunk = self.buffer[len(self.thought_content):]
                        self.thought_content = self.buffer
                        
                        if new_chunk.strip():
                            await self.ws_manager.send_event(
                                self.session_id,
                                "thinking_chunk",
                                {
                                    "thinking_id": self.thinking_id,
                                    "chunk": new_chunk
                                }
                            )
                            # Стримим iteration_thinking_chunk для IterationBlock UI
                            if self.intent_id:
                                await self.ws_manager.send_event(
                                    self.session_id,
                                    "iteration_thinking_chunk",
                                    {
                                        "intent_id": self.intent_id,
                                        "iteration_number": self.iteration_number,
                                    "chunk": new_chunk
                                }
                            )
                            # Отправляем как intent_thinking_append для streaming в UI
                            await self._send_intent_detail(new_chunk)
        
        async def _send_intent_detail(self, text: str, force_flush: bool = False) -> None:
            """Отправляет intent_thinking_append с текстом thinking если есть intent_id.
            
            Отправляет текст как есть для append к существующему thinkingText.
            Без буферизации по предложениям - просто streaming.
            
            Args:
                text: Новый chunk текста
                force_flush: Если True, flush буфера (игнорируется в новой реализации)
            """
            if not self.intent_id or not text:
                return
            import json as _json
            # Просто отправляем текст как есть для append
            await self.ws_manager.send_event(
                self.session_id,
                "intent_thinking_append",
                {
                    "intent_id": self.intent_id,
                    "text": text  # Текст как есть, фронтенд аппендит
                }
            )
        
        def get_thought(self) -> str:
            """Возвращает извлечённый thought."""
            return self.thought_content.strip()
        
        def get_remaining_buffer(self) -> str:
            """Возвращает оставшийся буфер (action часть)."""
            return self.buffer
    
    async def _think(
        self,
        state: ReActState,
        context: ConversationContext,
        file_ids: List[str]
    ) -> str:
        """Generate thought about current situation."""
        context_str = f"Цель: {state.goal}\n\n"
        
        # Add conversation history for reference resolution (NEW)
        if hasattr(context, 'messages') and context.messages:
            recent_messages = context.messages[-4:]  # Last 2 exchanges
            if recent_messages:
                context_str += "📝 Контекст разговора (для понимания референсов):\n"
                for msg in recent_messages:
                    role = "Пользователь" if msg.get('role') == 'user' else "Ассистент"
                    content = msg.get('content', '')[:300]  # Truncate
                    context_str += f"  {role}: {content}\n"
                context_str += "\n"
        
        # Add file context (uploaded files have PRIORITY #1)
        logger.info(f"[_think] Processing file_ids: {file_ids}, count: {len(file_ids) if file_ids else 0}")
        print(f"[_think] Processing file_ids: {file_ids}", flush=True)
        if hasattr(context, 'uploaded_files'):
            total_files_in_context = len(context.uploaded_files)
            logger.info(f"[_think] Total files in context.uploaded_files: {total_files_in_context}")
            print(f"[_think] Total files in context.uploaded_files: {total_files_in_context}, keys: {list(context.uploaded_files.keys())}", flush=True)
        # Use file_ids if provided, otherwise use all files from context
        files_to_process = file_ids if file_ids else []
        if not files_to_process and hasattr(context, 'uploaded_files') and context.uploaded_files:
            # If no file_ids provided, use all files from context
            files_to_process = list(context.uploaded_files.keys())
            logger.info(f"[_think] No file_ids provided, using all {len(files_to_process)} files from context")
            print(f"[_think] No file_ids provided, using all files from context: {files_to_process}", flush=True)
        
        if files_to_process:
            uploaded_files_found = []
            for file_id in files_to_process:
                file_data = context.get_file(file_id)
                if file_data:
                    logger.info(f"[_think] Found file {file_id}: {file_data.get('filename')}, type: {file_data.get('type')}, has_text: {'text' in file_data}")
                    print(f"[_think] Found file {file_id}: {file_data.get('filename')}, has_text: {'text' in file_data}, text_length: {len(file_data.get('text', ''))}", flush=True)
                else:
                    logger.warning(f"[_think] File {file_id} NOT found in context!")
                    print(f"[_think] WARNING: File {file_id} NOT found in context! Available files: {list(context.uploaded_files.keys()) if hasattr(context, 'uploaded_files') else 'N/A'}", flush=True)
                if file_data:
                    uploaded_files_found.append(file_data)
            if uploaded_files_found:
                logger.info(f"[_think] Adding {len(uploaded_files_found)} files to context_str")
                print(f"[_think] Adding {len(uploaded_files_found)} files to context_str", flush=True)
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
                    elif file_type.startswith('image/'):
                        # For images, add description (image data is stored as base64 in 'data' field)
                        context_str += f"- Изображение: {filename} (тип: {file_type})\n"
                    else:
                        context_str += f"- {filename}\n"
            else:
                logger.warning(f"[_think] file_ids provided ({files_to_process}) but no files found in context!")
                print(f"[_think] WARNING: file_ids provided but no files found!", flush=True)
        else:
            logger.info(f"[_think] No file_ids provided and no files in context")
            print(f"[_think] No file_ids provided and no files in context", flush=True)
        
        # Add open files context (PRIORITY #2)
        import json
        import time
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        log_data_think = {
            "location": "unified_react_engine.py:1350",
            "message": "H2,H4: _think - open_files from context",
            "data": {
                "has_get_open_files": hasattr(context, 'get_open_files'),
                "open_files_count": len(open_files),
                "open_files": open_files,
                "open_files_details": [
                    {
                        "type": f.get('type'),
                        "title": f.get('title'),
                        "document_id": f.get('document_id'),
                        "spreadsheet_id": f.get('spreadsheet_id'),
                        "url": f.get('url')
                    }
                    for f in open_files
                ]
            },
            "timestamp": time.time() * 1000,
            "sessionId": self.session_id,
            "runId": "run1",
            "hypothesisId": "H2,H4"
        }
        try:
                f.write(json.dumps(log_data_think, default=str) + "\n")
        except Exception:
            pass
        if open_files:
            context_str += "\n📂 ОТКРЫТЫЕ ФАЙЛЫ В РАБОЧЕЙ ОБЛАСТИ:\n"
            for file in open_files:
                file_type = file.get('type')
                title = file.get('title', 'Без названия')
                
                if file_type == 'sheets':
                    spreadsheet_id = file.get('spreadsheet_id') or file.get('spreadsheetId')
                    # Извлекаем ID из URL, если нет в данных
                    if not spreadsheet_id and file.get('url'):
                        url_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            spreadsheet_id = url_match.group(1)
                    
                    if spreadsheet_id:
                        context_str += f"- 📊 Таблица: {title} (ID: {spreadsheet_id})\n"
                        context_str += f"  Используй: sheets_read_range с spreadsheet_id={spreadsheet_id}\n"
                elif file_type == 'docs':
                    document_id = file.get('document_id') or file.get('documentId')
                    # Извлекаем ID из URL, если нет в данных
                    if not document_id and file.get('url'):
                        url_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            document_id = url_match.group(1)
                    
                    if document_id:
                        context_str += f"- 📄 Документ: {title} (ID: {document_id})\n"
                        context_str += f"  Используй: read_document с document_id={document_id}\n"
            
            context_str += "\n⚠️ ВАЖНО: Файлы УЖЕ открыты, используй их ID напрямую, НЕ ищи через search!\n"
        
        open_files_context_added_think = "📂 Открытые файлы" in context_str if open_files else False
        log_data_think_prompt = {
            "location": "unified_react_engine.py:1380",
            "message": "H2: _think - context added to prompt",
            "data": {
                "open_files_in_context": open_files_context_added_think,
                "context_str_length": len(context_str),
                "context_str_snippet": context_str[-500:] if len(context_str) > 500 else context_str,
                "open_files_count_in_prompt": context_str.count("📂 Открытые файлы") if open_files else 0
            },
            "timestamp": time.time() * 1000,
            "sessionId": self.session_id,
            "runId": "run1",
            "hypothesisId": "H2"
        }
        try:
                f.write(json.dumps(log_data_think_prompt, default=str) + "\n")
        except Exception:
            pass
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
        
        # Add conversation history for reference resolution (NEW)
        if hasattr(context, 'messages') and context.messages:
            recent_messages = context.messages[-4:]  # Last 2 exchanges
            if recent_messages:
                context_str += "📝 Контекст разговора (для понимания референсов типа 'его', 'это', 'еще'):\n"
                for msg in recent_messages:
                    role = "Пользователь" if msg.get('role') == 'user' else "Ассистент"
                    content = msg.get('content', '')[:300]  # Truncate
                    context_str += f"  {role}: {content}\n"
                context_str += "\n"
        
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
        import json
        import time
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        log_data_plan = {
            "location": "unified_react_engine.py:1520",
            "message": "H1,H2,H4: _plan_action - open_files from context",
            "data": {
                "has_get_open_files": hasattr(context, 'get_open_files'),
                "open_files_count": len(open_files),
                "open_files": open_files,
                "open_files_details": [
                    {
                        "type": f.get('type'),
                        "title": f.get('title'),
                        "document_id": f.get('document_id'),
                        "spreadsheet_id": f.get('spreadsheet_id'),
                        "url": f.get('url')
                    }
                    for f in open_files
                ]
            },
            "timestamp": time.time() * 1000,
            "sessionId": self.session_id,
            "runId": "run1",
            "hypothesisId": "H1,H2,H4"
        }
        try:
                f.write(json.dumps(log_data_plan, default=str) + "\n")
        except Exception:
            pass
        if open_files:
            context_str += "\n📂 ОТКРЫТЫЕ ФАЙЛЫ В РАБОЧЕЙ ОБЛАСТИ (ПРИОРИТЕТ #2):\n"
            for file in open_files:
                file_type = file.get('type')
                title = file.get('title', 'Без названия')
                
                if file_type == 'sheets':
                    spreadsheet_id = file.get('spreadsheet_id') or file.get('spreadsheetId')
                    # Извлекаем ID из URL, если нет в данных
                    if not spreadsheet_id and file.get('url'):
                        url_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            spreadsheet_id = url_match.group(1)
                    
                    if spreadsheet_id:
                        context_str += f"- 📊 Таблица: {title}\n"
                        context_str += f"  ID: {spreadsheet_id}\n"
                        context_str += f"  URL: {file.get('url', 'N/A')}\n"
                        context_str += f"  ⚠️ ИСПОЛЬЗУЙ: sheets_read_range с параметрами spreadsheet_id={spreadsheet_id}, range='A1:Z100'\n"
                elif file_type == 'docs':
                    document_id = file.get('document_id') or file.get('documentId')
                    # Извлекаем ID из URL, если нет в данных
                    if not document_id and file.get('url'):
                        url_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            document_id = url_match.group(1)
                    
                    if document_id:
                        context_str += f"- 📄 Документ: {title}\n"
                        context_str += f"  ID: {document_id}\n"
                        context_str += f"  URL: {file.get('url', 'N/A')}\n"
                        context_str += f"  ⚠️ ИСПОЛЬЗУЙ: read_document с параметром document_id={document_id}\n"
            
            context_str += "\n🚫 КРИТИЧЕСКИ ВАЖНО:\n"
            context_str += "1. НИКОГДА не используй find_and_open_file, workspace_find_and_open_file, workspace_search_files для файлов из этого списка!\n"
            context_str += "2. Если пользователь упоминает название файла из этого списка (например, 'Сказка', 'Зарплаты сотрудников', 'документ', 'таблица'), используй ПРЯМО ID из списка выше!\n"
            context_str += "3. НЕ создавай шаг 'Найти файл' в плане - файл УЖЕ открыт, просто используй его ID напрямую!\n"
            context_str += "4. Для ДОКУМЕНТОВ используй инструмент read_document с параметром document_id=<ID из списка выше>\n"
            context_str += "5. Для ТАБЛИЦ используй инструмент sheets_read_range с параметрами spreadsheet_id=<ID из списка выше>, range='A1:Z100'\n"
        
        open_files_context_added = "📂 Открытые файлы" in context_str if open_files else False
        log_data_prompt = {
            "location": "unified_react_engine.py:1540",
            "message": "H1: _plan_action - context added to prompt",
            "data": {
                "open_files_in_context": open_files_context_added,
                "context_str_length": len(context_str),
                "context_str_snippet": context_str[-500:] if len(context_str) > 500 else context_str,
                "open_files_count_in_prompt": context_str.count("📂 Открытые файлы") if open_files else 0
            },
            "timestamp": time.time() * 1000,
            "sessionId": self.session_id,
            "runId": "run1",
            "hypothesisId": "H1"
        }
        try:
                f.write(json.dumps(log_data_prompt, default=str) + "\n")
        except Exception:
            pass
        prompt = f"""Ты планируешь следующее действие для достижения цели.

{context_str}

Доступные инструменты:
{tools_str}

═══════════════════════════════════════════════════════════════
🎯 ПРИОРИТЕТЫ ИСТОЧНИКОВ ФАЙЛОВ (КРИТИЧЕСКИ ВАЖНО!)
═══════════════════════════════════════════════════════════════

ПРИОРИТЕТ #1 - ПРИКРЕПЛЁННЫЕ ФАЙЛЫ:
• Их содержимое УЖЕ в контексте выше (текст PDF/DOCX, изображения через Vision)
• НЕ вызывай find_and_open_file или search - используй контент напрямую!
• Если спрашивают "что в файле" и текст виден выше → FINISH сразу!

ПРИОРИТЕТ #2 - ОТКРЫТЫЕ ВКЛАДКИ:
• Используй document_id/spreadsheet_id из списка выше НАПРЯМУЮ
• НЕ ищи эти файлы - вызывай read_document или sheets_read_range с ID
• Поиск файла запрещён если он уже в списке открытых!

ПРИОРИТЕТ #3 - РАБОЧАЯ ПАПКА (только если #1 и #2 не применимы):
• Поиск разрешён ТОЛЬКО для файлов которых НЕТ в прикреплённых/открытых

═══════════════════════════════════════════════════════════════

ВАЖНО для данных:
- Если получен результат с количеством событий/данных, но БЕЗ деталей - получи ДЕТАЛИ
- НЕ завершай задачу, пока не получены все необходимые детали для ответа пользователю

⚠️ КРИТИЧЕСКИ ВАЖНО для ФОРМАТИРОВАНИЯ ДОКУМЕНТОВ:
- "красиво оформить" / "отформатировать" = ТОЛЬКО format_document_text и format_document_paragraph!
- ❌ ЗАПРЕЩЕНО: update_document - это ПЕРЕЗАПИСЬ всего текста!
- ❌ ЗАПРЕЩЕНО: insert_into_document - это ДОБАВЛЕНИЕ нового текста!
- ❌ ЗАПРЕЩЕНО: append_to_document - это ДОБАВЛЕНИЕ текста в конец!

✅ ДВА инструмента для форматирования:
1. format_document_paragraph - для стиля ВСЕХ абзацев (выравнивание, отступы)
   ⚠️ ВАЖНО: Используй TEXT_LENGTH из read_document как end_index!
   Пример: format_document_paragraph(document_id, start_index=1, end_index=TEXT_LENGTH, alignment="JUSTIFIED", indent_first_line=36)
2. format_document_text - для выделения текста (bold, italic)
   Пример: format_document_text(document_id, start_index=1, end_index=20, bold=True) - заголовок

📋 "Красиво оформить" = 3 ОБЯЗАТЕЛЬНЫХ шага:
1. format_document_paragraph(start_index=1, end_index=TEXT_LENGTH, alignment="JUSTIFIED", indent_first_line=36) - ВЕСЬ документ
2. format_document_text(start_index=1, end_index=<конец_заголовка>, bold=True) - заголовок жирным
3. Найти имена персонажей через search_document_text и выделить их жирным через format_document_text

⚠️ ОБЯЗАТЕЛЬНО:
- end_index для format_document_paragraph = TEXT_LENGTH (из результата read_document)
- НЕ выбирай произвольные значения типа 800 или 500!
- Выдели жирным: заголовок + имена персонажей + ключевые фразы
- НЕ меняй содержание текста!

Порядок действий:
1. read_document → найти [TEXT_LENGTH: X characters] в результате
2. format_document_paragraph(end_index=X) → выравнивание для ВСЕГО документа
3. format_document_text(bold=True) → заголовок жирным
4. search_document_text → найти имена персонажей
5. format_document_text(bold=True) → имена персонажей жирным
6. FINISH

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
    
    async def _think_and_plan(
        self,
        state: ReActState,
        context: ConversationContext,
        file_ids: List[str]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Объединённый вызов: анализ + планирование в одном LLM запросе.
        Стримит thought по мере поступления, затем парсит action plan.
        
        Returns:
            Tuple[thought: str, action_plan: Dict[str, Any]]
        """
        # Строим контекст (объединяем логику из _think и _plan_action)
        from datetime import datetime, timedelta
        import pytz
        from src.utils.config_loader import get_config
        tz = pytz.timezone(get_config().timezone)
        now = datetime.now(tz)
        current_date_str = now.strftime("%Y-%m-%d %H:%M")
        tomorrow = now + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        context_str = f"📅 ТЕКУЩАЯ ДАТА И ВРЕМЯ: {current_date_str} (завтра = {tomorrow_str})\n\n"
        context_str += f"Цель: {state.goal}\n\n"
        
        # Добавляем историю разговора
        if hasattr(context, 'messages') and context.messages:
            recent_messages = context.messages[-4:]
            if recent_messages:
                context_str += "📝 Контекст разговора:\n"
                for msg in recent_messages:
                    role = "Пользователь" if msg.get('role') == 'user' else "Ассистент"
                    content = msg.get('content', '')[:300]
                    context_str += f"  {role}: {content}\n"
                context_str += "\n"
        
        # Добавляем ПРИКРЕПЛЕННЫЕ ФАЙЛЫ (PRIORITY #1 - должны быть ПЕРВЫМИ!)
        logger.info(f"[_think_and_plan] Processing file_ids: {file_ids}, count: {len(file_ids) if file_ids else 0}")
        print(f"[_think_and_plan] Processing file_ids: {file_ids}", flush=True)
        if hasattr(context, 'uploaded_files'):
            total_files = len(context.uploaded_files)
            logger.info(f"[_think_and_plan] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}")
            print(f"[_think_and_plan] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}", flush=True)
        if file_ids:
            uploaded_files_found = []
            for file_id in file_ids:
                file_data = context.get_file(file_id)
                if file_data:
                    logger.info(f"[_think_and_plan] Found file {file_id}: {file_data.get('filename')}, type: {file_data.get('type')}, has_text: {'text' in file_data}")
                    print(f"[_think_and_plan] Found file {file_id}: {file_data.get('filename')}, has_text: {'text' in file_data}, text_length: {len(file_data.get('text', ''))}", flush=True)
                else:
                    logger.warning(f"[_think_and_plan] File {file_id} NOT found in context!")
                    print(f"[_think_and_plan] WARNING: File {file_id} NOT found! Available: {list(context.uploaded_files.keys()) if hasattr(context, 'uploaded_files') else 'N/A'}", flush=True)
                if file_data:
                    uploaded_files_found.append(file_data)
            
            if uploaded_files_found:
                logger.info(f"[_think_and_plan] Adding {len(uploaded_files_found)} uploaded files to context_str")
                print(f"[_think_and_plan] Adding {len(uploaded_files_found)} uploaded files to context_str", flush=True)
                context_str += "\n📎 ПРИКРЕПЛЕННЫЕ ФАЙЛЫ (ПРИОРИТЕТ #1 - используй их ПЕРВЫМ!):\n"
                context_str += "🚫 КРИТИЧЕСКИ ВАЖНО: НЕ используй инструменты open_file, find_and_open_file, workspace_open_file для этих файлов!\n"
                context_str += "🚫 Их содержимое УЖЕ здесь ниже - используй текст напрямую!\n"
                context_str += "🚫 НЕ ищи эти файлы в Google Drive или Workspace - их там нет!\n\n"
                for file_data in uploaded_files_found:
                    filename = file_data.get('filename', 'unknown')
                    file_type = file_data.get('type', '')
                    if file_type == 'application/pdf' and 'text' in file_data:
                        pdf_text = file_data.get('text', '')
                        max_len = 8000
                        if len(pdf_text) > max_len:
                            pdf_text = pdf_text[:max_len] + f"\n... (обрезано, полный текст {len(file_data.get('text', ''))} символов)"
                        context_str += f"- PDF: {filename}\n{pdf_text}\n\n"
                    elif file_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                      "application/msword") and 'text' in file_data:
                        docx_text = file_data.get('text', '')
                        max_len = 8000
                        if len(docx_text) > max_len:
                            docx_text = docx_text[:max_len] + f"\n... (обрезано, полный текст {len(file_data.get('text', ''))} символов)"
                        context_str += f"- Word документ: {filename}\n{docx_text}\n\n"
                    elif file_type.startswith('image/'):
                        context_str += f"- Изображение: {filename} (содержимое уже в сообщении)\n\n"
                    else:
                        context_str += f"- Файл: {filename} (тип: {file_type})\n\n"
                context_str += "🚫 ЗАПРЕЩЕНО: НЕ вызывай open_file, find_and_open_file, workspace_open_file для файлов выше!\n"
                context_str += "✅ ПРАВИЛЬНО: Используй текст файлов напрямую из секции выше для ответа на вопросы пользователя!\n\n"
            else:
                logger.warning(f"[_think_and_plan] file_ids provided ({file_ids}) but no files found in context!")
                print(f"[_think_and_plan] WARNING: file_ids provided but no files found!", flush=True)
        else:
            logger.info(f"[_think_and_plan] No file_ids provided")
            print(f"[_think_and_plan] No file_ids provided", flush=True)
        
        # Добавляем открытые файлы (PRIORITY #2)
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            context_str += "\n📂 ОТКРЫТЫЕ ФАЙЛЫ В РАБОЧЕЙ ОБЛАСТИ:\n"
            for file in open_files:
                file_type = file.get('type')
                title = file.get('title', 'Без названия')
                
                if file_type == 'sheets':
                    spreadsheet_id = file.get('spreadsheet_id') or file.get('spreadsheetId')
                    if not spreadsheet_id and file.get('url'):
                        url_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            spreadsheet_id = url_match.group(1)
                    if spreadsheet_id:
                        context_str += f"- 📊 Таблица: {title} (ID: {spreadsheet_id})\n"
                        context_str += f"  Используй: sheets_read_range с spreadsheet_id={spreadsheet_id}\n"
                elif file_type == 'docs':
                    document_id = file.get('document_id') or file.get('documentId')
                    if not document_id and file.get('url'):
                        url_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            document_id = url_match.group(1)
                    if document_id:
                        context_str += f"- 📄 Документ: {title} (ID: {document_id})\n"
                        context_str += f"  Используй: read_document с document_id={document_id}\n"
            context_str += "\n"
        
        # Добавляем историю действий С РЕЗУЛЬТАТАМИ
        if state.action_history and state.observations:
            context_str += "🔴 ИСТОРИЯ ВЫПОЛНЕННЫХ ДЕЙСТВИЙ (НЕ ПОВТОРЯЙ ИХ!):\n"
            # Берём последние 5 действий с их результатами
            start_idx = max(0, len(state.action_history) - 5)
            last_written_data = None  # Для оптимизации: запоминаем записанные данные
            completed_tools = []  # Список выполненных инструментов
            for i in range(start_idx, len(state.action_history)):
                action = state.action_history[i]
                completed_tools.append(action.tool_name)
                context_str += f"✅ {i+1}. {action.tool_name} — ВЫПОЛНЕНО"
                
                # Для add_rows/update_cells - показываем САМИ ДАННЫЕ, которые были записаны
                if action.tool_name in ["add_rows", "update_cells"] and action.arguments:
                    values = action.arguments.get("values")
                    if values:
                        # Сохраняем данные для последующего использования
                        last_written_data = values
                        context_str += f"\n  📊 ЗАПИСАННЫЕ ДАННЫЕ (используй их напрямую!):\n"
                        if isinstance(values, list):
                            for row_idx, row in enumerate(values[:10]):  # Показываем до 10 строк
                                context_str += f"    {row}\n"
                            if len(values) > 10:
                                context_str += f"    ... и ещё {len(values) - 10} строк\n"
                        else:
                            context_str += f"    {str(values)[:500]}\n"
                
                # Получаем соответствующий observation
                if i < len(state.observations):
                    obs = state.observations[i]
                    if obs and obs.raw_result:
                        result_str = str(obs.raw_result)[:600]  # Ограничиваем длину
                        context_str += f"\n  📋 Результат: {result_str}"
                context_str += "\n"
            
            # Если были записаны данные, явно указываем НЕ читать таблицу
            if last_written_data:
                context_str += "\n⚠️ ВАЖНО: Ты только что записал данные в таблицу. НЕ вызывай sheets_read_range - используй ЗАПИСАННЫЕ ДАННЫЕ выше!\n"
            
            # Явное указание не повторять действия
            context_str += f"\n🛑 НЕ ПОВТОРЯЙ УЖЕ ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ: {', '.join(completed_tools)}\n"
            context_str += "Если все нужные действия выполнены — используй FINISH!\n"
        
        # Получаем список доступных инструментов
        capability_descriptions = []
        for cap in self.capabilities[:50]:
            capability_descriptions.append(f"- {cap.name}: {cap.description}")
        tools_str = "\n".join(capability_descriptions)
        
        # Формируем объединённый промпт
        prompt = f"""Ты выполняешь задачу пошагово, используя доступные инструменты.

{context_str}

Доступные инструменты:
{tools_str}

🚫 КРИТИЧЕСКИ ВАЖНО ДЛЯ ПРИКРЕПЛЕННЫХ ФАЙЛОВ:
- Если в секции "ПРИКРЕПЛЕННЫЕ ФАЙЛЫ" выше есть файлы с их содержимым, НИКОГДА не используй инструменты:
  * open_file
  * find_and_open_file
  * workspace_open_file
  * workspace_find_and_open_file
  * search_files
  * drive_search_files
- Содержимое этих файлов УЖЕ в контексте выше - используй его напрямую для ответа на вопросы!
- Если пользователь спрашивает "что в файле", "что в документе", "а этот файл ты видишь" - отвечай используя текст из секции "ПРИКРЕПЛЕННЫЕ ФАЙЛЫ"!
- НЕ пытайся открыть эти файлы через инструменты - они уже загружены и их содержимое показано выше!
- Если в секции "ПРИКРЕПЛЕННЫЕ ФАЙЛЫ" есть Word документ или PDF - весь текст уже там, просто используй его для ответа!
- НЕ используй инструменты для открытия файлов, если их содержимое уже показано выше - это приведет к ошибке!

ПРАВИЛО МИНИМАЛЬНЫХ УТОЧНЕНИЙ:
Используй ASK_CLARIFICATION ТОЛЬКО в двух случаях:
1. Когда НЕВОЗМОЖНО выполнить задание без критически важных данных (например, "отправь письмо" без получателя — письмо физически нельзя отправить)
2. Когда пользователь САМ просит уточнить или задаёт вопрос ("а что именно?", "уточни")

ВО ВСЕХ ОСТАЛЬНЫХ СЛУЧАЯХ — выполняй задание с имеющимися данными!
- Если пользователь прикрепил файлы и спрашивает "что видишь?" — опиши содержимое ВСЕХ файлов, НЕ спрашивай "какой файл?"
- Если запрос частично неясен — выполни то, что можно, и в конце ответа ПРЕДЛОЖИ уточнения
- Пример правильного ответа: "Вот что я нашёл в файлах: [описание]. Если вас интересует что-то конкретное, уточните — я подберу нужную информацию."

ВАЖНО: Следующие запросы НЕ требуют уточнения (используй текущую дату/время из контекста):
- "покажи встречи на неделе" → означает текущую неделю (понедельник-воскресенье)
- "покажи встречи сегодня/завтра" → очевидные даты
- "что в файлах?", "что видишь?" → опиши ВСЕ прикреплённые файлы

ОСОБЕННО ВАЖНО ДЛЯ КАЛЕНДАРЯ:
1. **Проверка доступности участников**: Если в запросе указаны участники встречи и время, ТЫ ДОЛЖЕН САМ проверить их доступность через инструмент `get_calendar_events` для каждого участника на указанное время. НЕ спрашивай пользователя о доступности - проверь сам!

2. **Если участник занят**: Если при проверке календаря участника выяснилось, что он занят в указанное время:
   - Получи список его встреч на этот день через `get_calendar_events`
   - Используй `ASK_CLARIFICATION` с вопросом: "Участник [email] занят в указанное время. Вот его встречи на [дата]: [список встреч]. Как лучше поступить? (перенести встречу, выбрать другое время, создать встречу несмотря на конфликт)"

3. **Если в запросе "подбери время" или "найди свободное время"**: 
   - Используй `schedule_group_meeting` для автоматического поиска свободного времени для всех участников
   - ИЛИ проверь доступность через `get_calendar_events` для каждого участника и найди общее свободное окно
   - НЕ спрашивай пользователя - найди время сам!

4. **Порядок действий для создания встречи с участниками**:
   - Шаг 1: Если время указано - проверь доступность участников через `get_calendar_events`
   - Шаг 2: Если все свободны - создай встречу через `create_event` или `schedule_group_meeting`
   - Шаг 3: Если кто-то занят - покажи его встречи и спроси, как поступить (через `ASK_CLARIFICATION`)

⚠️ **КРИТИЧЕСКИ ВАЖНО - НЕ ЗАЦИКЛИВАЙСЯ:**
- НИКОГДА не вызывай `get_calendar_events` более ОДНОГО раза для одного временного диапазона!
- После ПЕРВОЙ проверки доступности СРАЗУ переходи к следующему шагу:
  * Если время свободно → вызови `create_event`
  * Если время занято → вызови `ASK_CLARIFICATION` и сообщи о конфликте
- Если ты уже получил результат от `get_calendar_events`, НЕ вызывай его снова!

🛑 **КРИТИЧЕСКОЕ ПРАВИЛО - ОПЕРАЦИИ ТОЛЬКО С ЯВНОЙ ПРОСЬБОЙ:**
Следующие операции НЕЛЬЗЯ выполнять без ЯВНОЙ просьбы пользователя:
- `create_event` - ТОЛЬКО если пользователь прямо просит "создай встречу", "запланируй", "добавь событие"
- `delete_event` - ТОЛЬКО если пользователь прямо просит "удали встречу", "отмени событие"
- `send_email` - ТОЛЬКО если пользователь прямо просит "отправь письмо", "напиши email"
- `update_document` - ТОЛЬКО если пользователь прямо просит изменить документ
- `add_rows`, `update_cells` - ТОЛЬКО если пользователь прямо просит записать данные

⚠️ ПРИМЕРЫ НЕПРАВИЛЬНОГО ПОВЕДЕНИЯ:
- Запрос "какие встречи у меня есть?" → НЕ создавай новые встречи! Только ПОКАЗЫВАЙ существующие!
- Запрос "какие письма пришли?" → НЕ отправляй письма! Только ПОКАЗЫВАЙ входящие!
- Запрос "найди встречи с участником X" → Это ПОИСК, НЕ создание! Используй get_calendar_events для поиска!

✅ ПРИМЕРЫ ПРАВИЛЬНОГО ПОВЕДЕНИЯ:
- "какие встречи у меня на неделе?" → get_calendar_events → покажи список
- "создай встречу с Иваном завтра" → create_event (пользователь ЯВНО просит создать)
- "найди встречи с anna@" → get_calendar_events с фильтром → покажи найденные

Примеры когда ASK_CLARIFICATION НУЖЕН (невозможно выполнить без данных):
- "отправь письмо" → нужен минимум получатель (нельзя отправить в никуда)
- "создай встречу" → нужно минимум время (нельзя создать без времени)

Примеры когда ASK_CLARIFICATION НЕ НУЖЕН (выполни и предложи):
- "что видишь?", "что в файлах?" → опиши ВСЕ файлы, в конце предложи уточнить
- "расскажи о документе" → опиши что есть, предложи углубиться в детали

⚡ **ОПТИМИЗАЦИЯ - НЕ ЧИТАЙ ДАННЫЕ, КОТОРЫЕ ТОЛЬКО ЧТО ЗАПИСАЛ:**
- Если ты только что вызвал `add_rows` или `update_cells` для записи данных в таблицу, ты УЖЕ ЗНАЕШЬ эти данные!
- НЕ вызывай `sheets_read_range` или `get_sheet_data` для чтения данных, которые ты сам только что записал.
- Используй данные напрямую из предыдущего шага для создания документа или отчёта.
- Читай таблицу ТОЛЬКО если тебе нужны данные, которые были там ДО твоих изменений.

Ответь в формате:
<thought>
Краткий анализ ситуации (2-3 предложения на русском):
1. Что уже сделано?
2. Что осталось сделать?
3. Какое следующее действие будет наиболее эффективным?
Если запрос неполный - укажи, каких данных не хватает.
</thought>
<action>
{{
    "tool_name": "имя_инструмента",
    "arguments": {{"param1": "value1", "param2": "value2"}},
    "description": "краткое описание действия",
    "reasoning": "почему выбрано это действие"
}}
</action>

Если цель полностью достигнута, используй:
{{
    "tool_name": "FINISH",
    "arguments": {{}},
    "description": "краткое описание выполненной задачи",
    "reasoning": "почему задача считается выполненной"
}}

ТОЛЬКО если НЕВОЗМОЖНО выполнить задание без критических данных (получатель письма, время встречи):
{{
    "tool_name": "ASK_CLARIFICATION",
    "arguments": {{
        "questions": ["Конкретный вопрос о недостающих данных"]
    }},
    "description": "Уточнение критически важных данных",
    "reasoning": "без этих данных задание невозможно выполнить"
}}

Отвечай ТОЛЬКО в указанном формате, без дополнительного текста."""
        
        try:
            messages = [
                SystemMessage(content="Ты эксперт по анализу задач и планированию действий. Отвечай в указанном формате на русском языке."),
                HumanMessage(content=prompt)
            ]
            
            # #region agent log - H10: Full prompt sent to LLM
            try:
                with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                    import json as _json
                    # Извлекаем ключевые секции промпта
                    goal_start = prompt.find("Цель:")
                    goal_end = prompt.find("\n", goal_start) if goal_start > 0 else -1
                    goal_section = prompt[goal_start:goal_end].strip() if goal_start > 0 else "NO GOAL"
                    
                    history_start = prompt.find("🔴 ИСТОРИЯ")
                    history_end = prompt.find("Доступные инструменты:")
                    history_section = prompt[history_start:history_end].strip() if history_start > 0 else "NO HISTORY SECTION"
                    
                    # Имя модели
                    model_name = getattr(self.fast_llm if state.iteration > 1 else self.llm, 'model_name', 'unknown')
                    if not model_name or model_name == 'unknown':
                        model_name = str(type(self.fast_llm if state.iteration > 1 else self.llm).__name__)
                    
                    f.write(_json.dumps({
                        "location": "unified_react_engine.py:_think_and_plan",
                        "message": "H10: FULL PROMPT TO LLM",
                        "data": {
                            "iteration": state.iteration,
                            "model_name": model_name,
                            "is_fast_llm": state.iteration > 1,
                            "goal": goal_section,
                            "history_section": history_section[:3000],
                            "action_history_count": len(state.action_history) if state.action_history else 0,
                            "observations_count": len(state.observations) if state.observations else 0,
                            "prompt_length": len(prompt),
                            "full_prompt": prompt[:5000]  # Первые 5000 символов
                        },
                        "timestamp": __import__("time").time() * 1000,
                        "sessionId": self.session_id,
                        "hypothesisId": "H10"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Создаём парсер для стриминга thought
            # Передаём intent_id для отправки intent_detail событий
            current_intent_id = getattr(self, '_current_intent_id', None)
            
            # REMOVED: intent_thinking_clear was causing the plan to disappear!
            # When thinkingText is cleared and phase is 'executing', 
            # showPlanningSection becomes false and the entire section vanishes.
            # Instead, we let the thinking text accumulate between iterations,
            # which shows the full reasoning process to the user.
            
            parser = self.StreamingThoughtParser(
                self.ws_manager, 
                self.session_id,
                intent_id=current_intent_id,
                iteration_number=state.iteration
            )
            
            # Выбираем модель: fast_llm для итераций 2+ (ускорение)
            # Первая итерация требует глубокого анализа, последующие - простое следование плану
            llm_to_use = self.fast_llm if state.iteration > 1 else self.llm
            
            # Стримим ответ
            full_response = ""
            _think_start = __import__("time").time()
            _chunk_count = 0
            async for chunk in llm_to_use.astream(messages):
                _chunk_count += 1
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
                    full_response += chunk_text
                    await parser.process_chunk(chunk_text)
            
            # Получаем thought из парсера
            thought = parser.get_thought()
            _think_duration = __import__("time").time() - _think_start
            
            # #region agent log - H8: Thinking duration
            try:
                with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({
                        "location": "unified_react_engine.py:_think_and_plan",
                        "message": "H8: Thinking stream completed",
                        "data": {
                            "iteration": state.iteration,
                            "duration_sec": round(_think_duration, 1),
                            "chunk_count": _chunk_count,
                            "thought_len": len(thought) if thought else 0,
                            "full_response_len": len(full_response)
                        },
                        "timestamp": __import__("time").time() * 1000,
                        "sessionId": self.session_id,
                        "hypothesisId": "H8"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Remove duplicate patterns from thought
            # Some LLMs (especially Claude 3 Haiku) tend to repeat their analysis
            # Detect and remove duplicated analysis blocks
            thought_lower = thought.lower() if thought else ""
            has_analysis_markers = (
                "анализ" in thought_lower or 
                "уже выполнено" in thought_lower or
                "что уже сделано" in thought_lower or
                "пользователь просит" in thought_lower
            )
            
            if thought and has_analysis_markers:
                lines = thought.split('\n')
                seen_starts = set()
                filtered_lines = []
                skip_mode = False
                
                for line in lines:
                    line_lower = line.lower().strip()
                    
                    # Check if this is a section/analysis start marker
                    is_analysis_start = (
                        line_lower.startswith("анализ ситуации") or
                        line_lower.startswith("анализирую ситуацию") or
                        line_lower.startswith("анализирую текущу") or
                        line_lower.startswith("проанализиру") or
                        line_lower.startswith("пользователь просит") or
                        (line_lower.startswith("1.") and ("уже" in line_lower or "что уже" in line_lower))
                    )
                    
                    if is_analysis_start:
                        # Normalize the key - take significant part
                        section_key = line_lower[:40].replace(" ", "")
                        if section_key in seen_starts:
                            # This is a duplicate section, skip it and all following lines until next unique section
                            skip_mode = True
                            continue
                        else:
                            seen_starts.add(section_key)
                            skip_mode = False
                    
                    if not skip_mode:
                        filtered_lines.append(line)
                
                thought = '\n'.join(filtered_lines).strip()
            import json as _json; import time as _time
            # Check for repeated patterns in thought AFTER filtering
            # Извлекаем action из оставшегося буфера или полного ответа
            remaining_buffer = parser.get_remaining_buffer()
            response_text = remaining_buffer if remaining_buffer else full_response
            
            # Ищем action блок
            action_match = re.search(r'<action>([\s\S]*?)</action>', response_text, re.DOTALL)
            if not action_match:
                # Пробуем найти JSON без тегов
                action_match = re.search(r'\{[\s\S]*"tool_name"[\s\S]*\}', response_text)
            
            if action_match:
                action_text = action_match.group(1) if action_match.lastindex else action_match.group(0)
                # Очищаем от тегов если есть
                action_text = re.sub(r'</?action>', '', action_text).strip()
                
                # Парсим JSON
                json_match = re.search(r'\{[\s\S]*\}', action_text)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        action_plan = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Fallback на парсинг всего текста
                        action_plan = json.loads(action_text)
                else:
                    action_plan = json.loads(action_text)
            else:
                # Fallback: пытаемся найти JSON в ответе
                json_match = re.search(r'\{[\s\S]*"tool_name"[\s\S]*\}', full_response)
                if json_match:
                    action_plan = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not find action plan in response")
            
            # Валидация
            if "tool_name" not in action_plan:
                raise ValueError("tool_name missing in action plan")
            tool_name = action_plan.get("tool_name", "")
            
            # #region agent log - H11: LLM response and parsed action
            try:
                with open("/Users/Dima/universal-multiagent/.cursor/debug.log", "a") as f:
                    import json as _json
                    model_name = getattr(self.fast_llm if state.iteration > 1 else self.llm, 'model_name', 'unknown')
                    f.write(_json.dumps({
                        "location": "unified_react_engine.py:_think_and_plan",
                        "message": "H11: LLM RESPONSE - PARSED ACTION",
                        "data": {
                            "iteration": state.iteration,
                            "model_name": model_name,
                            "thought": thought[:1000] if thought else "",
                            "action_plan": action_plan,
                            "tool_name": tool_name,
                            "full_response": full_response[:2000]
                        },
                        "timestamp": __import__("time").time() * 1000,
                        "sessionId": self.session_id,
                        "hypothesisId": "H11"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Check for dangerous operations without explicit request
            DANGEROUS_OPERATIONS = {
                "create_event": ["создай встречу", "запланируй встречу", "добавь событие", "назначь встречу", "schedule", "create event", "создай событие"],
                "delete_event": ["удали встречу", "отмени встречу", "удали событие", "cancel event", "delete event"],
                "send_email": ["отправь письмо", "напиши письмо", "send email", "отправь email"],
                "update_document": ["измени документ", "обнови документ", "запиши в документ", "update document"],
                "add_rows": ["добавь строки", "запиши строки", "add rows"],
                "update_cells": ["обнови ячейки", "запиши в ячейки", "update cells"],
            }
            
            goal_lower = state.goal.lower() if state.goal else ""
            if tool_name in DANGEROUS_OPERATIONS:
                required_keywords = DANGEROUS_OPERATIONS[tool_name]
                has_explicit_request = any(kw in goal_lower for kw in required_keywords)
                
                # Block dangerous operation if no explicit request
                if not has_explicit_request:
                    logger.warning(f"[UnifiedReActEngine] BLOCKED dangerous operation {tool_name} - no explicit request in goal: {state.goal}")
                    # Return FINISH instead of dangerous operation
                    action_plan = {
                        "tool_name": "FINISH",
                        "arguments": {},
                        "description": f"Завершаю задачу. Действие '{tool_name}' требует явного запроса пользователя.",
                        "reasoning": f"Операция {tool_name} заблокирована: пользователь не просил выполнить это действие. Запрос '{state.goal}' не содержит явной просьбы о создании/изменении/удалении."
                    }
                    thought = f"Операция {tool_name} требует явного запроса. Пользователь спросил: '{state.goal}', что является запросом на получение информации, а не на изменение данных."
                    return thought, action_plan
            
            tool_name = action_plan.get("tool_name", "")
            is_clarification = tool_name == "ASK_CLARIFICATION"
            goal_lower = state.goal.lower() if state.goal else ""
            has_meeting_keywords = any(kw in goal_lower for kw in ["встреч", "meeting", "назначь", "создай встречу", "запланир"])
            has_attendees = any("@" in arg for arg in str(action_plan.get("arguments", {})).split() if isinstance(arg, str))
            has_time = any(kw in goal_lower for kw in ["в ", "в ", "время", "time", "14:00", "15:00"])
            should_check_availability = has_meeting_keywords and has_attendees and has_time and not is_clarification
            # Если thought пустой, используем fallback
            if not thought:
                thought = f"Анализирую задачу: {state.goal[:100]}..."
            
            return thought, action_plan
            
        except Exception as e:
            logger.error(f"[UnifiedReActEngine] Error in _think_and_plan: {e}")
            # Fallback
            fallback_thought = f"Анализирую ситуацию... (итерация {state.iteration})"
            
            if self.capabilities:
                fallback_cap = self.capabilities[0]
                fallback_plan = {
                    "tool_name": fallback_cap.name,
                    "arguments": {},
                    "description": f"Fallback: использование {fallback_cap.name}",
                    "reasoning": f"Ошибка планирования: {str(e)}. Используется fallback инструмент."
                }
            else:
                fallback_plan = {
                    "tool_name": "error",
                    "arguments": {},
                    "description": "Ошибка планирования: нет доступных инструментов",
                    "reasoning": str(e)
                }
            
            return fallback_thought, fallback_plan
    
    async def _execute_action(
        self,
        action_plan: Dict[str, Any],
        context: ConversationContext
    ) -> Any:
        """Execute action through CapabilityRegistry (provider-agnostic)."""
        capability_name = action_plan.get("tool_name")
        if not capability_name:
            logger.warning("[UnifiedReActEngine] No tool_name in action_plan, skipping execution")
            return ""
        
        # CRITICAL: Block dangerous operations without explicit request
        # This is a safety check at execution time to prevent creating/deleting without user request
        DANGEROUS_OPS_EXECUTE = {
            "create_event": ["создай встречу", "запланируй встречу", "добавь событие", "назначь встречу", "schedule meeting", "create event", "создай событие", "запиши встречу"],
            "delete_event": ["удали встречу", "отмени встречу", "удали событие", "cancel event", "delete event"],
            "send_email": ["отправь письмо", "напиши письмо", "send email", "отправь email", "отправь сообщение"],
        }
        
        if capability_name in DANGEROUS_OPS_EXECUTE:
            # Get goal from context's last message
            goal = ""
            if hasattr(context, 'messages') and context.messages:
                for msg in reversed(context.messages):
                    if msg.get('role') == 'user':
                        goal = msg.get('content', '').lower()
                        break
            
            required_keywords = DANGEROUS_OPS_EXECUTE[capability_name]
            has_explicit_request = any(kw in goal for kw in required_keywords)
            
            if not has_explicit_request:
                logger.error(f"[UnifiedReActEngine] BLOCKED at execute: {capability_name} without explicit request. Goal: {goal[:100]}")
                return f"Операция {capability_name} заблокирована: пользователь не просил выполнить это действие. Для создания/удаления событий нужен явный запрос."
        
        arguments = action_plan.get("arguments", {})
        # Send real progress event BEFORE tool execution
        # For tools that support operations (get_calendar_events, etc.), send operation_start
        operation_id = None
        if self.ws_manager and self.session_id:
            display_name = self._get_tool_display_name(capability_name, arguments)
            intent_id = getattr(self, '_current_intent_id', None)
            
            # Check if this tool supports operations (returns list of items)
            tools_with_operations = {
                # Calendar (уже есть)
                'get_calendar_events': {
                    'title': 'Получаю календарные события',
                    'streaming_title': 'Календарные события',
                    'operation_type': 'read',
                    'file_type': 'calendar'
                },
                
                # Sheets - чтение
                'get_sheet_data': {
                    'title': 'Получаю данные из таблицы',
                    'streaming_title': 'Данные таблицы',
                    'operation_type': 'read',
                    'file_type': 'sheets'
                },
                
                # Sheets - запись
                'add_rows': {
                    'title': 'Записываю строки в таблицу',
                    'streaming_title': 'Записанные строки',
                    'operation_type': 'write',
                    'file_type': 'sheets'
                },
                'update_cells': {
                    'title': 'Обновляю ячейки в таблице',
                    'streaming_title': 'Обновленные ячейки',
                    'operation_type': 'write',
                    'file_type': 'sheets'
                },
                
                # Gmail - чтение
                'list_emails': {
                    'title': 'Получаю список писем',
                    'streaming_title': 'Письма',
                    'operation_type': 'read',
                    'file_type': 'email'
                },
                'search_emails': {
                    'title': 'Ищу письма',
                    'streaming_title': 'Найденные письма',
                    'operation_type': 'read',
                    'file_type': 'email'
                },
                
                # Docs - чтение
                'read_document': {
                    'title': 'Читаю документ',
                    'streaming_title': 'Содержимое документа',
                    'operation_type': 'read',
                    'file_type': 'docs'
                },
                
                # Docs - запись
                'update_document': {
                    'title': 'Обновляю документ',
                    'streaming_title': 'Записанный текст',
                    'operation_type': 'write',
                    'file_type': 'docs'
                },
                
                # Docs - добавление текста
                'append_to_document': {
                    'title': 'Добавляю текст',
                    'streaming_title': 'Добавляемый текст',
                    'operation_type': 'write',
                    'file_type': 'docs'
                },
                
                # Docs - вставка текста
                'insert_into_document': {
                    'title': 'Вставляю текст',
                    'streaming_title': 'Вставляемый текст',
                    'operation_type': 'write',
                    'file_type': 'docs'
                },
                
                # Slides - чтение
                'get_presentation': {
                    'title': 'Получаю информацию о презентации',
                    'streaming_title': 'Слайды презентации',
                    'operation_type': 'read',
                    'file_type': 'slides'
                },
                
                # Docs - форматирование текста
                'format_document_text': {
                    'title': 'Выделяю текст жирным...',
                    'streaming_title': 'Выделение текста',
                    'operation_type': 'write',
                    'file_type': 'docs'
                },
                
                # Docs - форматирование абзацев
                'format_document_paragraph': {
                    'title': 'Форматирую абзацы...',
                    'streaming_title': 'Выравнивание и отступы',
                    'operation_type': 'write',
                    'file_type': 'docs'
                },
            }
            if capability_name in tools_with_operations:
                operation_id = f"op-{int(time.time() * 1000)}"
                op_config = tools_with_operations[capability_name]
                
                # Extract file_id and form file_url for automatic file opening
                file_id = None
                file_url = None
                file_type = op_config.get('file_type')
                
                if file_type == 'sheets':
                    # Extract spreadsheet_id from arguments
                    spreadsheet_id = arguments.get('spreadsheet_id') or arguments.get('spreadsheetId')
                    if spreadsheet_id:
                        # Extract ID from URL if present
                        id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', spreadsheet_id)
                        if id_match:
                            spreadsheet_id = id_match.group(1)
                        elif '/d/' in spreadsheet_id:
                            spreadsheet_id = spreadsheet_id.split('/d/')[1].split('/')[0]
                        file_id = spreadsheet_id
                        file_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/preview"
                
                elif file_type == 'docs':
                    # Extract document_id from arguments
                    document_id = arguments.get('document_id') or arguments.get('documentId')
                    if document_id:
                        # Extract ID from URL if present
                        id_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', document_id)
                        if id_match:
                            document_id = id_match.group(1)
                        elif '/d/' in document_id:
                            document_id = document_id.split('/d/')[1].split('/')[0]
                        file_id = document_id
                        file_url = f"https://docs.google.com/document/d/{document_id}/preview"
                
                elif file_type == 'slides':
                    # Extract presentation_id from arguments
                    presentation_id = arguments.get('presentation_id') or arguments.get('presentationId')
                    if presentation_id:
                        # Extract ID from URL if present
                        id_match = re.search(r'/presentation/d/([a-zA-Z0-9-_]+)', presentation_id)
                        if id_match:
                            presentation_id = id_match.group(1)
                        elif '/d/' in presentation_id:
                            presentation_id = presentation_id.split('/d/')[1].split('/')[0]
                        file_id = presentation_id
                        file_url = f"https://docs.google.com/presentation/d/{presentation_id}/preview"
                
                await self.ws_manager.send_operation_start(
                    self.session_id,
                    operation_id,
                    op_config['title'],
                    op_config['streaming_title'],
                    op_config['operation_type'],
                    file_id=file_id,
                    file_url=file_url,
                    file_type=file_type,
                    intent_id=intent_id,
                    iteration_number=getattr(self, '_current_iteration', None)
                )
                
                # === For write operations, stream content IMMEDIATELY from arguments ===
                # This ensures user sees content being "written" before MCP call completes
                if capability_name in ['append_to_document', 'insert_into_document', 'update_document']:
                    content = arguments.get('content', '')
                    if content:
                        # Stream content line by line for visual effect
                        content_lines = content.split('\n')
                        for line in content_lines:
                            line = line.strip()
                            if line:
                                await self.ws_manager.send_operation_data(
                                    self.session_id,
                                    operation_id,
                                    line
                                )
                                # Small delay for visual streaming effect
                                import asyncio
                                await asyncio.sleep(0.05)
            elif intent_id:
                # Legacy: Send intent_detail for other tools (without dots - they will be added by frontend if needed)
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_detail",
                    {
                        "intent_id": intent_id,
                        "type": "execute",
                        "description": display_name  # Убрали точки - они не нужны, так как анимация убрана
                    }
                )
        _registry_start = time.time()
        # Add session_id, intent_id, and operation_id to arguments for tools that support operations
        # Tools can use these to send operations directly or return structured data
        if self.session_id:
            arguments['_session_id'] = self.session_id
            intent_id = getattr(self, '_current_intent_id', None)
            if intent_id:
                arguments['_intent_id'] = intent_id
            # Pass operation_id to tools that support operations for structured data return
            if operation_id:
                arguments['_operation_id'] = operation_id
        
        # Registry routes to appropriate provider (MCP or A2A)
        result = await self.registry.execute(capability_name, arguments)
        _registry_end = time.time()
        # Process result for operations (parse and stream data)
        if operation_id and self.ws_manager and self.session_id:
            intent_id = getattr(self, '_current_intent_id', None)
            
            # Calendar operations (existing implementation)
            if capability_name == 'get_calendar_events':
                # Parse calendar events from result string
                try:
                    result_str = str(result) if result else ""
                    
                    if 'Found' in result_str and 'event(s)' in result_str:
                        # Result is formatted string, extract count and events
                        lines = result_str.split('\n')
                        count_line = lines[0] if lines else ''
                        
                        # Extract count
                        count_match = re.search(r'Found (\d+) event\(s\)', count_line)
                        if count_match:
                            count = int(count_match.group(1))
                            
                            # Extract events from formatted string (lines starting with number or emoji)
                            events_data = []
                            for line in lines[1:]:
                                line = line.strip()
                                if not line:
                                    continue
                                # Match lines like "1. Event Name" or "📅 Event Name" or lines with event info
                                if re.match(r'^\d+\.', line) or line.startswith('📅') or ('Время:' in line and len(events_data) < count):
                                    # Clean up line
                                    event_info = re.sub(r'^\d+\.\s*', '', line)  # Remove number prefix
                                    event_info = event_info.replace('📅', '').strip()
                                    
                                    # If line contains "Время:", combine with previous event
                                    if 'Время:' in event_info and events_data:
                                        prev_event = events_data[-1]
                                        # Extract just the time part
                                        time_match = re.search(r'Время: ([^-\n]+)', event_info)
                                        if time_match:
                                            time_str = time_match.group(1).strip()
                                            events_data[-1] = f"{prev_event} - {time_str}"
                                    elif event_info and not 'Время:' in event_info:
                                        if not event_info.startswith('   '):  # Skip indented lines (time info)
                                            events_data.append(f"📅 {event_info}")
                            
                            # If we didn't extract events from formatted string, try to extract from numbered lines
                            if not events_data:
                                for line in lines[1:]:
                                    line = line.strip()
                                    if re.match(r'^\d+\.', line):
                                        event_info = re.sub(r'^\d+\.\s*', '', line).strip()
                                        if event_info and 'Found' not in event_info:
                                            events_data.append(f"📅 {event_info}")
                            
                            # Stream events (or just show count if we can't parse individual events)
                            if events_data:
                                for event_data in events_data:
                                    await self.ws_manager.send_operation_data(
                                        self.session_id,
                                        operation_id,
                                        event_data
                                    )
                            
                            # Send operation_end
                            await self.ws_manager.send_operation_end(
                                self.session_id,
                                operation_id,
                                f"Получено {count} встреч"
                            )
                        else:
                            # Couldn't parse count, send summary
                            result_summary = self._get_result_summary(capability_name, result)
                            if result_summary:
                                await self.ws_manager.send_operation_end(
                                    self.session_id,
                                    operation_id,
                                    result_summary
                                )
                    elif result_str.startswith('Found 0'):
                        # No events found
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            "Встречи не найдены"
                        )
                    else:
                        # Unknown format, send summary
                        result_summary = self._get_result_summary(capability_name, result)
                        if result_summary:
                            await self.ws_manager.send_operation_end(
                                self.session_id,
                                operation_id,
                                result_summary
                            )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process operation for {capability_name}: {e}", exc_info=True)
                    # Fallback to summary
                    result_summary = self._get_result_summary(capability_name, result) if capability_name else None
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
            
            # Sheets operations
            elif capability_name in ['get_sheet_data', 'add_rows', 'update_cells']:
                try:
                    items, summary = await self._parse_sheets_result(str(result), capability_name, arguments)
                    if items:
                        for item in items:
                            await self.ws_manager.send_operation_data(
                                self.session_id,
                                operation_id,
                                item
                            )
                    if summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process sheets operation for {capability_name}: {e}", exc_info=True)
                    result_summary = self._get_result_summary(capability_name, result)
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
            
            # Gmail operations
            elif capability_name in ['list_emails', 'search_emails']:
                try:
                    items, summary = await self._parse_gmail_result(str(result), capability_name, arguments)
                    if items:
                        for item in items:
                            await self.ws_manager.send_operation_data(
                                self.session_id,
                                operation_id,
                                item
                            )
                    if summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process gmail operation for {capability_name}: {e}", exc_info=True)
                    result_summary = self._get_result_summary(capability_name, result)
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
            
            # Docs operations
            elif capability_name in ['read_document', 'update_document', 'append_to_document', 'insert_into_document']:
                try:
                    # For write operations, content was already streamed BEFORE MCP call
                    # Only stream for read operations here
                    if capability_name == 'read_document':
                        items, summary = await self._parse_docs_result(str(result), capability_name, arguments)
                        if items:
                            import asyncio
                            for item in items:
                                await self.ws_manager.send_operation_data(
                                    self.session_id,
                                    operation_id,
                                    item
                                )
                                # Small delay for visual streaming effect (50ms per line)
                                await asyncio.sleep(0.05)
                    else:
                        # For write operations, just get the summary
                        _, summary = await self._parse_docs_result(str(result), capability_name, arguments)
                    if summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process docs operation for {capability_name}: {e}", exc_info=True)
                    result_summary = self._get_result_summary(capability_name, result)
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
            
            # Slides operations
            elif capability_name == 'get_presentation':
                try:
                    items, summary = await self._parse_slides_result(str(result), capability_name, arguments)
                    if items:
                        for item in items:
                            await self.ws_manager.send_operation_data(
                                self.session_id,
                                operation_id,
                                item
                            )
                    if summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process slides operation for {capability_name}: {e}", exc_info=True)
                    result_summary = self._get_result_summary(capability_name, result)
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
            
            # Docs formatting operations
            elif capability_name in ['format_document_text', 'format_document_paragraph']:
                result_str = str(result)
                if 'Successfully applied' in result_str:
                    if capability_name == 'format_document_paragraph':
                        summary = "✓ Абзацы отформатированы"
                    else:
                        summary = "✓ Текст выделен"
                    await self.ws_manager.send_operation_end(
                        self.session_id,
                        operation_id,
                        summary
                    )
                else:
                    result_summary = self._get_result_summary(capability_name, result)
                    if result_summary:
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            result_summary
                        )
        elif self.ws_manager and self.session_id:
            # Legacy: Send intent_detail AFTER tool execution with result summary
            intent_id = getattr(self, '_current_intent_id', None)
            if intent_id:
                # Generate result summary
                result_summary = self._get_result_summary(capability_name, result)
                if result_summary:
                    await self.ws_manager.send_event(
                        self.session_id,
                        "intent_detail",
                        {
                            "intent_id": intent_id,
                            "type": "analyze",
                            "description": result_summary
                        }
                    )
        
        return result
    
    async def _parse_sheets_result(self, result_str: str, capability_name: str, arguments: dict) -> tuple[list[str], str]:
        """Парсить результат sheets операций для стриминга."""
        items = []
        summary = ""
        
        if capability_name == 'get_sheet_data':
            # Проверяем, является ли результат JSON с raw_data
            try:
                import json
                result_data = json.loads(result_str)
                if isinstance(result_data, dict) and "raw_data" in result_data:
                    # Инструмент вернул структурированные данные
                    raw_data = result_data["raw_data"]
                    values = raw_data.get("values", [])
                    summary = result_data.get("formatted", f"Получено {len(values)} строк из таблицы")
                    
                    # Стримим строки
                    for i, row in enumerate(values, 1):
                        row_str = ' | '.join(str(cell) for cell in row) if isinstance(row, list) else str(row)
                        items.append(f"{i}. {row_str}")
                else:
                    # Старый формат - парсим строку
                    count_match = re.search(r'Retrieved (\d+) row\(s\)', result_str)
                    if count_match:
                        count = int(count_match.group(1))
                        summary = f"Получено {count} строк из таблицы"
                    else:
                        summary = result_str
            except (json.JSONDecodeError, TypeError):
                # Не JSON, парсим как строку
                count_match = re.search(r'Retrieved (\d+) row\(s\)', result_str)
                if count_match:
                    count = int(count_match.group(1))
                    summary = f"Получено {count} строк из таблицы"
                else:
                    summary = result_str
        
        elif capability_name == 'add_rows':
            # Формат: "Successfully added N row(s) to sheet '...'"
            # Для стриминга используем arguments['values']
            count_match = re.search(r'added (\d+) row\(s\)', result_str)
            if count_match:
                count = int(count_match.group(1))
                summary = f"Записано {count} строк"
            
            # Стримим строки из arguments['values']
            values = arguments.get('values', [])
            if isinstance(values, list):
                for i, row in enumerate(values, 1):
                    row_str = ' | '.join(str(cell) for cell in row) if isinstance(row, list) else str(row)
                    items.append(f"{i}. {row_str}")
        
        elif capability_name == 'update_cells':
            # Формат: "Successfully updated N cell(s)..."
            # Для стриминга используем arguments['values']
            count_match = re.search(r'updated (\d+)', result_str)
            if count_match:
                count = int(count_match.group(1))
                summary = f"Обновлено {count} ячеек"
            
            # Стримим строки из arguments['values']
            values = arguments.get('values', [])
            if isinstance(values, list):
                for i, row in enumerate(values, 1):
                    row_str = ' | '.join(str(cell) for cell in row) if isinstance(row, list) else str(row)
                    items.append(f"{i}. {row_str}")
        
        if not summary:
            summary = result_str or "Операция выполнена"
        
        return items, summary
    
    async def _parse_gmail_result(self, result_str: str, capability_name: str, arguments: dict) -> tuple[list[str], str]:
        """Парсить результат Gmail операций для стриминга."""
        items = []
        summary = ""
        
        # Формат: многострочный с письмами вида "1. 📧 Subject\n   От: from\n   ID: id\n"
        lines = result_str.split('\n')
        
        # Извлекаем количество писем из первой строки
        count_match = re.search(r'📬 (\d+) emails?', result_str)
        if count_match:
            count = int(count_match.group(1))
            summary = f"Найдено {count} писем"
        else:
            # Попробуем найти в другом формате
            count_match = re.search(r'(\d+) emails?', result_str)
            if count_match:
                count = int(count_match.group(1))
                summary = f"Найдено {count} писем"
        
        # Парсим письма - группируем строки по номерам
        current_email = None
        email_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Новая запись начинается с номера
            if re.match(r'^\d+\.', line):
                # Сохраняем предыдущую запись
                if current_email is not None and email_lines:
                    items.append(' '.join(email_lines))
                    email_lines = []
                
                # Начинаем новую запись
                email_info = re.sub(r'^\d+\.\s*', '', line).strip()
                email_lines = [email_info]
                current_email = email_info
            elif email_lines and (line.startswith('   От:') or line.startswith('   ID:') or line.startswith('   ')):
                # Продолжение текущей записи
                email_lines.append(line.strip())
        
        # Сохраняем последнюю запись
        if current_email is not None and email_lines:
            items.append(' '.join(email_lines))
        
        if not summary:
            summary = f"Найдено {len(items)} писем" if items else "Письма не найдены"
        
        return items, summary
    
    async def _parse_docs_result(self, result_str: str, capability_name: str, arguments: dict) -> tuple[list[str], str]:
        """Парсить результат Docs операций для стриминга."""
        items = []
        summary = ""
        
        if capability_name == 'read_document':
            # Формат: "Document: title\n\ncontent"
            # Разделяем по \n\n и стримим строки содержимого построчно
            parts = result_str.split('\n\n', 1)
            if len(parts) == 2:
                title_line = parts[0]
                content = parts[1]
                
                # Извлекаем название документа
                title_match = re.search(r'Document: (.+)', title_line)
                if title_match:
                    title = title_match.group(1)
                    summary = f"Документ: {title}"
                
                # Стримим содержимое построчно
                content_lines = content.split('\n')
                for line in content_lines:
                    line = line.strip()
                    if line:  # Пропускаем пустые строки
                        items.append(line)
            else:
                # Формат не соответствует ожидаемому, стримим всё построчно
                lines = result_str.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('Document:'):
                        items.append(line)
                
                summary = "Документ прочитан"
        
        elif capability_name == 'update_document':
            # Формат: "Document updated: title"
            # Для стриминга используем arguments['content']
            title_match = re.search(r'Document updated: (.+)', result_str)
            if title_match:
                title = title_match.group(1)
                summary = f"Документ обновлен: {title}"
            else:
                summary = "Документ обновлен"
            
            # Стримим содержимое из arguments['content']
            content = arguments.get('content', '')
            if content:
                content_lines = content.split('\n')
                for line in content_lines:
                    line = line.strip()
                    if line:
                        items.append(line)
        
        elif capability_name == 'append_to_document':
            # Для append стримим добавляемый текст из arguments['content']
            summary = "Текст добавлен"
            
            content = arguments.get('content', '')
            if content:
                content_lines = content.split('\n')
                for line in content_lines:
                    line = line.strip()
                    if line:
                        items.append(line)
        
        elif capability_name == 'insert_into_document':
            # Для insert стримим вставляемый текст из arguments['content']
            summary = "Текст вставлен"
            
            content = arguments.get('content', '')
            if content:
                content_lines = content.split('\n')
                for line in content_lines:
                    line = line.strip()
                    if line:
                        items.append(line)
        
        if not summary:
            summary = result_str or "Операция выполнена"
        
        return items, summary
    
    async def _parse_slides_result(self, result_str: str, capability_name: str, arguments: dict) -> tuple[list[str], str]:
        """Парсить результат Slides операций для стриминга."""
        items = []
        summary = ""
        
        # Формат: "Presentation: title\nSlides: N\nSlide IDs:\n  1. id\n..."
        lines = result_str.split('\n')
        
        # Извлекаем название и количество слайдов
        title_match = re.search(r'Presentation: (.+)', result_str)
        slides_match = re.search(r'Slides: (\d+)', result_str)
        
        if title_match:
            title = title_match.group(1)
            if slides_match:
                count = int(slides_match.group(1))
                summary = f"Презентация: {title} ({count} слайдов)"
            else:
                summary = f"Презентация: {title}"
        
        # Парсим слайды после "Slide IDs:"
        in_slide_ids = False
        for line in lines:
            line = line.strip()
            if 'Slide IDs:' in line:
                in_slide_ids = True
                continue
            
            if in_slide_ids:
                if re.match(r'^\d+\.', line):
                    slide_info = re.sub(r'^\d+\.\s*', '', line).strip()
                    items.append(f"Слайд: {slide_info}")
                elif line and not line.startswith('...'):
                    items.append(line)
        
        if not summary:
            summary = "Презентация получена"
        
        return items, summary
    
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
            # Special handling for content modification tools - return what was actually added/written
            # This prevents LLM from generating NEW content instead of citing what was written
            content_modification_tools = ['append_to_document', 'insert_into_document', 'update_document']
            
            for action in state.action_history:
                if action.tool_name in content_modification_tools:
                    content = action.arguments.get('content', '')
                    if content:
                        # Return a simple confirmation with the actual content that was added
                        return f"✅ Текст добавлен в документ:\n\n{content}"
            
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
ВАЖНО: Опиши КОНКРЕТНО что находится в КАЖДОМ файле:
- Для PDF/Word: кратко опиши содержание документа
- Для изображения: опиши что на нём изображено
Если на изображении есть люди - опиши что они делают и в каком контексте.
НЕ отказывайся отвечать на вопросы о людях на изображении - описывай общими словами!

ОБЯЗАТЕЛЬНО ответь по ВСЕМ прикреплённым файлам!

В конце ответа добавь: "Если вас интересует что-то конкретное в этих файлах, уточните — я подберу нужную информацию."

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

⚠️ КРИТИЧНО - СОХРАНЯЙ ССЫЛКИ:
- Если в данных есть markdown ссылки [название](url), СОХРАНИ их в ответе!
- Названия событий календаря должны быть КЛИКАБЕЛЬНЫМИ: [Офис](url), а НЕ просто "Офис"
- Email-адреса оставляй как есть

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
            
            # Create messages list with conversation history for context
            messages = []
            
            # Add conversation history for follow-up context (CRITICAL for reference resolution)
            # This allows the model to understand what was discussed before
            if context and hasattr(context, 'messages') and context.messages:
                recent_msgs = context.messages[-6:]  # Last 3 exchanges
                for msg in recent_msgs:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if not content:
                        continue
                    if role == 'user':
                        messages.append(HumanMessage(content=content))
                    elif role == 'assistant':
                        messages.append(AIMessage(content=content))
            
            # Create current message (multimodal if images present)
            if image_contents:
                message_content = [{"type": "text", "text": prompt}] + image_contents
                messages.append(HumanMessage(content=message_content))
            else:
                messages.append(HumanMessage(content=prompt))

            # Stream the response
            full_answer = ""
            
            # Check if main task intent already covers file analysis
            # If so, use it instead of creating a duplicate intent
            task_intent_id = getattr(self, '_task_intent_id', None)
            main_intent_is_file_analysis = file_contents_text and task_intent_id
            
            if main_intent_is_file_analysis:
                # Reuse the main task intent - don't create a duplicate
                intent_id = task_intent_id
            else:
                # Send intent event for "Формирую ответ" or similar
                intent_message = "Формирую ответ"
                if len(image_contents) > 0:
                    intent_message += f" (включая {len(image_contents)} изображение(я))..."
                else:
                    intent_message += "..."
                
                intent_id = f"intent-final-{int(time.time() * 1000)}"
                await self.ws_manager.send_event(
                    self.session_id,
                    "intent_start",
                    {"intent_id": intent_id, "text": intent_message}
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
            _stream_chunk_count = 0
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
                    _stream_chunk_count += 1
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
        
        # === NEW ARCHITECTURE: Complete the task-level intent ===
        task_intent_id = getattr(self, '_task_intent_id', None)
        if task_intent_id and self.ws_manager and self.session_id:
            await self.ws_manager.send_event(
                self.session_id,
                "intent_complete",
                {
                    "intent_id": task_intent_id,
                    "summary": f"✅ Задача выполнена за {state.iteration} шаг(ов)",
                    "auto_collapse": False  # Keep expanded to show result
                }
            )
        
        # Check if this is a confirmation request - return tool result directly without LLM reformulation
        final_result_str = str(final_result).lower() if final_result else ""
        confirmation_indicators = [
            "создать встречу на это время?",
            "требуется подтверждение",
            "подтвердите",
            "удалить события?"
        ]
        is_confirmation_request = any(ind in final_result_str for ind in confirmation_indicators)
        
        if is_confirmation_request and final_result:
            # For confirmation requests, return tool result as-is to preserve all information
            human_answer = str(final_result)
            logger.info(f"[UnifiedReActEngine] Confirmation request detected - returning tool result directly")
            
            # Extract meeting details from tool result and save to pending_confirmations
            # Look for the last schedule_group_meeting action
            for action in reversed(state.action_history):
                if action.tool_name == "schedule_group_meeting":
                    # Extract slot_start from result (format: "2026-01-15 16:10 - 17:10")
                    import re
                    slot_match = re.search(r'\*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', str(final_result))
                    if slot_match:
                        slot_start = slot_match.group(1)
                        
                        # Extract description from original goal if not in arguments
                        description = action.arguments.get("description")
                        if not description:
                            # Try to extract from original goal (look for "в содержании", "описание", "тост")
                            goal_lower = state.goal.lower()
                            if "в содержании" in goal_lower or "описание" in goal_lower or "тост" in goal_lower:
                                # Try multiple patterns - more flexible
                                patterns = [
                                    r'в содержании[^\w]*(?:напиши|напиши|добавь)[^\w]*(.+?)(?:\.|$)',
                                    r'в содержании[^\w]+(.+?)(?:\.|$)',
                                    r'описание[^\w]+(.+?)(?:\.|$)',
                                    r'тост[^\w]+(.+?)(?:\.|$)',
                                    r'(?:в содержании|описание|тост)[\s:]+(.+?)(?:\.|$)',
                                ]
                                for pattern in patterns:
                                    desc_match = re.search(pattern, state.goal, re.IGNORECASE | re.DOTALL)
                                    if desc_match:
                                        description = desc_match.group(1).strip()
                                        description = description.strip('"\'')
                                        if description:
                                            break
                                
                                # If still not found, try to extract everything after "в содержании" to end
                                if not description:
                                    desc_match = re.search(r'в содержании[^\w]+(.+)', state.goal, re.IGNORECASE | re.DOTALL)
                                    if desc_match:
                                        description = desc_match.group(1).strip()
                                        description = description.rstrip('.,;!?')
                                        description = description.strip('"\'')
                        
                        context.pending_confirmations["meeting"] = {
                            "tool": "schedule_group_meeting",
                            "arguments": {
                                "title": action.arguments.get("title", "Встреча"),
                                "attendees": action.arguments.get("attendees", []),
                                "duration": action.arguments.get("duration", "1h"),
                                "slot_start": slot_start,
                                "description": description,
                                "location": action.arguments.get("location"),
                                "original_goal": state.goal  # Save original goal for ReAct
                            }
                        }
                        logger.info(f"[UnifiedReActEngine] Saved pending confirmation: slot_start={slot_start}, description={description[:50] if description else None}")
                    break
        else:
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
        
        # Save response to context with source_files metadata for follow-up reference resolution
        if hasattr(context, 'add_message'):
            # Extract entities from the response for future reference resolution
            extracted_entities = extract_entities_from_response(human_answer)
            
            context.add_message(
                "assistant",
                human_answer,
                metadata={
                    "source_files": file_ids or [],
                    "extracted_entities": extracted_entities,
                    "goal": state.goal
                }
            )
            logger.info(f"[execute] Saved response with source_files={file_ids}, entities={extracted_entities[:5] if extracted_entities else []}")
        
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
        
        # === NEW ARCHITECTURE: Complete the task-level intent with failure status ===
        task_intent_id = getattr(self, '_task_intent_id', None)
        if task_intent_id and self.ws_manager and self.session_id:
            error_msg = analysis.error_message or "Не удалось выполнить"
            await self.ws_manager.send_event(
                self.session_id,
                "intent_complete",
                {
                    "intent_id": task_intent_id,
                    "summary": f"❌ {error_msg[:50]}",
                    "auto_collapse": False
                }
            )
        
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
        
        # === NEW ARCHITECTURE: Complete the task-level intent with timeout status ===
        task_intent_id = getattr(self, '_task_intent_id', None)
        if task_intent_id and self.ws_manager and self.session_id:
            await self.ws_manager.send_event(
                self.session_id,
                "intent_complete",
                {
                    "intent_id": task_intent_id,
                    "summary": f"⏱️ Достигнут лимит ({state.iteration} итераций)",
                    "auto_collapse": False
                }
            )
        
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
                    # === NEW ARCHITECTURE: Don't create new intent, just track tool ===
                    tool = data.get("tool", "unknown")
                    action = data.get("action", "")
                    
                    # Save tool for later use in observation
                    self._last_tool = tool
                    
                    # Don't create new intent - details are added in main loop
                    # Keep using task-level intent
                    pass
                
                elif event_type == "react_observation":
                    # === NEW ARCHITECTURE: Add result as intent_detail, don't complete yet ===
                    task_intent_id = getattr(self, '_task_intent_id', None)
                    if task_intent_id:
                        result = str(data.get("result", ""))
                        tool = getattr(self, '_last_tool', 'unknown')
                        
                        # Format result into human-readable Russian summary
                        summary = self._format_result_summary(result, tool)
                        
                        # Send summary as intent_detail
                        if summary:
                            await self.ws_manager.send_event(
                                self.session_id,
                                "intent_detail",
                                {
                                    "intent_id": task_intent_id,
                                    "type": "analyze",
                                    "description": summary
                                }
                            )
                        
                        # Extract and send result details (e.g., meeting names, file names)
                        details = self._extract_result_details(result)
                        for detail in details[:5]:  # Limit to 5 details per observation
                            await self.ws_manager.send_event(
                                self.session_id,
                                "intent_detail",
                                {
                                    "intent_id": task_intent_id,
                                    "type": "analyze",
                                    "description": detail
                                }
                            )
                        
                        # Don't complete intent here - only in _finalize_success
                
            else:
                logger.debug(f"[UnifiedReActEngine] Skipping event {event_type} - no WebSocket connection")
        except Exception as e:
            logger.debug(f"[UnifiedReActEngine] Failed to send event {event_type}: {e}")

