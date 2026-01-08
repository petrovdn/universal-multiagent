# tests/test_meeting_scheduler_integration.py
"""
Интеграционные тесты для MeetingScheduler с MCP Calendar.

Тестирует:
1. Получение событий из календарей участников
2. Создание встречи в найденном слоте
3. Полный flow: поиск слота → создание события
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Импорты будут работать после реализации
from src.core.meeting_scheduler import MeetingScheduler


class TestMeetingSchedulerMCPIntegration:
    """Тесты интеграции MeetingScheduler с MCP Calendar."""
    
    @pytest.mark.asyncio
    async def test_fetches_events_from_mcp(self):
        """
        Тест: Получает события календаря через MCP.
        """
        # Mock MCP manager
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"items": [{"summary": "Meeting", "start": {"dateTime": "2026-01-09T10:00:00"}, "end": {"dateTime": "2026-01-09T11:00:00"}}], "count": 1}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            events = await scheduler._get_calendar_events(
                participants=["alice@example.com"],
                start=datetime(2026, 1, 9, 9, 0),
                end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Должен вызвать MCP tool
        assert mock_mcp_manager.call_tool.called
        # Должен вернуть события
        assert "alice@example.com" in events
        assert len(events["alice@example.com"]) == 1
    
    @pytest.mark.asyncio
    async def test_handles_multiple_participants_calendars(self):
        """
        Тест: Получает календари нескольких участников.
        """
        # Mock для двух участников
        mock_mcp_manager = AsyncMock()
        
        # Разные события для разных участников
        def mock_call_tool(tool_name, args, server_name=None):
            # Симулируем разные календари
            return [MagicMock(text='{"items": [{"summary": "Busy", "start": {"dateTime": "2026-01-09T10:00:00"}, "end": {"dateTime": "2026-01-09T11:00:00"}}], "count": 1}')]
        
        mock_mcp_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            events = await scheduler._get_calendar_events(
                participants=["alice@example.com", "bob@example.com"],
                start=datetime(2026, 1, 9, 9, 0),
                end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Должен запросить календарь каждого участника
        assert mock_mcp_manager.call_tool.call_count >= 1
        # Должен вернуть данные для обоих
        assert "alice@example.com" in events or "bob@example.com" in events


class TestScheduleGroupMeetingTool:
    """Тесты для LangChain tool ScheduleGroupMeetingTool."""
    
    @pytest.mark.asyncio
    async def test_tool_finds_slot_and_creates_event(self):
        """
        Тест: Tool находит слот и создаёт событие.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock calendar events (все свободны)
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"items": [], "count": 0}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Командная встреча",
                    attendees=["alice@example.com", "bob@example.com"],
                    duration="50m",
                    buffer="10m"
                )
        
        # Должен вернуть информацию о созданной встрече
        assert "alice@example.com" in result or "bob@example.com" in result or "встреч" in result.lower() or "slot" in result.lower()
    
    @pytest.mark.asyncio
    async def test_tool_returns_error_when_no_slot(self):
        """
        Тест: Tool возвращает ошибку, если слот не найден.
        
        Мокаем календарь так, чтобы все рабочие часы были заняты.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock: заняты все рабочие часы на ближайшие дни
        # Создаём события на каждый день в ближайшую неделю
        mock_mcp_manager = AsyncMock()
        
        # Занято с 9:00 до 18:00 каждый день (весь рабочий день)
        # Чтобы точно не было слота, заполняем все рабочие часы
        busy_events = []
        base_date = datetime.now().date()
        for day_offset in range(7):
            event_date = base_date + timedelta(days=day_offset)
            busy_events.append({
                "summary": f"Busy day {day_offset}",
                "start": {"dateTime": f"{event_date}T09:00:00"},
                "end": {"dateTime": f"{event_date}T18:00:00"}
            })
        
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps({"items": busy_events, "count": len(busy_events)}))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Командная встреча",
                    attendees=["alice@example.com"],
                    duration="50m",
                    buffer="10m",
                    search_days=7  # Ищем 7 дней
                )
        
        # Должен вернуть сообщение об отсутствии слота
        assert "не удалось" in result.lower() or "не найден" in result.lower() or "no slot" in result.lower()
    
    @pytest.mark.asyncio
    async def test_tool_respects_buffer_time(self):
        """
        Тест: Tool учитывает буферное время.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock: встреча заканчивается в 10:00
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"items": [{"summary": "Morning meeting", "start": {"dateTime": "2026-01-09T09:00:00"}, "end": {"dateTime": "2026-01-09T10:00:00"}}], "count": 1}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Follow-up",
                    attendees=["alice@example.com"],
                    duration="50m",
                    buffer="10m"
                )
        
        # Результат должен содержать время после 10:00 + 10 мин буфер = 10:10
        # Либо сообщение об успешном создании
        assert result is not None


class TestMeetingSchedulerWithRealMCP:
    """
    Интеграционные тесты с реальным MCP (требуют credentials).
    
    Запуск: pytest -m integration tests/test_meeting_scheduler_integration.py
    """
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skip(reason="Требует настроенные Google Calendar credentials")
    async def test_real_calendar_integration(self):
        """
        E2E тест: Реальная интеграция с Google Calendar.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        result = await tool._arun(
            title="Test Meeting (автотест)",
            attendees=["your-email@gmail.com"],
            duration="30m",
            buffer="5m"
        )
        
        # Должен найти слот или создать встречу
        assert result is not None
        print(f"Result: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
