"""
TaskDecomposer - Decomposes complex multi-tool queries into subtasks.

Phase 2, Step 1: Breaks down queries like "Покажи фокус на сегодня" into
parallel subtasks (Gmail, Calendar, Drive) with dependencies.
"""

import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from src.utils.config_loader import get_config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SubTask:
    """Represents a single subtask in decomposition."""
    task_id: str
    description: str
    tool_name: str
    arguments: Dict[str, Any]
    dependencies: List[str]  # task_ids this depends on
    is_synthesis: bool  # Final synthesis task
    priority: int


@dataclass
class DecompositionResult:
    """Result of task decomposition."""
    subtasks: List[SubTask]
    parallel_groups: List[List[str]]  # task_ids for parallel execution
    execution_order: List[str]  # task_ids in execution order


class TaskDecomposer:
    """Decomposes complex queries into subtasks with dependencies."""
    
    def __init__(self):
        """Initialize TaskDecomposer with LLM."""
        config = get_config()
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            api_key=config.anthropic_api_key,
            temperature=0.3
        )
        
        # Tool name mappings: keywords -> tool names
        self.tool_mappings = {
            "email": ["list_emails", "search_emails"],
            "gmail": ["list_emails", "search_emails"],
            "письм": ["list_emails", "search_emails"],
            "почт": ["list_emails", "search_emails"],
            
            "calendar": ["get_calendar_events"],
            "календар": ["get_calendar_events"],
            "встреч": ["get_calendar_events", "create_event"],
            "событ": ["get_calendar_events"],
            
            "file": ["list_files", "search_files"],
            "файл": ["list_files", "search_files"],
            "drive": ["list_files", "search_files"],
            "диск": ["list_files", "search_files"],
            
            "sheet": ["get_sheet_data", "get_all_sheets_data"],
            "таблиц": ["get_sheet_data", "get_all_sheets_data"],
            "spreadsheet": ["get_sheet_data", "get_all_sheets_data"],
            
            "document": ["read_document", "create_document"],
            "документ": ["read_document", "create_document"],
        }
    
    async def decompose(self, query: str) -> DecompositionResult:
        """
        Decompose query into subtasks with dependencies.
        
        Args:
            query: User query (e.g., "Покажи фокус на сегодня")
            
        Returns:
            DecompositionResult with subtasks and execution plan
        """
        if not query or not query.strip():
            # Empty query - return minimal result
            return DecompositionResult(
                subtasks=[],
                parallel_groups=[],
                execution_order=[]
            )
        
        # Detect data sources and actions from query
        sources = self._detect_sources(query)
        actions = self._detect_actions(query)
        
        # Combine sources and actions into tasks
        all_tasks = sources + actions
        
        if not all_tasks:
            # Single tool query - minimal decomposition
            return self._create_single_tool_decomposition(query)
        
        # Multi-task query - create subtasks
        subtasks = []
        task_ids = []
        
        # Create subtask for each source/action
        task_info_map = {}  # Map task_id -> task_info for dependency resolution
        for task_info in all_tasks:
            task_id = f"task-{uuid4().hex[:8]}"
            task_ids.append(task_id)
            task_info_map[task_id] = task_info
            
            subtask = SubTask(
                task_id=task_id,
                description=task_info["description"],
                tool_name=task_info["tool_name"],
                arguments=task_info.get("arguments", {}),
                dependencies=[],  # Will be set after all tasks created
                is_synthesis=False,
                priority=1
            )
            subtasks.append(subtask)
        
        # Resolve dependencies: if query has "ее"/"его" (it/them), actions depend on previous actions
        query_lower = query.lower()
        dependency_indicators = ["ее", "его", "их", "it", "them"]
        has_dependency_reference = any(ind in query_lower for ind in dependency_indicators)
        
        if has_dependency_reference:
            # Find create action and send action
            create_task_id = None
            send_task_id = None
            
            for task_id in task_ids:
                task_info = task_info_map.get(task_id)
                if not task_info:
                    continue
                tool_name = task_info.get("tool_name", "")
                description = task_info.get("description", "").lower()
                
                if "create" in tool_name or "созда" in description:
                    create_task_id = task_id
                elif "send" in tool_name or "отправ" in description:
                    send_task_id = task_id
            
            # Set dependency: send depends on create
            if create_task_id and send_task_id:
                for subtask in subtasks:
                    if subtask.task_id == send_task_id:
                        subtask.dependencies.append(create_task_id)
                        logger.info(f"[TaskDecomposer] Set dependency: {send_task_id} ({subtask.tool_name}) depends on {create_task_id} (due to 'ее'/'его' in query)")
        
        # Create synthesis task only if we have 2+ source tasks (not actions)
        # Actions don't need synthesis, they produce their own results
        source_task_ids = [tid for tid, t in zip(task_ids, all_tasks) if "source" in t.get("type", "")]
        
        if len(source_task_ids) >= 2:
            synthesis_id = f"task-{uuid4().hex[:8]}"
            synthesis_task = SubTask(
                task_id=synthesis_id,
                description=f"Синтезировать результаты из {len(source_task_ids)} источников",
                tool_name="synthesize",
                arguments={"query": query, "source_task_ids": source_task_ids},
                dependencies=source_task_ids,
                is_synthesis=True,
                priority=2
            )
            subtasks.append(synthesis_task)
            execution_order = task_ids + [synthesis_id]
        else:
            # No synthesis needed for actions or single source
            execution_order = task_ids
        
        # Create parallel groups (all tasks without dependencies can run in parallel)
        # DependencyAnalyzer will handle this, but we create initial groups here
        parallel_groups = [task_ids] if len(task_ids) > 1 else []
        
        return DecompositionResult(
            subtasks=subtasks,
            parallel_groups=parallel_groups,
            execution_order=execution_order
        )
    
    def _detect_sources(self, query: str) -> List[Dict[str, Any]]:
        """
        Detect data sources from query using keyword matching.
        
        Args:
            query: User query
            
        Returns:
            List of source info dicts
        """
        query_lower = query.lower()
        sources = []
        
        # Special case: "фокус на сегодня" / "focus today" - includes all common sources
        focus_keywords = ["фокус", "focus", "сводка", "обзор", "summary", "overview"]
        today_keywords = ["сегодня", "today", "на сегодня", "for today"]
        
        is_focus_query = any(fk in query_lower for fk in focus_keywords) and \
                        any(tk in query_lower for tk in today_keywords)
        
        # Check for email/Gmail (only if checking/reading, not sending)
        email_keywords = ["почт", "письм", "email", "gmail"]
        send_keywords = ["отправь", "send", "отправь по", "send by"]
        is_email_sending = any(sk in query_lower for sk in send_keywords)
        is_email_reading = any(ek in query_lower for ek in email_keywords)
        
        if (is_email_reading and not is_email_sending) or is_focus_query:
            # Check if query mentions unread emails or has time filters (requires search_emails)
            has_unread_keywords = any(kw in query_lower for kw in ["непрочитанн", "unread", "новые", "new"])
            has_time_filters = any(kw in query_lower for kw in ["недел", "week", "день", "day", "месяц", "month"])
            
            if has_unread_keywords or has_time_filters:
                # Use search_emails for queries with filters (like "is:unread" or "newer_than:7d")
                query_for_search = "is:unread"
                if "недел" in query_lower or "week" in query_lower:
                    query_for_search = "is:unread newer_than:7d"
                
                sources.append({
                    "type": "source",
                    "description": "Проверяю непрочитанные письма",
                    "tool_name": "search_emails",
                    "arguments": {"query": query_for_search, "max_results": 10}
                })
            else:
                # Use list_emails for simple listing (no filters)
                sources.append({
                    "type": "source",
                    "description": "Проверяю письма",
                    "tool_name": "list_emails",
                    "arguments": {"max_results": 10, "label": "INBOX"}
                })
        
        # Check for calendar
        if any(kw in query_lower for kw in ["календар", "встреч", "событ", "calendar", "event"]) or is_focus_query:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            
            sources.append({
                "type": "source",
                "description": "Проверяю встречи на сегодня",
                "tool_name": "get_calendar_events",
                "arguments": {
                    "time_min": f"{today}T00:00:00Z",
                    "time_max": f"{tomorrow}T00:00:00Z",
                    "max_results": 10
                }
            })
        
        # Check for files/drive (only if explicitly mentioned or focus query)
        if any(kw in query_lower for kw in ["файл", "диск", "file", "drive", "документ"]) or \
           (is_focus_query and "файл" not in query_lower and "file" not in query_lower):
            # For focus queries, include files only if not explicitly excluded
            sources.append({
                "type": "source",
                "description": "Проверяю последние файлы",
                "tool_name": "list_files",
                "arguments": {"max_results": 10}
            })
        
        # Check for sheets
        if any(kw in query_lower for kw in ["таблиц", "sheet", "spreadsheet"]):
            sources.append({
                "type": "source",
                "description": "Проверяю данные в таблицах",
                "tool_name": "get_all_sheets_data",
                "arguments": {}
            })
        
        return sources
    
    def _detect_actions(self, query: str) -> List[Dict[str, Any]]:
        """
        Detect actions (create, send, etc.) from query.
        
        Args:
            query: User query
            
        Returns:
            List of action info dicts
        """
        query_lower = query.lower()
        actions = []
        
        # Check for presentation creation
        if any(kw in query_lower for kw in ["презентац", "presentation", "создай презентацию", "сделай презентацию"]):
            # Extract presentation topic/description
            topic = "презентацию"
            # Try to extract topic from query
            import re
            match = re.search(r"(?:про|about|on)\s+([^,и]+?)(?:,|и|$)", query_lower)
            if match:
                topic = match.group(1).strip()
            
            # Create proper arguments for CreatePresentationBatchInput (requires title and slides)
            # For orchestrated execution, we'll pass minimal valid structure
            # The actual slides content generation will happen in the tool itself if needed
            title = f"Презентация про {topic}"
            
            actions.append({
                "type": "action",
                "description": f"Создаю презентацию про {topic}",
                "tool_name": "create_presentation_batch",
                "arguments": {
                    "title": title,
                    "slides": [],  # Empty array - tool will generate content if needed, or use query for context
                    "query": query  # Pass query for context (tool may use it for content generation)
                },
                "dependencies": []
            })
        
        # Check for email sending (if not just checking)
        if any(kw in query_lower for kw in ["отправь", "send"]) and "проверь" not in query_lower:
            # Check if it's sending something specific (dependency)
            dependency_indicators = ["ее", "его", "их", "it", "them", "тот же"]
            has_dependency = any(ind in query_lower for ind in dependency_indicators)
            
            # If dependency found (e.g., "отправь ее"), we'll mark it but DependencyAnalyzer will handle it
            actions.append({
                "type": "action",
                "description": "Отправляю письмо",
                "tool_name": "send_email",
                "arguments": {"query": query},
                "dependencies": [],  # DependencyAnalyzer will set this based on "ее"/"его" in query
                "has_dependency_reference": has_dependency  # Flag for DependencyAnalyzer
            })
        
        return actions
    
    def _create_single_tool_decomposition(self, query: str) -> DecompositionResult:
        """
        Create minimal decomposition for single tool query.
        
        Args:
            query: User query
            
        Returns:
            DecompositionResult with single subtask
        """
        # Try to detect single tool
        sources = self._detect_sources(query)
        
        if sources:
            # Use first detected source
            source = sources[0]
            task_id = f"task-{uuid4().hex[:8]}"
            
            subtask = SubTask(
                task_id=task_id,
                description=source["description"],
                tool_name=source["tool_name"],
                arguments=source.get("arguments", {}),
                dependencies=[],
                is_synthesis=False,
                priority=1
            )
            
            return DecompositionResult(
                subtasks=[subtask],
                parallel_groups=[[task_id]],
                execution_order=[task_id]
            )
        else:
            # No sources detected - return empty
            return DecompositionResult(
                subtasks=[],
                parallel_groups=[],
                execution_order=[]
            )
