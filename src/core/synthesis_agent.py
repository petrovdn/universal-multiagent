"""
SynthesisAgent - Aggregates and synthesizes results from parallel subtasks.

Phase 2, Step 4: Takes results from multiple parallel subtasks and generates
a coherent, user-friendly summary using LLM.
"""

import json
from typing import Dict, Any, List
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.utils.config_loader import get_config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SynthesisResult:
    """Result of synthesis operation."""
    summary: str
    source_task_ids: List[str]
    key_points: List[str] = None
    raw_results: Dict[str, Any] = None


class SynthesisAgent:
    """Synthesizes results from parallel subtasks into coherent response."""
    
    def __init__(self):
        """Initialize SynthesisAgent with LLM."""
        config = get_config()
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.3,  # Lower temperature for more consistent synthesis
            max_tokens=2000
        )
    
    async def synthesize(
        self,
        query: str,
        subtask_results: Dict[str, Any],
        original_query: str
    ) -> SynthesisResult:
        """
        Synthesize results from multiple subtasks into coherent summary.
        
        Args:
            query: Original user query
            subtask_results: Dictionary mapping task_id to result
            original_query: Original user query (for context)
            
        Returns:
            SynthesisResult with summary and metadata
        """
        if not subtask_results:
            return SynthesisResult(
                summary="Нет данных для отображения",
                source_task_ids=[],
                key_points=[],
                raw_results={}
            )
        
        # Prepare data for LLM
        results_summary = self._prepare_results_summary(subtask_results)
        
        # Create synthesis prompt
        prompt = self._create_synthesis_prompt(query, results_summary, original_query)
        
        # Call LLM for synthesis
        try:
            messages = [
                SystemMessage(content=self._get_system_prompt()),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            summary = response.content.strip()
            
            # Extract key points (if LLM provides structured output)
            key_points = self._extract_key_points(summary)
            
            return SynthesisResult(
                summary=summary,
                source_task_ids=list(subtask_results.keys()),
                key_points=key_points,
                raw_results=subtask_results
            )
        except Exception as e:
            logger.error(f"[SynthesisAgent] Synthesis failed: {e}", exc_info=True)
            # Fallback to simple aggregation
            return self._fallback_synthesis(subtask_results)
    
    def _prepare_results_summary(self, subtask_results: Dict[str, Any]) -> str:
        """Prepare results summary for LLM prompt."""
        summary_parts = []
        
        for task_id, result in subtask_results.items():
            if isinstance(result, dict):
                # Extract key information
                if "emails" in result:
                    email_count = len(result["emails"])
                    summary_parts.append(f"Почта (задача {task_id}): {email_count} писем")
                elif "events" in result:
                    event_count = len(result["events"])
                    summary_parts.append(f"Календарь (задача {task_id}): {event_count} событий")
                elif "files" in result:
                    file_count = len(result["files"])
                    summary_parts.append(f"Файлы (задача {task_id}): {file_count} файлов")
                else:
                    # Generic result
                    summary_parts.append(f"Задача {task_id}: {json.dumps(result, ensure_ascii=False)[:500]}")
            elif isinstance(result, str):
                # PHASE 0 FIX: Handle string results from parallel branches
                # Results are now strings like "✓ get_calendar_events: Found 0 events..."
                # Include full result text for synthesis
                summary_parts.append(f"Задача {task_id}: {result[:1000]}")
            else:
                summary_parts.append(f"Задача {task_id}: {str(result)[:1000]}")
        
        return "\n".join(summary_parts)
    
    def _create_synthesis_prompt(
        self,
        query: str,
        results_summary: str,
        original_query: str
    ) -> str:
        """Create prompt for LLM synthesis."""
        return f"""Пользователь задал запрос: "{original_query}"

Были выполнены параллельные задачи и получены следующие результаты:

{results_summary}

Создай краткую, но информативную сводку на русском языке, которая:
1. Отвечает на исходный запрос пользователя
2. Объединяет информацию из всех источников
3. Выделяет ключевые моменты, на которые стоит обратить внимание
4. Использует естественный язык (не технические детали)

Сводка должна быть структурированной и легко читаемой. Если есть важные детали (количество писем, встреч, файлов), обязательно включи их.

Ответ (только сводка, без дополнительных комментариев):"""
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for synthesis."""
        return """Ты эксперт по синтезу информации из разных источников. 
Твоя задача - объединить результаты из нескольких параллельных задач в единую, 
понятную и полезную сводку для пользователя.

Важно:
- Используй русский язык
- Будь кратким, но информативным
- Выделяй ключевые моменты
- Структурируй информацию для удобства чтения
- Не упоминай технические детали (task_id, имена инструментов)"""
    
    def _extract_key_points(self, summary: str) -> List[str]:
        """Extract key points from summary (simple heuristic)."""
        # Look for bullet points or numbered lists
        lines = summary.split('\n')
        key_points = []
        
        for line in lines:
            line = line.strip()
            # Check for bullet points or numbered items
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                key_points.append(line[1:].strip())
            elif line and line[0].isdigit() and ('.' in line[:3] or ')' in line[:3]):
                # Numbered list
                key_points.append(line.split('.', 1)[-1].split(')', 1)[-1].strip())
        
        return key_points if key_points else [summary[:200]]  # Fallback to first 200 chars
    
    def _fallback_synthesis(self, subtask_results: Dict[str, Any]) -> SynthesisResult:
        """Fallback synthesis when LLM fails."""
        summary_parts = []
        
        for task_id, result in subtask_results.items():
            if isinstance(result, dict):
                if "emails" in result:
                    summary_parts.append(f"Найдено {len(result['emails'])} писем")
                elif "events" in result:
                    summary_parts.append(f"Найдено {len(result['events'])} событий")
                elif "files" in result:
                    summary_parts.append(f"Найдено {len(result['files'])} файлов")
        
        summary = "Сводка:\n" + "\n".join(f"- {part}" for part in summary_parts) if summary_parts else "Данные получены"
        
        return SynthesisResult(
            summary=summary,
            source_task_ids=list(subtask_results.keys()),
            key_points=summary_parts,
            raw_results=subtask_results
        )
