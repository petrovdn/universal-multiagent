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
from src.core.task_decomposer import SubTask, DecompositionResult
from src.core.dependency_analyzer import ExecutionPlan
from src.core.synthesis_agent import SynthesisAgent
from src.core.file_reference_resolver import (
    get_relevant_file_ids,
    find_source_for_reference,
    extract_entities_from_response,
)
from src.core.skills.skill_instructions_cache import SkillInstructionsCache
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm, supports_vision
from src.utils.logging_config import get_logger
from src.utils.config_loader import DATA_DIR

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
        # #region agent log - начало инициализации engine
        import json as _debug_json_init; import time as _debug_time_init
        _engine_init_start = _debug_time_init.time()
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_init_start:
                _debug_f_init_start.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_engine_init_start","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:61","message":"UnifiedReActEngine.__init__ start","data":{"mode":config.mode if hasattr(config, 'mode') else "unknown"},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        self.config = config
        self.registry = capability_registry
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
        
        # Get allowed capabilities based on config
        _capabilities_start = _debug_time_init.time()
        self.capabilities = self.registry.get_capabilities(
            categories=config.allowed_categories
        )
        _capabilities_duration = _debug_time_init.time() - _capabilities_start
        # #region agent log - capabilities получены
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_cap:
                _debug_f_cap.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_capabilities_obtained","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:86","message":"Capabilities obtained","data":{"capabilities_count":len(self.capabilities) if hasattr(self.capabilities, '__len__') else 0,"duration_ms":_capabilities_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Build LLM tools from capabilities for planning
        _tools_build_start = _debug_time_init.time()
        self.tools = self._build_tools_from_capabilities()
        _tools_build_duration = _debug_time_init.time() - _tools_build_start
        # #region agent log - tools построены
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tools:
                _debug_f_tools.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_tools_built","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:91","message":"Tools built from capabilities","data":{"tools_count":len(self.tools) if hasattr(self.tools, '__len__') else 0,"duration_ms":_tools_build_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Create LLM with thinking support
        _llm_create_start = _debug_time_init.time()
        self.llm = self._create_llm_with_thinking()
        _llm_create_duration = _debug_time_init.time() - _llm_create_start
        # #region agent log - LLM создан
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_llm:
                _debug_f_llm.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_llm_created","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:94","message":"LLM with thinking created","data":{"duration_ms":_llm_create_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Bind tools to LLM
        _bind_start = _debug_time_init.time()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        _bind_duration = _debug_time_init.time() - _bind_start
        # #region agent log - tools привязаны
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_bind:
                _debug_f_bind.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_tools_bound","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:97","message":"Tools bound to LLM","data":{"duration_ms":_bind_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Store context reference for StreamingThoughtParser access
        self._current_context: Optional[ConversationContext] = None
        
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
        
        # Tool explanation generator (Phase 1.1)
        from src.core.tool_explanation_generator import ToolExplanationGenerator
        self.tool_explanation_generator = ToolExplanationGenerator()
        
        # Source tracker (Phase 1.2)
        from src.core.source_tracker import SourceTracker
        self.source_tracker = SourceTracker(ws_manager, session_id)
        
        # Task decomposer and dependency analyzer (Phase 2, Steps 1-2)
        from src.core.task_decomposer import TaskDecomposer
        from src.core.dependency_analyzer import DependencyAnalyzer
        from src.core.synthesis_agent import SynthesisAgent
        self.task_decomposer = TaskDecomposer()
        self.dependency_analyzer = DependencyAnalyzer()
        self.synthesis_agent = SynthesisAgent()
        
        # Smart tool selection (Phase 3.1)
        # Feature flag: USE_SMART_TOOL_SELECTION (default: True - semantic search for tools)
        import os
        self.use_smart_tool_selection = os.getenv("USE_SMART_TOOL_SELECTION", "true").lower() == "true"
        
        self.smart_tool_selector = None
        self.skill_selector = None
        self.active_skill = None
        # Short-lived cache для formatted skill instructions (TTL 5 минут)
        self._skill_instructions_cache = SkillInstructionsCache(ttl_seconds=300)
        
        # Intent tracking for parallel branches
        self._use_existing_intent_id = None  # Set when executing parallel branch subtasks
        
        if self.use_smart_tool_selection:
            try:
                _smart_selector_start = _debug_time_init.time()
                from src.core.tool_selection.smart_selector import SmartToolSelector
                from src.core.skills.skill_loader import SkillLoader
                from src.core.skills.skill_selector import SkillSelector
                from pathlib import Path
                
                # Initialize SmartToolSelector
                cache_dir = DATA_DIR / "tool_embeddings"
                
                # Опция для принудительного пересчета embeddings при перезагрузке сервера
                # Установите FORCE_RECOMPUTE_EMBEDDINGS=true для пересчета всех embeddings
                import os
                force_recompute = os.getenv("FORCE_RECOMPUTE_EMBEDDINGS", "false").lower() == "true"
                
                if force_recompute:
                    logger.info("[UnifiedReActEngine] FORCE_RECOMPUTE_EMBEDDINGS=true: will recompute all embeddings")
                
                # SmartToolSelector теперь предзагружает embeddings в память при инициализации
                # Это позволяет избежать дисковых операций при каждом вызове select_tools
                self.smart_tool_selector = SmartToolSelector(
                    capabilities=self.capabilities,
                    cache_dir=cache_dir,
                    preload_embeddings=True,  # Предзагрузить embeddings в память
                    force_recompute=force_recompute  # Принудительно пересчитать если флаг установлен
                )
                _smart_selector_duration = _debug_time_init.time() - _smart_selector_start
                # #region agent log - SmartToolSelector создан
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_smart:
                        _debug_f_smart.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_smart_selector_created","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:167","message":"SmartToolSelector created with preload_embeddings=True","data":{"duration_ms":_smart_selector_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                except:
                    pass
                # #endregion
                
                # Initialize SkillLoader and SkillSelector
                project_root = Path(__file__).parent.parent.parent
                skills_dir = project_root / "skills"
                if skills_dir.exists():
                    loader = SkillLoader(skills_dir=skills_dir)
                    skills = loader.load_all_skills()
                    if skills:
                        self.skill_selector = SkillSelector(
                            skills=skills,
                            cache_dir=cache_dir
                        )
                        logger.info(f"[UnifiedReActEngine] Smart tool selection enabled with {len(skills)} skills")
                    else:
                        logger.warning("[UnifiedReActEngine] No skills found, skill selection disabled")
                else:
                    logger.warning(f"[UnifiedReActEngine] Skills directory not found: {skills_dir}")
                    
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Failed to initialize smart tool selection: {e}")
                self.use_smart_tool_selection = False
                logger.warning("[UnifiedReActEngine] Falling back to keyword-based tool selection")
        
        # #region agent log - завершение инициализации engine
        _engine_init_total_duration = _debug_time_init.time() - _engine_init_start
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_init_end:
                _debug_f_init_end.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_engine_init_complete","timestamp":int(_debug_time_init.time()*1000),"location":"unified_react_engine.py:250","message":"UnifiedReActEngine.__init__ complete","data":{"total_init_duration_ms":_engine_init_total_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
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
    
    def _detect_thinking_context(self, content: str) -> str:
        """Определяем контекст думания по содержимому (Cursor-style).
        
        Returns:
            ThinkingContext: 'planning', 'exploring', 'analyzing', 'selecting', 'verifying', 'deciding', 'thinking'
        """
        content_lower = content.lower()
        
        # #region agent log - логирование определения контекста
        import json as _debug_json_context; import time as _debug_time_context
        content_preview = content[:200]  # Первые 200 символов для анализа
        content_length = len(content)
        detected_context = None
        matched_keywords = []
        
        # Проверяем ключевые слова в порядке приоритета
        # ИСПРАВЛЕНИЕ: Используем корни слов для более точного поиска
        planning_keywords = ['план', 'шаг', 'сначала', 'затем', 'далее', 'порядок']
        exploring_keywords = ['чита', 'смотр', 'ищу', 'файл', 'код', 'исслед', 'изуча']  # Корни: чита(ть/ю), смотр(ю/ю), исслед(ую)
        analyzing_keywords = ['анализ', 'обрабатыв', 'понима', 'разбира']  # Корни: обрабатыв(аю/ать)
        selecting_keywords = ['инструмент', 'tool', 'использ', 'выбира', 'вызов']  # Корни: использ(ую/ую)
        verifying_keywords = ['проверя', 'убежда', 'тест', 'валидир']
        deciding_keywords = ['решил', 'решаю', 'вывод', 'итог', 'результат']
        
        if any(word in content_lower for word in planning_keywords):
            detected_context = 'planning'
            matched_keywords = [w for w in planning_keywords if w in content_lower]
        elif any(word in content_lower for word in exploring_keywords):
            detected_context = 'exploring'
            matched_keywords = [w for w in exploring_keywords if w in content_lower]
        elif any(word in content_lower for word in analyzing_keywords):
            detected_context = 'analyzing'
            matched_keywords = [w for w in analyzing_keywords if w in content_lower]
        elif any(word in content_lower for word in selecting_keywords):
            detected_context = 'selecting'
            matched_keywords = [w for w in selecting_keywords if w in content_lower]
        elif any(word in content_lower for word in verifying_keywords):
            detected_context = 'verifying'
            matched_keywords = [w for w in verifying_keywords if w in content_lower]
        elif any(word in content_lower for word in deciding_keywords):
            detected_context = 'deciding'
            matched_keywords = [w for w in deciding_keywords if w in content_lower]
        else:
            detected_context = 'thinking'
        
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_context:
                _debug_f_context.write(_debug_json_context.dumps({
                    "id": f"log_{int(_debug_time_context.time()*1000)}_detect_thinking_context",
                    "timestamp": int(_debug_time_context.time()*1000),
                    "location": "unified_react_engine.py:275",
                    "message": "_detect_thinking_context: определение контекста",
                    "data": {
                        "content_length": content_length,
                        "content_preview_first_200_chars": content_preview,
                        "content_preview_first_100_chars": content[:100],
                        "content_preview_first_50_chars": content[:50],
                        "detected_context": detected_context,
                        "matched_keywords": matched_keywords,
                        "all_keywords_checked": {
                            "planning": planning_keywords,
                            "exploring": exploring_keywords,
                            "analyzing": analyzing_keywords,
                            "selecting": selecting_keywords,
                            "verifying": verifying_keywords,
                            "deciding": deciding_keywords
                        }
                    },
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "THINKING_CONTEXT"
                }, ensure_ascii=False) + '\n')
        except:
            pass
        # #endregion
        
        return detected_context
    
    def _get_use_existing_intent_id(self, state: ReActState) -> Optional[str]:
        """
        Получить use_existing_intent_id из state.context для изоляции параллельных веток.
        
        CRITICAL FIX: Используем state.context вместо self._use_existing_intent_id
        чтобы избежать race condition между параллельными ветками.
        
        Args:
            state: ReActState с context, содержащим use_existing_intent_id
            
        Returns:
            use_existing_intent_id или None
        """
        if state.context and "use_existing_intent_id" in state.context:
            return state.context["use_existing_intent_id"]
        # Fallback для backward compatibility (не должно использоваться для параллельных веток)
        return getattr(self, '_use_existing_intent_id', None)
    
    def _determine_thinking_result(self, action_plan: Dict[str, Any], observation: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Определяем результат думания для отображения после завершения.
        
        Returns:
            ThinkingResult или None (если нет реальных tool calls)
        """
        tool_name = action_plan.get("tool_name", "")
        
        # Не показываем результат для FINISH или пустого tool_name (нет реальных tool calls)
        if not tool_name or tool_name.upper() == "FINISH" or tool_name == "ASK_CLARIFICATION":
            return None
        
        # Определяем тип результата по инструменту
        if tool_name in ["search_documents", "search_emails", "search_web", "search_calendar"]:
            return {"type": "searches", "count": 1}
        elif tool_name in ["read_document", "read_file", "get_document_content", "read_spreadsheet"]:
            return {"type": "files", "count": 1}
        elif tool_name in ["list_calendar_events", "list_emails", "get_contacts"]:
            return {"type": "sources", "count": 1}
        elif tool_name:
            return {"type": "tools", "count": 1}
        
        return None

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
        phase: Optional[str] = None,  # For Plan Mode: "research", "plan", "execute"
        skip_orchestration: bool = False,  # Skip orchestration for subtasks
        use_existing_intent_id: Optional[str] = None  # Use existing intent_id for subtasks (from parallel_branch_start)
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
        # #region agent log
        import json as _debug_json_exec; import time as _debug_time_exec
        _execute_start = _debug_time_exec.time()  # Сохраняем время старта для логирования в finally
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_exec:
                _debug_f_exec.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_execute_entry","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:324","message":"execute() entry point","data":{"goal":goal[:200],"skip_orchestration":skip_orchestration,"use_existing_intent_id":use_existing_intent_id,"phase":phase},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except:
            pass
        # #endregion
        
        # Нормализуем неразрывные пробелы (U+00A0) в обычные пробелы
        # Это критично для keyword matching в DANGEROUS_OPERATIONS и других проверках
        if goal:
            goal = goal.replace('\u00a0', ' ').replace('\xa0', ' ')
        
        file_ids = file_ids or []
        
        # CRITICAL: Save parallel subtask flag as LOCAL variable at the VERY START
        # This must be defined before ANY early returns to avoid NameError
        # This is checked at the end to skip final_result for subtasks
        _local_is_parallel_subtask = use_existing_intent_id is not None
        
        # CRITICAL: Save skip_orchestration flag as class attribute for ReAct cycle
        # Used to skip source tracking in orchestrated tasks (prevents old card UI)
        self._skip_source_tracking = skip_orchestration or _local_is_parallel_subtask
        
        # Send research phase started event
        if phase == "research":
            try:
                await self.ws_manager.send_event(
                    self.session_id,
                    "research_phase_started",
                    {
                        "goal": goal[:200] if goal else "",
                        "message": "Начинаю исследование доступных инструментов и данных..."
                    }
                )
            except Exception as e:
                logger.error(f"Failed to send research_phase_started event: {e}")
        
        # === Check for pending confirmation ===
        goal_lower = goal.lower().strip()
        confirmation_keywords = ["да", "давай", "создай", "подтверждаю", "ок", "ok", "yes", "согласен"]
        is_confirmation = any(kw in goal_lower for kw in confirmation_keywords) and len(goal_lower) < 20
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_conf:
                _debug_f_conf.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_confirmation_check","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:380","message":"Checking for confirmation","data":{"goal":goal[:200],"is_confirmation":is_confirmation,"has_pending_meeting":bool(context.pending_confirmations.get("meeting"))},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
        except:
            pass
        # #endregion
        
        if is_confirmation and context.pending_confirmations.get("meeting"):
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_conf_ret:
                    _debug_f_conf_ret.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_confirmation_return","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:380","message":"Returning from confirmation handler (BYPASSING ReAct cycle)","data":{"goal":goal[:200]},"sessionId":"debug-session","runId":"run1","hypothesisId":"H"}) + '\n')
            except:
                pass
            # #endregion
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
            
            # DIRECT TOOL CALL: Instead of passing to LLM (which fails with long descriptions),
            # directly call schedule_group_meeting with confirmed=True
            logger.info(f"[UnifiedReActEngine] Calling schedule_group_meeting directly with confirmed=True")
            
            # Prepare arguments for direct tool call
            tool_args = {
                "title": args.get("title", "Встреча"),
                "attendees": args.get("attendees", []),
                "duration": args.get("duration", "1h"),
                "slot_start": slot_start,
                "confirmed": True
            }
            
            # Add optional parameters
            if args.get("working_hours_start") is not None:
                tool_args["working_hours_start"] = args["working_hours_start"]
            if args.get("working_hours_end") is not None:
                tool_args["working_hours_end"] = args["working_hours_end"]
            if description:
                tool_args["description"] = description
            if args.get("location"):
                tool_args["location"] = args["location"]
            
            # Execute tool directly
            # CRITICAL FIX: Передаём state=None (fallback на self._current_state для backward compatibility)
            try:
                result = await self._execute_action(
                    action_plan={"tool_name": "schedule_group_meeting", "arguments": tool_args},
                    context=context,
                    state=None  # Fallback на self._current_state (для backward compatibility)
                )
                
                logger.info(f"[UnifiedReActEngine] Direct tool call result type: {type(result)}, value: {str(result)[:200]}")
                
                # schedule_group_meeting returns a string, not a dict
                if isinstance(result, str):
                    response_text = result
                elif isinstance(result, dict) and "response" in result:
                    response_text = result["response"]
                else:
                    response_text = str(result)
                
                logger.info(f"[UnifiedReActEngine] About to send final_result event with response: {response_text[:100]}")
                
                # CRITICAL FIX: Skip final_result for parallel subtasks - they use parallel_branch_complete instead
                # Check if this is a parallel subtask by checking use_existing_intent_id from state
                # CRITICAL: Используем _local_is_parallel_subtask, который определён в начале execute()
                # Не используем self._use_existing_intent_id из-за race condition между параллельными ветками
                is_parallel_subtask = _local_is_parallel_subtask
                if not is_parallel_subtask:
                    # Send final_result event through WebSocket directly (not via _stream_reasoning)
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result",
                        {
                            "content": response_text,
                            "status": "success"
                        }
                    )
                    logger.info(f"[UnifiedReActEngine] final_result event sent successfully")
                else:
                    logger.info(f"[UnifiedReActEngine] Skipping final_result for parallel subtask (use_existing_intent_id={use_existing_intent_id})")
                
                # Add assistant message to context
                context.add_message("assistant", response_text)
                
                # Return success message
                return {
                    "agent": self.__class__.__name__,
                    "response": response_text,
                    "status": "success"
                }
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Direct tool call failed: {e}")
                # Fallback to ReAct if direct call fails
                goal = f"Создай встречу '{tool_args['title']}' с участниками {attendees_str} на время {slot_start}"
        
        # === Упрощённая логика выбора файлов ===
        # НОВЫЙ ПОДХОД: Всё в контекст + LLM сам разбирается
        # file_ids используются только для оптимизации (включить полное содержимое конкретных файлов)
        # Сводка ВСЕХ файлов всегда показывается в промпте, даже если file_ids пустые
        if not file_ids and context and hasattr(context, 'uploaded_files') and context.uploaded_files:
            goal_lower = goal.lower()
            
            # #region agent log - начало разрешения файлов
            import json as _debug_json_file_resolve; import time as _debug_time_file_resolve
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_file_resolve:
                    _debug_f_file_resolve.write(_debug_json_file_resolve.dumps({
                        "id": f"log_{int(_debug_time_file_resolve.time()*1000)}_file_resolution_start",
                        "timestamp": int(_debug_time_file_resolve.time()*1000),
                        "location": "unified_react_engine.py:672",
                        "message": "FILE RESOLUTION START (simplified)",
                        "data": {
                            "goal": goal,
                            "uploaded_files_count": len(context.uploaded_files),
                            "uploaded_file_ids": list(context.uploaded_files.keys()),
                            "uploaded_file_names": [f.get('filename', 'unknown') for f in context.uploaded_files.values()]
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "FILE_RESOLUTION"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # 1. Multi-part query (явный запрос про несколько файлов)
            multi_part_indicators = [' и ', ' а также ', ' ещё ', ' еще ', ' плюс ', ' потом ']
            is_multi_part_query = any(ind in goal_lower for ind in multi_part_indicators)
            
            if is_multi_part_query and len(context.uploaded_files) > 1:
                file_ids = list(context.uploaded_files.keys())
                logger.info(f"[execute] Multi-part query detected, using ALL {len(file_ids)} files: {file_ids}")
                print(f"[execute] Multi-part query - using all files: {file_ids}", flush=True)
            # 2. General query (явный запрос про все файлы)
            elif any(p in goal_lower for p in ['что видишь', 'что в файл', 'опиши файл', 'опиши все', 'про все файлы', 'во всех файлах', 'в файлах']):
                file_ids = list(context.uploaded_files.keys())
                logger.info(f"[execute] General query about files, using ALL {len(file_ids)} files: {file_ids}")
                print(f"[execute] General query - using all files: {file_ids}", flush=True)
            # 3. Ищем файлы из предыдущего ответа (для follow-up вопросов)
            else:
                # Ищем в последнем ответе ассистента
                if hasattr(context, 'messages') and context.messages:
                    for msg in reversed(context.messages[-10:]):
                        if msg.get("role") == "assistant":
                            metadata = msg.get("metadata", {})
                            prev_source_files = metadata.get("source_files", [])
                            if prev_source_files:
                                file_ids = prev_source_files
                                logger.info(f"[execute] Using files from previous response: {file_ids}")
                                print(f"[execute] Using files from previous response: {file_ids}", flush=True)
                                break
                
                # Если не нашли в истории - оставляем file_ids пустым
                # LLM увидит сводку всех файлов и сам разберется
                if not file_ids:
                    logger.info(f"[execute] No specific files identified - LLM will use file summary from context")
                    print(f"[execute] No specific files - LLM will use file summary", flush=True)
            
            # #region agent log - результат разрешения
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_file_resolve:
                    _debug_f_file_resolve.write(_debug_json_file_resolve.dumps({
                        "id": f"log_{int(_debug_time_file_resolve.time()*1000)}_file_resolution_result",
                        "timestamp": int(_debug_time_file_resolve.time()*1000),
                        "location": "unified_react_engine.py:720",
                        "message": "FILE RESOLUTION: Result",
                        "data": {"file_ids": file_ids, "method": "simplified"},
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "FILE_RESOLUTION"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
        
        logger.info(f"[execute] Starting execution - goal: {goal[:100]}, file_ids: {file_ids}, file_ids count: {len(file_ids)}")
        print(f"[execute] Starting execution - goal: {goal[:100]}, file_ids: {file_ids}", flush=True)
        if hasattr(context, 'uploaded_files'):
            total_files = len(context.uploaded_files)
            logger.info(f"[execute] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}")
            print(f"[execute] Context has {total_files} uploaded files: {list(context.uploaded_files.keys())}", flush=True)
        _exec_start = time.time()
        _calendar_caps = [c.name for c in self.capabilities if 'calendar' in c.name.lower() or 'event' in c.name.lower()]
        
        # Note: _local_is_parallel_subtask is already defined at the start of execute()
        
        # #region agent log - проверка изоляции state для параллельных веток
        is_parallel_log = use_existing_intent_id is not None
        if is_parallel_log:
            import json as _debug_json_state_init; import time as _debug_time_state_init
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_state_init:
                    _debug_f_state_init.write(_debug_json_state_init.dumps({"id":f"log_{int(_debug_time_state_init.time()*1000)}_state_init","timestamp":int(_debug_time_state_init.time()*1000),"location":"unified_react_engine.py:660","message":"Creating new ReActState for parallel branch","data":{"is_parallel":True,"use_existing_intent_id":use_existing_intent_id,"goal":goal[:100],"engine_id":id(self)},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            except:
                pass
        # #endregion
        
        # Initialize state
        state = ReActState(goal=goal)
        # CRITICAL FIX: Сохраняем use_existing_intent_id в state.context для изоляции параллельных веток
        # Это предотвращает race condition, когда параллельные ветки перезаписывают self._use_existing_intent_id
        state.context = {
            "file_ids": file_ids,
            "session_id": self.session_id,
            "phase": phase,
            "use_existing_intent_id": use_existing_intent_id  # Изолированное значение для этой ветки
        }
        self._stop_requested = False
        
        # CRITICAL: Store context reference for StreamingThoughtParser access
        # CRITICAL FIX: Не храним context в self для параллельных веток, чтобы избежать утечки данных
        if not _local_is_parallel_subtask:
            self._current_context = context
        
        # === OPTIMIZATION: Send intent_start IMMEDIATELY for instant feedback ===
        # Analyze task phases (fast - regex only, no LLM)
        # CRITICAL: For parallel subtasks, DISABLE multi-phase to avoid creating new intents
        # PHASE 0 FIX: Disable multi-phase logic completely
        task_phases = []
        self._is_multi_phase = False
        # Оригинальный код закомментирован:
        # if use_existing_intent_id:
        #     # Parallel subtask: use provided intent_id, disable multi-phase
        #     task_phases = []
        #     self._is_multi_phase = False
        # else:
        #     task_phases = self._analyze_task_phases(goal)
        #     self._is_multi_phase = len(task_phases) >= 2
        self._task_phases = task_phases
        self._current_phase_category = None
        self._phase_intent_ids = {}  # category -> intent_id mapping
        # Create intent_start IMMEDIATELY (before any LLM calls)
        # Use existing intent_id if provided (for parallel subtasks)
        if use_existing_intent_id:
            task_intent_id = use_existing_intent_id
            self._current_intent_id = task_intent_id
            # PHASE 0 FIX: Only set _use_existing_intent_id if it's not None (for parallel branches)
            # For simple queries, use_existing_intent_id is None, so we should NOT set it
            if use_existing_intent_id is not None:
                self._use_existing_intent_id = use_existing_intent_id  # Store for ReAct loop to send parallel_branch_iteration events
            else:
                self._use_existing_intent_id = None  # Explicitly clear for simple queries
            logger.info(f"[UnifiedReActEngine] Using existing intent_id for subtask: {task_intent_id}")
        elif self._is_multi_phase:
            self._use_existing_intent_id = None  # Clear previous value
            logger.info(f"[UnifiedReActEngine] Multi-phase task detected: {len(task_phases)} phases")
            # Create the FIRST phase intent
            first_phase = task_phases[0]
            task_intent_id = f"phase-{int(time.time() * 1000)}"
            self._current_intent_id = task_intent_id
            self._current_phase_category = first_phase['category']
            self._phase_intent_ids[first_phase['category']] = task_intent_id
            # PHASE 0 FIX: Disable intent_start events
            # await self.ws_manager.send_event(
            #     self.session_id,
            #     "intent_start",
            #     {"intent_id": task_intent_id, "text": first_phase['description']}
            # )
        else:
            # Single-phase task: Create ONE task-level intent for the entire goal
            # CRITICAL FIX: Don't create new intent_id if this is a parallel subtask
            # Parallel subtasks should use use_existing_intent_id (handled in if block above)
            if use_existing_intent_id:
                # This should not happen - use_existing_intent_id should be handled in if block
                # But if it somehow reaches here, use it
                task_intent_id = use_existing_intent_id
                self._current_intent_id = task_intent_id
                logger.warning(f"[UnifiedReActEngine] WARNING: use_existing_intent_id={use_existing_intent_id} reached else block, using it")
            else:
                # Normal single-phase task: create new intent_id
                self._use_existing_intent_id = None  # Clear previous value
                task_intent_id = f"task-{int(time.time() * 1000)}"
                self._current_intent_id = task_intent_id
                
                # Generate meaningful task description from goal
                task_description = self._generate_task_description(goal, file_ids)
                # PHASE 0 FIX: Disable intent_start events
                # await self.ws_manager.send_event(
                #     self.session_id,
                #     "intent_start",
                #     {"intent_id": task_intent_id, "text": task_description}
                # )
        
        # #region agent log
        import json as _debug_json_intent; import time as _debug_time_intent
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_intent:
                _debug_f_intent.write(_debug_json_intent.dumps({"id":f"log_{int(_debug_time_intent.time()*1000)}_intent_id_set","timestamp":int(_debug_time_intent.time()*1000),"location":"unified_react_engine.py:720","message":"Intent ID set","data":{"goal":goal[:200],"use_existing_intent_id":use_existing_intent_id,"task_intent_id":task_intent_id,"_current_intent_id":self._current_intent_id,"_is_multi_phase":self._is_multi_phase,"skip_orchestration":skip_orchestration},"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
        except:
            pass
        # #endregion
        
        self._task_intent_id = self._current_intent_id  # Store for the entire execution
        
        # Phase 2, Steps 1-2: Test decomposition and dependency analysis in UI
        # Phase 2, Step 3: Real parallel execution for multi-tool queries
        # #region agent log
        import json as _debug_json_multi; import time as _debug_time_multi
        is_multi_tool = self._is_multi_tool_query(goal) if not skip_orchestration else False
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_multi:
                _debug_f_multi.write(_debug_json_multi.dumps({"id":f"log_{int(_debug_time_multi.time()*1000)}_multi_tool_check","timestamp":int(_debug_time_multi.time()*1000),"location":"unified_react_engine.py:700","message":"Checking if multi-tool query","data":{"goal":goal[:200],"skip_orchestration":skip_orchestration,"is_multi_tool_query":is_multi_tool},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        if not skip_orchestration and is_multi_tool:
            try:
                logger.info(f"[UnifiedReActEngine] Multi-tool query detected, using orchestration")
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_orch:
                        _debug_f_orch.write(_debug_json_multi.dumps({"id":f"log_{int(_debug_time_multi.time()*1000)}_orchestration_entry","timestamp":int(_debug_time_multi.time()*1000),"location":"unified_react_engine.py:702","message":"Entering orchestration path","data":{"goal":goal[:200]},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
                except:
                    pass
                # #endregion
                decomposition = await self.task_decomposer.decompose(goal)
                
                # Edge case: Empty decomposition
                if not decomposition.subtasks:
                    logger.warning(f"[UnifiedReActEngine] Empty decomposition, falling back to normal ReAct")
                    # Fall through to normal ReAct cycle
                else:
                    # CRITICAL: For orchestrated main task, skip source tracking to prevent old card UI
                    # Sources break tab UI and should never be shown for orchestrated execution
                    if not self._skip_source_tracking:
                        self._skip_source_tracking = True
                        logger.info(f"[UnifiedReActEngine] Setting _skip_source_tracking=True for orchestrated main task to prevent old card UI")
                    
                    execution_plan = self.dependency_analyzer.analyze(decomposition.subtasks)
                    
                    # Edge case: No execution groups
                    if not execution_plan.execution_groups:
                        logger.warning(f"[UnifiedReActEngine] No execution groups, falling back to normal ReAct")
                        # Fall through to normal ReAct cycle
                    # CRITICAL: If only one subtask, use normal ReAct cycle instead of orchestration
                    # This ensures LLM generates content (e.g., slides for presentations)
                    elif len(decomposition.subtasks) == 1:
                        logger.info(f"[UnifiedReActEngine] Single subtask detected ({decomposition.subtasks[0].tool_name}), falling back to normal ReAct for proper content generation")
                        # Fall through to normal ReAct cycle (will handle single task properly)
                    else:
                        # Send decomposition visualization event
                        await self.ws_manager.send_event(
                            self.session_id,
                            "task_decomposition",
                            {
                                "intent_id": self._current_intent_id,
                                "query": goal,
                                "subtasks": [
                                    {
                                        "task_id": st.task_id,
                                        "description": st.description,
                                        "tool_name": st.tool_name,
                                        "dependencies": st.dependencies,
                                        "is_synthesis": st.is_synthesis
                                    }
                                    for st in decomposition.subtasks
                                ],
                                "execution_groups": execution_plan.execution_groups,
                                "group_types": execution_plan.group_types
                            }
                        )
                        logger.info(f"[UnifiedReActEngine] Decomposition sent: {len(decomposition.subtasks)} subtasks, {len(execution_plan.execution_groups)} groups")
                        
                        # Phase 2, Step 3-4: Execute orchestrated (parallel) execution with synthesis
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_orch_ret:
                                _debug_f_orch_ret.write(_debug_json_multi.dumps({"id":f"log_{int(_debug_time_multi.time()*1000)}_orchestration_return","timestamp":int(_debug_time_multi.time()*1000),"location":"unified_react_engine.py:752","message":"Returning from orchestration (BYPASSING ReAct cycle)","data":{"goal":goal[:200],"subtasks_count":len(decomposition.subtasks)},"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
                        except:
                            pass
                        # #endregion
                        return await self._execute_orchestrated(goal, decomposition, execution_plan, context, file_ids)
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Orchestration failed: {e}", exc_info=True)
                # Fallback to normal ReAct cycle
                logger.info(f"[UnifiedReActEngine] Falling back to normal ReAct cycle")
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_orch_err:
                        _debug_f_orch_err.write(_debug_json_multi.dumps({"id":f"log_{int(_debug_time_multi.time()*1000)}_orchestration_error","timestamp":int(_debug_time_multi.time()*1000),"location":"unified_react_engine.py:754","message":"Orchestration failed, falling back to ReAct","data":{"goal":goal[:200],"error":str(e)[:200]},"sessionId":"debug-session","runId":"run1","hypothesisId":"F"}) + '\n')
                except:
                    pass
                # #endregion
        
        # Анализируем сложность задачи и выбираем модель/budget
        # #region agent log - начало анализа сложности
        _complexity_start = _debug_time_exec.time()
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_complexity_start:
                _debug_f_complexity_start.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_complexity_analysis_start","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:882","message":"Starting complexity analysis","data":{"goal":goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        complexity = self.complexity_analyzer.analyze(goal)
        
        _complexity_duration = _debug_time_exec.time() - _complexity_start
        # #region agent log - анализ сложности завершен
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_complexity:
                _debug_f_complexity.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_complexity_analysis_done","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:884","message":"Complexity analysis completed","data":{"complexity_level":complexity.level,"use_fast_model":complexity.use_fast_model,"budget_tokens":complexity.budget_tokens,"duration_ms":_complexity_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        # Выбираем модель и budget на основе сложности
        # #region agent log - выбор модели
        _model_select_start = _debug_time_exec.time()
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_model_start:
                _debug_f_model_start.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_model_selection_start","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:885","message":"Starting model selection","data":{"use_fast_model":complexity.use_fast_model},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        if complexity.use_fast_model:
            # Используем быструю модель без thinking
            self.llm = self.fast_llm
        else:
            # Используем основную модель с адаптивным budget
            self.llm = self._create_llm_with_thinking(complexity.budget_tokens)
        
        _model_select_duration = _debug_time_exec.time() - _model_select_start
        # #region agent log - модель выбрана
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_model_done:
                _debug_f_model_done.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_model_selection_done","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:890","message":"Model selection completed","data":{"duration_ms":_model_select_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        # Запускаем SmartProgress с оценочным временем
        # Всегда запускаем ReAct цикл - LLM сам решит, нужны ли инструменты
        _smart_progress_start = _debug_time_exec.time()
        await self.smart_progress.start(goal, complexity.estimated_duration_sec)
        _smart_progress_duration = _debug_time_exec.time() - _smart_progress_start
        # #region agent log - SmartProgress запущен
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_progress:
                _debug_f_progress.write(_debug_json_exec.dumps({"id":f"log_{int(_debug_time_exec.time()*1000)}_smart_progress_started","timestamp":int(_debug_time_exec.time()*1000),"location":"unified_react_engine.py:894","message":"SmartProgress started","data":{"duration_ms":_smart_progress_duration*1000},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
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
        
        # #region agent log
        import json as _debug_json_react; import time as _debug_time_react
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_react:
                _debug_f_react.write(_debug_json_react.dumps({"id":f"log_{int(_debug_time_react.time()*1000)}_react_loop_start","timestamp":int(_debug_time_react.time()*1000),"location":"unified_react_engine.py:791","message":"About to start ReAct loop","data":{"goal":goal[:200],"max_iterations":state.max_iterations,"iteration":state.iteration,"_stop_requested":getattr(self, '_stop_requested', False)},"sessionId":"debug-session","runId":"run1","hypothesisId":"E"}) + '\n')
        except:
            pass
        # #endregion
        
        try:
            # Main ReAct loop
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_react_entry:
                    _debug_f_react_entry.write(_debug_json_react.dumps({"id":f"log_{int(_debug_time_react.time()*1000)}_react_loop_entry","timestamp":int(_debug_time_react.time()*1000),"location":"unified_react_engine.py:1034","message":"Entering ReAct loop","data":{"goal":goal[:200],"max_iterations":state.max_iterations,"initial_iteration":state.iteration,"_stop_requested":getattr(self, '_stop_requested', False)},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            except:
                pass
            # #endregion
            while state.iteration < state.max_iterations:
                if self._stop_requested:
                    logger.info(f"[UnifiedReActEngine] Stop requested at iteration {state.iteration}")
                    break
                
                state.iteration += 1
                self._current_iteration = state.iteration  # Store for use in _execute_action
                logger.info(f"[UnifiedReActEngine] Starting iteration {state.iteration}")
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_react_iter:
                        _debug_f_react_iter.write(_debug_json_react.dumps({"id":f"log_{int(_debug_time_react.time()*1000)}_react_iteration_start","timestamp":int(_debug_time_react.time()*1000),"location":"unified_react_engine.py:1040","message":"ReAct iteration started","data":{"iteration":state.iteration,"goal":goal[:200]},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
                except:
                    pass
                # #endregion
                
                # === Send iteration_start event for UI ===
                # ВАЖНО: Используем _task_intent_id (первый intent) для ВСЕХ итераций,
                # чтобы они показывались под одним блоком, а не в разных phase-блоках
                iteration_intent_id = getattr(self, '_task_intent_id', None) or self._current_intent_id
                # Сохраняем для использования в операциях - операция должна быть в том же intent, что и итерация
                self._iteration_intent_id = iteration_intent_id
                
                # CRITICAL: If use_existing_intent_id is set (from parallel branch execution),
                # we need to send parallel_branch_iteration_* events instead of regular iteration_* events
                # The use_existing_intent_id is the branch_id from parallel_branch_start
                # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                use_existing_value = self._get_use_existing_intent_id(state)
                is_parallel = use_existing_value is not None
                if is_parallel:
                    branch_id = self._use_existing_intent_id
                    # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                    # Main task intent_id (parent intent) - use from context or fallback to _task_intent_id
                    main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                    
                    # #region agent log
                    import json as _debug_json_iter_start; import time as _debug_time_iter_start
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_iter_start:
                            _debug_f_iter_start.write(_debug_json_iter_start.dumps({"id":f"log_{int(_debug_time_iter_start.time()*1000)}_parallel_iteration_start","timestamp":int(_debug_time_iter_start.time()*1000),"location":"unified_react_engine.py:906","message":"Sending parallel_branch_iteration_start","data":{"main_intent_id":main_intent_id,"branch_id":branch_id,"iteration_number":state.iteration,"goal":state.goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                    except:
                        pass
                    # #endregion
                    
                    await self.ws_manager.send_event(
                        self.session_id,
                        "parallel_branch_iteration_start",
                        {
                            "intent_id": main_intent_id,  # Main task intent (parent)
                            "branch_id": branch_id,  # Branch ID (same as use_existing_intent_id)
                            "iteration_number": state.iteration
                        }
                    )
                else:
                    # #region agent log
                    import json as _debug_json_iter; import time as _debug_time_iter
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_iter:
                            _debug_f_iter.write(_debug_json_iter.dumps({"id":f"log_{int(_debug_time_iter.time()*1000)}_iteration_start","timestamp":int(_debug_time_iter.time()*1000),"location":"unified_react_engine.py:932","message":"Sending iteration_start","data":{"intent_id":iteration_intent_id,"iteration_number":state.iteration,"goal":state.goal[:100] if state.goal else "no_goal","session_id":self.session_id},"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
                    except:
                        pass
                    # #endregion
                    await self.ws_manager.send_event(
                        self.session_id,
                        "iteration_start",
                        {
                            "intent_id": iteration_intent_id,
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
                
                # CRITICAL: If this is a parallel branch iteration, send parallel_branch_iteration events
                # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                use_existing_value = self._get_use_existing_intent_id(state)
                if use_existing_value is not None:
                    branch_id = use_existing_value
                    # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                    main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                    
                    # #region agent log
                    import json as _debug_json_thinking_complete; import time as _debug_time_thinking_complete
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_thinking_complete:
                            _debug_f_thinking_complete.write(_debug_json_thinking_complete.dumps({"id":f"log_{int(_debug_time_thinking_complete.time()*1000)}_parallel_thinking_complete","timestamp":int(_debug_time_thinking_complete.time()*1000),"location":"unified_react_engine.py:949","message":"Sending parallel_branch_iteration_thinking_complete","data":{"main_intent_id":main_intent_id,"branch_id":branch_id,"iteration_number":state.iteration,"think_duration":think_duration,"goal":state.goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                    except:
                        pass
                    # #endregion
                    
                    await self.ws_manager.send_event(
                        self.session_id,
                        "parallel_branch_iteration_thinking_complete",
                        {
                            "intent_id": main_intent_id,  # Main task intent (parent)
                            "branch_id": branch_id,
                            "iteration_number": state.iteration,
                            "duration_sec": think_duration
                        }
                    )
                else:
                    await self.ws_manager.send_event(
                        self.session_id,
                        "iteration_thinking_complete",
                        {
                            "intent_id": self._current_intent_id,
                            "iteration_number": state.iteration,
                            "duration_sec": think_duration
                        }
                    )
                
                    # === Send iteration_thinking_result event (Cursor-style) ===
                thinking_result = self._determine_thinking_result(action_plan)
                if thinking_result:
                    # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                    use_existing_value = self._get_use_existing_intent_id(state)
                    if use_existing_value is not None:
                        branch_id = use_existing_value
                        # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                        main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                        
                        # #region agent log
                        import json as _debug_json_thinking_result; import time as _debug_time_thinking_result
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_thinking_result:
                                _debug_f_thinking_result.write(_debug_json_thinking_result.dumps({"id":f"log_{int(_debug_time_thinking_result.time()*1000)}_parallel_thinking_result","timestamp":int(_debug_time_thinking_result.time()*1000),"location":"unified_react_engine.py:977","message":"Sending parallel_branch_iteration_thinking_result","data":{"main_intent_id":main_intent_id,"branch_id":branch_id,"iteration_number":state.iteration,"thinking_result":thinking_result,"goal":state.goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                        except:
                            pass
                        # #endregion
                        
                        await self.ws_manager.send_event(
                            self.session_id,
                            "parallel_branch_iteration_thinking_result",
                            {
                                "intent_id": main_intent_id,  # Main task intent (parent)
                                "branch_id": branch_id,
                                "iteration_number": state.iteration,
                                "result": thinking_result
                            }
                        )
                    else:
                        await self.ws_manager.send_event(
                            self.session_id,
                            "iteration_thinking_result",
                            {
                                "intent_id": self._current_intent_id,
                                "iteration_number": state.iteration,
                                "result": thinking_result
                            }
                        )
                
                if self._stop_requested:
                    break
                
                # 2. PLAN - Action plan уже получен из _think_and_plan
                state.status = "acting"
                planned_tool = action_plan.get("tool_name", "")
                
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
                    
                    # CRITICAL FIX: Don't update intent title for parallel subtasks
                    # Parallel subtasks use parallel_branch_start events with their own titles
                    # Updating intent title here creates confusion in UI (tasks appear in wrong tabs)
                    # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                    use_existing_value = self._get_use_existing_intent_id(state)
                    is_parallel_subtask = use_existing_value is not None
                    if not is_parallel_subtask:
                        # Обновляем заголовок шага на основе первого действия (только для обычных задач)
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
                        use_existing_value = self._get_use_existing_intent_id(state)
                        logger.debug(f"[UnifiedReActEngine] Skipping intent_title_update for parallel subtask (branch_id={use_existing_value})")
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
                    
                    if is_compound and "modify" in phases:
                        # Составная задача - проверяем, выполнена ли фаза модификации
                        modify_done = any(
                            obs.action.tool_name in text_modifying_tools and obs.success
                            for obs in state.observations
                        )
                        
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
                        # Skip bold formatting, go directly to paragraph formatting
                        doc_id = action_plan.get("arguments", {}).get("document_id", "")
                        doc_length = self._get_document_length_from_observations(state)
                        logger.warning(f"[UnifiedReActEngine] BLOCK: {planned_tool} blocked, skipping bold, going to paragraph formatting")
                        
                        action_plan = {
                            "tool_name": "format_document_paragraph",
                            "arguments": {
                                "document_id": doc_id,
                                "start_index": 1,
                                "end_index": doc_length or 2000,
                                "alignment": "JUSTIFIED",
                                "line_spacing": 1.15,
                                "indent_first_line": 36
                            },
                            "description": "Форматирование абзацев: выравнивание и красная строка",
                            "reasoning": f"Задача форматирования: пропускаем bold, сразу paragraph"
                        }
                        planned_tool = "format_document_paragraph"
                
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
                # NEW FALLBACK LOGIC: Try next tool from relevant_tools list (max 3 attempts)
                if planned_tool.upper() != "FINISH" and hasattr(self, '_current_relevant_tools') and self._current_relevant_tools:
                    # Count how many tools from relevant_tools list we've tried
                    tried_relevant_tools = [
                        obs.action.tool_name 
                        for obs in state.observations 
                        if obs.action.tool_name in self._current_relevant_tools and not obs.success
                    ]
                    attempts_count = len(tried_relevant_tools)
                    
                    if attempts_count >= 1 and attempts_count < 3:
                        # Find next tool from relevant_tools list that we haven't tried
                        next_tool = None
                        for tool_name in self._current_relevant_tools:
                            if tool_name not in tried_relevant_tools:
                                next_tool = tool_name
                                break
                        
                        if next_tool:
                            logger.info(f"[UnifiedReActEngine] Tool {planned_tool} failed ({attempts_count} attempt(s)), switching to next relevant tool: {next_tool}")
                            
                            # Get error from last observation for context
                            last_error = ""
                            if state.observations:
                                last_obs = state.observations[-1]
                                if last_obs.error_message:
                                    last_error = last_obs.error_message[:200]
                                elif not last_obs.success:
                                    last_error = str(last_obs.raw_result)[:200]
                            
                            # Store error for next prompt
                            self._last_tool_error = last_error
                            
                            # Override action_plan
                            action_plan = {
                                "tool_name": next_tool,
                                "arguments": action_plan.get("arguments", {}),  # Keep same arguments
                                "description": f"Переключение на следующий релевантный инструмент: {next_tool}",
                                "reasoning": f"Инструмент {planned_tool} не сработал (попытка {attempts_count}/3). Пробуем следующий релевантный инструмент из списка."
                            }
                            planned_tool = next_tool
                        elif attempts_count >= 3:
                            # All relevant tools tried, force FINISH
                            logger.warning(f"[UnifiedReActEngine] All {attempts_count} attempts on relevant tools failed, forcing FINISH")
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
                                "final_answer": f"Не удалось выполнить задачу: испробовано {attempts_count} инструментов из релевантных, ни один не сработал. Последняя ошибка: {_error_msg}"
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
                    # PHASE 0 FIX: Disable Phase Transition completely
                    should_transition = False
                    # Оригинальная логика:
                    # should_transition = (
                    #     new_category != self._current_phase_category and 
                    #     new_category != 'general' and
                    #     (self._is_multi_phase or self._current_phase_category is not None) and
                    #     not is_formatting_transition  # Prevent UI flickering for formatting tasks
                    # )
                    
                    if should_transition:
                        # Complete current intent before starting new one
                        # PHASE 0 FIX: Disable intent_complete events
                        # if self._current_intent_id:
                        #     await self.ws_manager.send_event(
                        #         self.session_id,
                        #         "intent_complete",
                        #         {
                        #             "intent_id": self._current_intent_id,
                        #             "summary": "Завершено"
                        #         }
                        #     )
                        
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
                            # PHASE 0 FIX: Disable intent_start events (inside Phase Transition, which is already disabled)
                            # await self.ws_manager.send_event(
                            #     self.session_id,
                            #     "intent_start",
                            #     {"intent_id": new_intent_id, "text": phase_description}
                            # )
                            logger.info(f"[UnifiedReActEngine] Phase transition: {self._current_phase_category} -> {new_category}")
                        self._current_phase_category = new_category
                        # Обновляем _task_intent_id для новой фазы - итерации будут в новом intent
                        # Операции ищут свой intent через lookup, поэтому всё работает корректно
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
                        'create_document',
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
                    return await self._finalize_success(state, finish_reasoning, context, file_ids, is_parallel_subtask=_local_is_parallel_subtask)
                
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
                
                # #region agent log - проверка изоляции state.action_history для параллельных веток
                use_existing_value_action = self._get_use_existing_intent_id(state)
                is_parallel_action = use_existing_value_action is not None
                if is_parallel_action:
                    import json as _debug_json_action; import time as _debug_time_action
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_action:
                            _debug_f_action.write(_debug_json_action.dumps({"id":f"log_{int(_debug_time_action.time()*1000)}_action_added","timestamp":int(_debug_time_action.time()*1000),"location":"unified_react_engine.py:1775","message":"Action added to state.action_history","data":{"is_parallel":True,"use_existing_intent_id":use_existing_value_action,"goal":state.goal[:100],"tool_name":planned_tool,"state_id":id(state),"action_history_count":len(state.action_history) if state.action_history else 0,"action_history_tools":[a.tool_name for a in state.action_history] if state.action_history else []},"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
                    except:
                        pass
                # #endregion
                
                # === Generate and send tool explanation (Phase 1.1) ===
                tool_explanation = self.tool_explanation_generator.generate(
                    tool_name=planned_tool,
                    args=action_plan.get("arguments", {})
                )
                await self.ws_manager.send_event(
                    self.session_id,
                    "tool_explanation",
                    {
                        "intent_id": self._current_intent_id,
                        "iteration_number": state.iteration,
                        "tool_name": planned_tool,
                        "explanation": tool_explanation
                    }
                )
                
                # === Track source (Phase 1.2) ===
                # CRITICAL: Skip source tracking for orchestrated tasks (parallel or sequential) to prevent old card UI
                source_id = None
                _skip_source_tracking_flag = getattr(self, '_skip_source_tracking', False)
                if not _skip_source_tracking_flag:
                    source_name = self._get_source_name(planned_tool)
                    source_id = await self.source_tracker.track_source(
                        source_name=source_name,
                        tool_name=planned_tool,
                        preview_data=tool_explanation,
                        intent_id=self._current_intent_id
                    )
                else:
                    logger.debug(f"[UnifiedReActEngine] Skipping track_source in ReAct cycle for orchestrated task (tool: {planned_tool}) to prevent old card UI")
                
                # === Send iteration_action_start event for UI ===
                action_title = self._get_tool_display_name(planned_tool, action_plan.get("arguments", {}))
                # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                use_existing_value = self._get_use_existing_intent_id(state)
                if use_existing_value is not None:
                    branch_id = use_existing_value
                    # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                    main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                    
                    # #region agent log
                    import json as _debug_json_action_start; import time as _debug_time_action_start
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_action_start:
                            _debug_f_action_start.write(_debug_json_action_start.dumps({"id":f"log_{int(_debug_time_action_start.time()*1000)}_parallel_action_start","timestamp":int(_debug_time_action_start.time()*1000),"location":"unified_react_engine.py:1732","message":"Sending parallel_branch_iteration_action_start","data":{"main_intent_id":main_intent_id,"branch_id":branch_id,"iteration_number":state.iteration,"tool_name":planned_tool,"action_title":action_title,"goal":state.goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                    except:
                        pass
                    # #endregion
                    
                    await self.ws_manager.send_event(
                        self.session_id,
                        "parallel_branch_iteration_action_start",
                        {
                            "intent_id": main_intent_id,  # Main task intent (parent)
                            "branch_id": branch_id,
                            "iteration_number": state.iteration,
                            "title": action_title
                        }
                    )
                else:
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
                
                # CRITICAL FIX: Передаём state как параметр вместо self._current_state
                # Это предотвращает утечку данных между параллельными ветками
                # Раньше self._current_state перезаписывался параллельными ветками
                
                # CRITICAL: Ensure action_plan["tool_name"] matches planned_tool before execution
                # This prevents cases where planned_tool was changed but action_plan wasn't updated
                if action_plan.get("tool_name") != planned_tool:
                    # Use planned_tool (which is the most up-to-date value)
                    action_plan["tool_name"] = planned_tool
                
                try:
                    result = await self._execute_action(action_plan, context, state)
                    _exec_action_end = time.time()
                    
                    # === Update source as completed (Phase 1.2) ===
                    # Skip for orchestrated tasks (no source tracking to prevent old card UI)
                    if source_id:
                        await self.source_tracker.update_source_complete(
                            source_id=source_id,
                            result=result,
                            intent_id=self._current_intent_id
                        )
                    
                    # === Send iteration_action_complete event for UI ===
                    result_summary = "Выполнено"
                    # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                    use_existing_value = self._get_use_existing_intent_id(state)
                    if use_existing_value is not None:
                        branch_id = use_existing_value
                        # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                        main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                        
                        # #region agent log
                        import json as _debug_json_action_complete; import time as _debug_time_action_complete
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_action_complete:
                                _debug_f_action_complete.write(_debug_json_action_complete.dumps({"id":f"log_{int(_debug_time_action_complete.time()*1000)}_parallel_action_complete","timestamp":int(_debug_time_action_complete.time()*1000),"location":"unified_react_engine.py:1777","message":"Sending parallel_branch_iteration_action_complete","data":{"main_intent_id":main_intent_id,"branch_id":branch_id,"iteration_number":state.iteration,"result_summary":result_summary,"tool_name":planned_tool,"goal":state.goal[:100]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                        except:
                            pass
                        # #endregion
                        
                        await self.ws_manager.send_event(
                            self.session_id,
                            "parallel_branch_iteration_action_complete",
                            {
                                "intent_id": main_intent_id,  # Main task intent (parent)
                                "branch_id": branch_id,
                                "iteration_number": state.iteration,
                                "result": result_summary
                            }
                        )
                    else:
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
                    
                    # CRITICAL: Log error details for debugging
                    
                    # === Update source as error (Phase 1.2) ===
                    # Skip for orchestrated tasks (no source tracking to prevent old card UI)
                    if source_id:
                        await self.source_tracker.update_source_error(
                            source_id=source_id,
                            error=error_msg,
                            intent_id=self._current_intent_id
                        )
                    
                    # === Send iteration_action_complete event for UI (error case) ===
                    # CRITICAL FIX: Используем значение из state.context для изоляции параллельных веток
                    use_existing_value = self._get_use_existing_intent_id(state)
                    if use_existing_value is not None:
                        branch_id = use_existing_value
                        # PHASE 0 FIX: Read main_intent_id from context instead of self (race condition fix)
                        main_intent_id = getattr(context, '_parallel_main_intent_id', None) or getattr(self, '_task_intent_id', None) or iteration_intent_id
                        await self.ws_manager.send_event(
                            self.session_id,
                            "parallel_branch_iteration_action_complete",
                            {
                                "intent_id": main_intent_id,  # Main task intent (parent)
                                "branch_id": branch_id,
                                "iteration_number": state.iteration,
                                "result": f"Ошибка: {error_msg[:50]}..."
                            }
                        )
                    else:
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
                
                # #region agent log - проверка изоляции state.observations для параллельных веток
                use_existing_value_obs = self._get_use_existing_intent_id(state)
                is_parallel_obs = use_existing_value_obs is not None
                if is_parallel_obs:
                    import json as _debug_json_obs; import time as _debug_time_obs
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_obs:
                            _debug_f_obs.write(_debug_json_obs.dumps({"id":f"log_{int(_debug_time_obs.time()*1000)}_observation_added","timestamp":int(_debug_time_obs.time()*1000),"location":"unified_react_engine.py:1977","message":"Observation added to state.observations","data":{"is_parallel":True,"use_existing_intent_id":use_existing_value_obs,"goal":state.goal[:100],"tool_name":action_record.tool_name,"state_id":id(state),"observations_count":len(state.observations) if state.observations else 0,"observations_tools":[obs.action.tool_name for obs in state.observations] if state.observations else []},"sessionId":"debug-session","runId":"run1","hypothesisId":"E"}) + '\n')
                    except:
                        pass
                # #endregion
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
                
                # CRITICAL: Store error for next prompt if tool failed
                # This allows LLM to retry with different parameters if error is about parameters
                if not analysis.is_success and analysis.error_message:
                    self._last_tool_error = analysis.error_message
                    # Also check if error is about parameters (can retry with different params)
                    error_lower = analysis.error_message.lower()
                    is_param_error = any(keyword in error_lower for keyword in [
                        "parameter", "param", "argument", "arg", "invalid", "missing", 
                        "required", "неверный", "параметр", "аргумент", "неправильный",
                        "отсутствует", "требуется", "invalid id", "invalid value",
                        "not found", "tool.*not found", "available tools"
                    ])
                    # Also check if it's a tool execution error that might be fixable
                    is_tool_error = any(keyword in error_lower for keyword in [
                        "tool.*not found", "available tools", "failed to", "error"
                    ])
                    if is_param_error or is_tool_error:
                        # Mark that this tool can be retried with different parameters or approach
                        self._can_retry_with_params = True
                        self._failed_tool_name = action_record.tool_name
                    else:
                        self._can_retry_with_params = False
                        self._failed_tool_name = None
                
                state.add_reasoning_step("observe", f"Analysis: {analysis.progress_toward_goal:.0%} progress", {
                    "success": analysis.is_success,
                    "progress": analysis.progress_toward_goal,
                    "error": analysis.error_message
                })
                
                # 5. ADAPT - Make decision
                state.status = "adapting"
                
                if analysis.is_goal_achieved:
                    logger.info(f"[UnifiedReActEngine] Goal achieved at iteration {state.iteration}")
                    return await self._finalize_success(state, result, context, file_ids, is_parallel_subtask=_local_is_parallel_subtask)
                
                elif analysis.is_error:
                    # === ИСПРАВЛЕНИЕ E: Retry counter вместо немедленного FINISH ===
                    # Проверяем, сколько раз подряд мы получали ошибки
                    consecutive_errors = 0
                    for obs in reversed(state.observations[-3:]):  # Последние 3 попытки
                        if obs.error_message:
                            consecutive_errors += 1
                        else:
                            break
                    
                    # Если ошибок меньше 3 - продолжаем попытки
                    if consecutive_errors < 3:
                        logger.info(f"[UnifiedReActEngine] Error #{consecutive_errors}, retrying (max 3 attempts)...")
                        # Добавляем информацию об ошибке в reasoning для следующей итерации
                        error_info = analysis.error_message or "Action failed"
                        state.add_reasoning_step("adapt", f"Error encountered: {error_info[:100]}", {
                            "error": error_info,
                            "retry_count": consecutive_errors
                        })
                        await self._stream_reasoning("react_adapting", {
                            "reason": error_info,
                            "retry_count": consecutive_errors,
                            "max_retries": 3,
                            "iteration": state.iteration
                        })
                        # Продолжаем loop - LLM увидит ошибку в <completed_actions> и попробует по-другому
                        # НЕ вызываем _find_alternative сразу - даем LLM шанс самому исправиться
                    else:
                        # Максимум попыток достигнут - пробуем найти альтернативу
                        logger.warning(f"[UnifiedReActEngine] Max retries ({consecutive_errors}) reached, trying to find alternative...")
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
                                logger.warning(f"[UnifiedReActEngine] No alternatives found after {consecutive_errors} retries, failing gracefully")
                                return await self._finalize_failure(state, analysis, context)
                        else:
                            logger.warning(f"[UnifiedReActEngine] Alternatives disabled, failing after {consecutive_errors} retries")
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
            
            # #region agent log - ЗАВЕРШЕНИЕ выполнения execute()
            import json as _debug_json_exec_end; import time as _debug_time_exec_end
            _execute_duration = _debug_time_exec_end.time() - _execute_start if '_execute_start' in locals() else 0
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_exec_end:
                    _debug_f_exec_end.write(_debug_json_exec_end.dumps({
                        "id": f"log_{int(_debug_time_exec_end.time()*1000)}_execute_complete",
                        "timestamp": int(_debug_time_exec_end.time()*1000),
                        "location": "unified_react_engine.py:2287",
                        "message": "EXECUTE COMPLETE",
                        "data": {
                            "goal": goal,
                            "total_duration_sec": _execute_duration,
                            "iterations": state.iteration if 'state' in locals() else 0
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "EXECUTE"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
    
    async def _needs_tools(self, goal: str, context: ConversationContext, file_ids: Optional[List[str]] = None) -> bool:
        """
        Determine if the query needs tools or can be answered directly.
        
        NOTE: This method is DEPRECATED and no longer used in the main execution flow.
        We always run ReAct cycle now - LLM decides whether to use tools or not.
        Kept for potential future use or debugging.
        
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
            # Presentation keywords - CRITICAL for slides/presentation tasks
            'презентац', 'presentation', 'слайд', 'slide', 'доклад', 'сделай',
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
            # CRITICAL FIX: Для параллельных веток НЕ добавляем context.messages,
            # чтобы избежать утечки данных из других веток
            # Каждая параллельная ветка должна работать только со своим контекстом
            use_existing_value_needs = self._get_use_existing_intent_id(state)
            is_parallel_needs = use_existing_value_needs is not None
            
            # Build context string from recent messages
            context_str = ""
            # Skip для параллельных веток - они не должны видеть контекст других веток
            if not is_parallel_needs and hasattr(context, 'messages') and context.messages:
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
- Project Lad: "проекты", "портфель", "диаграмма ганта", "вехи", "загрузка ресурсов", "часы сотрудников", "workload"

ВАЖНО: 
- Если это УТОЧНЯЮЩИЙ вопрос (например "а на следующей неделе?", "а за прошлый месяц?", "еще покажи") 
  и в КОНТЕКСТЕ обсуждались встречи/письма/файлы/таблицы/проводки/проекты - это ДА, нужны те же инструменты.
- Короткие уточнения типа "а вчера?", "а там?" относятся к предыдущей теме разговора."""
            
            messages = [
                SystemMessage(content="Ты эксперт по определению необходимости использования инструментов. Учитывай контекст разговора. Отвечай только ДА или НЕТ."),
                HumanMessage(content=prompt)
            ]
            
            # #region agent log - ПРОМПТ для классификации задачи
            import json as _debug_json_needs_tools; import time as _debug_time_needs_tools
            _needs_tools_start = _debug_time_needs_tools.time()
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_needs_tools:
                    _debug_f_needs_tools.write(_debug_json_needs_tools.dumps({
                        "id": f"log_{int(_debug_time_needs_tools.time()*1000)}_needs_tools_prompt",
                        "timestamp": int(_debug_time_needs_tools.time()*1000),
                        "location": "unified_react_engine.py:2476",
                        "message": "NEEDS_TOOLS PROMPT",
                        "data": {
                            "goal": goal,
                            "context_str": context_str[:500] if context_str else "",
                            "FULL_PROMPT": prompt
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "NEEDS_TOOLS"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Use fast LLM (no extended thinking) for quick classification
            response = await self.fast_llm.ainvoke(messages)
            response_text = str(response.content).strip().upper()
            
            _needs_tools_duration = _debug_time_needs_tools.time() - _needs_tools_start
            
            llm_result = "ДА" in response_text or "YES" in response_text
            
            # #region agent log - ОТВЕТ для классификации задачи
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_needs_tools_response:
                    _debug_f_needs_tools_response.write(_debug_json_needs_tools.dumps({
                        "id": f"log_{int(_debug_time_needs_tools.time()*1000)}_needs_tools_response",
                        "timestamp": int(_debug_time_needs_tools.time()*1000),
                        "location": "unified_react_engine.py:2507",
                        "message": "NEEDS_TOOLS RESPONSE",
                        "data": {
                            "goal": goal,
                            "FULL_RESPONSE": str(response.content),
                            "response_text": response_text,
                            "needs_tools": llm_result,
                            "duration_sec": _needs_tools_duration
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "NEEDS_TOOLS"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Log the result
            logger.info(f"[_needs_tools] goal='{goal[:50]}...', llm_response='{response_text[:100]}', needs_tools={llm_result}")
            
            return llm_result
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
            
            # #region agent log - ПРОМПТ для простого ответа
            import json as _debug_json_direct; import time as _debug_time_direct
            _direct_start = _debug_time_direct.time()
            try:
                messages_for_log = []
                for msg in messages:
                    if hasattr(msg, 'content'):
                        messages_for_log.append({"role": type(msg).__name__, "content": str(msg.content)[:500]})
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_direct_prompt:
                    _debug_f_direct_prompt.write(_debug_json_direct.dumps({
                        "id": f"log_{int(_debug_time_direct.time()*1000)}_answer_directly_prompt",
                        "timestamp": int(_debug_time_direct.time()*1000),
                        "location": "unified_react_engine.py:2574",
                        "message": "ANSWER_DIRECTLY PROMPT",
                        "data": {
                            "goal": goal,
                            "messages": messages_for_log,
                            "uses_extended_thinking": uses_extended_thinking
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "ANSWER_DIRECTLY"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Send thinking_started event
            self._current_thinking_id = f"thinking-{int(time.time() * 1000)}"
            self._thinking_start_time = time.time()
            await self.ws_manager.send_event(
                self.session_id,
                "thinking_started",
                {"thinking_id": self._current_thinking_id, "started_at": int(time.time() * 1000)}
            )
            
            # CRITICAL FIX: Use streaming instead of ainvoke for real-time response
            # Send final_result_start event
            # CRITICAL FIX: Используем _local_is_parallel_subtask, который определён в начале execute()
            is_parallel_subtask = _local_is_parallel_subtask
            if not is_parallel_subtask:
                await self.ws_manager.send_event(
                    self.session_id,
                    "final_result_start",
                    {}
                )
            
            # Stream response chunks
            answer = ""
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
                    answer += chunk_text
                    # Send chunk for streaming
                    if not is_parallel_subtask:
                        if self.config.mode in ("query", "agent"):
                            await self.ws_manager.send_event(
                                self.session_id,
                                "final_result_chunk",
                                {"content": answer}  # Send accumulated content
                            )
            
            answer = answer.strip()
            
            _direct_duration = _debug_time_direct.time() - _direct_start
            
            # #region agent log - ОТВЕТ для простого ответа
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_direct_response:
                    _debug_f_direct_response.write(_debug_json_direct.dumps({
                        "id": f"log_{int(_debug_time_direct.time()*1000)}_answer_directly_response",
                        "timestamp": int(_debug_time_direct.time()*1000),
                        "location": "unified_react_engine.py:2627",
                        "message": "ANSWER_DIRECTLY RESPONSE",
                        "data": {
                            "goal": goal,
                            "FULL_RESPONSE": answer,
                            "duration_sec": _direct_duration
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "ANSWER_DIRECTLY"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
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
            
            # Send final result complete or message_complete based on mode
            # CRITICAL FIX: Skip final_result for parallel subtasks - they use parallel_branch_complete instead
            if not is_parallel_subtask:
                # Agent mode uses final_result like query mode (UI expects workflow.finalResult)
                if self.config.mode in ("query", "agent"):
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_complete",
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
            else:
                use_existing_value_log = self._get_use_existing_intent_id(state)
                logger.info(f"[UnifiedReActEngine] Skipping final_result for parallel subtask (use_existing_intent_id={use_existing_value_log})")
            
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
        
        # Documents - create vs modify
        elif any(w in goal_lower for w in ['создай документ', 'новый документ']):
            return ""  # Пустое название, будет заменено на осмысленное при первом действии
        
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
                'name': 'sheets_operation',
                'keywords': ['таблиц', 'sheet', 'запиш', 'запиши', 'записать', 'запись в', 
                            'получи данны', 'читай таблиц', 'проанализируй', 'анализ', 'создай таблиц'],
                'description': '📊 Работа с таблицей',
                'category': 'sheets'
            },
            {
                'name': 'docs_create',
                'keywords': ['создай документ', 'новый документ', 'create document'],
                'description': '📄 Работа с документом',
                'category': 'docs_create'
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
            
            # Sheets - используем объединённую категорию 'sheets'
            'sheets_create': 'sheets',
            'sheets_read_range': 'sheets',
            'sheets_write_range': 'sheets',
            'sheets_batch_update': 'sheets',
            # Sheets - LangChain tool names (actual names used by LLM)
            'get_sheet_data': 'sheets',
            'get_all_sheets_data': 'sheets',  # Добавлен маппинг
            'add_rows': 'sheets',
            'update_cells': 'sheets',
            'create_spreadsheet': 'sheets',
            'get_spreadsheet_info': 'sheets',
            'format_cells': 'sheets',
            'auto_resize_columns': 'sheets',
            'merge_cells': 'sheets',
            
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
            'create_document': 'docs_create',
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
            'docs_create': '📄 Работа с документом',
            'sheets': '📊 Работа с таблицей',  # Объединённая категория
            'sheets_create': '📊 Работа с таблицей',
            'sheets_read': '📊 Работа с таблицей',
            'sheets_write': '📊 Работа с таблицей',
            'files': '📁 Поиск и чтение файлов',
            'docs_write': '📄 Работа с документом',
            'docs_format': '📄 Работа с документом',
            'code': '🐍 Выполнение кода',
            'visualization': '📈 Создание графика',
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
            'create_document': '📄 Работа с документом',
            'read_document': '📄 Работа с документом',
            'append_to_document': '📄 Работа с документом',
            'insert_into_document': '📄 Работа с документом',
            'update_document': '📄 Работа с документом',
            'format_document_text': '📄 Работа с документом',
            'format_document_paragraph': '📄 Работа с документом',
            'get_calendar_events': '📅 Получение событий',
            'create_calendar_event': '📅 Создание встречи',
            'list_emails': '📧 Чтение писем',
            'search_emails': '📧 Поиск писем',
            # Sheets - объединённый заголовок для всех операций
            'get_sheet_data': '📊 Работа с таблицей',
            'get_all_sheets_data': '📊 Работа с таблицей',
            'add_rows': '📊 Работа с таблицей',
            'update_cells': '📊 Работа с таблицей',
            'create_spreadsheet': '📊 Работа с таблицей',
            'sheets_read_range': '📊 Работа с таблицей',
            'sheets_write_range': '📊 Работа с таблицей',
            'workspace_search_files': '📁 Поиск файлов',
        }
        return title_map.get(tool_name)
    
    def _is_multi_tool_query(self, goal: str) -> bool:
        """
        Determine if query requires multiple tools (Phase 2).
        
        Args:
            goal: User query
            
        Returns:
            True if query needs multiple tools
        """
        goal_lower = goal.lower()
        
        # Check for explicit multi-tool keywords
        multi_keywords = [
            "фокус", "focus", "сводка", "обзор", "summary", "overview",
            "все", "всё", "все вместе"
        ]
        if any(kw in goal_lower for kw in multi_keywords):
            return True
        
        # Check for multiple data sources mentioned together
        source_keywords = {
            "email": ["почт", "письм", "email", "gmail"],
            "calendar": ["календар", "встреч", "событ", "calendar", "event"],
            "files": ["файл", "диск", "file", "drive", "документ"],
            "sheets": ["таблиц", "sheet", "spreadsheet"]
        }
        
        # Check for action keywords (create, send, etc.)
        action_keywords = {
            "create": ["создай", "сделай", "create", "make", "презентац", "presentation", "документ", "document"],
            "send": ["отправь", "send", "send_email", "отправь письмо"],
            "check": ["проверь", "check", "проверить", "посмотри"],
            "read": ["прочитай", "read", "покажи", "show"]
        }
        
        # Count how many different sources are mentioned
        sources_found = set()
        for source_type, keywords in source_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                sources_found.add(source_type)
        
        # Count how many different actions are mentioned
        actions_found = set()
        for action_type, keywords in action_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                actions_found.add(action_type)
        
        
        # If 2+ sources mentioned, it's a multi-tool query
        if len(sources_found) >= 2:
            return True
        
        # REMOVED: Old logic that was too aggressive
        # Old: "If action + source, it's multi-tool" - this incorrectly classified
        # simple queries like "посмотри письма" as multi-tool
        # Simple queries with one action and one source should NOT be multi-tool
        # They should go through normal ReAct cycle
        # Only queries with multiple actions OR explicit "и" (and) should be multi-tool
        
        # Check for explicit "и" (and) between sources or actions
        if " и " in goal_lower or " and " in goal_lower:
            # Check if both sides mention different sources or actions
            parts = goal_lower.replace(" и ", "|").replace(" and ", "|").split("|")
            if len(parts) >= 2:
                sources_in_parts = []
                actions_in_parts = []
                
                for part in parts:
                    # Check sources in this part
                    part_sources = set()
                    for source_type, keywords in source_keywords.items():
                        if any(kw in part for kw in keywords):
                            part_sources.add(source_type)
                    if part_sources:
                        sources_in_parts.append(part_sources)
                    
                    # Check actions in this part
                    part_actions = set()
                    for action_type, keywords in action_keywords.items():
                        if any(kw in part for kw in keywords):
                            part_actions.add(action_type)
                    if part_actions:
                        actions_in_parts.append(part_actions)
                
                # If different sources in different parts, it's multi-tool
                if len(sources_in_parts) >= 2:
                    all_sources = set()
                    for ps in sources_in_parts:
                        all_sources.update(ps)
                    if len(all_sources) >= 2:
                        return True
                
                # If action in one part and source in another, it's multi-tool (unless dependency)
                # Check for dependency: "создай X и отправь ее" - sequential
                dependency_indicators = ["ее", "его", "их", "it", "them", "тот же", "тот же самый"]
                has_dependency = any(ind in goal_lower for ind in dependency_indicators)
                
                if not has_dependency and len(actions_in_parts) > 0 and len(sources_in_parts) > 0:
                    return True
                
                # If 2+ different actions in different parts (without dependency), it's multi-tool
                if not has_dependency and len(actions_in_parts) >= 2:
                    all_actions = set()
                    for pa in actions_in_parts:
                        all_actions.update(pa)
                    if len(all_actions) >= 2:
                        return True

        return False
    
    def _get_source_name(self, tool_name: str) -> str:
        """
        Get source name (service name) from tool name.
        
        Args:
            tool_name: Tool name (e.g., "list_emails", "get_sheet_data")
            
        Returns:
            Source name (e.g., "Gmail", "Google Sheets")
        """
        # Use service_names from ToolExplanationGenerator
        service_name = self.tool_explanation_generator.service_names.get(tool_name)
        if service_name:
            return service_name
        
        # Fallback: guess from tool name
        tool_lower = tool_name.lower()
        if "email" in tool_lower or "gmail" in tool_lower:
            return "Gmail"
        elif "sheet" in tool_lower or "spreadsheet" in tool_lower:
            return "Google Sheets"
        elif "calendar" in tool_lower or "event" in tool_lower:
            return "Google Calendar"
        elif "document" in tool_lower or ("doc" in tool_lower and "slide" not in tool_lower):
            return "Google Docs"
        elif "slide" in tool_lower or "presentation" in tool_lower:
            return "Google Slides"
        elif "drive" in tool_lower or "workspace" in tool_lower or "file" in tool_lower:
            return "Google Drive"
        else:
            return "Система"
    
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
            # Calendar (новые имена MCP)
            'get_calendar_events': 'Получаю события из календаря',
            'create_event': 'Создаю встречу',
            'update_event': 'Обновляю событие',
            'delete_calendar_events': 'Удаляю событие',
            'schedule_group_meeting': 'Назначаю встречу с участниками',
            'get_next_availability': 'Ищу свободное время',
            
            # Calendar (старые имена, для совместимости)
            'calendar_list_events': 'Получаю события из календаря',
            'calendar_create_event': 'Создаю встречу',
            'calendar_update_event': 'Обновляю событие',
            'calendar_delete_event': 'Удаляю событие',
            'calendar_get_event': 'Получаю информацию о событии',
            
            # Gmail (новые имена MCP)
            'list_emails': 'Получаю список писем',
            'search_emails': 'Ищу письма',
            'read_email': 'Читаю письмо',
            'send_email': 'Отправляю письмо',
            'draft_email': 'Создаю черновик письма',
            
            # Gmail (старые имена, для совместимости)
            'gmail_search': 'Ищу письма',
            'gmail_send_email': 'Отправляю письмо',
            'gmail_get_message': 'Читаю письмо',
            'gmail_list_messages': 'Получаю список писем',
            
            # Sheets (новые имена MCP)
            'read_sheets': 'Читаю данные из таблицы',
            'write_sheets': 'Записываю данные в таблицу',
            'append_rows': 'Добавляю строки в таблицу',
            'get_spreadsheet': 'Получаю информацию о таблице',
            'merge_cells': 'Объединяю ячейки',
            
            # Sheets (старые имена, для совместимости)
            'sheets_read_range': 'Читаю данные из таблицы',
            'sheets_write_range': 'Записываю данные в таблицу',
            'sheets_append_rows': 'Добавляю строки в таблицу',
            'sheets_get_spreadsheet': 'Получаю информацию о таблице',
            
            # Docs (новые имена MCP)
            'read_document': 'Читаю документ',
            'create_document': 'Создаю документ',
            'update_document': 'Обновляю документ',
            'append_to_document': 'Добавляю текст в документ',
            'insert_into_document': 'Вставляю текст в документ',
            
            # Docs (старые имена, для совместимости)
            'docs_read': 'Читаю документ',
            'docs_create': 'Создаю документ',
            'docs_update': 'Обновляю документ',
            
            # Files / Workspace (новые имена MCP)
            'search_document_text': 'Ищу текст в документах',
            'workspace_search_files': 'Ищу файлы',
            'workspace_find_and_open_file': 'Открываю файл',
            'workspace_get_file_info': 'Получаю информацию о файле',
            
            # Slides (новые имена MCP)
            'create_presentation_batch': 'Создаю презентацию',
            'create_slide': 'Добавляю слайд',
            
            # Slides (старые имена, для совместимости)
            'slides_create': 'Создаю презентацию',
            'slides_create_slide': 'Добавляю слайд',
            
            # 1C
            'onec_get_data': 'Запрашиваю данные из 1С',
            'onec_query': 'Выполняю запрос к 1С',
            
            # Python code
            'execute_python_code': 'Выполняю Python код',
        }
        
        # Get base action name
        base_name = tool_map.get(tool_name)
        
        if not base_name:
            # Fallback: convert snake_case to readable format (без эмодзи)
            readable = tool_name.replace('_', ' ').lower()
            # Capitalize first letter
            base_name = readable.capitalize() if readable else tool_name
        
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
    
    def _get_smart_result_summary(self, subtask: Any, result: Any) -> str:
        """
        Generate smart, brief summary for parallel branch result display.
        
        Returns short summary like "Найдено 7 событий" instead of full data.
        
        Args:
            subtask: SubTask object with tool_name
            result: Execution result (dict or raw result)
            
        Returns:
            Brief summary string in Russian
        """
        tool_name = subtask.tool_name if hasattr(subtask, 'tool_name') else None
        
        # Extract actual result from execution_result dict if needed
        actual_result = result
        if isinstance(result, dict):
            # Try to extract tool result from execution_result
            if "final_result" in result:
                # final_result might contain tool data or formatted string
                actual_result = result["final_result"]
            elif "response" in result:
                actual_result = result["response"]
            else:
                # Look for raw result in observations
                actual_result = result
        
        # Convert to string for parsing
        result_str = str(actual_result) if actual_result else ""
        import re
        
        # Calendar events - парсим строки типа "get_calendar_events: Found 7 event(s):" или "✓ get_calendar_events: Found 7 event(s):"
        if 'calendar' in (tool_name or '').lower() or 'event' in (tool_name or '').lower() or 'event' in result_str.lower():
            # Паттерн: "Found N event(s):" или "найдено N событий"
            count_match = re.search(r'(?:Found|found|найдено)\s+(\d+)\s+event', result_str, re.IGNORECASE)
            if count_match:
                count = count_match.group(1)
                return f"Найдено {count} событий"
            elif re.search(r'(?:Found|found|найдено)\s+0\s+event', result_str, re.IGNORECASE):
                return "Событий не найдено"
            else:
                return "Получены события календаря"
        
        # Email messages - парсим строки типа "list_emails: Found 10 email(s)"
        if 'email' in (tool_name or '').lower() or 'mail' in (tool_name or '').lower():
            # Паттерн: "Found N email(s)" или "найдено N писем"
            count_match = re.search(r'(?:Found|found|найдено)\s+(\d+)\s+(?:email|письм)', result_str, re.IGNORECASE)
            if count_match:
                count = count_match.group(1)
                return f"Найдено {count} писем"
            elif re.search(r'(?:Found|found|найдено)\s+0\s+(?:email|письм)', result_str, re.IGNORECASE):
                return "Писем не найдено"
            else:
                return "Получены данные почты"
        
        # Try using _get_result_summary first if we have tool_name (fallback)
        if tool_name and actual_result:
            summary = self._get_result_summary(tool_name, actual_result)
            if summary:
                # Remove emoji from summary for cleaner display
                summary = summary.replace("✅ ", "").replace("❌ ", "").strip()
                # Если summary на английском, переводим
                if 'found' in summary.lower() and 'event' in summary.lower():
                    count_match = re.search(r'(\d+)\s+event', summary, re.IGNORECASE)
                    if count_match:
                        return f"Найдено {count_match.group(1)} событий"
                elif 'found' in summary.lower() and 'email' in summary.lower():
                    count_match = re.search(r'(\d+)\s+email', summary, re.IGNORECASE)
                    if count_match:
                        return f"Найдено {count_match.group(1)} писем"
                return summary
        
        # Generic fallback
        if isinstance(result, dict):
            return "✓ Выполнено"
        elif result_str:
            # First line only, max 50 chars
            first_line = result_str.split('\n')[0][:50]
            return first_line + ("..." if len(result_str) > 50 else "")
        else:
            return "✓ Выполнено"
    
    class StreamingThoughtParser:
        """Парсит thought из стрима и отправляет по WebSocket.
        
        Также отправляет intent_detail события если передан intent_id,
        что позволяет показывать thinking в UI как часть intent блока.
        
        Стримит iteration_thinking_chunk для IterationBlock UI.
        """
        
        def __init__(self, ws_manager: WebSocketManager, session_id: str, intent_id: Optional[str] = None, iteration_number: int = 1, engine: Optional[Any] = None):
            self.ws_manager = ws_manager
            self.session_id = session_id
            self.intent_id = intent_id  # Для отправки intent_thinking_append
            self.iteration_number = iteration_number  # Для iteration_thinking_chunk
            self.engine = engine  # Ссылка на engine для сохранения operation_id
            self.buffer = ""
            self.thought_started = False
            self.thought_complete = False
            self.thought_content = ""
            self.thinking_id = f"thinking_{session_id}_{int(time.time() * 1000)}"
            self.thinking_context = None  # Для динамических заголовков "Думаю"
            self.context_sent = False  # Флаг что context уже отправлен
            # Check if this is a parallel branch iteration
            # PHASE 0 FIX: Check that _use_existing_intent_id is not None (not just hasattr)
            self.is_parallel_branch = engine and hasattr(engine, '_use_existing_intent_id') and getattr(engine, '_use_existing_intent_id', None) is not None
            self.branch_id = engine._use_existing_intent_id if self.is_parallel_branch else None
            
            # Для стриминга Python кода в реальном времени
            self.code_streaming_started = False
            self.code_start_marker = '"code": "'
            self.code_start_pos = -1  # Позиция начала кода в буфере
            self.last_code_streamed_pos = -1  # Последняя позиция стримленного кода
            self.in_code_string = False  # Флаг что мы внутри JSON строки кода
            self.code_escape_next = False  # Флаг что следующий символ экранирован
            self.accumulated_code = ""  # Накопленный код для отправки
            self.operation_id = None  # Operation ID для стриминга в operation view
            self.last_streamed_line_count = 0  # Количество стримленных строк в operation view
        
        async def process_chunk(self, chunk: str) -> None:
            """Обрабатывает chunk, извлекает thought и стримит.
            
            Отправляет:
            - thinking_chunk: legacy событие для ThinkingMessage
            - intent_detail: новое событие для IntentMessage (если есть intent_id)
            """
            self.buffer += chunk
            
            # Обрабатываем стриминг кода Python в реальном времени
            await self._handle_code_streaming()
            
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
                    
                    # Упрощенная логика: не определяем контекст
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
                            # Упрощенная логика: не определяем контекст, просто стримим
                            
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
                                if self.is_parallel_branch and self.branch_id:
                                    # Send parallel_branch_iteration_thinking_chunk for parallel branches
                                    # CRITICAL FIX: Get main_intent_id from context (stored in _parallel_main_intent_id)
                                    # or fallback to _task_intent_id or intent_id
                                    main_intent_id = None
                                    if self.engine:
                                        # Try to get from context if available (stored in _current_context)
                                        context = getattr(self.engine, '_current_context', None)
                                        if context:
                                            main_intent_id = getattr(context, '_parallel_main_intent_id', None)
                                        # Fallback to _task_intent_id
                                        if not main_intent_id:
                                            main_intent_id = getattr(self.engine, '_task_intent_id', None)
                                    # Final fallback to intent_id
                                    if not main_intent_id:
                                        main_intent_id = self.intent_id
                                    
                                    # #region agent log
                                    import json as _debug_json_thinking_chunk; import time as _debug_time_thinking_chunk
                                    try:
                                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_thinking_chunk:
                                            _debug_f_thinking_chunk.write(_debug_json_thinking_chunk.dumps({"id":f"log_{int(_debug_time_thinking_chunk.time()*1000)}_parallel_thinking_chunk","timestamp":int(_debug_time_thinking_chunk.time()*1000),"location":"unified_react_engine.py:3369","message":"Sending parallel_branch_iteration_thinking_chunk","data":{"main_intent_id":main_intent_id,"branch_id":self.branch_id,"iteration_number":self.iteration_number,"chunk_length":len(new_chunk)},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                                    except:
                                        pass
                                    # #endregion
                                    
                                    # Упрощенная логика: не отправляем context
                                    await self.ws_manager.send_event(
                                        self.session_id,
                                        "parallel_branch_iteration_thinking_chunk",
                                        {
                                            "intent_id": main_intent_id,  # Main task intent (parent)
                                            "branch_id": self.branch_id,
                                            "iteration_number": self.iteration_number,
                                            "chunk": new_chunk
                                        }
                                    )
                                else:
                                    # Send regular iteration_thinking_chunk
                                    # Упрощенная логика: не отправляем context
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
        
        async def _handle_code_streaming(self) -> None:
            """Обрабатывает стриминг Python кода в реальном времени из JSON.
            
            Отслеживает генерацию execute_python_code и стримит код по мере поступления токенов.
            """
            tool_marker = '"tool_name": "execute_python_code"'
            
            # Ищем паттерн "tool_name": "execute_python_code" если еще не начали стриминг
            if not self.code_streaming_started:
                if tool_marker in self.buffer:
                    # Нашли execute_python_code, начинаем отслеживать код
                    self.code_streaming_started = True
            
            # Если начали стриминг, но еще не нашли маркер начала кода, продолжаем искать
            if self.code_streaming_started and self.code_start_pos == -1:
                tool_pos = self.buffer.find(tool_marker)
                if tool_pos != -1:
                    code_marker_pos = self.buffer.find(self.code_start_marker, tool_pos)
                    if code_marker_pos != -1:
                        self.code_start_pos = code_marker_pos + len(self.code_start_marker)
                        self.last_code_streamed_pos = self.code_start_pos
                        self.in_code_string = True
                        # Создаём operation_id для стриминга в operation view (чат)
                        self.operation_id = f"op-{int(time.time() * 1000)}"
                        
                        # Сохраняем operation_id в engine для использования в _execute_action
                        if self.engine:
                            self.engine._execute_python_code_operation_id = self.operation_id
                        
                        # Отправляем operation_start для стриминга в operation view (чат)
                        # Проверяем наличие метода для совместимости с моками в тестах
                        if hasattr(self.ws_manager, 'send_operation_start'):
                            await self.ws_manager.send_operation_start(
                                self.session_id,
                                self.operation_id,
                                "Пишу код анализа...",
                                "Код Python",
                                "write",
                                file_type="code",
                                intent_id=self.intent_id,
                                iteration_number=self.iteration_number
                            )
                        
                        # Отправляем событие начала стриминга кода для code viewer (правое окно)
                        await self.ws_manager.send_event(
                            self.session_id,
                            "code_display_start",
                            {
                                "filename": "analysis.py",
                                "language": "python"
                            }
                        )
            
            # Если стриминг кода начался, извлекаем и стримим новые части кода
            if self.code_streaming_started and self.in_code_string and self.code_start_pos > 0:
                # Извлекаем код из буфера начиная с последней стримленной позиции
                # Код находится между "code": " и закрывающей "
                # Нужно правильно обрабатывать экранированные кавычки и символы
                
                code_chunk = ""
                i = self.last_code_streamed_pos
                code_complete = False
                
                while i < len(self.buffer):
                    char = self.buffer[i]
                    
                    if self.code_escape_next:
                        # Предыдущий символ был \, обрабатываем экранированный символ
                        if char == 'n':
                            code_chunk += '\n'
                        elif char == 't':
                            code_chunk += '\t'
                        elif char == 'r':
                            code_chunk += '\r'
                        elif char == '\\':
                            code_chunk += '\\'
                        elif char == '"':
                            code_chunk += '"'
                        else:
                            # Неизвестный escape, добавляем как есть
                            code_chunk += char
                        self.code_escape_next = False
                        i += 1
                        continue
                    
                    if char == '\\':
                        # Следующий символ экранирован
                        self.code_escape_next = True
                        i += 1
                        continue
                    
                    if char == '"':
                        # Конец строки кода (не экранированная кавычка)
                        self.in_code_string = False
                        self.last_code_streamed_pos = i + 1
                        code_complete = True
                        # Отправляем последний chunk кода если есть
                        if code_chunk:
                            self.accumulated_code += code_chunk
                            
                            # Стримим последние строки в operation view (чат)
                            if self.operation_id and hasattr(self.ws_manager, 'send_operation_data'):
                                all_lines = self.accumulated_code.split('\n')
                                # Стримим все оставшиеся строки (включая последнюю)
                                for i in range(self.last_streamed_line_count, len(all_lines)):
                                    line = all_lines[i]
                                    if line:  # Отправляем только непустые строки
                                        await self.ws_manager.send_operation_data(
                                            self.session_id,
                                            self.operation_id,
                                            line
                                        )
                            
                            # Стримим в code viewer (правое окно)
                            await self.ws_manager.send_event(
                                self.session_id,
                                "code_chunk",
                                {
                                    "filename": "analysis.py",
                                    "code": self.accumulated_code
                                }
                            )
                        # Отправляем событие завершения стриминга кода
                        await self.ws_manager.send_event(
                            self.session_id,
                            "code_display_complete",
                            {
                                "filename": "analysis.py",
                                "code": self.accumulated_code
                            }
                        )
                        break
                    
                    # Обычный символ кода
                    code_chunk += char
                    i += 1
                
                # Если накопили код и еще не завершили строку, стримим его
                if code_chunk and not code_complete and not self.code_escape_next:
                    old_accumulated_length = len(self.accumulated_code)
                    self.accumulated_code += code_chunk
                    self.last_code_streamed_pos = i
                    
                    # Стримим код в operation view (чат) - построчно для визуального эффекта
                    if self.operation_id and hasattr(self.ws_manager, 'send_operation_data'):
                        # Разбиваем накопленный код на строки
                        all_lines = self.accumulated_code.split('\n')
                        new_lines_count = 0
                        # Стримим новые полные строки (последняя может быть неполной)
                        for line_idx in range(self.last_streamed_line_count, len(all_lines) - 1):
                            line = all_lines[line_idx]
                            if line:  # Отправляем только непустые строки
                                await self.ws_manager.send_operation_data(
                                    self.session_id,
                                    self.operation_id,
                                    line
                                )
                                new_lines_count += 1
                        # Обновляем счетчик стримленных строк (исключаем последнюю неполную строку)
                        self.last_streamed_line_count = len(all_lines) - 1
                        
                        # ВАЖНО: Стримим последнюю неполную строку, если она есть и изменилась
                        # Это нужно для того, чтобы пользователь видел код в реальном времени
                        if len(all_lines) > self.last_streamed_line_count:
                            last_line = all_lines[-1]
                            # Отправляем неполную строку только если она непустая (чтобы избежать лишних обновлений)
                            if last_line:
                                await self.ws_manager.send_operation_data(
                                    self.session_id,
                                    self.operation_id,
                                    last_line
                                )
                    
                    # Стримим накопленный код в code viewer (правое окно) - всегда, даже если нет новых строк
                    await self.ws_manager.send_event(
                        self.session_id,
                        "code_chunk",
                        {
                            "filename": "analysis.py",
                            "code": self.accumulated_code
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
        
        # CRITICAL FIX: Для параллельных веток НЕ добавляем context.messages,
        # чтобы избежать утечки данных из других веток
        # Каждая параллельная ветка должна работать только со своим контекстом
        use_existing_value_thought = self._get_use_existing_intent_id(state)
        is_parallel_thought = use_existing_value_thought is not None
        
        # Add conversation history for reference resolution (NEW)
        # Skip для параллельных веток - они не должны видеть контекст других веток
        if not is_parallel_thought and hasattr(context, 'messages') and context.messages:
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
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
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

Проанализируй текущую ситуацию и кратко опиши своё рассуждение: что уже есть в контексте, что нужно сделать дальше, и какое действие будет наиболее эффективным. Пиши естественно, без структурированных списков.

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
        # CRITICAL FIX: Prioritize slides and projectlad tools to ensure they're in the first 50
        # Sort capabilities to put slides and projectlad tools first
        sorted_capabilities = sorted(
            self.capabilities,
            key=lambda cap: (
                0 if ('slide' in cap.name.lower() or 'presentation' in cap.name.lower()) else
                1 if 'projectlad' in cap.name.lower() else
                2, 
                cap.name
            )
        )
        
        for cap in sorted_capabilities[:50]:  # Limit to first 50, but slides tools are prioritized
            capability_descriptions.append(f"- {cap.name}: {cap.description}")
        
        tools_str = "\n".join(capability_descriptions)
        
        # Build context
        context_str = f"Цель: {state.goal}\n\n"
        context_str += f"Текущий анализ: {thought}\n\n"
        
        # CRITICAL FIX: Для параллельных веток НЕ добавляем context.messages,
        # чтобы избежать утечки данных из других веток
        # Каждая параллельная ветка должна работать только со своим контекстом
        use_existing_value_action = self._get_use_existing_intent_id(state)
        is_parallel_action_gen = use_existing_value_action is not None
        
        # Add conversation history for reference resolution (NEW)
        # Skip для параллельных веток - они не должны видеть контекст других веток
        if not is_parallel_action_gen and hasattr(context, 'messages') and context.messages:
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

📋 "Красиво оформить" = format_document_paragraph:
- alignment="JUSTIFIED" — выравнивание по ширине
- indent_first_line=36 — красная строка
- line_spacing=1.15 — межстрочный интервал

⚠️ ОБЯЗАТЕЛЬНО:
- end_index для format_document_paragraph = TEXT_LENGTH (из результата read_document)
- НЕ используй format_document_text (bold) — не выделяй жирным!
- НЕ меняй содержание текста!

Порядок действий:
1. read_document → найти [TEXT_LENGTH: X characters] в результате
2. format_document_paragraph(end_index=X) → выравнивание для ВСЕГО документа
3. FINISH

⚠️ КРИТИЧЕСКИ ВАЖНО для PROJECT LAD (управление проектами):
- "загрузка ресурсов" / "часы сотрудников" / "workload" = projectlad_get_resource_utilization
- ❌ ЗАПРЕЩЕНО: projectlad_get_indicators (это для метрик проекта, НЕ для ресурсов)
- ❌ ЗАПРЕЩЕНО: projectlad_get_indicator_analytics (это для аналитики метрик, НЕ для ресурсов)
- ✅ ПРАВИЛЬНО: projectlad_get_resource_utilization - ТОЛЬКО этот tool для загрузки сотрудников!

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
                    "description": f"Выполняю {fallback_cap.name}",
                    "reasoning": f"Ошибка планирования: {str(e)}. Используется fallback инструмент."
                }
            else:
                return {
                    "tool_name": "error",
                    "arguments": {},
                    "description": "Ошибка планирования: нет доступных инструментов",
                    "reasoning": str(e)
                }
    
    def _get_relevant_tools(self, goal: str, completed_tools: List[str]) -> List[Dict[str, str]]:
        """
        Возвращает только релевантные инструменты для текущей задачи.
        Максимум 5-7 инструментов вместо 50+.
        
        Использует SmartToolSelector если включен (USE_SMART_TOOL_SELECTION=true),
        иначе использует keyword-based подход (legacy).
        """
        # Try smart tool selection first (if enabled)
        if self.use_smart_tool_selection and self.smart_tool_selector:
            try:
                import time
                _smart_select_start = time.time()
                # #region agent log
                import json as _debug_json_tool_select; import time as _debug_time_tool_select
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                        _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_tool_selection_start","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4054","message":"Starting smart tool selection","data":{"goal":goal,"completed_tools":completed_tools,"use_smart_tool_selection":self.use_smart_tool_selection},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                except:
                    pass
                # #endregion
                selected_caps = self.smart_tool_selector.select_tools(
                    query=goal,
                    max_tools=7,
                    completed_tools=completed_tools
                )
                _smart_select_duration = time.time() - _smart_select_start
                
                # Convert to dict format
                result = []
                for cap in selected_caps:
                    # Не обрезаем описание - передаём полное для лучшего понимания LLM
                    result.append({
                        "name": cap.name,
                        "description": cap.description
                    })
                
                # Always add FINISH
                if not any(t["name"] == "FINISH" for t in result):
                    result.append({
                        "name": "FINISH",
                        "description": "Завершить задачу, когда все шаги выполнены"
                    })
                
                selected_names = [t["name"] for t in result]
                logger.info(
                    f"[UnifiedReActEngine] Smart tool selection: {len(result)} tools selected "
                    f"in {_smart_select_duration:.3f}s for goal: {goal[:50]}"
                )
                logger.info(f"[UnifiedReActEngine] Selected tools: {selected_names}")
                
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                        _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_smart_tools_selected","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4086","message":"Smart tool selection completed","data":{"selected_tools":selected_names,"tools_count":len(result),"goal":goal,"goal_lower":goal.lower(),"has_doc_keywords":any(kw in goal.lower() for kw in ["документ", "doc", "текст", "сказк", "допиши", "напиши"]),"has_presentation_keywords":any(kw in goal.lower() for kw in ["презентац", "presentation", "slide", "слайд"])},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                except:
                    pass
                # #endregion
                
                # CRITICAL FIX: Если запрос содержит ключевые слова для документов,
                # но SmartToolSelector не выбрал инструменты для документов - добавляем их принудительно
                goal_lower = goal.lower()
                has_doc_keywords = any(kw in goal_lower for kw in ["документ", "doc", "текст", "сказк", "допиши", "напиши"])
                has_presentation_keywords = any(kw in goal_lower for kw in ["презентац", "presentation", "slide", "слайд"])
                
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                        _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_doc_keyword_check","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4095","message":"Checking doc keywords for forced tool addition","data":{"goal":goal,"has_doc_keywords":has_doc_keywords,"has_presentation_keywords":has_presentation_keywords,"selected_tools_before":selected_names},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                except:
                    pass
                # #endregion
                
                # Если есть ключевые слова для документов, но НЕТ для презентаций - приоритет документам
                if has_doc_keywords and not has_presentation_keywords:
                    # Проверяем, есть ли инструменты для документов в выбранных
                    doc_tools_in_selected = any(t["name"] in ["read_document", "append_to_document", "insert_into_document", "update_document", "format_document_paragraph", "format_document_text"] for t in result)
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                            _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_doc_tools_check","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4102","message":"Checking if doc tools in selected","data":{"doc_tools_in_selected":doc_tools_in_selected,"selected_tools":selected_names},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                    except:
                        pass
                    # #endregion
                    
                    if not doc_tools_in_selected:
                        # Добавляем обязательные инструменты для документов
                        required_doc_tools = []
                        # Определяем, создание или модификация
                        create_keywords = ["создай документ", "создать документ", "новый документ", "create document", "создай новый", "создай файл"]
                        is_create_doc = any(kw in goal_lower for kw in create_keywords)
                        
                        if is_create_doc:
                            required_doc_tools = ["create_document", "append_to_document", "format_document_paragraph"]
                        else:
                            # Модификация существующего - начинаем с read_document
                            required_doc_tools = ["read_document", "append_to_document", "insert_into_document", "update_document", "format_document_paragraph"]
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                                _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_forcing_doc_tools","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4115","message":"Forcing doc tools addition","data":{"is_create_doc":is_create_doc,"required_doc_tools":required_doc_tools},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                        except:
                            pass
                        # #endregion
                        
                        # Находим эти инструменты в capabilities и добавляем в результат
                        added_tools = []
                        for tool_name in required_doc_tools:
                            if tool_name not in selected_names:
                                # Ищем capability по имени в уже загруженных capabilities
                                for cap in self.capabilities:
                                    if cap.name == tool_name:
                                        result.insert(0, {  # Вставляем в начало (высокий приоритет)
                                            "name": cap.name,
                                            "description": cap.description
                                        })
                                        selected_names.insert(0, cap.name)
                                        added_tools.append(tool_name)
                                        logger.info(f"[UnifiedReActEngine] FORCED ADD: Added {tool_name} to tools list (doc keyword detected)")
                                        break
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_select:
                                _debug_f_tool_select.write(_debug_json_tool_select.dumps({"id":f"log_{int(_debug_time_tool_select.time()*1000)}_doc_tools_added","timestamp":int(_debug_time_tool_select.time()*1000),"location":"unified_react_engine.py:4130","message":"Doc tools added to result","data":{"added_tools":added_tools,"selected_tools_after":selected_names},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
                        except:
                            pass
                        # #endregion
                        
                        # Удаляем лишние инструменты, если превысили лимит
                        if len(result) > 7:
                            result = result[:7]
                            selected_names = [t["name"] for t in result]
                
                return result[:7]  # Max 7 tools
                
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Smart tool selection failed: {e}, falling back to keyword-based", exc_info=True)
                # Fall through to legacy keyword-based selection
        else:
            logger.debug(f"[UnifiedReActEngine] Smart tool selection disabled (use_smart={self.use_smart_tool_selection}, selector={self.smart_tool_selector is not None})")
        
        # Legacy keyword-based tool selection (fallback)
        goal_lower = goal.lower()
        relevant_tool_names = set()
        
        # #region agent log
        import json as _debug_json_keyword; import time as _debug_time_keyword
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_keyword:
                _debug_f_keyword.write(_debug_json_keyword.dumps({"id":f"log_{int(_debug_time_keyword.time()*1000)}_keyword_selection_start","timestamp":int(_debug_time_keyword.time()*1000),"location":"unified_react_engine.py:4096","message":"Starting keyword-based tool selection","data":{"goal":goal,"goal_lower":goal_lower,"has_doc_keywords":any(kw in goal_lower for kw in ["документ", "doc", "текст", "сказк", "допиши", "напиши"]),"has_presentation_keywords":any(kw in goal_lower for kw in ["презентац", "presentation", "slide", "слайд"]),"has_beautiful_keywords":any(kw in goal_lower for kw in ["красиво", "красив", "оформить", "формат"])},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
        except:
            pass
        # #endregion
        
        # Определяем категорию задачи и добавляем релевантные инструменты
        if any(kw in goal_lower for kw in ["документ", "doc", "текст", "сказк", "допиши", "напиши"]):
            # Ключевые слова для СОЗДАНИЯ нового документа (приоритетные - проверяем первыми)
            create_keywords = ["создай документ", "создать документ", "новый документ", "create document", "создай новый", "создай файл"]
            is_create_doc = any(kw in goal_lower for kw in create_keywords)
            
            # Ключевые слова для МОДИФИКАЦИИ существующего (только если НЕТ создания)
            # Исключаем "добавь в" из modify_keywords, если есть создание - это часть задачи создания
            modify_keywords = ["измени документ", "открой документ", "в документ", "допиши", "отформатируй", "обнови документ"]
            # "добавь в" считается модификацией ТОЛЬКО если нет создания
            if not is_create_doc:
                modify_keywords.append("добавь в")
            is_modify_doc = any(kw in goal_lower for kw in modify_keywords) if not is_create_doc else False
            
            if is_create_doc:
                # Создание нового документа — НЕ нужен read_document
                tools_to_add = ["create_document", "append_to_document", "format_document_paragraph"]
                relevant_tool_names.update(tools_to_add)
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_keyword:
                        _debug_f_keyword.write(_debug_json_keyword.dumps({"id":f"log_{int(_debug_time_keyword.time()*1000)}_doc_create_tools","timestamp":int(_debug_time_keyword.time()*1000),"location":"unified_react_engine.py:4114","message":"Document creation tools added","data":{"is_create_doc":is_create_doc,"tools_to_add":tools_to_add,"goal":goal},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                except:
                    pass
                # #endregion
            else:
                # Модификация существующего — начинаем с read_document
                tools_to_add = ["read_document", "append_to_document", "insert_into_document", "update_document", "format_document_paragraph"]
                relevant_tool_names.update(tools_to_add)
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_keyword:
                        _debug_f_keyword.write(_debug_json_keyword.dumps({"id":f"log_{int(_debug_time_keyword.time()*1000)}_doc_modify_tools","timestamp":int(_debug_time_keyword.time()*1000),"location":"unified_react_engine.py:4119","message":"Document modification tools added","data":{"is_create_doc":is_create_doc,"is_modify_doc":is_modify_doc,"tools_to_add":tools_to_add,"goal":goal},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                except:
                    pass
                # #endregion
            # Note: format_document_text (bold) removed - we skip bold formatting
        
        if any(kw in goal_lower for kw in ["таблиц", "sheet", "excel", "данн"]):
            # Проверяем, нужен ли анализ нескольких вкладок
            multi_sheet_keywords = ["несколько вкладок", "две вкладки", "все вкладки", "проанализируй", "анализ", "расширенный", "большой", "подробный"]
            needs_multi_sheet = any(kw in goal_lower for kw in multi_sheet_keywords)
            
            # Проверяем, просит ли пользователь записать данные
            is_write_request = any(kw in goal_lower for kw in ["запиш", "добав", "обнов", "измен"])
            
            if needs_multi_sheet:
                # Для анализа нескольких вкладок используем get_all_sheets_data
                # НЕ добавляем add_rows/update_cells - это инструменты для записи, не для анализа!
                relevant_tool_names.update([
                    "get_all_sheets_data", "execute_python_code"
                ])
            else:
                # Для простого чтения одной вкладки
                # Добавляем инструменты записи только если пользователь явно просит записать
                if is_write_request:
                    relevant_tool_names.update([
                        "sheets_read_range", "get_sheet_data", "add_rows", "update_cells"
                    ])
                else:
                    # Только чтение
                    relevant_tool_names.update([
                        "sheets_read_range", "get_sheet_data"
                    ])
        
        if any(kw in goal_lower for kw in ["календар", "встреч", "событ", "meeting"]):
            relevant_tool_names.update([
                "get_calendar_events", "create_event", "delete_event", "schedule_group_meeting"
            ])
        
        # 1С Бухгалтерия tools - ПРИОРИТЕТ для запросов о зарплате
        # Проверяем наличие упоминания 1С или бухгалтерии
        has_1c_keyword = any(kw in goal_lower for kw in ["1с", "1c", "бухгалтери", "учет", "одata", "из 1с", "из 1c"])
        # Проверяем наличие упоминания зарплаты
        has_salary_keyword = any(kw in goal_lower for kw in ["зарплат", "оплат", "труд", "сотрудник", "персонал", "счет 70", "выгрузи"])
        
        if has_1c_keyword:
            # Для запросов о зарплате - приоритет onec_get_salary_by_employee_month
            if has_salary_keyword:
                relevant_tool_names.add("onec_get_salary_by_employee_month")
            # Для запросов о выручке
            if any(kw in goal_lower for kw in ["выручк", "доход", "продаж"]):
                relevant_tool_names.add("onec_get_revenue_by_counterparty_month")
            # Для запросов о продажах/документах
            if any(kw in goal_lower for kw in ["продаж", "реализац", "документ"]):
                relevant_tool_names.add("onec_get_sales_list")
        
        if any(kw in goal_lower for kw in ["письм", "email", "почт"]):
            relevant_tool_names.update([
                "list_emails", "read_email", "send_email"
            ])
        
        if any(kw in goal_lower for kw in ["файл", "file", "найди", "открой"]):
            relevant_tool_names.update([
                "drive_search_files", "workspace_open_file", "search_files"
            ])
        
        # Project Lad - управление проектами
        if any(kw in goal_lower for kw in ["project", "lad", "проект", "портфель", "загрузк", "ресурс", "workload", "часы сотрудник"]):
            # Для загрузки ресурсов нужны оба инструмента - сначала найти проект, потом получить данные
            relevant_tool_names.update([
                "projectlad_list_projects",  # Чтобы найти project_id и version_id
                "projectlad_get_resource_utilization",  # Чтобы получить загрузку
                "projectlad_get_project_works"  # На случай если проект вложенный
            ])
        
        # Всегда добавляем FINISH
        relevant_tool_names.add("FINISH")
        
        # Исключаем уже успешно выполненные инструменты (кроме FINISH и форматирования абзацев)
        repeatable_tools = {"FINISH", "format_document_paragraph"}
        
        # СПЕЦИАЛЬНАЯ ЛОГИКА: После выполнения onec_get_salary_by_employee_month
        # автоматически добавляем инструменты для работы с Sheets (для создания таблицы)
        if "onec_get_salary_by_employee_month" in completed_tools:
            # Добавляем инструменты Sheets для создания/обновления таблицы с данными
            relevant_tool_names.update([
                "create_spreadsheet", "sheets_read_range", "get_sheet_data",
                "get_all_sheets_data", "add_rows", "update_cells"
            ])
        
        filtered_names = [t for t in relevant_tool_names 
                         if t not in completed_tools or t in repeatable_tools]
        
        # Собираем описания релевантных инструментов
        # Для docs инструментов явно указываем обязательные параметры
        docs_tool_params = {
            "create_document": "Input: title (название документа), initial_text (опционально, начальный текст). Возвращает document_id и url.",
            "append_to_document": "Input: document_id (ID документа), content (текст для добавления). ВАЖНО: НЕ используй маркдаун (**) в content!",
            "insert_into_document": "Input: document_id, index (позиция), content (текст). ВАЖНО: НЕ используй маркдаун!",
            "update_document": "Input: document_id, content (новый текст)",
            "format_document_paragraph": "Input: document_id, start_index (int), end_index (int), alignment (START/JUSTIFIED), line_spacing (float: 1.15/1.5/2.0), indent_first_line (float в пунктах: 36=стандартная красная строка)"
        }
        
        # Для calendar инструментов явно указываем обязательные параметры
        calendar_tool_params = {
            "schedule_group_meeting": "Input: title (ОБЯЗАТЕЛЬНО! заголовок встречи), attendees (list of emails), duration (default '50m'), description (optional), working_hours_start (hour 0-23, default 9, для 'после обеда' используй 13), working_hours_end (hour 0-23, default 18), confirmed (False для поиска времени, True для создания), slot_start (required when confirmed=True). ПРОЦЕСС: 1) Вызов с confirmed=False → находит время, 2) Показываешь пользователю → ждешь подтверждения, 3) Вызов с confirmed=True + slot_start → создает встречу",
            "create_event": "Input: title (ОБЯЗАТЕЛЬНО!), start_time (ISO format), attendees (optional list), description (optional), location (optional)",
            "get_calendar_events": "Input: start_time (ОБЯЗАТЕЛЬНО! ВАЖНО: если пользователь говорит 'на неделе', 'на этой неделе', 'за неделю' - используй start_time='на неделе', НЕ 'сегодня'! Используй '15 января' или '2026-01-15' для конкретной даты, 'сегодня' только если пользователь явно говорит 'сегодня'). Примеры: start_time='на неделе' (для запросов 'посмотри на неделю'), start_time='сегодня' (только если пользователь говорит 'сегодня'), start_time='15 января'"
        }
        
        # Для 1С salary tool - приоритетное описание
        onec_salary_tool_params = {
            "onec_get_salary_by_employee_month": """⭐ ПРИОРИТЕТНЫЙ TOOL для запросов о зарплате из 1С!
            
Используй этот tool для ВСЕХ запросов о зарплате, оплате труда, расчетах с персоналом из 1С:Бухгалтерия.

Агрегирует данные из проводок по счету 70 (Расчеты с персоналом по оплате труда) по месяцам и сотрудникам.

Input:
- from_date: Начальная дата (формат: YYYY-MM-DD), например "2025-01-01" или "2026-01-01"
- to_date: Конечная дата (формат: YYYY-MM-DD), например "2025-12-31" или "2026-12-31"
- organization_guid: Опционально, GUID организации

Returns: Данные по зарплате, сгруппированные по месяцам и сотрудникам.
Format: [{"month": "2025-12", "employee_name": "Артем Малышев", "salary": 50000}, ...]

Примеры использования:
- "выгрузи из 1С зарплату сотрудников" → from_date="2025-01-01", to_date="2025-12-31"
- "зарплата за 2026 год" → from_date="2026-01-01", to_date="2026-12-31"
- Если период не указан, используй текущий год или последние 12 месяцев"""
        }
        
        # Для code execution инструментов явно указываем доступные библиотеки
        code_execution_tool_params = {
            "execute_python_code": """⚠️ КРИТИЧЕСКИ ВАЖНО:
1. Данные УЖЕ переданы в переменную 'data'. Используй: sheets_data = data.get("sheets", [])
2. НЕ ВСТАВЛЯЙ данные в код! НЕ пиши salaries_data = [{'gender': 'М'...}] - это ЗАПРЕЩЕНО!
3. Библиотеки: ТОЛЬКО math, datetime, json, statistics. БЕЗ pandas/numpy!
4. ОБЯЗАТЕЛЬНО в конце: result = {"chartData": [...]} - без этого диаграммы не появятся!

📋 СТРУКТУРА ДАННЫХ (sheets):
sheets_data = data.get("sheets", [])  # Список листов
# Каждый лист: {"name": "Зарплата", "headers": ["Сотрудник", "Месяц", "Зарплата"], "data": [...], "rows": [...]}
# sheet["name"] - название листа (НЕ "title"!)
# sheet["data"] или sheet["rows"] - список словарей с данными:
#   [{"Сотрудник": "Иванов", "Месяц": "Январь", "Зарплата": "100"}, ...]
# Доступ к полям: row["Сотрудник"], row["Зарплата"] (НЕ row[0], row[1]!)

Пример кода:
```python
sheets_data = data.get("sheets", [])
salary_sheet = next((s for s in sheets_data if s["name"] == "Зарплата"), None)
if salary_sheet:
    for row in salary_sheet["data"]:
        name = row["Сотрудник"]
        salary = int(row["Зарплата"])
```"""
        }
        
        result = []
        
        for cap in self.capabilities:
            if cap.name in filtered_names:
                # Для docs инструментов используем явное описание параметров
                if cap.name in docs_tool_params:
                    desc = f"{cap.description.split('.')[0]}. {docs_tool_params[cap.name]}"
                # Для calendar инструментов используем явное описание параметров
                elif cap.name in calendar_tool_params:
                    desc = f"{cap.description.split('.')[0]}. {calendar_tool_params[cap.name]}"
                # Для code execution инструментов используем явное описание параметров
                elif cap.name in code_execution_tool_params:
                    desc = f"{cap.description.split('.')[0]}. {code_execution_tool_params[cap.name]}"
                # Для 1С salary tool используем приоритетное описание
                elif cap.name in onec_salary_tool_params:
                    desc = onec_salary_tool_params[cap.name]
                else:
                    desc = cap.description[:200]  # Расширенный лимит до 200 символов
                result.append({
                    "name": cap.name,
                    "description": desc
                })
        
        # Добавляем FINISH если его нет
        if not any(t["name"] == "FINISH" for t in result):
            result.append({
                "name": "FINISH",
                "description": "Завершить задачу, когда все шаги выполнены"
            })
        
        # === ИСПРАВЛЕНИЕ A: Приоритизация инструментов ===
        goal_lower_for_priority = goal.lower()
        
        # Приоритет 1: Запросы о зарплате из 1С
        needs_salary_priority = any(kw in goal_lower_for_priority for kw in [
            "зарплат", "оплат", "труд", "сотрудник", "персонал",
            "выгрузи из 1с", "выгрузи из 1c", "из 1с", "из 1c",
            "счет 70", "расчеты с персоналом"
        ]) and any(kw in goal_lower_for_priority for kw in ["1с", "1c", "бухгалтери", "учет"])
        
        if needs_salary_priority and "onec_get_salary_by_employee_month" not in completed_tools:
            prioritized = []
            # 1. Сначала добавляем onec_get_salary_by_employee_month
            salary_tool = next((t for t in result if t["name"] == "onec_get_salary_by_employee_month"), None)
            if salary_tool:
                prioritized.append(salary_tool)
                result = [t for t in result if t["name"] != "onec_get_salary_by_employee_month"]
            
            # 2. Затем остальные tools
            prioritized.extend(result)
            result = prioritized
        
        # Приоритет 2: Анализ нескольких вкладок - get_all_sheets_data должен быть ПЕРВЫМ
        needs_multi_sheet_priority = any(kw in goal_lower_for_priority for kw in [
            "несколько вкладок", "две вкладки", "все вкладки", 
            "проанализируй", "анализ", "расширенный", "большой", 
            "подробный", "глубокий", "полный", "комплексный"
        ])
        
        if needs_multi_sheet_priority:
            prioritized = []
            # 1. Сначала добавляем get_all_sheets_data (если еще не вызван)
            if "get_all_sheets_data" not in completed_tools:
                for t in result:
                    if t["name"] == "get_all_sheets_data":
                        prioritized.append(t)
                        break
            # 2. Затем execute_python_code (для расширенного анализа)
            if any(kw in goal_lower_for_priority for kw in ["расширенный", "большой", "подробный", "глубокий", "полный", "комплексный"]):
                for t in result:
                    if t["name"] == "execute_python_code":
                        prioritized.append(t)
                        break
            # 3. Затем остальные (но БЕЗ инструментов записи для анализа)
            for t in result:
                if t["name"] not in ["get_all_sheets_data", "execute_python_code", "add_rows", "update_cells"]:
                    if t not in prioritized:
                        prioritized.append(t)
            result = prioritized
        
        final_result = result[:7]  # Максимум 7 инструментов
        
        return final_result
    
    def _is_specific_file_query(self, goal: str, context: ConversationContext, file_ids: List[str]) -> bool:
        """
        Определяет, является ли запрос конкретным (про конкретные файлы) или общим.
        
        Args:
            goal: Запрос пользователя
            context: Контекст разговора
            file_ids: Список выбранных file_ids (если есть)
            
        Returns:
            True если запрос конкретный (про конкретные файлы), False если общий
        """
        goal_lower = goal.lower()
        
        # Общие запросы - всегда показывать сводку
        general_patterns = [
            'что видишь', 'что в файл', 'опиши файл', 'опиши все', 
            'про все файлы', 'во всех файлах', 'в файлах', 'что в файлах',
            'что на них', 'что на файлах'
        ]
        if any(p in goal_lower for p in general_patterns):
            return False  # Общий запрос - показывать сводку
        
        # Если есть конкретные file_ids (не все файлы) - это конкретный запрос
        if file_ids and hasattr(context, 'uploaded_files') and context.uploaded_files:
            all_file_ids = set(context.uploaded_files.keys())
            selected_file_ids = set(file_ids)
            if selected_file_ids and selected_file_ids != all_file_ids:
                return True  # Выбраны не все файлы - конкретный запрос
        
        # Проверяем, упоминаются ли конкретные файлы по имени
        if hasattr(context, 'uploaded_files') and context.uploaded_files:
            for file_id, file_data in context.uploaded_files.items():
                filename = file_data.get('filename', '')
                if filename:
                    # Проверяем упоминание имени файла (без расширения)
                    filename_base = filename.rsplit('.', 1)[0].lower()
                    if filename_base in goal_lower or filename.lower() in goal_lower:
                        return True  # Упоминается конкретный файл
        
        # Проверяем упоминания по описаниям из истории (УЛУЧШЕННАЯ ЛОГИКА)
        file_summaries = self._get_file_summaries_from_history(context)
        
        # Извлекаем ключевые слова из запроса (исключая стоп-слова)
        import re
        goal_words = set(re.findall(r'[а-яёa-z]+', goal_lower))
        stopwords = {'меня', 'интересует', 'описание', 'что', 'как', 'где', 'когда', 'про', 'об', 'в', 'на', 'с', 'по', 'к', 'у', 'о', 'за', 'от', 'из', 'до', 'для', 'это', 'этот', 'эта', 'эти', 'тот', 'та', 'те'}
        goal_keywords = goal_words - stopwords
        
        # Ищем совпадения ключевых слов из запроса в описаниях файлов
        matching_files = []
        for file_id, description in file_summaries.items():
            desc_lower = description.lower()
            desc_words = set(re.findall(r'[а-яёa-z]+', desc_lower))
            # Проверяем пересечение ключевых слов (минимум 1 совпадение значимого слова)
            common_words = goal_keywords & desc_words
            if common_words:
                # Исключаем очень короткие слова (меньше 3 символов)
                significant_common = {w for w in common_words if len(w) >= 3}
                if significant_common:
                    matching_files.append(file_id)
        
        # Если нашли совпадения - это конкретный запрос
        if matching_files:
            return True
        
        # Если запрос короткий и не содержит общих паттернов - вероятно конкретный
        if len(goal.split()) <= 5 and not any(p in goal_lower for p in ['все', 'всё', 'каждый', 'любой']):
            return True  # Короткий запрос без общих слов - вероятно конкретный
        
        return False  # По умолчанию считаем общим
    
    def _get_file_summaries_from_history(self, context: ConversationContext) -> Dict[str, str]:
        """
        Извлекает описания файлов из предыдущих ответов ассистента.
        
        Ищет в истории сообщений, где файлы были упомянуты, и извлекает
        их описания для использования в сводке.
        
        Returns:
            Dict[file_id: str, description: str] - описания файлов
        """
        file_summaries = {}
        
        if not context or not hasattr(context, 'messages'):
            return file_summaries
        
        # Ищем в последних ответах ассистента (обратный порядок - от новых к старым)
        for msg in reversed(context.messages):
            if msg.get("role") != "assistant":
                continue
            
            metadata = msg.get("metadata", {})
            source_files = metadata.get("source_files", [])
            content = msg.get("content", "")
            
            if not source_files or not content:
                continue
            
            # Пытаемся найти описания файлов в тексте ответа
            # Ищем паттерны типа "Файл: filename - описание" или "Изображение: filename - описание"
            import re
            
            # Простой паттерн: ищем упоминания имен файлов и текст после них
            for file_id in source_files:
                if file_id in file_summaries:
                    continue  # Уже нашли описание
                
                file_data = context.get_file(file_id)
                if not file_data:
                    continue
                
                filename = file_data.get('filename', '')
                if not filename:
                    continue
                
                # Ищем упоминание файла в тексте
                filename_base = filename.rsplit('.', 1)[0]  # Без расширения
                
                # Паттерны для поиска описания
                patterns = [
                    rf"{re.escape(filename)}[:\-]\s*([^\.]+(?:\.[^\.]+)*)",
                    rf"{re.escape(filename_base)}[:\-]\s*([^\.]+(?:\.[^\.]+)*)",
                    rf"Изображение.*?{re.escape(filename)}[:\-]\s*([^\.]+(?:\.[^\.]+)*)",
                    rf"PDF.*?{re.escape(filename)}[:\-]\s*([^\.]+(?:\.[^\.]+)*)",
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        description = match.group(1).strip()
                        if len(description) > 10:  # Минимальная длина описания
                            file_summaries[file_id] = description
                            break
        
        return file_summaries
    
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
        import time
        _think_plan_start = time.time()
        _llm_duration = 0  # Initialize to avoid NameError
        
        # ========== ОПТИМИЗИРОВАННЫЙ ПРОМПТ С XML-СТРУКТУРОЙ ==========
        # Perplexity рекомендации:
        # 1. История действий В НАЧАЛЕ (0-5% позиция) - не в середине!
        # 2. XML-теги для чёткой структуры
        # 3. Только релевантные инструменты (3-7, не 50)
        # 4. 5-7 критических правил (не 100 строк)
        # 5. Явный next_step
        
        from datetime import datetime, timedelta
        import pytz
        from src.utils.config_loader import get_config
        tz = pytz.timezone(get_config().timezone)
        now = datetime.now(tz)
        current_date_str = now.strftime("%Y-%m-%d %H:%M")
        
        # Собираем список выполненных инструментов
        completed_tools = [a.tool_name for a in state.action_history] if state.action_history else []
        
        # #region agent log - проверка completed_tools для параллельных веток
        use_existing_value_log = self._get_use_existing_intent_id(state)
        is_parallel_check = use_existing_value_log is not None
        if is_parallel_check:
            import json as _debug_json_completed; import time as _debug_time_completed
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_completed:
                    _debug_f_completed.write(_debug_json_completed.dumps({"id":f"log_{int(_debug_time_completed.time()*1000)}_parallel_completed_tools","timestamp":int(_debug_time_completed.time()*1000),"location":"unified_react_engine.py:4758","message":"Parallel branch - completed_tools check","data":{"is_parallel":True,"use_existing_intent_id":use_existing_value_log,"goal":state.goal[:100],"completed_tools":completed_tools,"action_history_count":len(state.action_history) if state.action_history else 0},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
            except:
                pass
        # #endregion
        
        # Получаем релевантные инструменты (3-7 штук вместо 50)
        _tools_start = time.time()
        relevant_tools = self._get_relevant_tools(state.goal, completed_tools)
        _tools_duration = time.time() - _tools_start
        logger.info(f"[UnifiedReActEngine] _get_relevant_tools took {_tools_duration:.3f}s, selected {len(relevant_tools)} tools")
        
        # CRITICAL: Store relevant tools list for fallback logic
        # Tools are already sorted by relevance (first is most relevant)
        self._current_relevant_tools = [t['name'] for t in relevant_tools]
        
        # #region agent log
        import json as _debug_json_prompt; import time as _debug_time_prompt
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_prompt:
                _debug_f_prompt.write(_debug_json_prompt.dumps({"id":f"log_{int(_debug_time_prompt.time()*1000)}_tools_for_prompt","timestamp":int(_debug_time_prompt.time()*1000),"location":"unified_react_engine.py:4502","message":"Tools selected for prompt","data":{"goal":state.goal,"selected_tools":self._current_relevant_tools,"tools_descriptions":{t['name']:t['description'][:200] for t in relevant_tools}},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
        except:
            pass
        # #endregion
        
        tools_str = "\n".join([f"- {t['name']}: {t['description']}" for t in relevant_tools])
        
        # Select relevant skill (if smart tool selection is enabled)
        skill_instructions = ""
        import time
        _skill_start = time.time()
        if self.use_smart_tool_selection and self.skill_selector:
            try:
                selected_skill = self.skill_selector.select_skill(state.goal)
                if selected_skill:
                    self.active_skill = selected_skill
                    
                    # Проверяем cache для formatted instructions
                    cached_instructions = self._skill_instructions_cache.get(selected_skill.name)
                    
                    if cached_instructions:
                        # Cache hit - используем из cache
                        skill_instructions = cached_instructions
                        logger.debug(f"[UnifiedReActEngine] Using cached skill instructions for {selected_skill.name}")
                    else:
                        # Cache miss - форматируем заново
                        skill_instructions = f"""
<skill_instructions>
АКТИВНЫЙ SKILL: {selected_skill.name}

{selected_skill.get_instructions()}
</skill_instructions>"""
                        # Сохраняем в cache
                        self._skill_instructions_cache.set(selected_skill.name, skill_instructions)
                        logger.debug(f"[UnifiedReActEngine] Cached skill instructions for {selected_skill.name}")
                    
                    logger.info(f"[UnifiedReActEngine] Selected skill: {selected_skill.name}")
                else:
                    logger.info(f"[UnifiedReActEngine] No skill selected for goal: {state.goal[:50]}")
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Skill selection failed: {e}", exc_info=True)
        else:
            logger.debug(f"[UnifiedReActEngine] Smart tool selection disabled or skill_selector not available")
        _skill_duration = time.time() - _skill_start
        if self.use_smart_tool_selection:
            logger.info(f"[UnifiedReActEngine] Skill selection took {_skill_duration:.3f}s")
        
        # ===== СЕКЦИЯ 1: TASK_STATUS (в начале!) =====
        # Подсчитываем количество неудачных попыток подряд
        consecutive_errors = 0
        if state.action_history and state.observations:
            for i in range(len(state.action_history) - 1, -1, -1):
                if i < len(state.observations) and state.observations[i] and not state.observations[i].success:
                    consecutive_errors += 1
                else:
                    break
        
        # Если 3 или больше ошибок подряд - запросить помощь у пользователя
        error_status = ""
        if consecutive_errors >= 3:
            error_status = f"\n⚠️ КРИТИЧНО: {consecutive_errors} неудачных попыток подряд. Нужна помощь пользователя для продолжения."
        
        task_status = f"""<task_status>
Цель: {state.goal}
Итерация: {state.iteration}{error_status}
Дата: {current_date_str}
</task_status>"""
        
        # ===== СЕКЦИЯ 2: COMPLETED_ACTIONS (сразу после статуса - критично!) =====
        completed_section = ""
        # #region agent log - проверка изоляции контекста для параллельных веток
        use_existing_value_parallel = self._get_use_existing_intent_id(state)
        is_parallel = use_existing_value_parallel is not None
        if is_parallel:
            import json as _debug_json_parallel; import time as _debug_time_parallel
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_parallel:
                    _debug_f_parallel.write(_debug_json_parallel.dumps({"id":f"log_{int(_debug_time_parallel.time()*1000)}_parallel_completed_actions","timestamp":int(_debug_time_parallel.time()*1000),"location":"unified_react_engine.py:4727","message":"Parallel branch - checking completed actions","data":{"is_parallel":True,"use_existing_intent_id":use_existing_value_parallel,"goal":state.goal[:100],"action_history_count":len(state.action_history) if state.action_history else 0,"action_history_tools":[a.tool_name for a in state.action_history] if state.action_history else []},"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
            except:
                pass
        # #endregion
        if state.action_history and state.observations:
            completed_lines = []
            for i, action in enumerate(state.action_history):
                obs = state.observations[i] if i < len(state.observations) else None
                status = "DONE" if obs and obs.success else "FAILED"
                result_preview = ""
                if obs and obs.raw_result:
                    # For execute_python_code, show more of the result (up to 2000 chars) to include chartData
                    if action.tool_name == "execute_python_code":
                        result_str = str(obs.raw_result)
                        # If result contains chartData, show it explicitly
                        if "chartData" in result_str or "Result:" in result_str:
                            result_preview = f" → {result_str[:2000]}..."
                        else:
                            result_preview = f" → {result_str[:500]}..."
                    else:
                        result_preview = f" → {str(obs.raw_result)[:150]}..."
                completed_lines.append(f"{i+1}. {action.tool_name} — {status}{result_preview}")
            
            # Determine if we can retry failed tools (if error was about parameters)
            can_retry_note = ""
            if hasattr(self, '_can_retry_with_params') and self._can_retry_with_params and hasattr(self, '_failed_tool_name') and self._failed_tool_name:
                can_retry_note = f"\n\n⚠️ ВАЖНО: Инструмент {self._failed_tool_name} завершился с ошибкой параметров. МОЖНО повторить этот инструмент с ДРУГИМИ параметрами!"
            
            completed_section = f"""
<completed_actions>
ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ:
{chr(10).join(completed_lines)}{can_retry_note}

ПРАВИЛО: Не повторяй одно и то же действие с теми же параметрами. Но если действие завершилось с ошибкой параметров - МОЖНО повторить с другими параметрами.
</completed_actions>"""
        
        # ===== СЕКЦИЯ 3: PREVIOUS_ERRORS (если были ошибки при предыдущих попытках) =====
        error_section = ""
        if hasattr(self, '_last_tool_error') and self._last_tool_error:
            retry_instruction = ""
            if hasattr(self, '_can_retry_with_params') and self._can_retry_with_params and hasattr(self, '_failed_tool_name') and self._failed_tool_name:
                retry_instruction = f"\n\n💡 РЕШЕНИЕ: Попробуй использовать инструмент {self._failed_tool_name} снова, но с ДРУГИМИ параметрами, которые соответствуют ошибке выше."
            else:
                retry_instruction = "\n\n💡 РЕШЕНИЕ: Попробуй другой подход или другой инструмент."
            
            error_section = f"""
<previous_errors>
⚠️ ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ:
{self._last_tool_error}{retry_instruction}
</previous_errors>"""
            # Clear error after using it (but keep retry flags for completed_section)
            # Don't clear _can_retry_with_params and _failed_tool_name yet - they're used in completed_section
        
        # ===== СЕКЦИЯ 4: BLOCKED_TOOLS (не повторять выполненные) =====
        # Исключаем failed_tool_name из blocked_tools, если можно повторить с другими параметрами
        tools_to_block = completed_tools.copy() if completed_tools else []
        if hasattr(self, '_can_retry_with_params') and self._can_retry_with_params and hasattr(self, '_failed_tool_name') and self._failed_tool_name:
            # Если инструмент можно повторить с другими параметрами - не блокируем его
            if self._failed_tool_name in tools_to_block:
                tools_to_block.remove(self._failed_tool_name)
        
        # Специальные блокировки для get_all_sheets_data (чтобы не читать повторно)
        goal_lower_check = state.goal.lower()
        if "get_all_sheets_data" in completed_tools:
            tools_to_block.extend(["get_sheet_data", "sheets_read_range", "get_all_sheets_data"])
        
        blocked_str = ", ".join(set(tools_to_block)) if tools_to_block else "нет"
        
        # Секция только если есть заблокированные инструменты
        blocked_section = ""
        if tools_to_block:
            blocked_section = f"""
<blocked_tools>
ЗАПРЕЩЕНО ПОВТОРЯТЬ: {blocked_str}
</blocked_tools>"""
        
        # ===== СЕКЦИЯ 5: CONTEXT (открытые файлы, прикреплённые файлы) =====
        context_section = ""
        
        # Открытые файлы
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        if open_files:
            files_lines = []
            for file in open_files:
                file_type = file.get('type')
                title = file.get('title', 'Без названия')
                if file_type == 'docs':
                    doc_id = file.get('document_id') or file.get('documentId')
                    if not doc_id and file.get('url'):
                        url_match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                        if url_match:
                            doc_id = url_match.group(1)
                    if doc_id:
                        files_lines.append(f"- Документ: {title} (ID: {doc_id})")
                elif file_type == 'sheets':
                    sheet_id = file.get('spreadsheet_id') or file.get('spreadsheetId')
                    if sheet_id:
                        files_lines.append(f"- Таблица: {title} (ID: {sheet_id})")
            
            if files_lines:
                context_section += f"""
<open_files>
{chr(10).join(files_lines)}
</open_files>"""
        
        # Прикреплённые файлы - НОВЫЙ ПОДХОД: всё в контекст + LLM сам разбирается
        # Для конкретных запросов (про конкретные файлы) - не показываем сводку всех файлов
        # Для общих запросов ("что в файлах?") - показываем сводку всех файлов
        if hasattr(context, 'uploaded_files') and context.uploaded_files:
            # Определяем, является ли запрос конкретным или общим
            is_specific_query = self._is_specific_file_query(state.goal, context, file_ids)
            
            # Получаем описания файлов из предыдущих ответов
            file_summaries = self._get_file_summaries_from_history(context)
            
            # Определяем, какие файлы нужно включить полностью
            # Приоритет: 1) файлы из file_ids (явно запрошены), 2) файлы из предыдущего ответа
            files_to_include_fully = set(file_ids) if file_ids else set()
            
            # Ищем файлы из предыдущего ответа
            if hasattr(context, 'messages') and context.messages:
                for msg in reversed(context.messages[-10:]):  # Последние 10 сообщений
                    if msg.get("role") == "assistant":
                        metadata = msg.get("metadata", {})
                        prev_source_files = metadata.get("source_files", [])
                        if prev_source_files:
                            files_to_include_fully.update(prev_source_files)
                            break  # Берем только из последнего ответа
            
            # Если нет файлов для полного включения - используем все файлы
            if not files_to_include_fully:
                files_to_include_fully = set(context.uploaded_files.keys())
            
            # Формируем содержимое файлов
            files_full_content = []
            all_files_summary = []
            
            for file_id, file_data in context.uploaded_files.items():
                filename = file_data.get('filename', 'unknown')
                file_type = file_data.get('type', '')
                
                # Получаем описание из истории или создаем базовое
                description = file_summaries.get(file_id, '')
                if not description:
                    if file_type.startswith('image/'):
                        description = 'Изображение'
                    elif file_type == 'application/pdf':
                        description = 'PDF документ'
                    else:
                        description = f'Файл ({file_type})'
                
                # Если файл нужно включить полностью - добавляем его содержимое
                if file_id in files_to_include_fully:
                    if 'text' in file_data:
                        text = file_data.get('text', '')
                        files_full_content.append(f"=== {filename} ===\n{text}")
                    elif file_type.startswith('image/'):
                        files_full_content.append(f"=== {filename} ===\n[Изображение включено в сообщение]")
                    else:
                        files_full_content.append(f"=== {filename} ===\n[Файл типа {file_type}]")
                
                # Для общих запросов - добавляем в сводку
                if not is_specific_query:
                    all_files_summary.append(f"{len(all_files_summary) + 1}. {filename} — {description}")
            
            # Формируем секцию
                context_section += f"""
<attached_files>"""
            
            # Показываем сводку только для общих запросов
            if not is_specific_query and all_files_summary:
                context_section += f"""
📎 ДОСТУПНЫЕ ФАЙЛЫ В СЕССИИ:
{chr(10).join(all_files_summary)}

"""
            
            # Показываем полное содержимое
            if files_full_content:
                context_section += f"""📄 СОДЕРЖИМОЕ ФАЙЛОВ:
{chr(10).join(files_full_content)}

"""
            
            # Инструкция зависит от типа запроса
            if is_specific_query:
                context_section += """💡 ИНСТРУКЦИЯ:
- Используй содержимое файлов выше для ответа на вопрос пользователя
- НЕ используй open_file для этих файлов - их содержимое УЖЕ выше!
</attached_files>"""
            else:
                context_section += """💡 ИНСТРУКЦИЯ:
- Если пользователь спрашивает про конкретный файл - используй его полное содержимое выше
- Если пользователь спрашивает про несколько файлов - используй соответствующие файлы
- Если нужна информация о файле, которого нет в полном содержимом - обратись к нему по имени из сводки
- НЕ используй open_file для этих файлов - их содержимое УЖЕ выше или доступно по имени!
</attached_files>"""
        
        # ===== СЕКЦИЯ 5: AVAILABLE_TOOLS (только релевантные!) =====
        tools_section = f"""
<available_tools>
{tools_str}
</available_tools>"""
        
        # ===== СЕКЦИЯ 6: CRITICAL_RULES (5-7 правил, не 100 строк) =====
        # Проверяем, был ли вызван get_all_sheets_data
        has_get_all_sheets = "get_all_sheets_data" in completed_tools
        goal_lower = state.goal.lower()
        needs_extended_analysis = any(kw in goal_lower for kw in ["расширенный", "большой", "подробный", "глубокий", "полный", "комплексный"])
        
        special_rules = ""
        # Проверяем, нужно ли использовать get_all_sheets_data для анализа нескольких вкладок
        goal_lower_check = state.goal.lower()
        needs_multi_sheet_analysis = any(kw in goal_lower_check for kw in ["несколько вкладок", "две вкладки", "все вкладки", "проанализируй", "анализ", "расширенный", "большой", "подробный", "глубокий", "полный", "комплексный"])
        
        if needs_multi_sheet_analysis and not has_get_all_sheets:
            special_rules += "\n6. ⚠️ КРИТИЧЕСКИ ВАЖНО: Для анализа таблицы с несколькими вкладками ОБЯЗАТЕЛЬНО используй get_all_sheets_data ПЕРВЫМ! НЕ используй get_sheet_data или sheets_read_range - они читают только одну вкладку!"
        
        if has_get_all_sheets:
            special_rules += "\n7. ⚠️ КРИТИЧЕСКИ ВАЖНО: После get_all_sheets_data данные УЖЕ получены со ВСЕХ вкладок! НЕ вызывай get_sheet_data, sheets_read_range или другие инструменты чтения - данные уже в контексте!"
        
        if needs_extended_analysis and has_get_all_sheets:
            special_rules += "\n8. ⚠️ РАСШИРЕННЫЙ АНАЛИЗ: После get_all_sheets_data сразу используй execute_python_code для написания кода анализа! НЕ пытайся читать данные повторно!"
        
        # Правило для Project Lad
        needs_projectlad = any(kw in goal_lower_check for kw in ["project", "lad", "проект", "портфель", "загрузк", "ресурс", "workload", "часы сотрудник"])
        if needs_projectlad:
            special_rules += """
10. 📊 PROJECT LAD — ОБЯЗАТЕЛЬНЫЙ ПОРЯДОК ДЛЯ ЗАГРУЗКИ РЕСУРСОВ:
   ⚠️ КРИТИЧЕСКИ ВАЖНО: Для получения загрузки ресурсов нужны project_id И version_id!
   
   ПРАВИЛЬНЫЙ ПОРЯДОК:
   1. Вызови projectlad_list_projects
   2. В ответе ищи КОНКРЕТНЫЙ проект по НАЗВАНИЮ (например "Atlas")
   3. Если проект ВЛОЖЕННЫЙ (находится в секции "ВЛОЖЕННЫЕ ПРОЕКТЫ (Children)"):
      - НЕ используй данные родительского проекта!
      - Используй данные ВЛОЖЕННОГО проекта (находится под разделителем ──────)
   4. Копируй project_id и version_id ТОЧНО как показано для НУЖНОГО проекта
   
   ПРИМЕР ответа projectlad_list_projects:
   • Портфель: Разработка продуктов
     project_id: 20DCveXE7Cf88cBuui9Fx  ← НЕ ИСПОЛЬЗУЙ ЭТО для Atlas!
     version_id: UOz6dC2GB5n25jbBwmQ0B   ← НЕ ИСПОЛЬЗУЙ ЭТО для Atlas!
     ──────────────────────────
     ВЛОЖЕННЫЕ ПРОЕКТЫ (Children):
     ──────────────────────────
      • Atlas — веб-платформа
        project_id: IzNRF5kByOLXRJ_0k2_Cc  ← ИСПОЛЬЗУЙ ЭТО для Atlas!
        version_id: koNwJOYXf8vrk4x0aqsIl   ← ИСПОЛЬЗУЙ ЭТО для Atlas!
   
   ⚠️ ДЛЯ ВЛОЖЕННОГО ПРОЕКТА "Atlas":
   - project_id: IzNRF5kByOLXRJ_0k2_Cc (НЕ 20DCveXE7Cf88cBuui9Fx!)
   - version_id: koNwJOYXf8vrk4x0aqsIl (НЕ UOz6dC2GB5n25jbBwmQ0B!)
   
   ❌ ЗАПРЕЩЕНО: Использовать project_id/version_id родительского проекта для вложенного проекта!
   ✅ ПРАВИЛЬНО: Всегда бери данные КОНКРЕТНОГО проекта который запрашивается, а не его родителя!"""
        
        # === ИСПРАВЛЕНИЕ C: Явный список библиотек для execute_python_code ===
        code_execution_rule = ""
        if any(kw in goal_lower for kw in ["расширенный", "большой", "подробный", "глубокий", "полный", "комплексный", "анализ", "проанализируй"]):
            code_execution_rule = """
6. ⚠️ execute_python_code — ОБЯЗАТЕЛЬНО НАПИШИ КОД!
   - arguments.code ОБЯЗАТЕЛЕН! Пустые arguments недопустимы!
   - Данные в переменной 'data': sheets_data = data.get("sheets", [])
   - Структура листа: {"name": "Зарплата", "data": [{"Сотрудник": "Иванов", "Зарплата": "100"}, ...]}
   - Доступ: sheet["name"], row["Зарплата"] (НЕ row[0]!)
   - ЗАПРЕЩЕНО вставлять сами данные в код!
   
   ⚠️ ОПРЕДЕЛЕНИЕ ПОЛА ПО РУССКОЙ ФАМИЛИИ:
   - Женские фамилии ЗАКАНЧИВАЮТСЯ на "а" или "я": Овцова, Сидорова, Хрюшечкина
   - Мужские фамилии НЕ заканчиваются на "а"/"я": Петров, Козаков, Иванов
   - ПРАВИЛЬНЫЙ КОД:
     def is_female(name):
         return name.strip().lower().endswith(('а', 'я'))
     
     for row in data:
         if is_female(row['Сотрудник']):
             girls_data.append(row)
         else:
             boys_data.append(row)
   
   - НЕ используй 'ОВ' in name — это НЕПРАВИЛЬНО! (Овцова содержит ОВ, но это девочка!)
   
   ⚠️ СОЗДАЙ 6-8 РАЗНЫХ ДИАГРАММ! Используй разные типы:
   - "bar" — столбчатая диаграмма для сравнения
   - "line" — линейный график для динамики по времени
   - "pie" — круговая диаграмма для долей
   - "donut" — кольцевая диаграмма
   
   📊 ПРИМЕРЫ ДИАГРАММ для данных о зарплатах/выработке:
   1. "Зарплата мальчиков по месяцам" (line)
   2. "Зарплата девочек по месяцам" (line)
   3. "Выработка мальчиков по месяцам" (line)
   4. "Выработка девочек по месяцам" (line)
   5. "Сравнение средней зарплаты" (bar)
   6. "Сравнение средней выработки" (bar)
   7. "Доля зарплаты по группам" (pie)
   8. "Эффективность по группам" (donut)
   
   ⚠️ ЗАЩИТА ОТ division by zero:
   - Перед делением ПРОВЕРЯЙ что список не пустой: if len(boys) > 0: avg = sum(boys) / len(boys) else: avg = 0
   
   ⚠️ ФОРМАТ chartData для ApexCharts:
   result = {"chartData": [
       {"title": "Название", "chartType": "line", "series": [{"name": "Мальчики", "data": [100, 110, 120]}], "options": {"xaxis": {"categories": ["Янв", "Фев", "Мар"]}}},
       {"title": "Название2", "chartType": "bar", "series": [{"name": "Значения", "data": [50, 60]}], "options": {"xaxis": {"categories": ["Группа1", "Группа2"]}}},
       {"title": "Доли", "chartType": "pie", "series": [45, 55], "options": {"labels": ["Мальчики", "Девочки"]}}
   ]}
   
   ⚠️ ВАЖНО для pie/donut: series — это массив чисел [45, 55], НЕ объектов! labels в options!"""
        
        rules_section = f"""
<critical_rules>
1. НЕ повторяй действия из <completed_actions> — это приведёт к зацикливанию
2. После всех шагов вызови FINISH
3. При ошибке попробуй альтернативу, не повторяй то же действие
4. Данные из предыдущих шагов УЖЕ в контексте — не читай повторно
5. Если прикреплены файлы — НЕ открывай их через инструменты{code_execution_rule}{special_rules}
</critical_rules>"""
        
        # ===== СЕКЦИЯ 7: OUTPUT_FORMAT =====
        format_section = """
<output_format>
Ответь СТРОГО в формате:

<thought>
Кратко опиши своё рассуждение: что ты понял из задачи, какие данные уже есть в контексте, и что собираешься сделать дальше. Пиши естественно, без структурированных списков "что сделано / что осталось".
</thought>
<action>
{
    "tool_name": "имя_инструмента",
    "arguments": {"param": "value"},
    "description": "что делаем",
    "reasoning": "почему"
}
</action>

Для завершения:
{"tool_name": "FINISH", "arguments": {}, "description": "задача выполнена", "reasoning": "все шаги сделаны"}
</output_format>"""
        
        # ===== СОБИРАЕМ ПРОМПТ =====
        # Порядок критичен! История СРАЗУ после статуса (первые 10% контекста)
        prompt = f"""{task_status}
{completed_section}
{error_section}
{blocked_section}
{context_section}
{skill_instructions}
{tools_section}
{rules_section}
{format_section}"""
        
        # #region agent log - ПОЛНОЕ логирование промпта для всех веток
        use_existing_value_prompt = self._get_use_existing_intent_id(state)
        is_parallel_prompt = use_existing_value_prompt is not None
        import json as _debug_json_full_prompt_log; import time as _debug_time_full_prompt_log
        try:
            # Собираем информацию о доступных инструментах
            available_tools_list = []
            if 'tools_section' in locals():
                import re
                tool_matches = re.findall(r'- (\w+):', tools_section)
                available_tools_list = tool_matches
            
            relevant_tools_list = []
            if 'relevant_tools' in locals():
                relevant_tools_list = [t.get('name', '') for t in relevant_tools]
            
            # Формируем уникальный ID для этого промпта
            prompt_id = f"prompt_{state.goal[:30].replace(' ', '_')}_{state.iteration}_{int(_debug_time_full_prompt_log.time()*1000)}"
            
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_full_prompt:
                _debug_f_full_prompt.write(_debug_json_full_prompt_log.dumps({
                    "id": prompt_id,
                    "timestamp": int(_debug_time_full_prompt_log.time()*1000),
                    "location": "unified_react_engine.py:5126",
                    "message": "FULL PROMPT TO LLM",
                    "data": {
                        "is_parallel": is_parallel_prompt,
                        "use_existing_intent_id": use_existing_value_prompt,
                        "goal": state.goal,
                        "iteration": state.iteration,
                        "FULL_PROMPT": prompt,
                        "relevant_tools": relevant_tools_list,
                        "available_tools_in_prompt": available_tools_list
                    },
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "PROMPT"
                }, ensure_ascii=False) + '\n')
        except Exception as e:
            pass
        # #endregion
        
        try:
            messages = [
                SystemMessage(content="Ты эксперт по анализу задач и планированию действий. Отвечай в указанном формате на русском языке."),
                HumanMessage(content=prompt)
            ]
            
            # CRITICAL: Создаём llm_with_tools ТОЛЬКО с релевантными инструментами
            # Это предотвращает выбор инструментов, которых нет в списке релевантных
            relevant_tool_names = [t['name'] for t in relevant_tools]
            
            # Создаём парсер для стриминга thought
            # ВАЖНО: Используем _task_intent_id (первый intent) для ВСЕХ итераций,
            # чтобы все iteration_thinking_chunk шли в один intent block
            iteration_intent_id = getattr(self, '_task_intent_id', None) or getattr(self, '_current_intent_id', None)
            
            parser = self.StreamingThoughtParser(
                self.ws_manager,
                self.session_id,
                intent_id=iteration_intent_id,
                iteration_number=state.iteration,
                engine=self  # Передаем engine для сохранения operation_id
            )
            relevant_base_tools = [t for t in self.tools if t.name in relevant_tool_names]
            
            # #region agent log - проверка инструментов, которые попадают в bind_tools для параллельных веток
            use_existing_value_bind = self._get_use_existing_intent_id(state)
            is_parallel_bind = use_existing_value_bind is not None
            if is_parallel_bind:
                import json as _debug_json_bind; import time as _debug_time_bind
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_bind:
                        _debug_f_bind.write(_debug_json_bind.dumps({"id":f"log_{int(_debug_time_bind.time()*1000)}_bind_tools","timestamp":int(_debug_time_bind.time()*1000),"location":"unified_react_engine.py:5173","message":"Tools bound to LLM for parallel branch","data":{"is_parallel":True,"use_existing_intent_id":use_existing_value_bind,"goal":state.goal[:100],"relevant_tool_names":relevant_tool_names,"bound_tools_names":[t.name for t in relevant_base_tools],"bound_tools_count":len(relevant_base_tools),"has_get_calendar_events_in_bound":"get_calendar_events" in [t.name for t in relevant_base_tools],"has_list_emails_in_bound":"list_emails" in [t.name for t in relevant_base_tools]},"sessionId":"debug-session","runId":"run1","hypothesisId":"G"}) + '\n')
                except:
                    pass
            # #endregion
            
            # Создаём llm_with_relevant_tools только с релевантными инструментами
            llm_with_relevant_tools = self.llm.bind_tools(relevant_base_tools)
            llm_to_use = llm_with_relevant_tools
            
            # Стримим ответ
            import time
            _llm_start = time.time()
            full_response = ""
            _chunk_count = 0
            last_chunk = None  # Сохраняем последний chunk для проверки tool_calls
            async for chunk in llm_to_use.astream(messages):
                _chunk_count += 1
                last_chunk = chunk  # Сохраняем для проверки tool_calls
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
            
            _llm_duration = time.time() - _llm_start
            logger.info(f"[UnifiedReActEngine] LLM streaming took {_llm_duration:.3f}s ({_chunk_count} chunks)")
            
            # #region agent log - ПОЛНЫЙ ответ LLM
            try:
                import json as _debug_json_llm_response; import time as _debug_time_llm_response
                response_id = f"response_{state.goal[:30].replace(' ', '_')}_{state.iteration}_{int(_debug_time_llm_response.time()*1000)}"
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_llm_response:
                    _debug_f_llm_response.write(_debug_json_llm_response.dumps({
                        "id": response_id,
                        "timestamp": int(_debug_time_llm_response.time()*1000),
                        "location": "unified_react_engine.py:5237",
                        "message": "FULL LLM RESPONSE",
                        "data": {
                            "is_parallel": self._get_use_existing_intent_id(state) is not None,
                            "use_existing_intent_id": self._get_use_existing_intent_id(state),
                            "goal": state.goal,
                            "iteration": state.iteration,
                            "FULL_RESPONSE": full_response,
                            "duration_sec": _llm_duration
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "RESPONSE"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Получаем thought из парсера
            thought = parser.get_thought()
            
            # CRITICAL: Проверяем tool_calls в ответе LLM (если используется llm_with_tools)
            # Если LLM вернул tool_calls, используем их вместо парсинга XML
            action_plan_from_tool_calls = None
            if last_chunk and hasattr(last_chunk, 'tool_calls') and last_chunk.tool_calls:
                # LLM вернул tool_calls - используем их
                tool_calls = last_chunk.tool_calls
                
                # #region agent log - LLM выбрал инструменты
                try:
                    import json as _debug_json_tool_calls; import time as _debug_time_tool_calls
                    tool_calls_for_log = []
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            tool_calls_for_log.append({"name": tc.get("name"), "args": tc.get("args", {})})
                        elif hasattr(tc, "name"):
                            tool_calls_for_log.append({"name": tc.name, "args": getattr(tc, "args", {})})
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_tool_calls:
                        _debug_f_tool_calls.write(_debug_json_tool_calls.dumps({
                            "id": f"log_{int(_debug_time_tool_calls.time()*1000)}_llm_tool_calls",
                            "timestamp": int(_debug_time_tool_calls.time()*1000),
                            "location": "unified_react_engine.py:5676",
                            "message": "LLM SELECTED TOOLS",
                            "data": {
                                "goal": state.goal,
                                "iteration": state.iteration,
                                "tool_calls": tool_calls_for_log,
                                "tool_calls_count": len(tool_calls)
                            },
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "TOOL_CALLS"
                        }, ensure_ascii=False) + '\n')
                except:
                    pass
                # #endregion
                
                if tool_calls and len(tool_calls) > 0:
                    # Берем первый tool_call (обычно один)
                    first_tool_call = tool_calls[0]
                    tool_name = None
                    tool_args = {}
                    
                    # Обрабатываем разные форматы tool_calls
                    if isinstance(first_tool_call, dict):
                        tool_name = first_tool_call.get("name")
                        tool_args = first_tool_call.get("args", {})
                    elif hasattr(first_tool_call, "name"):
                        tool_name = first_tool_call.name
                        tool_args = getattr(first_tool_call, "args", {})
                    
                    if tool_name:
                        action_plan_from_tool_calls = {
                            "tool_name": tool_name,
                            "arguments": tool_args,
                            "description": f"Вызов инструмента {tool_name}",
                            "reasoning": f"LLM выбрал инструмент {tool_name} для выполнения задачи"
                        }
            
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
            
            # #region agent log - логируем response_text перед парсингом
            try:
                import json as _debug_json_parse; import time as _debug_time_parse
                parse_id = f"parse_{state.goal[:30].replace(' ', '_')}_{state.iteration}_{int(_debug_time_parse.time()*1000)}"
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_parse:
                    _debug_f_parse.write(_debug_json_parse.dumps({
                        "id": parse_id,
                        "timestamp": int(_debug_time_parse.time()*1000),
                        "location": "unified_react_engine.py:5345",
                        "message": "PARSING ACTION FROM TEXT",
                        "data": {
                            "is_parallel": self._get_use_existing_intent_id(state) is not None,
                            "use_existing_intent_id": self._get_use_existing_intent_id(state),
                            "goal": state.goal,
                            "iteration": state.iteration,
                            "used_remaining_buffer": bool(remaining_buffer),
                            "remaining_buffer_length": len(remaining_buffer) if remaining_buffer else 0,
                            "full_response_length": len(full_response) if full_response else 0,
                            "RESPONSE_TEXT_TO_PARSE": response_text,
                            "full_response_preview": full_response[:500] if full_response else ""
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "PARSE"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Если есть action_plan из tool_calls, используем его, иначе парсим XML
            if action_plan_from_tool_calls:
                action_plan = action_plan_from_tool_calls
            else:
                # Ищем action блок в тексте (fallback для случаев, когда LLM не использует tool_calls)
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
                        
                        # Fix: escape real newlines inside "code" value
                        # LLM sometimes generates code with real \n instead of \\n
                        def fix_code_newlines(match):
                            code_value = match.group(1)
                            # Replace real newlines with escaped
                            fixed = code_value.replace('\n', '\\n').replace('\r', '\\r')
                            return f'"code": "{fixed}"'
                        
                        json_str = re.sub(r'"code":\s*"((?:[^"\\]|\\.)*)"\s*(?=[,}])', fix_code_newlines, json_str, flags=re.DOTALL)
                        
                        try:
                            action_plan = json.loads(json_str)
                        except json.JSONDecodeError as json_err:
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
            
            # #region agent log - ПОСЛЕ парсинга action_plan, ДО нормализации
            try:
                import json as _debug_json_parsed; import time as _debug_time_parsed
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_parsed:
                    _debug_f_parsed.write(_debug_json_parsed.dumps({
                        "id": f"log_{int(_debug_time_parsed.time()*1000)}_action_parsed",
                        "timestamp": int(_debug_time_parsed.time()*1000),
                        "location": "unified_react_engine.py:5420",
                        "message": "ACTION PARSED (before normalization)",
                        "data": {
                            "is_parallel": self._get_use_existing_intent_id(state) is not None,
                            "use_existing_intent_id": self._get_use_existing_intent_id(state),
                            "goal": state.goal,
                            "iteration": state.iteration,
                            "selected_tool": tool_name,
                            "action_plan": action_plan,
                            "was_from_tool_calls": action_plan_from_tool_calls is not None,
                            "relevant_tools": relevant_tool_names
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "PARSED"
                    }, ensure_ascii=False) + '\n')
            except Exception as e:
                pass
            # #endregion
            
            # CRITICAL: Remove prefix like "functions." if LLM returns it
            # Some LLMs return "functions.list_emails" instead of "list_emails"
            if tool_name.startswith("functions."):
                tool_name = tool_name.replace("functions.", "", 1)
                action_plan["tool_name"] = tool_name  # Update action_plan too
            # Also handle other possible prefixes
            if "." in tool_name and not tool_name.startswith("FINISH"):
                # If tool_name contains dot and is not FINISH, try to extract base name
                # e.g., "functions.list_emails" -> "list_emails"
                parts = tool_name.split(".")
                if len(parts) > 1:
                    # Take the last part as the actual tool name
                    potential_tool_name = parts[-1]
                    # Check if this tool exists in capabilities
                    if any(c.name == potential_tool_name for c in self.capabilities):
                        tool_name = potential_tool_name
                        action_plan["tool_name"] = tool_name
            
            # Validate execute_python_code has code
            if tool_name == "execute_python_code":
                code = action_plan.get("arguments", {}).get("code", "")
                if not code or not code.strip():
                    # LLM forgot to include code - return error to force retry with code
                    logger.warning("[UnifiedReActEngine] execute_python_code called without code, forcing retry")
                    action_plan["arguments"]["code"] = """
# ОШИБКА: Код не был предоставлен!
# Необходимо написать Python код для анализа данных.
# Данные доступны в переменной 'data':
#   sheets_data = data.get("sheets", [])
#   sheet = sheets_data[0]  # {"name": "...", "data": [{...}, ...]}
#   for row in sheet["data"]:
#       value = row["ColumnName"]
raise ValueError("Код анализа не был предоставлен. Перепишите action с полным Python кодом в arguments.code")
"""
            
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
            
            _think_plan_total = time.time() - _think_plan_start
            _other_time = _think_plan_total - _tools_duration - _skill_duration - _llm_duration
            logger.info(
                f"[UnifiedReActEngine] _think_and_plan total: {_think_plan_total:.3f}s "
                f"(tools: {_tools_duration:.3f}s, skill: {_skill_duration:.3f}s, "
                f"llm: {_llm_duration:.3f}s, other: {_other_time:.3f}s)"
            )
            
            return thought, action_plan

        except Exception as e:
            _think_plan_total = time.time() - _think_plan_start if '_think_plan_start' in locals() else 0
            logger.error(f"[UnifiedReActEngine] Error in _think_and_plan after {_think_plan_total:.3f}s: {e}", exc_info=True)
            
            # Fallback
            fallback_thought = f"Анализирую ситуацию... (итерация {state.iteration})"
            
            # Вместо первого capability, используем релевантный для задачи
            goal_lower = state.goal.lower() if state.goal else ""
            fallback_tool = None
            
            # Определяем подходящий инструмент и аргументы на основе ключевых слов
            fallback_arguments = {}
            
            if any(kw in goal_lower for kw in ["встреч", "календар", "meeting"]):
                # Календарные задачи - разделяем READ и WRITE операции
                create_keywords = ["создай", "назначь", "запланир", "добавь", "schedule", "create"]
                is_create_request = any(kw in goal_lower for kw in create_keywords)
                
                if is_create_request:
                    # Создание встречи
                    preferred_tools = ["schedule_group_meeting", "create_event"]
                else:
                    # Просмотр встреч (по умолчанию) - get_calendar_events ПЕРВЫМ
                    preferred_tools = ["get_calendar_events"]
                    
                    # Извлекаем временной период из запроса для аргументов
                    if "следующ" in goal_lower and "недел" in goal_lower:
                        fallback_arguments = {"start_time": "на следующей неделе"}
                    elif "прошл" in goal_lower and "недел" in goal_lower:
                        fallback_arguments = {"start_time": "на прошлой неделе"}
                    elif "эт" in goal_lower and "недел" in goal_lower:
                        fallback_arguments = {"start_time": "на этой неделе"}
                    elif "недел" in goal_lower:
                        fallback_arguments = {"start_time": "на неделе"}
                    elif "завтра" in goal_lower:
                        fallback_arguments = {"start_time": "завтра"}
                    elif "сегодня" in goal_lower:
                        fallback_arguments = {"start_time": "сегодня"}
                
                for cap in self.capabilities:
                    if cap.name in preferred_tools:
                        fallback_tool = cap
                        break
            elif any(kw in goal_lower for kw in ["документ", "doc", "текст"]):
                # Документы
                for cap in self.capabilities:
                    if cap.name in ["read_document", "create_document"]:
                        fallback_tool = cap
                        break
            
            # Если не нашли специфичный, используем первый доступный
            if not fallback_tool and self.capabilities:
                fallback_tool = self.capabilities[0]
            
            if fallback_tool:
                fallback_plan = {
                    "tool_name": fallback_tool.name,
                    "arguments": fallback_arguments,
                    "description": f"Выполняю {fallback_tool.name}",
                    "reasoning": f"Выполняю действие для достижения цели"
                }
            else:
                fallback_plan = {
                    "tool_name": "error",
                    "arguments": {},
                    "description": "Ошибка планирования: нет доступных инструментов",
                    "reasoning": str(e)
                }
            
            return fallback_thought, fallback_plan
    
    async def _execute_orchestrated(
        self,
        goal: str,
        decomposition: DecompositionResult,
        execution_plan: ExecutionPlan,
        context: ConversationContext,
        file_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Execute orchestrated (parallel) execution for multi-tool queries (Phase 2, Step 3).
        
        Args:
            goal: Original user query
            decomposition: DecompositionResult from TaskDecomposer
            execution_plan: ExecutionPlan from DependencyAnalyzer
            context: Conversation context
            file_ids: Optional file IDs
            
        Returns:
            Execution result
        """
        # Execute by groups
        all_results = {}
        errors = {}
        
        for group_idx, group in enumerate(execution_plan.execution_groups):
            group_subtasks = [st for st in decomposition.subtasks if st.task_id in group]
            
            try:
                if execution_plan.group_types[group_idx] == "parallel":
                    # Parallel execution
                    results = await self._execute_parallel_subtasks(group_subtasks, context)
                    # Filter out errors from results
                    for task_id, result in results.items():
                        if isinstance(result, dict) and "error" in result:
                            errors[task_id] = result["error"]
                        else:
                            # PHASE 0 FIX: Extract final_result from execution_result dict for synthesis
                            # synthesis_agent expects actual tool results, not full execution_result dict
                            if isinstance(result, dict) and "final_result" in result:
                                # Extract final_result which contains actual tool data
                                all_results[task_id] = result.get("final_result", result)
                            else:
                                all_results[task_id] = result
                else:
                    # Sequential execution (for dependencies)
                    # CRITICAL: Skip source tracking for orchestrated tasks to prevent old card UI
                    for subtask in group_subtasks:
                        try:
                            result = await self._execute_single_subtask(subtask, context, skip_source_tracking=True)
                            all_results[subtask.task_id] = result
                        except Exception as e:
                            logger.error(f"[UnifiedReActEngine] Subtask {subtask.task_id} failed: {e}")
                            errors[subtask.task_id] = str(e)
                            all_results[subtask.task_id] = {"error": str(e)}
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Group {group_idx} execution failed: {e}", exc_info=True)
                # Mark all subtasks in group as failed
                for subtask in group_subtasks:
                    errors[subtask.task_id] = str(e)
                    all_results[subtask.task_id] = {"error": str(e)}
        
        # Find synthesis task and generate final result using SynthesisAgent
        synthesis_task = next((st for st in decomposition.subtasks if st.is_synthesis), None)
        
        if synthesis_task:
            # Phase 2, Step 4: Use SynthesisAgent to synthesize results with streaming
            try:
                # Filter out error results for synthesis (but keep them for reporting)
                successful_results = {k: v for k, v in all_results.items() if not (isinstance(v, dict) and "error" in v)}
                
                if successful_results:
                    # Send "Готовлю результат..." block (final_result_start)
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_start",
                        {}
                    )
                    
                    # Stream synthesis result
                    summary = await self.synthesis_agent.synthesize_streaming(
                        query=goal,
                        subtask_results=successful_results,
                        original_query=goal,
                        ws_manager=self.ws_manager,
                        session_id=self.session_id
                    )
                    
                    # Extract key points from summary
                    from src.core.synthesis_agent import SynthesisAgent
                    key_points = self.synthesis_agent._extract_key_points(summary)
                    
                    # Include error information if any
                    if errors:
                        error_summary = f"\n\nОшибки: {len(errors)} задач завершились с ошибками."
                        summary += error_summary
                        # Send error chunk
                        await self.ws_manager.send_event(
                            self.session_id,
                            "final_result_chunk",
                            {"chunk": error_summary}
                        )
                    
                    # Send final_result_complete (with or without errors)
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_complete",
                        {
                            "content": summary,
                            "key_points": key_points or [],
                            "errors": errors if errors else None,
                            "status": "success" if not errors else "partial_success"
                        }
                    )
                    
                    return {
                        "agent": self.__class__.__name__,
                        "response": summary,
                        "status": "success" if not errors else "partial_success",
                        "orchestration_used": True,
                        "parallel_tasks": len([st for st in decomposition.subtasks if not st.dependencies and not st.is_synthesis]),
                        "synthesis_used": True,
                        "key_points": key_points,
                        "errors": errors if errors else None
                    }
                else:
                    # All tasks failed - use fallback
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_start",
                        {}
                    )
                    await self.ws_manager.send_event(
                        self.session_id,
                        "final_result_complete",
                        {"content": "Не удалось выполнить задачи. Проверьте подключение к сервисам."}
                    )
                    return {
                        "agent": self.__class__.__name__,
                        "response": "Не удалось выполнить задачи. Проверьте подключение к сервисам.",
                        "status": "failed",
                        "orchestration_used": True,
                        "synthesis_used": True,
                        "errors": errors if errors else None
                    }
            except Exception as e:
                logger.error(f"[UnifiedReActEngine] Synthesis failed: {e}", exc_info=True)
                # Fallback to simple aggregation
                summary = f"Выполнено {len([r for r in all_results.values() if not (isinstance(r, dict) and 'error' in r)])} из {len(all_results)} задач"
                if errors:
                    summary += f". Ошибки: {len(errors)} задач."
                
                # Send fallback result
                await self.ws_manager.send_event(
                    self.session_id,
                    "final_result_start",
                    {}
                )
                await self.ws_manager.send_event(
                    self.session_id,
                    "final_result_complete",
                    {"content": summary}
                )
                
                return {
                    "agent": self.__class__.__name__,
                    "response": summary,
                    "status": "partial_success" if errors else "success",
                    "orchestration_used": True,
                    "errors": errors if errors else None
                }
        else:
            # No synthesis task - return combined results
            return {
                "agent": self.__class__.__name__,
                "response": "Задачи выполнены",
                "status": "success",
                "orchestration_used": True,
                "results": all_results
            }
    
    async def _execute_parallel_subtasks(
        self,
        subtasks: List[SubTask],
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Execute subtasks in parallel using asyncio.gather (Phase 2, Step 3).
        
        Args:
            subtasks: List of subtasks to execute in parallel
            context: Conversation context
            
        Returns:
            Dictionary mapping task_id to result
        """
        # CRITICAL: Save main intent_id BEFORE starting parallel branches
        # This is the parent intent where all parallel branches belong
        main_intent_id = self._current_intent_id
        logger.info(f"[UnifiedReActEngine] Parallel execution: main_intent_id={main_intent_id}, branches={[st.task_id for st in subtasks]}")
        
        # #region agent log
        import json as _debug_json_parallel; import time as _debug_time_parallel
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_parallel:
                _debug_f_parallel.write(_debug_json_parallel.dumps({"id":f"log_{int(_debug_time_parallel.time()*1000)}_parallel_start","timestamp":int(_debug_time_parallel.time()*1000),"location":"unified_react_engine.py:5532","message":"Starting parallel execution","data":{"main_intent_id":main_intent_id,"branches":[{"task_id":st.task_id,"description":st.description,"tool_name":st.tool_name} for st in subtasks]},"sessionId":"debug-session","runId":"run1","hypothesisId":"F"}) + '\n')
        except:
            pass
        # #endregion
        
        # CRITICAL: Store main_intent_id in context ONCE before all parallel branches start
        # This ensures all branches use the same main_intent_id (no race condition)
        context._parallel_main_intent_id = main_intent_id
        
        # CRITICAL: Send parallel_branch_start events FIRST for new UI (ParallelExecutionContainer)
        # Then track sources for source cards (existing UI)
        
        # Send parallel_branch_start for each subtask (for new ParallelExecutionContainer UI)
        branch_start_tasks = []
        for subtask in subtasks:
            branch_start_tasks.append(
                self.ws_manager.send_event(
                    self.session_id,
                    "parallel_branch_start",
                    {
                        "intent_id": main_intent_id,  # Use saved main_intent_id (NOT self._current_intent_id which changes)
                        "branch_id": subtask.task_id,
                        "description": subtask.description,
                        "tool_name": subtask.tool_name
                    }
                )
            )
        
        # Send all branch_start events in parallel
        await asyncio.gather(*branch_start_tasks)
        
        # CRITICAL: DO NOT track sources for parallel subtasks - they break tab UI with old card mode
        # Parallel branches are tracked through parallel_branch_start/complete events, not source_loading
        # Sources (SourceCard) are an old UI mode that should never appear for parallel execution
        source_ids = {}
        # Skip track_source for all parallel subtasks - use empty source_ids
        logger.info(f"[UnifiedReActEngine] Skipping track_source for {len(subtasks)} parallel subtasks - using tab UI instead of old card mode")
        
        # Create wrapper functions that send events immediately after each task completes
        async def execute_and_send_complete(subtask, source_id):
            """Execute subtask and send parallel_branch_complete event immediately upon completion."""
            task_start_time = time.time()
            try:
                result = await self._execute_single_subtask_with_source_id(
                    subtask, 
                    context, 
                    source_id,
                    main_intent_id  # Pass main_intent_id to each subtask
                )
                task_duration = time.time() - task_start_time
                
                # Extract brief result summary for display in tab
                # Use smart summary instead of full result to avoid clutter
                result_summary = self._get_smart_result_summary(subtask, result)
                
                # CRITICAL: Send parallel_branch_complete IMMEDIATELY after task completion
                # This allows UI to update tab status and show result right away
                await self.ws_manager.send_event(
                    self.session_id,
                    "parallel_branch_complete",
                    {
                        "intent_id": main_intent_id,  # Use saved main_intent_id
                        "branch_id": subtask.task_id,
                        "status": "completed",
                        "duration_sec": task_duration,  # Use actual task duration, not total parallel duration
                        "result_summary": result_summary  # Brief result for display in tab
                    }
                )
                
                return result
            except Exception as e:
                task_duration = time.time() - task_start_time
                logger.error(f"[UnifiedReActEngine] Subtask {subtask.task_id} failed: {e}")
                
                # Send parallel_branch_complete with error IMMEDIATELY
                await self.ws_manager.send_event(
                    self.session_id,
                    "parallel_branch_complete",
                    {
                        "intent_id": main_intent_id,  # Use saved main_intent_id
                        "branch_id": subtask.task_id,
                        "status": "failed",
                        "duration_sec": task_duration,
                        "error": str(e)
                    }
                )
                
                raise  # Re-raise to be caught by asyncio.gather
        
        # Create coroutines for each subtask execution with immediate event sending
        # CRITICAL: Pass None for source_id since we don't track sources for parallel subtasks
        tasks = []
        for subtask in subtasks:
            tasks.append(execute_and_send_complete(
                subtask,
                None  # No source tracking for parallel subtasks - use tab UI instead
            ))
        
        # Execute in parallel - events are sent immediately as each task completes
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results (events already sent)
        result_dict = {}
        for subtask, result in zip(subtasks, results):
            if isinstance(result, Exception):
                result_dict[subtask.task_id] = {"error": str(result)}
            else:
                result_dict[subtask.task_id] = result
        
        return result_dict
    
    async def _execute_single_subtask(
        self,
        subtask: SubTask,
        context: ConversationContext,
        skip_source_tracking: bool = False  # Skip source tracking for orchestrated tasks (prevents old card UI)
    ) -> Any:
        """
        Execute a single subtask with source tracking (Phase 2, Step 3).
        
        NOTE: For parallel execution, use _execute_single_subtask_with_source_id
        after tracking sources in parallel.
        
        Args:
            subtask: SubTask to execute
            context: Conversation context
            skip_source_tracking: If True, skip source tracking (for orchestrated tasks to prevent old card UI)
            
        Returns:
            Execution result
        """
        # Track source first (for sequential execution), but skip for orchestrated tasks
        source_id = None
        if not skip_source_tracking:
            source_name = self._get_source_name(subtask.tool_name)
            source_id = await self.source_tracker.track_source(
                source_name=source_name,
                tool_name=subtask.tool_name,
                preview_data=subtask.description,
                intent_id=self._current_intent_id
            )
        else:
            logger.debug(f"[UnifiedReActEngine] Skipping track_source for orchestrated subtask {subtask.task_id} to prevent old card UI")
        
        return await self._execute_single_subtask_with_source_id(subtask, context, source_id, self._task_intent_id)
    
    async def _execute_single_subtask_with_source_id(
        self,
        subtask: SubTask,
        context: ConversationContext,
        source_id: Optional[str],  # None for parallel subtasks (no source tracking)
        main_intent_id: str  # CRITICAL: Parent intent_id for parallel branches
    ) -> Any:
        """
        Execute a single subtask with pre-tracked source (Phase 2, Step 3).
        
        Args:
            subtask: SubTask to execute
            context: Conversation context
            source_id: Pre-tracked source ID (from parallel track_source)
            
        Returns:
            Execution result
        """
        try:
            # Transform arguments if needed (e.g., legacy format -> new format)
            arguments = subtask.arguments.copy() if subtask.arguments else {}
            
            # Handle create_presentation_batch: if arguments have "topic"/"query" instead of "title"/"slides"
            if subtask.tool_name == "create_presentation_batch":
                # Legacy format: {"topic": "...", "query": "..."} -> convert to {"title": "...", "slides": [...]}
                if "topic" in arguments and "title" not in arguments:
                    topic = arguments.get("topic", "презентацию")
                    query_for_context = arguments.get("query", "")
                    title = f"Презентация про {topic}"
                    arguments = {
                        "title": title,
                        "slides": [],  # Will be filled below if empty
                        "query": query_for_context  # Keep query for context
                    }
                
                # CRITICAL: If slides array is empty, generate a basic slide with title
                # MCP server requires at least one slide
                slides = arguments.get("slides", [])
                if not slides or len(slides) == 0:
                    title = arguments.get("title", "Презентация")
                    # Extract topic from title if possible (e.g., "Презентация про собак" -> "собак")
                    topic_text = title
                    if "про " in title.lower():
                        topic_text = title.lower().split("про ", 1)[-1].strip()
                    elif "about " in title.lower():
                        topic_text = title.lower().split("about ", 1)[-1].strip()
                    
                    # Create a basic introductory slide
                    basic_slide = {
                        "title": title,
                        "content": f"Презентация о {topic_text}",
                        "layout": "TITLE_AND_BODY"
                    }
                    arguments["slides"] = [basic_slide]
            
            # CRITICAL: Execute through full ReAct cycle instead of direct registry.execute
            # This ensures LLM generates content (e.g., slides for presentations, query for emails)
            # Save current intent_id and task_intent_id to restore after subtask execution
            saved_intent_id = self._current_intent_id
            saved_task_intent_id = self._task_intent_id
            # CRITICAL FIX: main_intent_id is already stored in context._parallel_main_intent_id
            # by _execute_parallel_subtasks BEFORE all branches start (no race condition)
            # DO NOT overwrite it here - it's already set correctly for all parallel branches
            # context._parallel_main_intent_id = main_intent_id  # REMOVED - already set in _execute_parallel_subtasks
            # CRITICAL: Mark this as a parallel subtask BEFORE execute() call
            # This flag is used to skip final_result/message_complete for subtasks
            self._is_parallel_subtask = True
            
            # #region agent log
            import json as _debug_json_subtask; import time as _debug_time_subtask
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_subtask:
                    _debug_f_subtask.write(_debug_json_subtask.dumps({"id":f"log_{int(_debug_time_subtask.time()*1000)}_subtask_execute","timestamp":int(_debug_time_subtask.time()*1000),"location":"unified_react_engine.py:5748","message":"Executing parallel subtask","data":{"subtask_id":subtask.task_id,"subtask_description":subtask.description,"use_existing_intent_id":subtask.task_id,"main_intent_id_from_context":getattr(context, '_parallel_main_intent_id', None),"main_intent_id_param":main_intent_id},"sessionId":"debug-session","runId":"run1","hypothesisId":"F"}) + '\n')
            except:
                pass
            # #endregion
            
            try:
                # Execute through full ReAct cycle with skip_orchestration=True to avoid recursion
                # Use subtask.task_id as intent_id (matches parallel_branch_start event)
                execution_result = await self.execute(
                    goal=subtask.description,
                    context=context,
                    file_ids=None,
                    phase=None,
                    skip_orchestration=True,  # Don't try to decompose subtasks again
                    use_existing_intent_id=subtask.task_id  # Use branch intent_id from parallel_branch_start
                )
                
                # Extract result from execution_result dict
                if isinstance(execution_result, dict):
                    result = execution_result.get("response", execution_result)
                else:
                    result = execution_result
            finally:
                # Restore original intent_id and task_intent_id
                self._current_intent_id = saved_intent_id
                self._task_intent_id = saved_task_intent_id
                # Note: _saved_main_intent_id is NOT cleared here to avoid race conditions
                # It will be naturally overwritten by the next parallel subtask if any
            
            # Update source as completed (skip for parallel subtasks - no source tracking)
            if source_id:
                await self.source_tracker.update_source_complete(
                    source_id=source_id,
                    result=result,
                    intent_id=saved_intent_id  # Use saved intent_id (main task intent)
                )
            else:
                logger.debug(f"[UnifiedReActEngine] Skipping update_source_complete for parallel subtask (no source_id)")
            
            return result
        except Exception as e:
            # Update source as error (skip for parallel subtasks - no source tracking)
            if source_id:
                await self.source_tracker.update_source_error(
                    source_id=source_id,
                    error=str(e),
                    intent_id=self._current_intent_id
                )
            else:
                logger.debug(f"[UnifiedReActEngine] Skipping update_source_error for parallel subtask (no source_id)")
            raise
    
    async def _execute_action(
        self,
        action_plan: Dict[str, Any],
        context: ConversationContext,
        state: Optional[ReActState] = None
    ) -> Any:
        """Execute action through CapabilityRegistry (provider-agnostic).
        
        Args:
            action_plan: Action plan with tool_name and arguments
            context: Conversation context
            state: ReActState for access to observations (for auto-fix functionality)
                   If None, uses self._current_state as fallback (for backward compatibility)
        """
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
            
            # Для операций используем intent, который содержит текущую итерацию
            # iteration_intent_id - это тот intent, который используется для iteration_start (см. строку 609)
            iteration_intent_id = getattr(self, '_task_intent_id', None) or getattr(self, '_current_intent_id', None)
            
            # Но! Если была смена фазы и _task_intent_id обновился, 
            # то текущая итерация может быть в СТАРОМ intent
            # Поэтому для операций берём intent, который использовался для последнего iteration_start
            # Это сохраняется в _iteration_intent_id
            intent_id = getattr(self, '_iteration_intent_id', None) or iteration_intent_id
            
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
                
                # Docs - создание
                'create_document': {
                    'title': 'Создаю документ',
                    'streaming_title': 'Новый документ',
                    'operation_type': 'write',
                    'file_type': 'docs'
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
                
                # Slides - создание
                'create_presentation': {
                    'title': 'Создаю презентацию',
                    'streaming_title': 'Новая презентация',
                    'operation_type': 'write',
                    'file_type': 'slides'
                },
                
                # Slides - чтение
                'get_presentation': {
                    'title': 'Получаю информацию о презентации',
                    'streaming_title': 'Слайды презентации',
                    'operation_type': 'read',
                    'file_type': 'slides'
                },
                
                # Slides - добавление слайда
                'create_slide': {
                    'title': 'Добавляю слайд',
                    'streaming_title': 'Новый слайд',
                    'operation_type': 'write',
                    'file_type': 'slides'
                },
                
                # Slides - вставка текста
                'insert_slide_text': {
                    'title': 'Добавляю текст на слайд',
                    'streaming_title': 'Текст слайда',
                    'operation_type': 'write',
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
                
                # Python code execution - стриминг кода
                'execute_python_code': {
                    'title': 'Пишу код анализа...',
                    'streaming_title': 'Код Python',
                    'operation_type': 'write',
                    'file_type': 'code'
                },
                
                # Slides - создание презентации
                'create_presentation_batch': {
                    'title': 'Создаю презентацию...',
                    'streaming_title': 'Презентация',
                    'operation_type': 'write',
                    'file_type': 'slides'
                },
            }
            if capability_name in tools_with_operations:
                # Для execute_python_code проверяем, не создан ли уже operation_id в парсере
                if capability_name == 'execute_python_code' and hasattr(self, '_execute_python_code_operation_id'):
                    operation_id = self._execute_python_code_operation_id
                    # Удаляем временный атрибут после использования
                    delattr(self, '_execute_python_code_operation_id')
                    # Не отправляем operation_start - он уже отправлен из парсера
                    skip_operation_start = True
                else:
                    operation_id = f"op-{int(time.time() * 1000)}"
                    skip_operation_start = False
                
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
                
                # Отправляем operation_start только если он еще не отправлен (из парсера)
                if not skip_operation_start:
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
                
                # === Python code execution: код уже стримлен в реальном времени через _handle_code_streaming ===
                # Код отображается в правой панели (code viewer) во время генерации токенов
                # Старый построчный стриминг удален, так как код уже стримлен
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
        
        # Auto-fix: для sheets tools автоматически подставляем spreadsheet_id из open_files
        sheets_tools = ['get_all_sheets_data', 'get_sheet_data', 'add_rows', 'update_cells', 
                        'sheets_read_range', 'sheets_write_range']
        if capability_name in sheets_tools:
            if 'spreadsheet_id' not in arguments or not arguments.get('spreadsheet_id'):
                # Пытаемся найти spreadsheet_id из открытых файлов
                open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
                
                for file in open_files:
                    if file.get('type') == 'sheets':
                        spreadsheet_id = file.get('spreadsheet_id') or file.get('spreadsheetId')
                        # Извлекаем из URL если нет в данных
                        if not spreadsheet_id and file.get('url'):
                            url_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', file.get('url', ''))
                            if url_match:
                                spreadsheet_id = url_match.group(1)
                        if spreadsheet_id:
                            arguments['spreadsheet_id'] = spreadsheet_id
                            logger.info(f"[Auto-fix] Added spreadsheet_id={spreadsheet_id} from open_files for {capability_name}")
                            break
        
        # Auto-fix: для execute_python_code автоматически передаём данные из get_all_sheets_data через input_data
        if capability_name == 'execute_python_code' and 'input_data' not in arguments:
            # Ищем результат get_all_sheets_data в предыдущих observations
            # CRITICAL FIX: Используем переданный state вместо self._current_state для изоляции параллельных веток
            current_state = state if state else getattr(self, '_current_state', None)
            if current_state and hasattr(current_state, 'observations'):
                for i, obs in enumerate(reversed(current_state.observations)):
                    if obs and hasattr(obs, 'raw_result'):
                        raw_result = obs.raw_result
                        # Проверяем, это результат get_all_sheets_data?
                        # Ищем в action_history соответствующий action
                        action_idx = len(current_state.observations) - 1 - i
                        if action_idx < len(current_state.action_history):
                            action = current_state.action_history[action_idx]
                            if action.tool_name == 'get_all_sheets_data':
                                parsed_data = None
                                
                                # raw_result может быть уже объектом или строкой
                                if isinstance(raw_result, dict):
                                    # Уже объект - проверяем наличие sheets
                                    if 'sheets' in raw_result:
                                        parsed_data = raw_result  # {"spreadsheetTitle": ..., "sheets": [...]}
                                    else:
                                        parsed_data = {"sheets": [raw_result]}
                                elif isinstance(raw_result, list):
                                    parsed_data = {"sheets": raw_result}
                                else:
                                    # Строка - пытаемся распарсить
                                    result_str = str(raw_result)
                                    try:
                                        import json
                                        # Tool может возвращать форматированную строку с JSON внутри
                                        # Формат: "Spreadsheet '...' contains N sheet(s):\n...\n\nFull data (JSON):\n{...}"
                                        json_marker = "Full data (JSON):\n"
                                        if json_marker in result_str:
                                            json_part = result_str.split(json_marker, 1)[1]
                                            parsed_result = json.loads(json_part)
                                            if isinstance(parsed_result, dict) and 'sheets' in parsed_result:
                                                parsed_data = parsed_result
                                        elif result_str.strip().startswith('{'):
                                            parsed_result = json.loads(result_str)
                                            if isinstance(parsed_result, dict):
                                                if 'sheets' in parsed_result:
                                                    parsed_data = parsed_result
                                                else:
                                                    parsed_data = {"sheets": [parsed_result]}
                                        elif result_str.strip().startswith('['):
                                            parsed_result = json.loads(result_str)
                                            if isinstance(parsed_result, list):
                                                parsed_data = {"sheets": parsed_result}
                                    except Exception:
                                        pass
                                
                                if parsed_data and parsed_data.get('sheets'):
                                    # Transform raw values to structured data with headers
                                    for sheet in parsed_data.get('sheets', []):
                                        values = sheet.get('values', [])
                                        if values and len(values) > 1:
                                            headers = values[0]
                                            rows_as_dicts = []
                                            for row in values[1:]:
                                                padded_row = row + [''] * (len(headers) - len(row))
                                                rows_as_dicts.append(dict(zip(headers, padded_row[:len(headers)])))
                                            sheet['rows'] = rows_as_dicts
                                            sheet['headers'] = headers
                                            sheet['data'] = rows_as_dicts
                                        elif values:
                                            sheet['headers'] = values[0] if values else []
                                            sheet['rows'] = []
                                            sheet['data'] = []
                                    arguments['input_data'] = parsed_data
                                
                                if 'input_data' in arguments:
                                    break
        
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
        
        # === Stream presentation structure BEFORE API call ===
        if capability_name == 'create_presentation_batch' and operation_id and self.ws_manager:
            import asyncio
            title = arguments.get('title', 'Презентация')
            slides = arguments.get('slides', [])
            theme = arguments.get('theme', 'professional')
            
            if slides:
                # Stream presentation structure
                await self.ws_manager.send_operation_data(
                    self.session_id,
                    operation_id,
                    f"📊 Создаю презентацию: {title}"
                )
                await asyncio.sleep(0.05)
                await self.ws_manager.send_operation_data(
                    self.session_id,
                    operation_id,
                    f"🎨 Тема: {theme}"
                )
                await asyncio.sleep(0.05)
                await self.ws_manager.send_operation_data(
                    self.session_id,
                    operation_id,
                    f"📑 Слайдов: {len(slides)}"
                )
                await asyncio.sleep(0.05)
                
                # Stream each slide structure
                for i, slide in enumerate(slides, 1):
                    slide_title = slide.get('title', f'Слайд {i}')
                    slide_content = slide.get('content', '')
                    
                    await self.ws_manager.send_operation_data(
                        self.session_id,
                        operation_id,
                        f"\n📄 Слайд {i}: {slide_title}"
                    )
                    await asyncio.sleep(0.05)
                    
                    # Stream content preview
                    if isinstance(slide_content, str):
                        if slide_content.strip():
                            preview = slide_content[:100] + ('...' if len(slide_content) > 100 else '')
                            await self.ws_manager.send_operation_data(
                                self.session_id,
                                operation_id,
                                f"   {preview}"
                            )
                            await asyncio.sleep(0.05)
                    elif isinstance(slide_content, list):
                        for item in slide_content[:3]:  # Показываем первые 3 пункта
                            if isinstance(item, dict):
                                item_text = item.get('text', '')
                                item_type = item.get('type', 'text')
                                prefix = "   • " if item_type == 'bullet' else "   " if item_type == 'subheading' else "   "
                                if item_text:
                                    preview = item_text[:80] + ('...' if len(item_text) > 80 else '')
                                    await self.ws_manager.send_operation_data(
                                        self.session_id,
                                        operation_id,
                                        f"{prefix}{preview}"
                                    )
                                    await asyncio.sleep(0.05)
                        if len(slide_content) > 3:
                            await self.ws_manager.send_operation_data(
                                self.session_id,
                                operation_id,
                                f"   ... и ещё {len(slide_content) - 3} пунктов"
                            )
                            await asyncio.sleep(0.05)
        
        # Registry routes to appropriate provider (MCP or A2A)
        try:
            result = await self.registry.execute(capability_name, arguments)
        except Exception as e:
            raise
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
            
            # Python code execution operations
            elif capability_name == 'execute_python_code':
                try:
                    # Code was already streamed before execution
                    # Now process results and send operation_end
                    result_str = str(result) if result else ""
                    
                    # Try to extract chartData from result and send to frontend
                    chart_data = None
                    result_data = None
                    try:
                        import json
                        import ast
                        # Result might be formatted as "Result:\n{...}" or just dict repr
                        # Python exec returns dict with single quotes, not JSON!
                        dict_str = ""
                        if result_str.strip().startswith("{"):
                            dict_str = result_str.strip()
                        elif "Result:" in result_str:
                            # Extract dict after "Result:"
                            json_start = result_str.find("{")
                            if json_start != -1:
                                json_end = result_str.rfind("}") + 1
                                if json_end > json_start:
                                    dict_str = result_str[json_start:json_end]
                        
                        if dict_str:
                            # Try ast.literal_eval first (handles Python dict repr)
                            try:
                                result_data = ast.literal_eval(dict_str)
                            except (ValueError, SyntaxError) as e1:
                                # Fallback to json.loads
                                try:
                                    result_data = json.loads(dict_str)
                                except json.JSONDecodeError as e2:
                                    # Log parsing error
                                    logger.warning(f"[UnifiedReActEngine] Failed to parse chartData. ast error: {e1}, json error: {e2}, dict_str[:100]: {dict_str[:100]}")
                        
                        if result_data and isinstance(result_data, dict) and "chartData" in result_data:
                            chart_data = result_data["chartData"]
                    except Exception as e:
                        pass
                    
                    # Send chart_dashboard event if we have chartData
                    if chart_data and isinstance(chart_data, list) and len(chart_data) > 0:
                        await self.ws_manager.send_event(
                            self.session_id,
                            "chart_dashboard",
                            {
                                "title": "Анализ данных",
                                "charts": chart_data
                            }
                        )
                        logger.info(f"[UnifiedReActEngine] Sent chart_dashboard event with {len(chart_data)} chart(s)")
                    else:
                        logger.warning(f"[UnifiedReActEngine] No chartData found in result. Result preview: {result_str[:200]}")
                    
                    # Send operation_end with summary
                    summary = "Код выполнен успешно"
                    if chart_data:
                        summary = f"Код выполнен, создано {len(chart_data)} диаграмм"
                    
                    await self.ws_manager.send_operation_end(
                        self.session_id,
                        operation_id,
                        summary
                    )
                except Exception as e:
                    logger.warning(f"[UnifiedReActEngine] Failed to process code execution operation: {e}", exc_info=True)
                    await self.ws_manager.send_operation_end(
                        self.session_id,
                        operation_id,
                        "Код выполнен"
                    )
            
            # Sheets operations
            elif capability_name in ['get_sheet_data', 'get_all_sheets_data', 'add_rows', 'update_cells']:
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
            elif capability_name in ['create_document', 'read_document', 'update_document', 'append_to_document', 'insert_into_document']:
                try:
                    # For create_document, extract title and send file_preview
                    if capability_name == 'create_document':
                        # Extract document_id and title from result
                        result_str = str(result)
                        
                        # Try multiple patterns for document_id
                        doc_id_match = re.search(r'ID: ([a-zA-Z0-9-_]+)', result_str) or re.search(r'\(ID: ([a-zA-Z0-9-_]+)\)', result_str)
                        # Try multiple patterns for title
                        title_match = re.search(r"'([^']+)' created successfully", result_str) or re.search(r'Document \'([^\']+)\' created', result_str)
                        
                        if doc_id_match and title_match:
                            document_id = doc_id_match.group(1)
                            document_title = title_match.group(1)
                            
                            # Extract URL if present
                            url_match = re.search(r'URL: (https?://[^\s]+)', result_str)
                            document_url = url_match.group(1) if url_match else f"https://docs.google.com/document/d/{document_id}/edit"
                            
                            # Send file_preview event for frontend to open tab
                            await self.ws_manager.send_event(
                                self.session_id,
                                "file_preview",
                                {
                                    "file_type": "docs",
                                    "file_id": document_id,
                                    "file_url": document_url,
                                    "streaming_title": document_title,
                                    "title": document_title
                                }
                            )
                        
                        summary = "✓ Документ создан"
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                    # For write operations, content was already streamed BEFORE MCP call
                    # Only stream for read operations here
                    elif capability_name == 'read_document':
                        items, summary = await self._parse_docs_result(str(result), capability_name, arguments)
                        # Save document text for smart bold formatting
                        if items:
                            self._last_document_text = "\n".join(items)
                            import asyncio
                            for item in items:
                                await self.ws_manager.send_operation_data(
                                    self.session_id,
                                    operation_id,
                                    item
                                )
                                # Small delay for visual streaming effect (50ms per line)
                                await asyncio.sleep(0.05)
                        if summary:
                            await self.ws_manager.send_operation_end(
                                self.session_id,
                                operation_id,
                                summary
                            )
                    else:
                        # For other write operations, just get the summary
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
            elif capability_name in ['create_presentation', 'create_presentation_batch', 'create_presentation_from_doc', 'get_presentation']:
                try:
                    if capability_name in ['create_presentation', 'create_presentation_batch', 'create_presentation_from_doc']:
                        # Extract presentation_id and title from result for auto-opening
                        result_str = str(result)
                        
                        # Try multiple patterns for presentation_id
                        pres_id_match = (
                            re.search(r'presentation_id["\']?\s*[:=]\s*["\']?([a-zA-Z0-9-_]+)', result_str) or
                            re.search(r'presentationId["\']?\s*[:=]\s*["\']?([a-zA-Z0-9-_]+)', result_str) or
                            re.search(r'ID:\s*([a-zA-Z0-9-_]+)', result_str) or
                            re.search(r'\(ID:\s*([a-zA-Z0-9-_]+)\)', result_str)
                        )
                        
                        # Try multiple patterns for title
                        title_match = (
                            re.search(r"title[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", result_str) or
                            re.search(r"'([^']+)'\s*created", result_str) or
                            re.search(r'Presentation\s*["\']([^"\']+)["\']', result_str)
                        )
                        
                        if pres_id_match:
                            presentation_id = pres_id_match.group(1)
                            presentation_title = title_match.group(1) if title_match else arguments.get('title', 'Презентация')
                            
                            # Extract URL if present
                            url_match = re.search(r'url["\']?\s*[:=]\s*["\']?(https?://[^\s"\']+)', result_str, re.IGNORECASE)
                            presentation_url = url_match.group(1) if url_match else f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                            
                            # Send slides_action event for frontend to open tab in right panel
                            await self.ws_manager.send_event(
                                self.session_id,
                                "slides_action",
                                {
                                    "action": "create",
                                    "presentation_id": presentation_id,
                                    "presentation_url": presentation_url,
                                    "title": presentation_title,
                                    "description": f"Создана презентация '{presentation_title}'"
                                }
                            )
                            
                            # Send file_preview event for frontend to open tab
                            await self.ws_manager.send_event(
                                self.session_id,
                                "file_preview",
                                {
                                    "file_type": "slides",
                                    "file_id": presentation_id,
                                    "file_url": presentation_url,
                                    "streaming_title": presentation_title,
                                    "title": presentation_title
                                }
                            )
                            
                            summary = "✓ Презентация создана"
                        await self.ws_manager.send_operation_end(
                            self.session_id,
                            operation_id,
                            summary
                        )
                    elif capability_name == 'get_presentation':
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
            # КРИТИЧНО: Для конкретных запросов используем только нужные файлы
            file_contents_text = ""
            
            # #region agent log - проверка file_ids в _generate_final_answer
            import json as _debug_json_final; import time as _debug_time_final
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_final:
                    _debug_f_final.write(_debug_json_final.dumps({
                        "id": f"log_{int(_debug_time_final.time()*1000)}_generate_final_answer_start",
                        "timestamp": int(_debug_time_final.time()*1000),
                        "location": "unified_react_engine.py:8030",
                        "message": "_generate_final_answer: file_ids check",
                        "data": {
                            "goal": state.goal,
                            "file_ids": file_ids,
                            "file_ids_count": len(file_ids) if file_ids else 0,
                            "all_files_count": len(context.uploaded_files) if context and hasattr(context, 'uploaded_files') else 0
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "FILE_SELECTION"
                    }, ensure_ascii=False) + '\n')
            except:
                pass
            # #endregion
            
            # Определяем, является ли запрос конкретным
            is_specific_query = False
            if context:
                is_specific_query = self._is_specific_file_query(state.goal, context, file_ids or [])
                
                # #region agent log - результат проверки конкретности запроса
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_final:
                        _debug_f_final.write(_debug_json_final.dumps({
                            "id": f"log_{int(_debug_time_final.time()*1000)}_is_specific_query",
                            "timestamp": int(_debug_time_final.time()*1000),
                            "location": "unified_react_engine.py:8045",
                            "message": "_generate_final_answer: is_specific_query",
                            "data": {
                                "goal": state.goal,
                                "is_specific_query": is_specific_query,
                                "file_ids": file_ids
                            },
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "FILE_SELECTION"
                        }, ensure_ascii=False) + '\n')
                except:
                    pass
                # #endregion
                
                # Если запрос конкретный, но file_ids содержит все файлы - фильтруем
                if is_specific_query and file_ids and context and hasattr(context, 'uploaded_files'):
                    all_file_ids = set(context.uploaded_files.keys())
                    provided_file_ids = set(file_ids)
                    
                    # Если переданы все файлы, но запрос конкретный - нужно найти нужные файлы
                    if provided_file_ids == all_file_ids:
                        # Ищем файлы по упоминаниям в запросе
                        goal_lower = state.goal.lower()
                        relevant_file_ids = []
                        
                        for file_id, file_data in context.uploaded_files.items():
                            filename = file_data.get('filename', '')
                            if filename:
                                filename_base = filename.rsplit('.', 1)[0].lower()
                                if filename_base in goal_lower or filename.lower() in goal_lower:
                                    relevant_file_ids.append(file_id)
                        
                        # Ищем по описаниям из истории
                        if not relevant_file_ids:
                            file_summaries = self._get_file_summaries_from_history(context)
                            for file_id, description in file_summaries.items():
                                desc_words = set(description.lower().split()[:5])
                                goal_words = set(goal_lower.split())
                                if desc_words & goal_words:
                                    relevant_file_ids.append(file_id)
                        
                        # Если нашли релевантные файлы - используем только их
                        if relevant_file_ids:
                            file_ids = relevant_file_ids
                            # #region agent log - фильтрация file_ids
                            try:
                                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_final:
                                    _debug_f_final.write(_debug_json_final.dumps({
                                        "id": f"log_{int(_debug_time_final.time()*1000)}_filtered_file_ids",
                                        "timestamp": int(_debug_time_final.time()*1000),
                                        "location": "unified_react_engine.py:8080",
                                        "message": "_generate_final_answer: filtered file_ids",
                                        "data": {
                                            "goal": state.goal,
                                            "original_file_ids": list(provided_file_ids),
                                            "filtered_file_ids": file_ids,
                                            "reason": "specific query but all files provided"
                                        },
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "FILE_SELECTION"
                                    }, ensure_ascii=False) + '\n')
                            except:
                                pass
                            # #endregion
            
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

После таблицы добавь примечание (только если НЕ в режиме агент):
"💡 Если нужно создать Google таблицу с этими данными, используйте инструменты для работы с таблицами."
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
                # КРИТИЧНО: Для конкретных запросов - описываем только нужные файлы
                if is_specific_query:
                    prompt = f"""Пользователь спросил: "{state.goal}"

Вот содержимое прикрепленных файлов:
{file_contents_text}

{table_instruction}
ВАЖНО: Опиши КОНКРЕТНО что находится в прикрепленных файлах:
- Для PDF/Word: кратко опиши содержание документа
- Для изображения: опиши что на нём изображено
Если на изображении есть люди - опиши что они делают и в каком контексте.
НЕ отказывайся отвечать на вопросы о людях на изображении - описывай общими словами!

ОТВЕТЬ ТОЛЬКО ПО ПРИКРЕПЛЕННЫМ ФАЙЛАМ ВЫШЕ (не по всем файлам сессии)!

Ответ:"""
                else:
                    # Общий запрос - описываем все файлы
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
                # PHASE 0 FIX: Disable intent_start events
                # await self.ws_manager.send_event(
                #     self.session_id,
                #     "intent_start",
                #     {"intent_id": intent_id, "text": intent_message}
                # )
            
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
            # PHASE 0 FIX: Disable intent_complete events
            # await self.ws_manager.send_event(
            #     self.session_id,
            #     "intent_complete",
            #     {"intent_id": intent_id, "summary": "Анализ завершён"}
            # )
            
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
        file_ids: Optional[List[str]] = None,
        is_parallel_subtask: bool = False  # CRITICAL: passed from execute() to skip final_result for subtasks
    ) -> Dict[str, Any]:
        """Finalize successful execution."""
        state.status = "done"
        
        # === NEW ARCHITECTURE: Complete the task-level intent ===
        # PHASE 0 FIX: Disable intent_complete events
        # task_intent_id = getattr(self, '_task_intent_id', None)
        # if task_intent_id and self.ws_manager and self.session_id:
        #     await self.ws_manager.send_event(
        #         self.session_id,
        #         "intent_complete",
        #         {
        #             "intent_id": task_intent_id,
        #             "summary": f"✅ Задача выполнена за {state.iteration} шаг(ов)",
        #             "auto_collapse": False  # Keep expanded to show result
        #         }
        #     )
        
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
                                "working_hours_start": action.arguments.get("working_hours_start"),  # Сохраняем для повторного использования
                                "working_hours_end": action.arguments.get("working_hours_end"),
                                "original_goal": state.goal  # Save original goal for ReAct
                            }
                        }
                        logger.info(f"[UnifiedReActEngine] Saved pending confirmation: slot_start={slot_start}, description={description[:50] if description else None}")
                    break
        elif is_parallel_subtask:
            # CRITICAL: For parallel subtasks, DON'T call _generate_final_answer
            # It sends final_result_start/chunk/complete events that overwrite tabs in UI
            # PHASE 0 FIX: Include actual tool result instead of just brief summary
            # This preserves tool data for synthesis step later
            if state.observations:
                last_obs = state.observations[-1]
                # Include actual result from tool, not just tool name
                if last_obs.raw_result:
                    result_str = str(last_obs.raw_result)
                    # Keep result but add tool name for context
                    human_answer = f"✓ {last_obs.action.tool_name}: {result_str}"
                else:
                    human_answer = f"✓ {last_obs.action.tool_name}: выполнено"
            else:
                human_answer = "✓ Выполнено"
            logger.info(f"[UnifiedReActEngine] Parallel subtask - skipping _generate_final_answer, using tool result")
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
        
        # CRITICAL: Skip sending react_complete and final_result for parallel subtasks
        # Their results will be aggregated by synthesis and shown in parallel tabs
        # react_complete on frontend sets finalResult, which overwrites tabs
        if is_parallel_subtask:
            logger.info(f"[UnifiedReActEngine] Skipping react_complete and final events for parallel subtask: {state.goal[:50]}")
            return result_summary
        
        # Send react_complete event (only for non-parallel tasks)
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
        # CRITICAL: Use is_parallel_subtask parameter (passed from execute()) - thread-safe for asyncio
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
        # PHASE 0 FIX: Disable intent_complete events
        # task_intent_id = getattr(self, '_task_intent_id', None)
        # if task_intent_id and self.ws_manager and self.session_id:
        #     error_msg = analysis.error_message or "Не удалось выполнить"
        #     await self.ws_manager.send_event(
        #         self.session_id,
        #         "intent_complete",
        #         {
        #             "intent_id": task_intent_id,
        #             "summary": f"❌ {error_msg[:50]}",
        #             "auto_collapse": False
        #         }
        #     )
        
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
        # PHASE 0 FIX: Disable intent_complete events
        # task_intent_id = getattr(self, '_task_intent_id', None)
        # if task_intent_id and self.ws_manager and self.session_id:
        #     await self.ws_manager.send_event(
        #         self.session_id,
        #         "intent_complete",
        #         {
        #             "intent_id": task_intent_id,
        #             "summary": f"⏱️ Достигнут лимит ({state.iteration} итераций)",
        #             "auto_collapse": False
        #         }
        #     )
        
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

