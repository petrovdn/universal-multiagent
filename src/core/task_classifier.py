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
        # Simple generative patterns (checked BEFORE complex_keywords)
        # These are tasks like "напиши поздравление" that don't need planning
        self.simple_generative_patterns = [
            r"напиши\s+(краткое\s+)?(поздравление|стих|стихотворение|шутку|анекдот|сообщение|текст|письмо\s+с\s+поздравлением)",
            r"придумай\s+(поздравление|стих|шутку|название|имя|историю)",
            r"сочини\s+(стих|песню|историю|сказку)",
            r"write\s+(a\s+)?(greeting|poem|joke|message|story)",
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
        
        # Extract words for word-boundary matching
        words = set(re.findall(r'\b\w+\b', request_lower))
        
        # PRIORITY 0.5: Check for simple generative tasks BEFORE complex keywords
        # These use "напиши" but don't need planning - just generate text
        # #region agent log
        import json
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"task_classifier.py:_heuristic_classify","message":"Checking simple generative patterns","data":{"request_preview":request_lower[:100],"patterns_count":len(self.simple_generative_patterns)},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        for pattern in self.simple_generative_patterns:
            try:
                if re.search(pattern, request_lower):
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"task_classifier.py:_heuristic_classify","message":"Simple generative pattern matched","data":{"pattern":pattern},"timestamp":int(time.time()*1000)})+'\n')
                    except: pass
                    # #endregion
                    logger.info(f"[TaskClassifier] Simple generative pattern found: {pattern}")
                    return TaskType.SIMPLE
            except Exception as e:
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"task_classifier.py:_heuristic_classify","message":"Error in regex pattern","data":{"pattern":pattern,"error":str(e)},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                logger.warning(f"[TaskClassifier] Error matching pattern {pattern}: {e}")
                continue
        
        # PRIORITY 1: Check complex keywords (they take precedence)
        # If we find complex keywords, it's definitely complex
        for keyword in self.complex_keywords:
            # Check if keyword is a complete word or a significant substring (>= 4 chars)
            if keyword in words or (len(keyword) >= 4 and keyword in request_lower):
                return TaskType.COMPLEX
        
        # PRIORITY 2: Check simple keywords (only if no complex keywords found)
        # This catches most simple requests immediately without further checks
        # Use word boundaries to avoid false matches (e.g., "покажи" should not match "пока")
        for keyword in self.simple_keywords:
            # Check if keyword is a complete word (to avoid false matches like "пока" in "покажи")
            if keyword in words:
                return TaskType.SIMPLE
        
        # PRIORITY 3: Check length and structure
        # Very short requests (1-3 words) without complex keywords are usually simple
        words_list = request_lower.split()
        if len(words_list) <= 3 and len(request_lower) < 30:
            # Short and simple - likely a simple task
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
    
    def _check_for_references(
        self,
        user_request: str,
        context: ConversationContext
    ) -> bool:
        """
        Check if request contains references to previous entities.
        
        Patterns: "этот/тот файл", "его/её", "туда", "this/that"
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            True if references detected, False otherwise
        """
        reference_patterns = [
            r'\b(этот|этого|этому|этим|этом|эта|эту|этой|это|эти|этих)\b',  # Все формы "этот"
            r'\b(тот|того|тому|тем|том|та|ту|той|то|те|тех)\b',  # Все формы "тот"
            r'\b(такой|такого|такому|таким|таком|такая|такую|такой|такое|такие|таких)\b',
            r'\b(его|её|их|ему|ей|им)\b',
            r'\b(туда|там|сюда|здесь)\b',
            r'\b(the|that|this|these|those)\s+(file|meeting|email|sheet|document)',
        ]
        
        request_lower = user_request.lower()
        for pattern in reference_patterns:
            if re.search(pattern, request_lower):
                # Check if there are entities in memory
                if hasattr(context, 'entity_memory') and context.entity_memory.has_recent_entities():
                    logger.info(f"[TaskClassifier] Detected reference pattern: {pattern}")
                    return True
        return False
    
    def _is_simple_action_with_reference(
        self,
        user_request: str
    ) -> bool:
        """
        Проверяет, является ли запрос простым действием с референсом.
        Простое действие: один глагол + референс, без сложных операций.
        
        Примеры простых:
        - "открой этот файл"
        - "удали это письмо"
        - "покажи ту встречу"
        
        Примеры сложных:
        - "открой этот файл и отправь его по почте"
        - "найди этот файл, прочитай его и создай саммари"
        """
        request_lower = user_request.lower().strip()
        
        # Проверяем наличие союзов "и", "потом", "затем" - признак многошаговости
        multi_step_indicators = [' и ', ' потом ', ' затем ', ' после ', ' а затем ', ' then ', ' and then ', ' а потом ']
        for indicator in multi_step_indicators:
            if indicator in request_lower:
                return False  # Это сложное многошаговое действие
        
        # Проверяем количество глаголов действия
        action_verbs = ['открой', 'удали', 'покажи', 'найди', 'создай', 'отправь', 'добавь', 'измени', 'обнови', 'прочитай', 'открыть', 'удалить', 'показать', 'найти', 'создать', 'отправить', 'добавить', 'изменить', 'обновить', 'прочитать']
        verb_count = sum(1 for verb in action_verbs if verb in request_lower)
        
        if verb_count <= 1:
            return True  # Один глагол = простое действие
        
        return False  # Несколько глаголов = сложное
    
    def _is_continuation(
        self,
        user_request: str,
        context: ConversationContext
    ) -> bool:
        """
        Check if request is a continuation of previous dialogue.
        
        Patterns: "а теперь", "соберем все", "сделай вывод", "то же самое"
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            True if continuation detected, False otherwise
        """
        continuation_patterns = [
            r'\b(а теперь|теперь давай|а сейчас)\b',
            r'\b(соберем|собери|объедин)',
            r'\b(вывод|итог|резюм|суммар)',
            r'\b(все вместе|воедино)\b',
            r'\b(то же самое|также|тоже)\b',
        ]
        
        request_lower = user_request.lower()
        for pattern in continuation_patterns:
            if re.search(pattern, request_lower):
                # Check if there are previous messages
                if len(context.messages) > 2:
                    logger.info(f"[TaskClassifier] Detected continuation pattern: {pattern}")
                    return True
        return False
    
    async def classify_task(
        self,
        user_request: str,
        context: ConversationContext
    ) -> TaskType:
        """
        Classify task as simple or complex using hybrid approach with context awareness.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            TaskType (SIMPLE or COMPLEX)
        """
        # Step 0: Check for references or continuation (NEW - context-aware)
        has_reference = self._check_for_references(user_request, context)
        is_continuation = self._is_continuation(user_request, context)
        
        if has_reference:
            # Референс обнаружен, но проверяем сложность действия
            if self._is_simple_action_with_reference(user_request):
                # Простое действие с референсом: "открой этот файл", "удали это письмо"
                # НЕ требует планирования - entity_memory автоматически даст ID
                logger.info(f"[TaskClassifier] Simple action with reference, classifying as SIMPLE for request: {user_request[:50]}")
                return TaskType.SIMPLE
            else:
                # Сложное действие: "найди этот файл и отправь его по почте"
                logger.info(f"[TaskClassifier] Complex action with reference, classifying as COMPLEX for request: {user_request[:50]}")
                return TaskType.COMPLEX
        
        if is_continuation:
            logger.info(f"[TaskClassifier] Detected continuation, classifying as COMPLEX for request: {user_request[:50]}")
            return TaskType.COMPLEX
        
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

