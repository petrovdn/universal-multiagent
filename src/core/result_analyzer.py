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
        quick_analysis = self._quick_analysis(result, action)
        if quick_analysis:
            logger.info(f"[ResultAnalyzer] Quick analysis: success={quick_analysis.is_success}, error={quick_analysis.is_error}")
            
            # #region agent log - H3,H4: ResultAnalyzer quick analysis
            import time as _time
            import json as _json
            open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "result_analyzer:quick_analysis", "message": "Quick analysis result", "data": {"tool_name": action.tool_name, "is_success": quick_analysis.is_success, "is_error": quick_analysis.is_error, "is_goal_achieved": quick_analysis.is_goal_achieved, "error_message": quick_analysis.error_message, "result_preview": str(result)[:300]}, "timestamp": int(_time.time()*1000), "sessionId": "debug-session", "hypothesisId": "H3,H4"}) + '\n')
            # #endregion
            
            return quick_analysis
        
        # Use LLM for deeper analysis
        logger.info(f"[ResultAnalyzer] Performing LLM analysis for action {action.tool_name}")
        return await self._llm_analyze(action, result, goal, previous_observations)
    
    def _quick_analysis(self, result: Any, action: ActionRecord) -> Optional[Analysis]:
        """
        Quick analysis without LLM for obvious cases.
        
        Args:
            result: Action result
            action: Action record
            
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
                # #region agent log - H4: Error indicator detected
                import time as _time
                import json as _json
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "result_analyzer:error_indicator", "message": "ERROR INDICATOR DETECTED", "data": {"tool_name": action.tool_name, "indicator": indicator, "result_preview": result_str[:500]}, "timestamp": int(_time.time()*1000), "sessionId": "debug-session", "hypothesisId": "H4"}) + '\n')
                # #endregion
                
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
        goal_achieved_indicators = [
            "created successfully", "запланирована", "✅",
            "event id:", "событие создано", "встреча запланирована",
            "отправлено успешно", "sent successfully"
        ]
        
        # Check for goal achieved first
        for indicator in goal_achieved_indicators:
            if indicator in result_str:
                # #region agent log - H_LOOP: Goal achieved detected
                import time as _time
                import json as _json
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "result_analyzer:GOAL_ACHIEVED", "message": "GOAL ACHIEVED detected", "data": {"tool_name": action.tool_name, "indicator": indicator, "result_preview": result_str[:200]}, "timestamp": int(_time.time()*1000), "sessionId": "debug-session", "hypothesisId": "H_LOOP"}) + '\n')
                # #endregion
                
                return Analysis(
                    is_success=True,
                    is_goal_achieved=True,  # Goal is fully achieved!
                    is_error=False,
                    progress_toward_goal=1.0,
                    confidence=0.95
                )
        
        for indicator in success_indicators:
            if indicator in result_str and len(result_str) < 500:  # Short, clear success messages
                # #region agent log - H_LOOP: Success but not goal achieved
                import time as _time
                import json as _json
                open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a').write(_json.dumps({"location": "result_analyzer:success_not_achieved", "message": "Success but NOT goal achieved", "data": {"tool_name": action.tool_name, "indicator": indicator, "result_preview": result_str[:200]}, "timestamp": int(_time.time()*1000), "sessionId": "debug-session", "hypothesisId": "H_LOOP"}) + '\n')
                # #endregion
                
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

