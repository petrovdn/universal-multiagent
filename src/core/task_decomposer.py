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
        
        # Detect data sources from query
        sources = self._detect_sources(query)
        
        if not sources:
            # Single tool query - minimal decomposition
            return self._create_single_tool_decomposition(query)
        
        # Multi-source query - create subtasks
        subtasks = []
        source_task_ids = []
        
        # Create subtask for each source
        for source_info in sources:
            task_id = f"task-{uuid4().hex[:8]}"
            source_task_ids.append(task_id)
            
            subtask = SubTask(
                task_id=task_id,
                description=source_info["description"],
                tool_name=source_info["tool_name"],
                arguments=source_info.get("arguments", {}),
                dependencies=[],
                is_synthesis=False,
                priority=1
            )
            subtasks.append(subtask)
        
        # Create synthesis task that depends on all sources
        synthesis_id = f"task-{uuid4().hex[:8]}"
        synthesis_task = SubTask(
            task_id=synthesis_id,
            description=f"Синтезировать результаты из {len(sources)} источников",
            tool_name="synthesize",
            arguments={"query": query, "source_task_ids": source_task_ids},
            dependencies=source_task_ids,
            is_synthesis=True,
            priority=2
        )
        subtasks.append(synthesis_task)
        
        # Create parallel groups (all source tasks can run in parallel)
        parallel_groups = [source_task_ids]
        
        # Execution order: parallel sources, then synthesis
        execution_order = source_task_ids + [synthesis_id]
        
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
        
        # Check for email/Gmail
        if any(kw in query_lower for kw in ["почт", "письм", "email", "gmail"]) or is_focus_query:
            sources.append({
                "description": "Проверяю непрочитанные письма",
                "tool_name": "list_emails",
                "arguments": {"query": "is:unread", "max_results": 10}
            })
        
        # Check for calendar
        if any(kw in query_lower for kw in ["календар", "встреч", "событ", "calendar", "event"]) or is_focus_query:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            
            sources.append({
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
                "description": "Проверяю последние файлы",
                "tool_name": "list_files",
                "arguments": {"max_results": 10}
            })
        
        # Check for sheets
        if any(kw in query_lower for kw in ["таблиц", "sheet", "spreadsheet"]):
            sources.append({
                "description": "Проверяю данные в таблицах",
                "tool_name": "get_all_sheets_data",
                "arguments": {}
            })
        
        return sources
    
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
