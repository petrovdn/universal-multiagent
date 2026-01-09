# tests/test_real_progress_events.py
"""
TDD-тесты для реального прогресса вместо fake progress messages.

Проблема: Сейчас агент отправляет статичные сообщения типа 
"Изучаю контекст запроса...", "Анализирую структуру задачи..."
каждые 5 секунд — они не отражают реальную работу.

Решение: Отправлять реальные события при выполнении действий,
без fake прогресса.

TDD: Тесты написаны ДО реализации — они должны падать.
"""
import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock


class MockWebSocketManager:
    """Мок WebSocket менеджера для захвата событий с таймстампами."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.connection_count = 1
        self._start_time = None
    
    async def send_event(self, session_id: str, event_type: str, data: Dict[str, Any]):
        if self._start_time is None:
            self._start_time = datetime.now()
        
        elapsed_ms = (datetime.now() - self._start_time).total_seconds() * 1000
        
        self.events.append({
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "elapsed_ms": elapsed_ms
        })
    
    def get_connection_count(self, session_id: str) -> int:
        return self.connection_count
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["event_type"] == event_type]
    
    def get_intent_details(self) -> List[Dict[str, Any]]:
        return self.get_events_by_type("intent_detail")
    
    def get_fake_progress_messages(self) -> List[Dict[str, Any]]:
        """Возвращает события с фальшивыми progress сообщениями."""
        fake_patterns = [
            "Изучаю контекст",
            "Анализирую структуру",
            "Извлекаю ключевую",
            "Определяю требуемые",
            "Оцениваю возможные",
            "Выбираю оптимальную",
            "Подготавливаю параметры",
        ]
        
        fake_events = []
        for event in self.get_intent_details():
            description = event["data"].get("description", "")
            if any(pattern in description for pattern in fake_patterns):
                fake_events.append(event)
        
        return fake_events


# ============================================================================
# ТЕСТЫ: Отсутствие fake progress messages
# ============================================================================

class TestNoFakeProgressMessages:
    """Тесты проверяющие отсутствие фальшивых сообщений прогресса."""
    
    @pytest.mark.asyncio
    async def test_no_static_progress_messages_during_think_phase(self):
        """
        Тест: Во время фазы THINK не должны отправляться статичные сообщения.
        
        Текущее поведение (БАГ):
        - Отправляется "Изучаю контекст запроса..." через 5 сек
        - Отправляется "Анализирую структуру задачи..." через 10 сек
        - И т.д.
        
        Ожидаемое поведение:
        - НЕТ статичных сообщений по таймеру
        - Только реальные события при действиях
        """
        from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
        from src.core.capability_registry import CapabilityRegistry
        from src.core.action_provider import CapabilityCategory
        from src.core.context_manager import ConversationContext
        
        mock_ws = MockWebSocketManager()
        
        config = ReActConfig(
            mode="agent",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=3
        )
        
        registry = CapabilityRegistry()
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=registry,
            ws_manager=mock_ws,
            session_id="test-no-fake-progress",
            model_name=None
        )
        
        context = ConversationContext(session_id="test-no-fake-progress")
        
        # Выполняем простой запрос
        await engine.execute(goal="напиши хокку", context=context)
        
        # Проверяем: НЕ должно быть fake progress messages
        fake_messages = mock_ws.get_fake_progress_messages()
        
        assert len(fake_messages) == 0, \
            f"НЕ должно быть fake progress messages, но получили {len(fake_messages)}: " \
            f"{[e['data'].get('description', '') for e in fake_messages]}"


# ============================================================================
# ТЕСТЫ: Контекстно-зависимые интенты
# ============================================================================

class TestContextDependentIntents:
    """Тесты контекстно-зависимых интентов."""
    
    def test_calendar_request_shows_calendar_intents(self):
        """
        Тест: Запрос про календарь показывает релевантные интенты.
        
        Запрос: "создай встречу с bob@test.com на 2 часа"
        Ожидаемые интенты:
        - "Определяю участников" или "Проверяю календарь" 
        - "Создаю встречу" или "Планирую событие"
        
        НЕ ожидаем: generic "Изучаю контекст запроса..."
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        # Тестируем метод _get_task_intents
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        intents = engine._get_task_intents("создай встречу с bob@test.com на 2 часа")
        
        # Должны быть специфичные для календаря интенты
        intents_text = " ".join(intents).lower()
        
        assert any(keyword in intents_text for keyword in ["участник", "календар", "встреч", "событ"]), \
            f"Для запроса про календарь должны быть релевантные интенты. Получили: {intents}"
        
        # НЕ должно быть generic интентов
        assert "изучаю контекст" not in intents_text, \
            f"НЕ должно быть generic интентов типа 'Изучаю контекст'. Получили: {intents}"
    
    def test_email_request_shows_email_intents(self):
        """
        Тест: Запрос про почту показывает релевантные интенты.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        intents = engine._get_task_intents("найди письма от boss@company.com")
        
        intents_text = " ".join(intents).lower()
        
        assert any(keyword in intents_text for keyword in ["письм", "почт", "email"]), \
            f"Для запроса про почту должны быть релевантные интенты. Получили: {intents}"
    
    def test_sheets_request_shows_data_intents(self):
        """
        Тест: Запрос про таблицы показывает релевантные интенты.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        intents = engine._get_task_intents("покажи данные из таблицы Продажи")
        
        intents_text = " ".join(intents).lower()
        
        assert any(keyword in intents_text for keyword in ["данн", "таблиц"]), \
            f"Для запроса про таблицы должны быть релевантные интенты. Получили: {intents}"
    
    def test_generic_request_has_simple_intent(self):
        """
        Тест: Для generic запроса — простой интент без fake детализации.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        intents = engine._get_task_intents("что такое Python?")
        
        # Должен быть простой интент, не список fake сообщений
        assert len(intents) <= 2, \
            f"Для простого запроса не нужно много интентов. Получили {len(intents)}: {intents}"
        
        intents_text = " ".join(intents).lower()
        assert "изучаю контекст" not in intents_text
        assert "анализирую структуру" not in intents_text


# ============================================================================
# ТЕСТЫ: Human-readable tool names
# ============================================================================

class TestToolDisplayNames:
    """Тесты человеко-читаемых названий tools."""
    
    def test_calendar_tool_has_readable_name(self):
        """
        Тест: Calendar tools имеют человеко-читаемые названия.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        display_name = engine._get_tool_display_name("calendar_list_events", {})
        
        # Должно содержать что-то про календарь/события
        assert any(k in display_name.lower() for k in ["календар", "событ", "встреч"]), \
            f"calendar_list_events должен иметь читаемое название. Получили: '{display_name}'"
    
    def test_gmail_tool_has_readable_name(self):
        """
        Тест: Gmail tools имеют человеко-читаемые названия.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        display_name = engine._get_tool_display_name("gmail_search", {"query": "test"})
        
        assert any(k in display_name.lower() for k in ["письм", "почт", "email"]), \
            f"gmail_search должен иметь читаемое название. Получили: '{display_name}'"
    
    def test_sheets_tool_has_readable_name(self):
        """
        Тест: Sheets tools имеют человеко-читаемые названия.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        display_name = engine._get_tool_display_name("sheets_read_range", {})
        
        assert any(k in display_name.lower() for k in ["таблиц", "данн"]), \
            f"sheets_read_range должен иметь читаемое название. Получили: '{display_name}'"
    
    def test_tool_display_includes_query_context(self):
        """
        Тест: Название tool включает контекст из аргументов.
        
        gmail_search с query="от директора" → "📧 Ищу письма «от директора»"
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        engine = UnifiedReActEngine.__new__(UnifiedReActEngine)
        
        display_name = engine._get_tool_display_name("gmail_search", {"query": "от директора"})
        
        assert "директор" in display_name.lower(), \
            f"Название должно включать query. Получили: '{display_name}'"


# ============================================================================
# Запуск тестов
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
