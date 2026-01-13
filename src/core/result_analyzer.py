"""
Result analyzer for ReAct orchestrator.
Analyzes action results to determine success, progress, and next steps.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic

from src.core.react_state import ActionRecord, Observation
from src.utils.config_loader import get_config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Analysis:
    """Result of analyzing an action's outcome."""
    is_success: bool
    is_goal_achieved: bool
    is_error: bool
    progress_toward_goal: float  # 0.0 to 1.0
    error_message: Optional[str] = None
    next_action_suggestion: Optional[str] = None
    confidence: float = 0.5  # Confidence in analysis
    extracted_data: Optional[Dict[str, Any]] = None


class ResultAnalyzer:
    """
    Analyzes results of actions to determine success, progress, and next steps.
    Uses LLM for intelligent analysis when needed.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize result analyzer.
        
        Args:
            model_name: Model name for LLM (optional, uses default from config)
        """
        self.model_name = model_name
        config = get_config()
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            api_key=config.anthropic_api_key,
            temperature=0.3
        )
        logger.info(f"[ResultAnalyzer] Initialized with model {model_name or 'default'}")
    
    async def analyze(
        self,
        action: ActionRecord,
        result: Any,
        goal: str,
        previous_observations: Optional[list] = None
    ) -> Analysis:
        """
        Analyze result of an action relative to the goal.
        
        Args:
            action: The action that was executed
            result: Raw result from action execution
            goal: Original goal
            previous_observations: Previous observations for context
            
        Returns:
            Analysis object with success status, progress, and suggestions
        """
        # Quick check for obvious success/failure
        quick_analysis = self._quick_analysis(result, action, goal)
        if quick_analysis:
            logger.info(f"[ResultAnalyzer] Quick analysis: success={quick_analysis.is_success}, error={quick_analysis.is_error}")
            return quick_analysis
        
        # Use LLM for deeper analysis
        logger.info(f"[ResultAnalyzer] Performing LLM analysis for action {action.tool_name}")
        return await self._llm_analyze(action, result, goal, previous_observations)
    
    def _quick_analysis(self, result: Any, action: ActionRecord, goal: Optional[str] = None) -> Optional[Analysis]:
        """
        Quick analysis without LLM for obvious cases.
        
        Args:
            result: Action result
            action: Action record
            goal: Original goal (for compound task detection)
            
        Returns:
            Analysis if quick check succeeded, None otherwise
        """
        result_str = str(result).lower()
        
        # Check for obvious errors
        error_indicators = [
            "error", "failed", "exception", "ошибка", "не удалось",
            "not found", "не найдено", "permission denied", "доступ запрещен"
        ]
        
        for indicator in error_indicators:
            if indicator in result_str:
                return Analysis(
                    is_success=False,
                    is_goal_achieved=False,
                    is_error=True,
                    progress_toward_goal=0.0,
                    error_message=f"Error detected: {indicator}",
                    confidence=0.9
                )
        
        # Check for obvious success
        success_indicators = [
            "success", "created", "updated", "sent", "успешно",
            "создано", "обновлено", "отправлено", "completed"
        ]
        
        # Strong success indicators that mean goal is fully achieved
        # NOTE: "created successfully" removed because creating a file/spreadsheet 
        # is usually an intermediate step, not the final goal.
        # Only final actions like sending emails or scheduling meetings should be here.
        goal_achieved_indicators = [
            "запланирована", "✅",
            "event id:", "событие создано", "встреча запланирована",
            "отправлено успешно", "sent successfully", "email sent"
        ]
        
        # Indicators that require user confirmation - treat as goal achieved
        # so agent stops and shows result to user for approval
        confirmation_required_indicators = [
            "создать встречу на это время?",  # Main confirmation prompt
            "создать встречу?", "создаю встречу?",
            "подтвердите", "требуется подтверждение",
            "удалить все", "удалить события?",
            "confirmed=true"
        ]
        
        # Check if user confirmation is needed - stop and show to user
        for indicator in confirmation_required_indicators:
            if indicator in result_str:
                return Analysis(
                    is_success=True,
                    is_goal_achieved=True,  # Stop here, show to user
                    is_error=False,
                    progress_toward_goal=0.9,  # Almost done, just need confirmation
                    next_action_suggestion="Ожидание подтверждения от пользователя",
                    confidence=0.95
                )
        
        # Tools that are typically intermediate steps - never mark as goal achieved
        intermediate_tools = [
            "create_spreadsheet", "create_document", "sheets_create_spreadsheet",
            "list_workspace_files", "search_workspace_files", "find_and_open_file",
            "read_document", "sheets_read_range", "sheets_write_range"
        ]
        
        # Tools that complete their goal when successful (content modification)
        # These tools modify content, so one successful execution = goal achieved
        goal_completing_tools = [
            "append_to_document", "insert_into_document", "update_document"
        ]
        
        # For goal-completing tools, successful execution means goal is achieved
        # BUT: check if goal has additional requirements (like formatting)
        if action.tool_name in goal_completing_tools:
            goal_lower = goal.lower() if goal else ""
            # Паттерны дополнительных требований (форматирование)
            format_keywords = ["форматир", "красиво", "оформи", "format", "выдели", "жирн"]
            has_additional_requirements = any(kw in goal_lower for kw in format_keywords)
            
            if "success" in result_str or "успешно" in result_str:
                # Если есть дополнительные требования (форматирование) - НЕ завершаем
                if has_additional_requirements:
                    return Analysis(
                        is_success=True,
                        is_goal_achieved=False,  # Ещё нужно форматирование!
                        is_error=False,
                        progress_toward_goal=0.5,  # Только половина пути
                        confidence=0.9,
                        next_action_suggestion="Контент добавлен, теперь нужно применить форматирование"
                    )
                
                return Analysis(
                    is_success=True,
                    is_goal_achieved=True,  # Content was modified successfully
                    is_error=False,
                    progress_toward_goal=1.0,
                    confidence=0.95
                )
        
        # Formatting tools - check if goal has multiple formatting requirements
        formatting_tools = ["format_document_text", "format_document_paragraph"]
        if action.tool_name in formatting_tools:
            goal_lower = goal.lower() if goal else ""
            # Patterns for different formatting types
            bold_keywords = ["жирн", "bold", "выдели"]
            align_keywords = ["выравнивани", "выровня", "отступ", "красная строка", "align", "indent", "paragraph", "абзац"]
            has_bold_requirement = any(kw in goal_lower for kw in bold_keywords)
            has_align_requirement = any(kw in goal_lower for kw in align_keywords) or "красиво" in goal_lower
            
            # If success and multiple formatting types needed, don't mark goal achieved yet
            if "success" in result_str or "successfully" in result_str:
                # If we did format_document_text (bold) but still need alignment
                if action.tool_name == "format_document_text" and has_align_requirement:
                    return Analysis(
                        is_success=True,
                        is_goal_achieved=False,  # Still need alignment
                        is_error=False,
                        progress_toward_goal=0.7,
                        confidence=0.9,
                        next_action_suggestion="Текст выделен жирным, теперь нужно применить выравнивание абзацев"
                    )
                # If we did format_document_paragraph (alignment) but still need bold
                if action.tool_name == "format_document_paragraph" and has_bold_requirement:
                    return Analysis(
                        is_success=True,
                        is_goal_achieved=False,  # Still need bold
                        is_error=False,
                        progress_toward_goal=0.7,
                        confidence=0.9,
                        next_action_suggestion="Выравнивание применено, теперь нужно выделить заголовок жирным"
                    )
        
        # Check for goal achieved first (but not for intermediate tools)
        if action.tool_name not in intermediate_tools:
            for indicator in goal_achieved_indicators:
                if indicator in result_str:
                    return Analysis(
                        is_success=True,
                        is_goal_achieved=True,  # Goal is fully achieved!
                        is_error=False,
                        progress_toward_goal=1.0,
                        confidence=0.95
                    )
        
        for indicator in success_indicators:
            if indicator in result_str and len(result_str) < 500:  # Short, clear success messages
                return Analysis(
                    is_success=True,
                    is_goal_achieved=False,  # Don't assume goal achieved from single action
                    is_error=False,
                    progress_toward_goal=0.3,  # Some progress
                    confidence=0.8
                )
        
        # If result is too complex or ambiguous, return None to trigger LLM analysis
        return None
    
    async def _llm_analyze(
        self,
        action: ActionRecord,
        result: Any,
        goal: str,
        previous_observations: Optional[list] = None
    ) -> Analysis:
        """
        Use LLM to analyze action result.
        
        Args:
            action: Action record
            result: Action result
            goal: Original goal
            previous_observations: Previous observations
            
        Returns:
            Analysis object
        """
        # Build context from previous observations
        context_str = ""
        if previous_observations:
            context_str = "\nПредыдущие действия:\n"
            for obs in previous_observations[-3:]:  # Last 3 observations
                context_str += f"- {obs.action.tool_name}: {'успешно' if obs.success else 'ошибка'}\n"
        
        # Truncate result if too long
        result_str = str(result)
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "\n... (результат обрезан)"
        
        prompt = f"""Ты анализируешь результат выполнения действия в рамках задачи.

Цель задачи: {goal}

Выполненное действие:
- Инструмент: {action.tool_name}
- Параметры: {action.arguments}

Результат выполнения:
{result_str}
{context_str}

ВАЖНЫЕ ПРАВИЛА АНАЛИЗА:
1. Если результат содержит только КОЛИЧЕСТВО без деталей (например, "Found 10 events", "Found 5 files"),
   это НЕПОЛНЫЙ результат - цель НЕ достигнута, нужно получить детали
2. Если пользователь просит посмотреть/показать данные, результат должен содержать ДЕТАЛИ, а не только количество
3. Для календаря: "Found 10 events" без списка событий = НЕПОЛНЫЙ результат, нужно получить детали событий
4. Для файлов: список файлов без содержимого = НЕПОЛНЫЙ результат, если пользователь просил прочитать/показать
5. Для писем: список писем без содержимого = НЕПОЛНЫЙ результат, если пользователь просил прочитать/показать

Проанализируй результат и ответь в формате JSON:
{{
    "is_success": true/false,  // Успешно ли выполнено действие?
    "is_goal_achieved": true/false,  // Достигнута ли цель задачи? (false, если нет деталей)
    "is_error": true/false,  // Есть ли ошибка?
    "progress_toward_goal": 0.0-1.0,  // Прогресс к цели (0.0 = нет прогресса, 1.0 = цель достигнута)
    "error_message": "текст ошибки или null",  // Сообщение об ошибке, если есть
    "next_action_suggestion": "что делать дальше или null",  // Предложение следующего действия (например, "получить детали событий")
    "confidence": 0.0-1.0  // Уверенность в анализе
}}

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""

        try:
            messages = [
                SystemMessage(content="Ты эксперт по анализу результатов выполнения задач. Отвечай только валидным JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = response.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            import json
            import re
            
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                analysis_data = json.loads(json_str)
            else:
                # Fallback: try parsing entire response
                analysis_data = json.loads(response_text)
            
            return Analysis(
                is_success=analysis_data.get("is_success", False),
                is_goal_achieved=analysis_data.get("is_goal_achieved", False),
                is_error=analysis_data.get("is_error", False),
                progress_toward_goal=float(analysis_data.get("progress_toward_goal", 0.0)),
                error_message=analysis_data.get("error_message"),
                next_action_suggestion=analysis_data.get("next_action_suggestion"),
                confidence=float(analysis_data.get("confidence", 0.5))
            )
            
        except Exception as e:
            logger.error(f"[ResultAnalyzer] Error in LLM analysis: {e}")
            # Fallback to conservative analysis
            return Analysis(
                is_success=False,
                is_goal_achieved=False,
                is_error=True,
                progress_toward_goal=0.0,
                error_message=f"Ошибка анализа: {str(e)}",
                confidence=0.3
            )
