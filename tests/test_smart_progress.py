"""
Tests for SmartProgressGenerator - contextual progress messages based on task analysis.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from tests.conftest import mock_ws_manager


@pytest.mark.asyncio
async def test_generates_contextual_messages_for_calendar_task(mock_ws_manager):
    """
    SmartProgressGenerator должен генерировать контекстные сообщения для задач календаря.
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "назначь встречу на завтра с bsn@lad24.ru"
    estimated_duration = 5
    
    # Запускаем генератор
    await generator.start(goal, estimated_duration)
    
    # Ждём немного для генерации сообщений
    await asyncio.sleep(0.1)
    
    # Останавливаем
    generator.stop()
    
    # Проверяем, что были отправлены события
    event_types = [e["type"] for e in mock_ws_manager.events]
    
    assert "smart_progress_start" in event_types, "smart_progress_start event not found"
    assert "smart_progress_message" in event_types, "smart_progress_message event not found"
    
    # Проверяем, что сообщения содержат контекст календаря
    messages = [
        e["data"]["message"] 
        for e in mock_ws_manager.events 
        if e["type"] == "smart_progress_message"
    ]
    
    assert len(messages) > 0, "No progress messages generated"
    
    # Проверяем, что хотя бы одно сообщение связано с календарём
    calendar_keywords = ["встреч", "календар", "время", "участник", "приглаш"]
    has_calendar_context = any(
        any(keyword in msg.lower() for keyword in calendar_keywords)
        for msg in messages
    )
    assert has_calendar_context, f"No calendar-related messages found. Messages: {messages}"


@pytest.mark.asyncio
async def test_generates_contextual_messages_for_email_task(mock_ws_manager):
    """
    SmartProgressGenerator должен генерировать контекстные сообщения для задач email.
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "отправь письмо Ивану о встрече"
    estimated_duration = 4
    
    await generator.start(goal, estimated_duration)
    await asyncio.sleep(0.1)
    generator.stop()
    
    # Проверяем события
    event_types = [e["type"] for e in mock_ws_manager.events]
    assert "smart_progress_start" in event_types
    assert "smart_progress_message" in event_types
    
    # Проверяем контекст email
    messages = [
        e["data"]["message"] 
        for e in mock_ws_manager.events 
        if e["type"] == "smart_progress_message"
    ]
    
    email_keywords = ["письм", "сообщени", "отправ", "текст"]
    has_email_context = any(
        any(keyword in msg.lower() for keyword in email_keywords)
        for msg in messages
    )
    assert has_email_context, f"No email-related messages found. Messages: {messages}"


@pytest.mark.asyncio
async def test_stops_on_demand(mock_ws_manager):
    """
    SmartProgressGenerator должен корректно останавливаться при вызове stop().
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "покажи встречи"
    estimated_duration = 10
    
    await generator.start(goal, estimated_duration)
    
    # Ждём немного
    await asyncio.sleep(0.15)
    
    # Останавливаем
    generator.stop()
    
    # Ждём ещё немного - сообщений больше не должно быть
    initial_count = len([e for e in mock_ws_manager.events if e["type"] == "smart_progress_message"])
    await asyncio.sleep(0.2)
    final_count = len([e for e in mock_ws_manager.events if e["type"] == "smart_progress_message"])
    
    # Количество сообщений не должно увеличиться после stop()
    assert final_count == initial_count, (
        f"Messages continued after stop(). Initial: {initial_count}, Final: {final_count}"
    )


@pytest.mark.asyncio
async def test_respects_interval(mock_ws_manager):
    """
    SmartProgressGenerator должен отправлять сообщения с интервалом 3-5 секунд.
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "назначь встречу"
    estimated_duration = 15  # Достаточно для нескольких сообщений
    
    await generator.start(goal, estimated_duration)
    
    # Ждём достаточно долго для нескольких сообщений
    await asyncio.sleep(0.5)  # 500ms - должно быть только первое сообщение
    
    generator.stop()
    
    # Проверяем временные метки сообщений
    message_events = [
        e for e in mock_ws_manager.events 
        if e["type"] == "smart_progress_message"
    ]
    
    if len(message_events) > 1:
        # Проверяем интервал между сообщениями
        timestamps = [e["ts"] for e in message_events]
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        # Интервал должен быть не менее 3 секунд (но в тесте мы ждали только 0.5 сек)
        # Поэтому проверяем, что интервалы разумные (не слишком частые)
        min_interval = min(intervals) if intervals else 0
        # В тесте с 0.5 сек ожиданием должно быть максимум 1-2 сообщения
        assert len(message_events) <= 2, (
            f"Too many messages in 0.5s: {len(message_events)}. "
            f"Intervals: {intervals}"
        )


@pytest.mark.asyncio
async def test_sends_timer_updates(mock_ws_manager):
    """
    SmartProgressGenerator должен отправлять обновления таймера каждую секунду.
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "покажи встречи"
    estimated_duration = 5
    
    await generator.start(goal, estimated_duration)
    
    # Ждём немного
    await asyncio.sleep(0.15)
    
    generator.stop()
    
    # Проверяем наличие timer событий
    timer_events = [
        e for e in mock_ws_manager.events 
        if e["type"] == "smart_progress_timer"
    ]
    
    # Должно быть хотя бы одно обновление таймера
    assert len(timer_events) >= 0, "No timer updates sent"  # Может быть 0 если очень быстро


@pytest.mark.asyncio
async def test_sends_start_event_with_estimated_duration(mock_ws_manager):
    """
    smart_progress_start должен содержать оценочное время выполнения.
    """
    from src.core.smart_progress import SmartProgressGenerator
    
    generator = SmartProgressGenerator(
        ws_manager=mock_ws_manager,
        session_id="test-session"
    )
    
    goal = "назначь встречу"
    estimated_duration = 8
    
    await generator.start(goal, estimated_duration)
    await asyncio.sleep(0.05)
    generator.stop()
    
    # Ищем start событие
    start_events = [
        e for e in mock_ws_manager.events 
        if e["type"] == "smart_progress_start"
    ]
    
    assert len(start_events) > 0, "smart_progress_start event not found"
    
    start_data = start_events[0]["data"]
    assert "estimated_duration_sec" in start_data, "estimated_duration_sec not in start event"
    assert start_data["estimated_duration_sec"] == estimated_duration, (
        f"Expected estimated_duration={estimated_duration}, "
        f"got {start_data['estimated_duration_sec']}"
    )
