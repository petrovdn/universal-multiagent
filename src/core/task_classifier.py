"""
Task Classifier for determining task complexity.
Uses hybrid approach: heuristics + LLM for edge cases.
"""

from enum import Enum
from typing import Optional
import re

from src.core.context_manager import ConversationContext
from src.agents.model_factory import create_llm
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TaskType(Enum):
    """Task complexity type."""
    SIMPLE = "simple"
    COMPLEX = "complex"


class TaskClassifier:
    """
    Classifies user requests as simple or complex tasks.
    Uses heuristics first, then LLM for edge cases.
    """
    
    def __init__(self):
        """Initialize TaskClassifier."""
        self.llm = None  # Lazy initialization
        # Simple task indicators (heuristics)
        self.simple_keywords = [
            "привет", "hello", "hi", "здравствуй",
            "спасибо", "thanks", "thank you",
            "пока", "bye", "goodbye",
            "как дела", "how are you",
            "что ты", "what are you",
            "кто ты", "who are you",
        ]
        # Complex task indicators
        self.complex_keywords = [
            "создай", "create", "сделай", "make",
            "найди", "find", "ищи", "search",
            "отправь", "send", "write", "напиши",
            "проанализируй", "analyze", "анализ",
            "составь", "составить", "подготовь",
            "план", "plan", "список", "list",
            "сравни", "compare", "сравнение",
            "загрузи", "upload", "скачай", "download",
        ]
    
    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self.llm is None:
            # Use fast model for classification
            try:
                self.llm = create_llm("claude-3-haiku")  # Fast and cheap
            except Exception as e:
                logger.warning(f"[TaskClassifier] Failed to create LLM: {e}, using default")
                self.llm = create_llm()
        return self.llm
    
    def _heuristic_classify(self, user_request: str) -> Optional[TaskType]:
        """
        Classify task using heuristics.
        
        Returns:
            TaskType if confident, None if uncertain
        """
        request_lower = user_request.lower().strip()
        
        # Very short requests are usually simple
        if len(request_lower) < 20:
            # Check if it's a greeting or simple question
            for keyword in self.simple_keywords:
                if keyword in request_lower:
                    return TaskType.SIMPLE
            # Very short without keywords might be simple
            if len(request_lower.split()) <= 3:
                return TaskType.SIMPLE
        
        # Check for complex task indicators
        for keyword in self.complex_keywords:
            if keyword in request_lower:
                return TaskType.COMPLEX
        
        # Requests with multiple sentences or long text are usually complex
        sentences = re.split(r'[.!?]+', user_request)
        if len(sentences) > 2:
            return TaskType.COMPLEX
        
        # Requests with numbers or specific instructions
        if re.search(r'\d+', user_request) or ':' in user_request:
            return TaskType.COMPLEX
        
        # Uncertain - return None to use LLM
        return None
    
    async def _llm_classify(self, user_request: str, context: ConversationContext) -> TaskType:
        """
        Classify task using LLM for edge cases.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            TaskType
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        
        system_prompt = """Ты классификатор задач. Определи, является ли запрос пользователя простой задачей или сложной.

ПРОСТАЯ задача:
- Приветствие, благодарность, прощание
- Простые вопросы (кто ты, что ты)
- Односложные ответы
- Запросы, требующие только одного действия без дополнительных шагов

СЛОЖНАЯ задача:
- Требует нескольких шагов
- Создание, анализ, поиск, сравнение
- Работа с файлами, данными
- Любые задачи, требующие планирования

Ответь только одним словом: SIMPLE или COMPLEX."""

        # Escape braces in user_request to avoid f-string syntax errors
        escaped_user_request = user_request.replace("{", "{{").replace("}", "}}")
        # Use .format() instead of f-string to avoid issues
        user_prompt = "Запрос пользователя: {request}".format(request=escaped_user_request)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            llm = self._get_llm()
            response = await llm.ainvoke(messages)
            result_text = response.content.strip().upper()
            
            if "SIMPLE" in result_text:
                return TaskType.SIMPLE
            else:
                return TaskType.COMPLEX
        except Exception as e:
            logger.error(f"[TaskClassifier] LLM classification error: {e}")
            # Default to complex if LLM fails
            return TaskType.COMPLEX
    
    async def classify_task(
        self,
        user_request: str,
        context: ConversationContext
    ) -> TaskType:
        """
        Classify task as simple or complex using hybrid approach.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            TaskType (SIMPLE or COMPLEX)
        """
        # Step 1: Heuristic classification
        heuristic_result = self._heuristic_classify(user_request)
        
        # If heuristic is confident - return result
        if heuristic_result is not None:
            logger.info(f"[TaskClassifier] Heuristic classification: {heuristic_result.value} for request: {user_request[:50]}")
            return heuristic_result
        
        # Step 2: LLM classification for edge cases
        llm_result = await self._llm_classify(user_request, context)
        logger.info(f"[TaskClassifier] LLM classification: {llm_result.value} for request: {user_request[:50]}")
        return llm_result

