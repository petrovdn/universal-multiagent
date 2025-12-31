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
        # Check simple keywords FIRST for fastest classification
        self.simple_keywords = [
            # Приветствия (most common)
            "привет", "hello", "hi", "здравствуй", "здравствуйте",
            "добрый день", "добрый вечер", "доброе утро",
            "good morning", "good evening", "good afternoon",
            # Благодарности
            "спасибо", "thanks", "thank you", "благодарю", "благодарствую",
            # Прощания (only exact word matches to avoid matching "пока" in "покажи")
            "bye", "goodbye", "до свидания", "до встречи",
            "see you", "see ya",
            # Простые вопросы
            "как дела", "how are you", "как поживаешь",
            "что ты", "what are you", "кто ты", "who are you",
            "что умеешь", "what can you do",
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
            "покажи", "show", "открой", "open", "открыть",  # Actions that require multiple steps
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
        Optimized for speed: checks simple keywords FIRST (most common cases).
        
        Returns:
            TaskType if confident, None if uncertain
        """
        request_lower = user_request.lower().strip()
        
        # #region agent log
        import json
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:_heuristic_classify","message":"Heuristic classification started","data":{"user_request":user_request[:200],"request_lower":request_lower[:200]},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        # Extract words for word-boundary matching
        words = set(re.findall(r'\b\w+\b', request_lower))
        
        # PRIORITY 1: Check complex keywords FIRST (they take precedence)
        # If we find complex keywords, it's definitely complex
        for keyword in self.complex_keywords:
            # Check if keyword is a complete word or a significant substring (>= 4 chars)
            if keyword in words or (len(keyword) >= 4 and keyword in request_lower):
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:_heuristic_classify","message":"Complex keyword found","data":{"keyword":keyword,"result":"COMPLEX","matched_as_word":keyword in words},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                return TaskType.COMPLEX
        
        # PRIORITY 2: Check simple keywords (only if no complex keywords found)
        # This catches most simple requests immediately without further checks
        # Use word boundaries to avoid false matches (e.g., "покажи" should not match "пока")
        for keyword in self.simple_keywords:
            # Check if keyword is a complete word (to avoid false matches like "пока" in "покажи")
            if keyword in words:
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:_heuristic_classify","message":"Simple keyword found","data":{"keyword":keyword,"result":"SIMPLE","matched_as_word":True},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                return TaskType.SIMPLE
        
        # PRIORITY 3: Check length and structure
        # Very short requests (1-3 words) without complex keywords are usually simple
        words_list = request_lower.split()
        if len(words_list) <= 3 and len(request_lower) < 30:
            # Short and simple - likely a simple task
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:_heuristic_classify","message":"Short request detected","data":{"word_count":len(words_list),"length":len(request_lower),"result":"SIMPLE"},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            return TaskType.SIMPLE
        
        # PRIORITY 4: Check for complexity indicators
        # Requests with multiple sentences are usually complex
        sentences = re.split(r'[.!?]+', user_request)
        if len(sentences) > 2:
            return TaskType.COMPLEX
        
        # Requests with numbers or specific instructions (like "step 1:") are complex
        if re.search(r'\d+', user_request) or ':' in user_request:
            return TaskType.COMPLEX
        
        # Long requests are usually complex
        if len(request_lower) > 100:
            return TaskType.COMPLEX
        
        # Uncertain - return None to use LLM
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:_heuristic_classify","message":"Heuristic uncertain, will use LLM","data":{"user_request":user_request[:200]},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
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
            # #region agent log
            import json
            import time
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:classify_task","message":"Final classification (heuristic)","data":{"result":heuristic_result.value,"user_request":user_request[:200]},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            return heuristic_result
        
        # Step 2: LLM classification for edge cases
        llm_result = await self._llm_classify(user_request, context)
        logger.info(f"[TaskClassifier] LLM classification: {llm_result.value} for request: {user_request[:50]}")
        # #region agent log
        import json
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"task_classifier.py:classify_task","message":"Final classification (LLM)","data":{"result":llm_result.value,"user_request":user_request[:200]},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        return llm_result

